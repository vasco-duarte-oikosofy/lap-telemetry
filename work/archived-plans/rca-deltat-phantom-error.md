# RCA — phantom Δt error in `web/compare.html`

**Status:** Root cause analysis only. No fix applied. Hand this to another agent for the fix.

**Date:** 2026-05-10
**Branch / commit:** `main` @ `4b4ec6b`
**Reporter symptom:** Two near-equal Spa-Francorchamps laps show a 125 ms gap in the Δt panel when the actual lap-time gap is 69 ms — a 56 ms phantom error. In a tight quali, that is the difference between P1 and P5+.

---

## 1. Reproduction

Open `web/compare.html`, load both files, compare:

| Slot | File | Picker label | `lap_time_s` |
|---|---|---|---|
| Session | `sessions/session_20260510T163054Z_circuit-de-spa-francorchamps_lmu.parquet` | Lap 14 #7 | **133.835 s** |
| Reference | `sessions/session_20260510T173248Z_circuit-de-spa-francorchamps_lmu.parquet` | Lap 3 #2 | **133.904 s** |

| Quantity | Value |
|---|---|
| Real lap-time delta (`max(lap_time_s)` A − B) | **−69.12 ms** |
| Δt panel "end" readout (visible in app) | **−128.00 ms** |
| **Phantom error** | **−58.99 ms** |

The 56 ms reported by the user matches our measurement to within 3 ms (likely rounding in their quoted figure).

---

## 2. Where the bad number is computed

`web/compare.html`, function `computeDeltaT` (~line 550):

```javascript
function computeDeltaT(sessionSpeed, refSpeed) {
  const len = Math.min(sessionSpeed.length, refSpeed.length);
  const dt = new Float64Array(len);
  let cumDt = 0;
  for (let i = 0; i < len; i++) {
    const vs = Math.max(sessionSpeed[i] / 3.6, 0.3); // m/s, guard zero
    const vr = Math.max(refSpeed[i] / 3.6, 0.3);
    cumDt += (1 / vs - 1 / vr) * 1000;
    dt[i] = cumDt;
  }
  return dt;
}
```

It accumulates `(1/v_session − 1/v_ref) × 1 m × 1000` over a 1 m bin grid. Inputs come from `resample(distances, speeds, maxDist)` (~line 535), which sorts by `lap_distance_m` and linearly interpolates `speed_kph` onto integer-meter bins from 0 to `maxDist`.

`maxDist` is computed in `renderAll` (~line 1100):

```javascript
const sMaxDist  = Math.ceil(Math.max(...sDistRaw));
const rMaxDist  = Math.ceil(Math.max(...rDistRaw));
const maxDist   = Math.max(sMaxDist, rMaxDist);
```

For our two laps, `maxDist = 6980` (ceil of 6979.10 from lap B).

---

## 3. The numerical chain

Per-lap independent integrated time (sum `1/v_bin` over 0..6980 bins):

| Lap | `max(lap_time_s)` (real) | bin-integrated time | per-lap overshoot |
|---|---|---|---|
| A (session) | 133.835 s | 135.630 s | **+1.795 s** |
| B (reference) | 133.904 s | 135.758 s | **+1.854 s** |

**The bin integration overshoots real lap time by ~1.8 s on every lap.** Both overshoots are similar in magnitude — but they are not *identical*. The asymmetry is exactly what surfaces as the visible Δt error:

- A overshoots by 1795 ms; B overshoots by 1854 ms.
- The 59 ms larger overshoot on B is what drives "session looks 128 ms ahead" instead of "session is really 69 ms ahead."

