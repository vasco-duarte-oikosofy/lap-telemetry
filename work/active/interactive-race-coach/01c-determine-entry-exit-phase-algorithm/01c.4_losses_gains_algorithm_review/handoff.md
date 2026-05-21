# Handoff — 01c.4 Losses and Gains Algorithm Review

## What was done

Two deliverables in this slice:

1. **Decision document + delta-time unification** — unified losses to use
   the same delta-time formula as gains for all three phases. Removed
   `speed_delta / 100.0` heuristic. `gain_end_distance_m` populated for
   both losses and gains.

2. **Entry/exit distance deltas** — added `entry_distance_delta_m`,
   `exit_distance_delta_m`, and `reference_phase_distance_m` fields.
   These compare driver vs reference phase-transition distances:
   "you lifted 8 m earlier than reference" / "you got back to full
   throttle 10 m earlier than reference."

## What is on disk now

### Modified files
- **`product/python/lap_telemetry/coach/lap_comparator.py`** (281 lines) — Unified delta-time for losses. Reference phase detection for entry and exit. Distance delta computation and population on CornerLoss.
- **`product/python/lap_telemetry/coach/js_pipeline.py`** (106 lines) — Added `ref_throttle_norm` and `ref_brake_norm` parameters.
- **`product/python/lap_telemetry/coach/facts.py`** (97 lines) — Added `entry_distance_delta_m`, `exit_distance_delta_m`, `reference_phase_distance_m` to CornerLoss and to_dict().
- **`dev/scripts/compute_delta_t.mjs`** (152 lines) — Resample reference throttle/brake alongside driver throttle/brake.
- **`dev/scripts/test_losses_delta_time.py`** (200 lines) — Tests for losses delta-time, gain_end_distance_m, entry/exit distance deltas, sign conventions, dict serialization.
- **`docs/specs/interactive-race-coach-and-engineer.md`** — Updated gain distance deltas section (no longer deferred). Marked brake/throttle distance comparison as done. Marked `speed_delta / 100.0` replacement as done. Added same-corner overlapping phase deduplication section.
- **`package.json`** — Added `test_losses_delta_time.js` to feature test list.

### New files
- **`work/.../01c.4/decision.md`** — 7 decisions on delta-time, overlap, heuristic removal, distance deltas, schema.
- **`work/.../01c.4/delta_loss_gain_delta_break_throttle.md`** — Entry/exit distance delta algorithm spec.
- **`work/.../01c.4/learnings.md`** — Key learnings.
- **`work/.../01c.4/handoff.md`** — This file.

## Barcelona output (after all changes)

Top losses — t3 exit_brake/exit_throttle now show distance deltas:
```json
"exit_brake": { "exit_distance_delta_m": -4.0, "reference_phase_distance_m": 1165.0 }
"exit_throttle": { "exit_distance_delta_m": -9.0, "reference_phase_distance_m": 1165.0 }
```
Negative = driver released brakes/got to throttle LATER than reference (slower exit).

Top gains — t5 exit now shows distance delta:
```json
"exit": { "exit_distance_delta_m": 10.0, "reference_phase_distance_m": 2168.0 }
```
Positive = driver got to full throttle 10 m EARLIER than reference (better exit).

## Sign conventions for distance deltas

| Phase | Field | Positive | Negative |
|-------|-------|----------|----------|
| entry | `entry_distance_delta_m` | Driver lifted earlier (cautious) | Driver lifted later (aggressive) |
| exit | `exit_distance_delta_m` | Driver exited earlier (better) | Driver exited later (worse) |

Same sign, opposite coaching meaning per phase. LLM prompt must interpret.

## Open items

1. **Same-corner deduplication** — overlapping min_speed + exit phases documented in spec, decision delegated to prompt-contract slice
2. **Multi-apex/chicanes** — documented in spec lines 110-126

## How to verify
```bash
bash scripts/test-summary.sh --feature interactive-race-coach    # 8 scripts, 249 assertions
bash scripts/test-summary.sh                                      # full suite, 1224 assertions
python3 product/python/demo_coach_slice01.py                      # demo output
npm run build                                                      # build
```