# RCA — Δt blow-up at end of lap

**Symptom:** Comparing `144714Z / Lap 4 #6 / 1:45.856 ★` (session) against
`151203Z / Lap 5 #4 / 1:43.958 ★` (reference) in `web/compare.html` shows
roughly +1 900 ms Δt throughout the lap, then the line rockets to **+26 000 –
54 000 ms** in the final 20 m of the graph.  
**Actual lap-time delta:** 105.856 − 103.958 = **1 898 ms** (correct).  
**Root cause confirmed by:** direct inspection of parquet data + simulated resampler in Python.

---

## 1. The boundary-artifact frames

When LMU crosses a lap boundary the sim updates `mLapNumber` in one tick, but
`mLapDist` and `mLapStartET` are not guaranteed to reset in the same tick. The
recorder picks up one or more frames where:

| field | value | interpretation |
|---|---|---|
| `lap_number` | NEW lap | lap counter already ticked |
| `lap_distance_m` | ≈ track length | mLapDist **not yet reset** |
| `lap_time_s` = `mCurrentET − mLapStartET` | small negative or ~0 | mLapStartET just updated |

These frames are called **boundary-artifact frames**. They belong, by
`lap_number`, to the new lap's segment, but their `lap_distance_m` is near the
END of the track (not near 0 where the new lap starts).

**144714Z lap#6** has 3 artifact frames:  

```
d=4653.37  t=-0.1439  sess=794.4       ← mLapStartET updated 144 ms after mLapNumber
d=4654.29  t=-0.1439
d=4655.16  t=-0.1439
```

**151203Z lap#4** has 6 artifact frames:  

```
d=4650.22  t=-0.0421  sess=526.8       ← mLapStartET updated only 42 ms after mLapNumber
d=4652.07  t=-0.0421
d=4652.94  t=-0.0421
d=4653.86  t=-0.0421
d=4654.72  t=-0.0421
d=4656.52  t=-0.0421
```

The timing gap differs between sessions because it is determined by the exact
scheduling of the LMU physics tick relative to the recorder's 50 Hz poll.

---

## 2. The filter that should catch them — and why it misses

`computeKeepIndices` (compare.html) drops a frame when:

```js
t < -0.05  AND  d > halfTrack
```

**144714Z lap#6 artifacts:** `t = -0.1439 < -0.05` ✓ → correctly **dropped**.  
**151203Z lap#4 artifacts:** `t = -0.0421 > -0.05` ✗ → **NOT dropped** — they
survive into the resampled data.

The -0.05 s threshold was derived from the M3 live-test observation where
boundary artifacts had `t ≈ -0.17 s`. The 151203Z session's artifacts sit
just inside the threshold at −0.042 s.

---

## 3. How the survivors corrupt `lap_time_s` resampling

The `resample()` function sorts all frames in the segment by `lap_distance_m`
(stable, tie-break by original frame index) and uses linear interpolation
(`interpAt`) to fill 1 m distance bins.

After the sort, the reference lap#4's distance-axis looks like this near the
end of the track (excerpt, showing only the high-distance region):

```
…
d=4649.14  t=103.9579   ← real end-of-lap frame
d=4650.06  t=103.9579   ← real
d=4650.22  t=-0.0421    ← ARTIFACT (earlier frame_idx, lower position after stable sort)
d=4651.84  t=103.9579   ← real
d=4652.07  t=-0.0421    ← ARTIFACT
d=4652.76  t=103.9579   ← real
d=4652.94  t=-0.0421    ← ARTIFACT
d=4653.86  t=-0.0421    ← ARTIFACT
d=4654.72  t=-0.0421    ← ARTIFACT
d=4656.52  t=-0.0421    ← ARTIFACT  (highest d → becomes the clamped boundary value)
```

`interpAt` does a binary search and linear interpolation between adjacent
(sorted-by-d) frames. At each distance bin:

| bin | lo frame | hi frame | interpolated `lap_time_s` |
|---|---|---|---|
| 4650 m | d=4650.06, t=103.96 | d=4650.22, t=**-0.042** | **≈ 65 s** |
| 4651 m | d=4650.22, t=-0.042 | d=4651.84, t=103.96 | **≈ 50 s** |
| 4652 m | d=4651.84, t=103.96 | d=4652.07, t=**-0.042** | **≈ 33 s** |
| 4653 m | d=4652.94, t=-0.042 | d=4653.86, t=-0.042 | **= -0.042 s** |
| 4654–4656 m | all artifact | clamped to -0.042 | **= -0.042 s** |