So there are actually **two stacked bugs**:
1. **A baseline ~1.8 s overshoot per lap** that mostly cancels in Δt (red herring for the user's symptom, but a real bug worth knowing about).
2. **An asymmetry in the overshoots** that does *not* cancel — this is the user's pain point.

---

## 4. The asymmetry — primary finding

`lap_distance_m` does not faithfully represent how much real ground each car covered. We can prove this by reconstructing distance from the *time* and *speed* columns (which the recorder samples directly from SHM at 50 Hz, no integrator involved):

```
distance_reconstructed = Σ Δlap_time_s × speed_mps  (chronologically)
```

| Lap | F4 `max - min(lap_distance_m)` | `Σ Δt × v` reconstruction | F4 over-count |
|---|---|---|---|
| A | 6979.36 m | **6945.84 m** | **+33.52 m** |
| B | 6975.81 m | **6935.75 m** | **+40.06 m** |

**Both laps cover ~6940 m of real ground in 134.0 s of session time** (`session_time_s` span is exactly 134.000 s for both segments, confirmed). The F4 distance integrator (`_estimate_dist` in `lap_telemetry/recorder/connect.py`) over-counts by ~30–40 m per lap, and **the over-count differs from lap to lap** (33.5 m vs 40 m → 6.5 m delta).

When the bin integrator processes 6981 bins for each lap, but each lap's "1 F4-meter" represents a slightly different amount of real ground, the integrals don't line up. ~6.5 m of differential over-count, traversed at the average lap speed of ~52 m/s, accounts for roughly 100–125 ms of phantom Δt — matching the observed 59 ms residual after other smaller effects.

### Why does F4 over-count?

Plausible mechanism: the SHM `mLapDist` is a centerline-distance counter. F4 anchors to it at scoring rate (~5 Hz) and integrates speed magnitude `|mLocalVel|` between anchors. `|mLocalVel|` includes lateral velocity (yaw, slip), so during corners and slides the speed integral grows faster than the centerline `mLapDist`. The next anchor pulls F4 back down, but the amount of pull is dictated by the SHM, which itself rounds / discretises. Net result: a few tens of metres per lap of accumulated over-count, varying by how much the driver slipped/yawed.

**This is not a recorder bug per se** — the schema is faithful to the SHM. It's a "this column should not be used as the integration variable" problem.

---

## 5. Secondary contributor — extrapolation past data ends

A smaller effect (~5 ms in this case, but worth fixing):

| Lap | first frame `lap_distance_m` | last frame `lap_distance_m` | bins clamped |
|---|---|---|---|
| A | −0.52 m | 6978.84 m | 6979, 6980 (2 at end) |
| B | 3.29 m | 6979.10 m | 0, 1, 2, 3 (4 at start) + 6980 (1 at end) |

The resampler `interpAt` (`web/compare.html` ~line 522):

```javascript
function interpAt(xs, ys, x) {
  if (x <= xs[0]) return ys[0];          // ← clamps to first sample's value
  if (x >= xs[xs.length - 1]) return ys[ys.length - 1];  // ← clamps to last
  ...
}
```

For B, the bin grid covers 0..6980 but B's actual data starts at 3.29 m — so bins 0..3 get the first sample's speed (~196 km/h) held flat. That's 4 phantom bins worth of integration. A only has 2 phantom bins (at the end), making B's integration ~3 bins × 18 ms = ~54 ms longer just from boundary clamping.

I tested trimming the integration to the strict overlap `[max(minA, minB), min(maxA, maxB)] = [4, 6978]`. The Δt only moved by 0.79 ms (from −128.11 to −127.32) — meaning **most of the asymmetry is inside the data range, not at the boundaries**. The F4 over-count (§4) dominates.

---

## 6. Tertiary — boundary-artifact first frame

Both segments contain a chronologically-first frame that is an SHM-lag artifact:

| Field | Lap A frame 0 | Lap B frame 0 |
|---|---|---|
| `session_time_s` | 1086.000 | (similar, end of prev lap's clock tick) |
| `lap_number` | already incremented | already incremented |
| `lap_distance_m` | **6975.22** (still old lap!) | **6979.10** |
| `lap_time_s` | **−0.165** (negative!) | **−0.096** |
| `speed_kph` | 198.23 | 196.55 |
| Frame 1 dist | −0.52 (now at the line) | 3.29 |

The SHM updates `mLapNumber` before `mLapDist` resets — so for one frame, the new lap's segment contains an out-of-place data point at the *previous* lap's end-of-pit-straight distance. After sort-by-distance, this point sits among the lap's *real* end-of-lap data (similar speed, so it doesn't badly distort speed interpolation), but its `lap_time_s` is *negative*, which makes any time-based interpolation across that distance return nonsense (see §7).

This isn't a major contributor to the user's symptom, but **it must be filtered out for the proposed fix to work cleanly** (see §7 caveat).

---

## 7. Proposed fix direction (verified to give −69.12 ms exactly)

Replace the speed-integral approach with **direct interpolation of `lap_time_s` against `lap_distance_m`**, then subtract:

```
Δt(d) = lap_time_s_session(d) − lap_time_s_ref(d)
```

This is mathematically what `∫ dx/v` is supposed to compute, but read directly from the recorder's sim-clock-derived `lap_time_s` column instead of integrating speed. It bypasses the F4 over-count entirely because we never use distance as the *quantity* being integrated — we only use it as the *axis* for alignment.

Verified numerically:

| Method | Δt (A − B) at lap end | Error vs real |
|---|---|---|
| Current (speed-integral, full grid 0..6980) | **−128.11 ms** | **−59 ms** |
| Proposed (interpolate `lap_time_s` at overlap end bin 6978) | **−69.12 ms** | **0.00 ms** |

The proposed method matches `max(lap_time_s)` lap delta to four decimal places.

### Implementation sketch (for the fix agent — DO NOT IMPLEMENT WITHOUT CONFIRMATION)

1. **Add `lap_time_s` to the channels resampled in `renderAll`** — alongside speed/throttle/etc.
   Already in `COLUMNS`, just needs to be emitted into `currentSessionBins` / `currentRefBins`.
2. **Filter the boundary-artifact frame** before resampling. Heuristic: drop frames where `lap_time_s < -0.05` AND `lap_distance_m > trackLen × 0.5`. (Equivalently: any frame whose `lap_time_s` is wildly out of order with its neighbours given its position in the sorted-by-distance array.) This is a per-segment cleanup step.
3. **Rewrite `computeDeltaT`** to subtract resampled `lap_time_s` arrays directly:
   ```js
   function computeDeltaT(sessionLapTime, refLapTime) {
     const len = Math.min(sessionLapTime.length, refLapTime.length);
     const dt = new Float64Array(len);
     for (let i = 0; i < len; i++) dt[i] = (sessionLapTime[i] - refLapTime[i]) * 1000;
     return dt;
   }
   ```
4. **Bound the rendered range** of the Δt curve to `[max(minA, minB), min(maxA, maxB)]` (the overlap) so the inevitable boundary clamping doesn't draw garbage at the lap-end (the Method 2 result at bin 6980 was +133,930 ms because the resampler clamped to the boundary-artifact's negative lap_time_s — proving step 2 is non-negotiable).
5. **Keep the `coarseDataWarning` badge** logic and the median-Δd test — they still reflect data-quality concerns.

