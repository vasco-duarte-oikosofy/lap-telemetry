# Entry gain algorithm — revised

## What changed since the previous spec

The original `entry_gain_algorithm.md` specified that entry gains
would use the same `speed_delta / 100.0` heuristic as losses, plus a
distance delta (`entry_distance_delta_m`) from detecting the
reference's entry point. This document **replaces** that approach for
gains with a delta-time measurement, matching what we already do for
`minimum_speed` and `exit` gains.

## Lessons from Barcelona fixture (swapped)

Using `--swap` on the Barcelona fixture (faster reference lap as
"driver"), the current heuristic vs real delta-time for every entry
gain:

| corner | entry_m | apex_m | heuristic | entry→apex Δt | heuristic / Δt |
|--------|--------:|-------:|----------:|--------------:|----------------:|
| t7     | 2820    | 2923   | −104 ms   | −155 ms       | 67 %            |
| t1     | 680     | 841    | −85 ms    | −156 ms       | 54 %            |
| t8     | 3352    | 3507   | −46 ms    | −58 ms        | 79 %            |
| t11    | 4226    | 4343   | −34 ms    | −67 ms        | 50 %            |
| t4     | 1596    | 1731   | −33 ms    | −81 ms        | 41 %            |
| t10    | 3989    | 4033   | −21 ms    | −29 ms        | 72 %            |
| t9     | 3680    | 3785   | −15 ms    | −52 ms        | 29 %            |
| t3     | 909     | 1161   | −17 ms    | +37 ms ⚠     | wrong sign      |

The heuristic under-reports every gain, typically by 30–60%. The t3
case is even worse: it **flips the sign** because the driver lifted at
the same point as for t2 (a connected chicane), and the delta_t got
*worse* from entry to apex (driver gained on entry but gave some back
in the chicane), yet the heuristic says "gain" because the driver was
traveling faster at the entry point.

## Decision: entry gains use Δt entry→apex

### Rationale

Each phase measures the delta-time gain **within its own phase
boundary**:

| Phase | Gain window | Why |
|-------|------------|-----|
| entry | entry_point → apex | Entry ends at apex. After that, minimum_speed takes over. |
| minimum_speed | apex → apex (speed comparison) + apex → straight_end (Δt) | The apex is the boundary between entry and exit. |
| exit | exit_point → straight_end | Exit advantage compounds down the straight. |

Measuring entry→apex isolates the entry-phase contribution. If the
driver gained 156 ms from entry to apex but then lost 20 ms from apex
to minimum-speed, the two facts are separate:
- entry gain: −156 ms
- minimum_speed loss: +20 ms

Summing both gives the net corner effect, and the LLM can present them
as distinct coaching points — "you carried great speed into the corner
but sacrificed mid-corner speed."

### Why NOT entry→straight_end

The exit phase already measures the advantage from exit_point to
straight_end. If entry gains also measured to straight_end, the entry
and exit gains would overlap, and the same advantage could be reported
twice for one corner. Keeping each phase within its own boundaries
avoids double-counting.

## Algorithm

For entry **gains** only (`entry_delta < 0`, i.e. driver was faster at
the entry point):

```python
if entry_delta < 0:
    # GAIN — real delta-time from entry to apex
    apex_idx = int(corner.apex_s_m)
    if 0 <= entry_idx < len(delta_t) and 0 <= apex_idx < len(delta_t):
        loss_s = delta_t[apex_idx] - delta_t[entry_idx]
    else:
        loss_s = entry_delta / 100.0  # fallback heuristic
```

For entry **losses** (`entry_delta > 0`): unchanged — still uses
`entry_delta / 100.0` heuristic.

### Sign convention

`delta_t[i]` = driver cumulative time − reference cumulative time.
Positive = behind. Negative = ahead.

`loss_s = delta_t[apex] − delta_t[entry]`

| Scenario | delta_t trend | loss_s | Meaning |
|----------|-------------|-------|--------|
| Driver gains from entry to apex | gets more negative | negative | "you gained X ms entering this corner" |
| Driver loses from entry to apex | gets more positive | positive | "you lost X ms entering this corner" |
| No change | flat | ~0 | No entry-phase effect |

This matches the existing convention: `loss_s < 0` = gain, `loss_s > 0`
= loss.

### Edge case: t2/t3 chicane (shared entry point)

When two connected corners share an entry lift point (the driver lifts
once for a chicane), `find_entry_point()` may return the same distance
for both. The entry→apex delta_t will then measure different windows:
- t2 entry (909m) → t2 apex (940m): short window, may show a loss
- t3 entry (909m) → t3 apex (1161m): long window, likely shows a gain

This is **correct behaviour** — each corner's entry gain is measured
over its own zone. The LLM can present them separately:
- "You were slightly slower in the t2 chicane entry"
- "But you carried excellent speed through to the t3 apex"

### Edge case: entry_detected > apex

If `entry_idx >= apex_idx` (shouldn't happen with 200 m look-back but
defensive), fall back to the heuristic.

## Still deferred: `entry_distance_delta_m`

The original spec also called for detecting the reference's entry
point and reporting `entry_distance_delta_m` ("you lifted 8 m later
than reference"). This is still valuable but **orthogonal** to the
delta-time fix. It will be implemented in a later slice alongside
`exit_distance_delta_m`, since both require resampling the reference
lap's pedal channels.

## Acceptance criteria

- Entry gains use `delta_t[apex] - delta_t[entry]` instead of
  `speed_delta / 100.0`.
- Entry losses still use `speed_delta / 100.0` (unchanged).
- t1 entry gain on Barcelona (swapped) ≈ −156 ms (was −84 ms).
- All existing tests pass.
- New test covers entry→apex delta-time gain with synthetic data.