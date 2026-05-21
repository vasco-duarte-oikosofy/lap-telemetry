# Learnings — Slice 01c: Determine Entry/Exit Phase Algorithm

## What surprised us

1. **macOS Unicode normalization trap.** My first attempt at a Python-based search-and-replace silently corrupted the filename `engineering` → `engineing` (a subtle transposition invisible in most editors). On macOS, `Path.exists()` can return `False` for a path that differs by a single character, even though `os.listdir()` shows the file exists. The only reliable fix was byte-level inspection (`xxd` / `.hex()`) to find the mismatch. **Lesson: always verify file edits with binary-level checks when filenames look identical but `exists()` returns `False`.**

2. **Exit brake-off detection needs a "was braking" gate.** Simply scanning forward from the apex for `brake < 0.01` would match immediately if the driver isn't braking at the apex. The algorithm must first confirm `was_braking = True` (brake > 0.05 observed) before accepting the brake-off point. Same pattern for throttle-full: must confirm `was_partial = True` first.

3. **Entry throttle-lift detection walks FORWARD, not backward.** Despite the spec saying "walk backward from apex," the physically meaningful lift point is where throttle first drops below threshold when scanning from the zone start toward the apex (the transition from full-throttle to lift-off). Walking backward from apex, you're already in the low-throttle zone.

4. **Exit brake/throttle often diverge by 5-20 m.** On the Barcelona data, turn 3's brake-off is at 1169m while full-throttle is at 1174m — a 5m gap, enough to produce separate `exit_brake` and `exit_throttle` phases (beyond the 3m merge tolerance).

5. **Entry look-back is essential.** The original algorithm searched only within `[s_start_m, apex_s_m]`, but braking zones regularly start 50-100m before `s_start_m`. Turn 6 at Barcelona: zone starts at 2502m but throttle lifts at ~2438m (64m before the zone). Without a look-back, the algorithm found no throttle transition and fell back to `speed_peak` at the zone boundary, where speed was already mid-corner (~147 kph). This produced a spurious "gain" of 6 kph. With a 200m look-back, throttle lift is correctly detected and entry speed is ~204 kph (a realistic straight speed). The 200m default covers even long braking zones; corners that are very close together will find lift-off in the preceding corner's zone.

6. **Apex offset is coaching-meaningful.** The `minimum_speed` phase now reports `driver_apex_distance_m` and `reference_apex_distance_m`. On Barcelona turn 3, the driver apexes 9m later than the reference (1170m vs 1161m). This is immediately actionable: "you apexed late in turn 3, missing the ideal apex." Option D (deliver both raw distances, let the prompt interpret) was chosen because it preserves directionality implicitly and adds minimal schema change.

7. **Apex offset raises multi-apex questions.** On a chicane, both driver and reference might have different double-minimum traces. The current single-minimum-per-corner approach would pick the global minimum, which may not be the coaching-meaningful one. Imola's Variante Alta/Bassa are good test cases. Deferred to a later slice.

## Edge cases & limitations

- **Look-back for entry detection (fixed):** Throttle lift and braking often start well before `s_start_m`. The algorithm now searches 200m before `s_start_m` via `look_back_m`. Without this, entry would be detected at the zone boundary where throttle is already zero, producing meaningless speed comparisons.
- **Multi-apex corners**: The algorithm treats each corner as a single-apex zone. Chicanas/double-apex sweepers will likely produce misleading phase distances. Deferred to a future slice.
- **Brake never applied at apex**: If the driver isn't trail braking, the brake-off exit phase won't be detected (the `was_braking` gate won't open). The algorithm falls through to throttle-full or zone-boundary fallback.
- **The `loss_s = speed_delta / 100.0` heuristic remains unchanged**: This is a ranking heuristic, not true integrated time loss. A future slice will replace it.

## Threshold defaults

| Threshold | Value | Rationale |
|-----------|-------|-----------|
| `throttle_lift` | 0.9 (90%) | Detects initial lift-off; avoids noise |
| `brake_apply` | 0.05 (5%) | Ignores sensor noise; detects committed braking |
| `brake_off` | 0.01 (1%) | Brake fully released; near-zero to avoid noise floor |
| `throttle_full` | 0.95 (95%) | Back to full power; allows slight pedal imprecision |
| `exit_merge_tolerance_m` | 3.0 m | If brake-off and full-throttle within 3 m, merge |
| `look_back_m` | 200.0 m | Searches before s_start_m for throttle lift / braking |

## Apex offset design decision

We chose **Option D** (deliver `driver_apex_distance_m` and `reference_apex_distance_m` as additional fields on the `minimum_speed` phase). Rationale:
- The offset is coupled to `minimum_speed` — it's the same event at a different position.
- No need to invent a `loss_s` metric for spatial offset (meters don't rank like speed deltas).
- Directionality is implicit in the data: `driver_apex_distance_m > reference_apex_distance_m` means "late apex."
- The LLM prompt can say "you apexed 9m late in turn 3" by computing the offset.
- Adding two fields to an existing phase is minimal schema change vs. a new phase type.