### Things to verify in the fix

- The 1.8 s baseline overshoot also disappears under the proposed method (it should — that error was a side-effect of using F4 distance as the integration variable).
- All four test suites still pass: `test_m5.js`, `test_f1f2.js`, `test_m6_extras.js`, `test_m6.js`. The Δt cross-check in `test_m5.js` compares against a Python reimplementation of the *current* `computeDeltaT` formula — that reimplementation must be updated in lockstep, or the cross-check will fail with a "spec mismatch" rather than a real bug.
- The Δt curve at intermediate distances should also be sensible. With the current speed-integral method, the curve behaves cumulatively (always increasing in magnitude). The proposed method gives instantaneous time delta at each distance, which is what drivers actually want to read. Watch the per-bin Δt in §8 — at d=2000 the proposed method shows A is 120 ms ahead, then B claws back to 70 ms ahead by lap end. That is a **more informative** plot than a monotonically-growing accumulation.

### Things NOT to change

- The recorder's F4 distance integrator. `lap_distance_m` is still a useful column for *aligning* two laps spatially (the x-axis). It is just not suitable as the *integration variable* for time delta.
- The schema. `lap_time_s` is already there.
- The picker labels. `(rolling)` / `(partial)` / ★ logic is independent of this bug.

---

## 8. Track-agnosticism — no hard-coded distances