**Python-simulated values (from the actual parquet data):**

```
bin 4649m: ref=103.9579s   (correct)
bin 4650m: ref=103.9579s   (correct, actual last real frame is d=4650.06)
bin 4651m: ref= 50.0366s   ← corrupted
bin 4652m: ref= 33.0087s   ← corrupted
bin 4653m: ref=  -0.0421s  ← corrupted
bin 4654m: ref=  -0.0421s  ← corrupted
bin 4655m: ref=  -0.0421s  ← corrupted
bin 4656m: ref=  -0.0421s  ← corrupted
```

The **session** lap (144714Z lap#6) has no surviving artifacts (all filtered at
step 2), so its bins are clean: t=105.856 s all the way to its maxDist.

---

## 4. Δt values at the final bins (pre-smooth)

`computeDeltaT` computes `dtBins[d] = (s_t[d] − r_t[d]) × 1000 ms`.

```
bin 4645m:  s=105.856  r=103.958  → dt = +1 898 ms   (correct)
bin 4646m:  s=105.856  r=103.958  → dt = +1 898 ms
…
bin 4650m:  s=105.856  r=103.958  → dt = +1 898 ms
bin 4651m:  s=105.856  r= 50.037  → dt = +55 819 ms  ← corrupted
bin 4652m:  s=105.856  r= -0.042  → dt = +105 898 ms ← beyond overlapEnd but in dtBins
…
bin 4656m:  s=105.856  r= -0.042  → dt = +105 898 ms
```

`overlapEnd = min(ceil(sMaxDist), ceil(rMaxDist)) = min(4652, 4657) = 4652`.

So bin 4651 is the last bin rendered — and it already has dt = +55 819 ms.

---

## 5. `smoothDt` propagates the corruption backwards

`smoothDt` applies a **symmetric ±20 m boxcar**, shrinking near array
boundaries: `radius = min(20, i, n−1−i)`. For the final bins of the dtBins
array (length = maxDist + 1 = 4657):

| rendered bin | radius | averaging window | bins outside overlap included |
|---|---|---|---|
| 4651 (overlapEnd) | `min(20, 4651, 5)` = **5** | 4646 – 4656 | 4652–4656 (5 corrupted bins) |
| 4645 | `min(20, 4645, 11)` = **11** | 4634 – 4656 | 4652–4656 (5 corrupted bins) |
| 4635 | `min(20, 4635, 21)` = **20** | 4615 – 4655 | 4652–4655 (4 corrupted bins) |

Python-estimated smoothed Δt values at key bins:

```
bin 4630m:  radius=20  all clean   →  smoothed ≈  1 898 ms   (correct)
bin 4631m:  radius=20  bin 4651 enters window → smoothed ≈  3 213 ms
bin 4635m:  radius=20  1 corrupted bin        → smoothed ≈  4 200 ms
bin 4640m:  radius=16  1 corr + 5 OOB bins    → smoothed ≈ 19 290 ms
bin 4645m:  radius=11  17 clean + 6 corrupt   → smoothed ≈ 26 870 ms
bin 4651m:  radius= 5  5 clean + 6 corrupt    → smoothed ≈ 54 070 ms
```

**This matches the user's observation:** the line is correct (~+1 900 ms) up to
approximately 4 630 m, then rises sharply to **≈ 25 000 – 54 000 ms** in the
final 20 m — exactly as the ±20 m boxcar reaches the corrupted bins.

---

## 6. Why the tooltip values differ from the line

The tooltip reads `currentDtBins[binIdx]` directly (the raw dtBins array, not
the `smoothDt` output). Wait — actually `currentDtBins` IS the output of
`smoothDt` (see `renderAll`: `currentDtBins = smoothDt(computeDeltaT(...))`).
The "end Δt readout" in the plot reads `dtBins[overlapEnd]` which is the
smoothed value at overlapEnd ≈ 54 000 ms.

