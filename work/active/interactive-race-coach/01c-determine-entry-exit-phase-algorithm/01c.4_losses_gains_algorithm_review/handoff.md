# Handoff — 01c.4 Losses and Gains Algorithm Review

## What was done

This was a **review + implementation** slice. The decision document
(`decision.md`) establishes that losses should use the same delta-time
formula as gains for all three phases. The implementation unifies the
code accordingly.

## What is on disk now

### Modified files
- **`product/python/lap_telemetry/coach/lap_comparator.py`** (233 lines, was 241) — All three phases (minimum_speed, entry, exit) now use delta-time for both losses and gains. The `if speed_delta > 0: heuristic` branches are removed. `gain_end_distance_m` is populated for both losses and gains.

### New files
- **`dev/scripts/test_losses_delta_time.py`** (122 lines) + **`dev/scripts/test_losses_delta_time.js`** — Tests: losses use delta-time (not heuristic), gain_end_distance_m always populated, sign convention preserved, dict serialization includes gain_end_distance_m.
- **`work/active/.../01c.4/decision.md`** — Decision document with 7 decisions.
- **`work/active/.../01c.4/learnings.md`** — Key learnings.

### Modified config
- **`package.json`** — Added `test_losses_delta_time.js` to `testFeatures.interactive-race-coach`.

## Current gain/loss algorithm summary

| Phase | Loss formula | Gain formula | gain_end_distance_m |
|-------|-------------|-------------|---------------------|
| entry | `delta_t[apex] - delta_t[entry]` | `delta_t[apex] - delta_t[entry]` | apex |
| minimum_speed | `delta_t[straight_end] - delta_t[apex]` | `delta_t[straight_end] - delta_t[apex]` | straight_end |
| exit | `delta_t[straight_end] - delta_t[exit]` | `delta_t[straight_end] - delta_t[exit]` | straight_end |

**Loss and gain formulas are now identical** — the sign emerges naturally
from delta_t values. The `speed_delta / 100.0` heuristic is removed for
all phases (kept only as a fallback for out-of-range indices).

## Barcelona output after this change

Losses increase significantly because real delta-time captures compounding:

| Phase | Old heuristic | New delta-time |
|-------|-------------|----------------|
| exit_brake | 0.120s | 0.194s |
| minimum_speed | 0.106s | 0.190s |
| exit_throttle | 0.126s | 0.179s |

## Deferred TODOs
- **`entry_distance_delta_m` / `exit_distance_delta_m`**: Distance comparison of driver vs reference phase transition points. Orthogonal to delta-time unification. Requires resampling reference pedal traces and detecting their entry/exit points.
- **`gain_end_distance_m` rename**: Field name is slightly misleading for losses. Could rename to `measurement_end_distance_m` but deferred to avoid web UI changes.
- **Whole-lap accounting validation**: Sum of all loss_s should approximate lap_time_delta_s. Can be added as a sanity check in a future slice.

## How to verify
```bash
bash scripts/test-summary.sh --feature interactive-race-coach    # feature tests (8 scripts, 233 assertions)
bash scripts/test-summary.sh                                      # full suite (50 scripts, 1224 assertions)
python3 product/python/demo_coach_slice01.py                      # demo output
npm run build                                                      # build
```