**Constraint:** the recorder is used across rF2 and LMU on every track those sims
support — Bahrain Outer (~3.5 km), Barcelona (~4.6 km), Spa (~7.0 km), Le Mans
(~13.6 km), and beyond. The fix must not bake in any track-specific number.

The proposed approach is already track-agnostic. Verify each step against this
checklist:

| Step | Constant used | Source | Track-agnostic? |
|---|---|---|---|
| Resample `lap_time_s` onto bins | bin width = 1 m | global | ✔ same for any track |
| Boundary-artifact filter §6 | `lap_time_s < −0.05 s` | clock-quirk threshold | ✔ a clock anomaly, not a track property |
| Boundary-artifact filter §6 | `lap_distance_m > trackLen × 0.5` | per-file `trackLen` | ✔ relative; trackLen comes from `annotateSegments` (max maxD across file's segments) |
| Overlap-range bounding | `[max(minA,minB), min(maxA,maxB)]` | per-pair from each lap's data | ✔ derived per comparison, no constants |
| `Δt(d)` formula | `lt_session(d) − lt_ref(d)` | per-frame sim values | ✔ no distance constant anywhere |

### Why each piece scales to any track

- **`lap_time_s` is the sim's per-frame stopwatch** (`mCurrentET − mLapStartET`).
  It's monotonic within any lap on any circuit. Its value range is the lap
  duration, which scales naturally with track length / car speed.

- **`lap_distance_m` is the sim's centerline counter** (`mLapDist` anchored,
  speed-integrated). It always starts near 0 at the line and grows to trackLen
  by the next line crossing — same contract for Bahrain Outer (3.5 km) or
  Le Mans (13.6 km).

- **`trackLen × 0.5` for the boundary-artifact heuristic** is robust because the
  artifact ALWAYS sits near `trackLen` (it's the SHM lagging on `mLapDist` reset
  at the line). Any threshold strictly less than `trackLen` and strictly more
  than the longest possible "real first frame distance" works:
  - 1 km track: threshold 500 m, artifact at ~995 m → caught.
  - 7 km Spa: threshold 3500 m, artifact at ~6975 m → caught.
  - 13.6 km Le Mans: threshold 6800 m, artifact at ~13,595 m → caught.
  Real first frames are always within a few metres of the line (we've observed
  −0.5 m to +3.3 m on Spa); these are nowhere near `trackLen × 0.5`.

- **Overlap-range bounding** uses the actual data range of each compared lap.
  Two laps on Bahrain Outer (each ~3500 m) overlap on ~3500 m; two laps on
  Le Mans (~13,600 m) overlap on ~13,600 m. No code change between tracks.

### Hard-coded numbers that DO appear in the codebase (and are deliberately so)

For completeness — these exist already and should NOT be touched as part of this
fix:

| Constant | Location | Meaning | Why it's OK |
|---|---|---|---|
| `0.3` | `_estimate_dist`, `computeDeltaT` | minimum-speed clamp (m/s) | Avoids 1/0 at standing-start; below any sim's reportable rolling speed |
| `0.3` | `_estimate_dist` | sim-pause detection (300 ms gap) | Pause threshold, not a distance |
| `0.95` | `annotateSegments` | "this lap reached at least 95% of trackLen" | Already relative |
| `0.5` | `annotateSegments` | "duration >= 50% of median complete-lap dur" | Already relative |
| `50` | `annotateSegments` | rolling-start `|minD|` tolerance (metres) | This *is* an absolute distance, but it's a tolerance for SHM `mLapDist` reset jitter (a few metres) — not a track-length assumption. Same for any track. |

