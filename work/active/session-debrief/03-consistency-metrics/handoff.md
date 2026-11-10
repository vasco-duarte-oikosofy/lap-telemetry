# Handoff — Slice 03: consistency metrics

## State on disk

| File | Job |
|---|---|
| `product/python/lap_telemetry/session_consistency.py` | Pace summary, speed envelope, both rankings, phase spreads |
| `product/python/lap_telemetry/lap_signals.py` | Added `sector_times()` (extracted from `summary.py`), `row_rate_ratio()`, per-segment `sample_rate_hz()` |
| `product/python/lap_telemetry/session_laps.py` | Rejects duplicated-row laps as `short`; sample rate from the median segment |
| `product/python/lap_telemetry/session_facts.py` | Payload gained the `consistency` section |
| `product/python/lap_telemetry/summary.py` | Now uses `sector_times()`; output byte-identical |
| `dev/scripts/lap_inventory_audit.py` | Justifies the new `short` gate (duration **or** row rate) |

## Commands

```bash
bash scripts/test-summary.sh --feature session-debrief        # 21 scripts, 568 assertions
bash scripts/test-summary.sh                                  # 1553 passed, 4 pre-existing
PYTHONPATH=product/python python3 -m lap_telemetry debrief <session> --json
```

Paul Ricard fixture, current numbers: **18 eligible / 16 clean** (was 19/17
before the row-rate gate), best 1:19.135, spread 3.356 s, std dev 0.872 s,
envelope 1:16.376, **2.759 s available from repeatability**.

## API worth knowing about slices 04–06

```python
facts.consistency.pace               # LapPace: best/median/worst/spread/std/envelope/available
facts.consistency.recurring_losses   # ranked by mean_loss_s, with laps_affected/laps
facts.consistency.inconsistent_corners  # ranked by spread_s (seconds)
facts.consistency.phase_spread       # ranked by own-unit spread (km/h), with point_spread_m
```

- `recurring_losses` and `inconsistent_corners` are deliberately separate. Slice
  05 must weight them, not concatenate them.
- `laps_affected` is out of the laps where the phase was **measurable**, which is
  often fewer than the clean-lap count. Do not render it as "x of all laps".
- The envelope is optimistic by construction (instantaneous speed changes). The
  report must say so; do not present `time_available_s` as achievable in one lap.
- Consistency uses clean laps only, filtered in `build_consistency`.

## Deferred / next

- **Slice 04** (extended corner facts): gear at apex/exit, brake peak and area,
  trail-braking depth, steering corrections, rear slip, TC/ABS duty, lateral line
  offset. All channels exist on current recordings.
- Bug 33 (reference baseline) is still open; it does not touch this slice.
- New observation, filed as **bug 34**: three committed laps contain duplicated
  rows with a stalled clock. The analysis now rejects them, but the recorder
  still produces them.
- The sector path is still worth reviving if the recorder ever publishes fresh
  per-lap sector channels; `lap_signals.sector_times()` is ready.
- `phase_spread` is a descriptive list, not a ranking input yet; slice 05 may or
  may not use it.