The tooltip reports the smoothed bin at the cursor's distance, so hovering at
4 645 m shows ≈ 26 870 ms and at the very last rendered pixel ≈ 54 000 ms.

---

## 7. Summary — causal chain

```
LMU SHM: mLapNumber ticks 42 ms before mLapDist/mLapStartET resets
       ↓
Recorder captures 6 frames with  lap_number=4  d≈4650–4657m  t=-0.042s
       ↓
computeKeepIndices threshold is -0.05s; -0.042 > -0.05 → frames NOT dropped
       ↓
resample() sorts by distance → artifact frames interleave with real end-of-lap frames
       ↓
interpAt() linearly interpolates between real frames (t≈103.96s) and artifact
frames (t=-0.042s) → ref lap_time_s corrupted to 50→33→-0.042s at bins 4651–4656m
       ↓
computeDeltaT: dtBins[4651] = (105.856 − 50.0) × 1000 ≈ +55 800 ms
               dtBins[4652–4656] ≈ +105 900 ms
       ↓
smoothDt ±20m boxcar mixes corrupted bins (4651–4656) into rendered bins 4631–4651
       ↓
Rendered Δt rises from +1 898 ms at 4 630 m to ≈ +54 000 ms at overlapEnd
```

---

## 8. Fix options for the implementation agent

### Option A — Widen the filter threshold to 0.0 s (minimal patch)

```js
// compare.html  computeKeepIndices()
// OLD:
if (Number.isFinite(t) && Number.isFinite(d) && t < -0.05 && d > halfTrack) continue;
// NEW:
if (Number.isFinite(t) && Number.isFinite(d) && t < 0.0  && d > halfTrack) continue;
```

Catches the -0.042 s artifacts. Risk: drops any frame where the new lap's
first `session_time_s` tick lands at `mCurrentET - mLapStartET = 0.000`
exactly. In practice the recorder's 50 Hz sample never lands exactly on the
tick edge, so this is safe. The `d > halfTrack` guard already prevents
false-positives near the start/finish line.

### Option B — Widen to a small positive threshold (robust fix)

```js
if (Number.isFinite(t) && Number.isFinite(d) && t < 0.5 && d > halfTrack) continue;
```

Catches artifacts with t anywhere from −∞ to +0.5 s at d > halfTrack. A real
frame at d > halfTrack can only have t < 0.5 s if the driver covered more than
~2 300 m in under 0.5 s — physically impossible at any racing speed. Zero false
positives. Recommended.

### Option C — Post-resample monotonicity enforcement (defensive, independent)

After resampling `lap_time_s` (before `smoothLapTime` or after), enforce the
physical invariant that lap elapsed time is non-decreasing:

```js
// After:  const rLapTimeBins = resample(rDistRaw, smoothLapTime(rLapTime, rKeep), maxDist);
for (let d = 1; d <= maxDist; d++) {
  if (rLapTimeBins[d] < rLapTimeBins[d-1]) rLapTimeBins[d] = rLapTimeBins[d-1];
}
// Same for sLapTimeBins
```

`lap_time_s` must be monotonically non-decreasing within a lap by definition
(it is the sim's elapsed lap clock). Any drop is a corruption. Clamping
forwards is safe and eliminates ALL forms of this class of bug regardless of
which artifact slips through the filter. Apply this on top of Option B for
defence-in-depth.

### Recommended approach

Ship **Option B** (widen threshold to 0.5 s) as the root-cause fix and
**Option C** (monotonicity enforcement) as a defensive guard. Both are 2–4
line changes in `renderAll` and `computeKeepIndices`. Neither requires changes
to the recorder or the parquet schema.

---

## 9. Files to change

| File | Location | Change |
|---|---|---|
| `web/compare.html` | `computeKeepIndices()` | Option B: `t < 0.5` |
| `web/compare.html` | `renderAll()` after `sLapTimeBins`/`rLapTimeBins` assignment | Option C: monotonicity clamp |
| `scripts/test_f8f9f10f11.js` or a new test file | new test | Regression: load 151203Z, compare lap 4 vs 144714Z lap 6, assert `|endDt − 1898| < 100` |

No recorder changes needed — the recorder faithfully records what the SHM
provides; the boundary artifact is a SHM property. The fix is in the reader.