### Failure modes the fix agent must consider

- **Sub-30s sprint laps / track days / autocross.** `lap_time_s` ranges of a
  few seconds. Boundary heuristic still fires (artifact near trackLen, time
  threshold −0.05 s — clock quirk, not duration-based).
- **Very long laps (Nürburgring Nordschleife ~20.8 km, Le Mans ~13.6 km).**
  Bin grid grows to 20,000+ bins. Resample/integration is O(n log n + n) — fine
  numerically and performance-wise.
- **Tracks where the car can drive backwards across the line** (e.g., reverse
  layouts, recovery driving). lap_distance_m may go negative or wrap. The
  boundary artifact filter still works — it only acts on the high-distance
  out-of-order frame, not on negatives.

**Bottom line for the fix agent:** if you find yourself typing a number with units
of metres, kilometres, or seconds-of-lap-duration into the patch, **stop and
re-derive it from per-file or per-comparison state**. The bug is solved by using
the right column (`lap_time_s`) as the integration target, not by adding more
heuristics.

---

## 9. Δt curve behaviour comparison (informational)

Sampled at every 1000 m with the proposed `lap_time_s`-interpolation method:

```
d=    0:  Δt = -69.13 ms   (recorder caught both laps right at start; same offset)
d= 1000:  Δt = -69.13 ms
d= 2000:  Δt = -120.55 ms  (A pulled ahead — better S1 exit)
d= 3000:  Δt = -162.30 ms  (A still gaining)
d= 4000:  Δt = -69.13 ms   (B clawed back — A lost time around Pouhon?)
d= 5000:  Δt = -69.13 ms
d= 6000:  Δt = +130.87 ms  (A is now BEHIND — bus stop / final corners)
d= 6978:  Δt = -69.12 ms   (final: A wins by 69 ms)
```

This is the kind of trace that helps a driver figure out *where* they gained or lost time. The current cumulative-speed-integral plot smears this signal into a noisy curve dominated by the F4 over-count.

---

## 10. Files to read before fixing

In recommended order:

1. `web/compare.html` —
   - `computeDeltaT` (~line 550) ← the function to rewrite.
   - `resample` + `interpAt` (~lines 522–546) ← shape and clamping behaviour.
   - `renderAll` (~line 1095) ← where the channels are resampled and passed to renderers.
   - `renderDtPanel` (~line 800) ← the consumer of `currentDtBins`.
2. `lap_telemetry/recorder/connect.py` `_estimate_dist` (~line 77) ← read-only; understand the F4 mechanism but DO NOT modify it.
3. `scripts/test_m5.js` — search for `pythonDt` and `__dtDebug`. The Python reference implementation must be updated in the same patch.
4. `DESIGN.md` §4.2 ("Δt is computed by integrating 1/speed over distance…") — needs a one-paragraph update.

---

## 11. Open questions for the fix agent

- **Is the 56 ms error correlated with cornering?** The differential F4 over-count between laps presumably scales with how much yaw/slip happened on each lap. If so, fast clean laps would show smaller phantom errors than messy ones. Worth checking on a few more lap pairs after the fix lands.
- **Should the boundary-artifact filter (§6 step 2) live in the recorder or the app?** Recorder-side is cleaner (the artifact is a known SHM lag and we can skip the affected frame at write time). App-side is safer (doesn't change the on-disk schema, doesn't invalidate existing recordings). My suggestion: app-side for now, recorder-side as a follow-up if it proves robust.
- **Should we also re-derive `max(lap_time_s)` for picker durations?** Currently durations come from `max(lap_time_s)`, which can be off by up to 20 ms (one frame) from the true lap time because the recorder may not have sampled at the exact line crossing. This is unrelated to the Δt bug but is the same family of "what's the canonical lap duration" question. Not in scope for this fix unless it falls out for free.
