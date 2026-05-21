# Slice 01c: Determine Entry/Exit Phase Algorithm

## Goal

Replace the fixed-offset entry/exit phase detection in `lap_comparator.py` with an algorithm that uses throttle, brake, and speed traces to determine where corner entry begins and where the corner exit ends. The minimum-speed detection at the apex is correct and stays unchanged.

## Problem

The current `compare_laps()` in `lap_comparator.coach.lap_comparator` determines corner entry and exit using a blind 30-meter offset from the apex:

- **Entry:** `speed[floor(apex_s_m - 30)]` — a single speed sample 30 m before the apex.
- **Exit:** `speed[floor(apex_s_m + 30)]` — a single speed sample 30 m after the apex.

This produces misleading facts:
- A long braking zone may start 150+ m before the apex; sampling 30 m before misses the actual entry entirely.
- Exit throttle application may happen well before or after the 30 m offset.
- The algorithm doesn't use brake or throttle data, even though these channels exist in the Parquet files.

For coaching to be actionable, we need to report *what the driver did* at each phase transition:

- **Entry:** where the driver lifts off throttle and/or applies brakes.
- **Exit-1 (brake release):** where the driver releases the brakes completely — the end of trail braking.
- **Exit-2 (full throttle):** where the driver gets back to full throttle — the end of the corner's acceleration phase.

Often exit-1 and exit-2 coincide (brake off = throttle full immediately), but when they differ, both are coaching-meaningful: "still trail braking past the apex" vs "late getting back to power."

## Non-goals

- Do not change the `LapComparisonFacts` output schema or the LLM prompt contract.
- Do not change the track coaching model format or the model loader.
- Do not modify `demo_coach_slice01.py` beyond updating it to exercise the new algorithm.
- Do not add straight-zone time-loss analysis (future slice).
- Do not change the `loss_s = speed_delta / 100.0` heuristic (future slice to replace with integrated time loss).
- Do not solve multi-apex corners. These need definition in a later slice (the current single-apex model may misidentify transitions for chicanas/double-apex sweepers).

## Required Behavior

### Entry phase detection

For each corner defined by the track model (with `s_start_m`, `apex_s_m`, `s_end_m`), determine the entry point by walking backward from the apex through the speed trace and (when available) the throttle and brake traces:

1. **Find the speed local maximum** — walk backward from `apex_s_m` toward `s_start_m`. The last index where speed peaks before the sustained drop into the apex. This is always available and marks the transition from acceleration to deceleration.
2. **Find the throttle lift point** — walk backward from `apex_s_m`. The first index (going backward) where throttle drops below a threshold (e.g. < 90% of full, or < 0.9 on a 0–1 scale). This is the **preferred entry marker** because it's the earliest action the driver takes — where corner preparation begins.
3. **Find the brake application point** — walk backward from `apex_s_m`. The first index (going backward) where brake rises above a threshold (e.g. > 5% of max brake, or > 0.05 on a 0–1 scale). This confirms commitment to the corner.
4. **Combine:**
   - If throttle data exists: `entry_s = s_lift` — the throttle lift point. This is the coaching-meaningful point: "you lifted later than the reference driver."
   - If no throttle data: `entry_s = s_peak` — the speed local maximum. Falls back to the speed-only signal.
   - The brake point (`s_brake`) is available as a secondary fact but does not override the entry point.
5. Report entry phase facts using `speed[entry_s]` compared to `ref_speed[entry_s]`.

### Exit phase detection

For each corner, determine two exit sub-phases by walking forward from the apex:

1. **Find the brake release point (exit-1)** — walk forward from `apex_s_m`. The first index where brake returns to 0% (or near-zero, e.g. < 0.01). This marks the end of trail braking: "you were still on the brakes here."
2. **Find the full throttle point (exit-2)** — walk forward from `apex_s_m`. The first index where throttle reaches 100% (or near-full, e.g. ≥ 0.95 on a 0–1 scale). This marks the end of the corner's acceleration phase: "you got back to full throttle here."
3. **Do NOT use the speed local maximum for exit.** Speed keeps increasing past the exit into the next straight, so a speed peak is not the exit — it's the approach to the next corner.
4. **Combine:**
   - If brake data exists: `exit_brake_s = s_brake_off` — the distance where brakes are fully released.
   - If throttle data exists: `exit_throttle_s = s_throttle_full` — the distance where throttle reaches full.
   - If neither exists: fall back to `s_end_m` from the track model (the zone boundary).
   - Often `exit_brake_s ≈ exit_throttle_s` (driver releases brake and immediately goes full throttle). When they differ, both distances are reported because each is independently coaching-meaningful.
5. Report exit phase facts using `speed[exit_brake_s]` and `speed[exit_throttle_s]` compared to the reference at the same distance.

### Exit fact structure

When brake and throttle data are both available, the exit may produce up to two phase entries per corner:

- `phase: "exit_brake"` — speed at brake release, with `distance_m` = `exit_brake_s`
- `phase: "exit_throttle"` — speed at full throttle, with `distance_m` = `exit_throttle_s`

When `exit_brake_s` and `exit_throttle_s` are within a small tolerance (e.g. ≤ 3 m), emit a single `phase: "exit"` fact at the midpoint distance.

When only one channel is available, emit a single exit fact tagged with the detected channel.

When neither channel is available, emit a single `phase: "exit"` fact at `s_end_m`.

### Minimum-speed phase (unchanged)

The `minimum_speed` phase detection is correct — it finds the minimum speed within the corner zone `[s_start_m, s_end_m]`. No changes needed.

### Columns required

The algorithm must handle both cases:
- **Full data:** Parquet has `brake`, `throttle`, and `speed_kph` columns alongside `lap_distance_m`.
- **Speed-only:** Parquet lacks `brake`/`throttle` — fall back to speed-only entry detection (local maximum) and zone-boundary exit.

The resampling step must extend to handle brake and throttle channels when present, putting them on the same 1 m distance grid as speed.

### Phase output and deduplication

Each corner can produce up to four phase entries: `entry`, `minimum_speed`, `exit_brake` (or `exit`), and `exit_throttle` (if distinct from `exit_brake`). The existing top-3 cap (`losses[:3]`) remains. No deduplication by corner_id is applied — a single corner may appear with multiple phases.

## Algorithm Guidance

A simple first implementation:

1. **Resample** `speed_kph`, and optionally `brake` and `throttle`, onto the same 1 m distance grid using the existing `resample_column()` helper.

2. **For each corner** in the track model:

   **Entry (walking backward from apex within `[s_start_m, apex_s_m]`):**
   - If throttle data exists: find `s_lift` = last distance where `throttle[i] < 0.9` walking backward from apex. Use `s_lift` as the entry point.
   - If no throttle data: find `s_peak` = last local maximum in speed before the sustained drop. Use `s_peak` as the entry point.
   - Optionally compute `s_brake` (first distance walking backward from apex where `brake[i] > 0.05`) as a secondary fact.

   **Minimum speed (unchanged):**
   - `min(speed[s_start_m:apex_s_m+1])`.

   **Exit (walking forward from apex within `[apex_s_m, s_end_m]`):**
   - If brake data exists: find `s_brake_off` = first distance walking forward from apex where `brake[i] < 0.01`.
   - If throttle data exists: find `s_throttle_full` = first distance walking forward from apex where `throttle[i] ≥ 0.95`.
   - If both exist and `|s_brake_off - s_throttle_full| ≤ 3`: emit single `phase: "exit"` at midpoint.
   - If both exist and they differ: emit `phase: "exit_brake"` and `phase: "exit_throttle"` as separate facts.
   - If only one exists: emit `phase: "exit"` at that distance.
   - If neither exists: emit `phase: "exit"` at `s_end_m`.

3. **For each detected phase**, compute `speed_delta = reference_value - driver_value` and derive `loss_s` using the same `speed_delta / 100.0` heuristic (unchanged in this slice).

4. **Sort** all corner-phase facts by `loss_s` descending and take the top 3 losses and top 3 gains (unchanged).

## Thresholds

| Threshold | Value | Rationale |
|-----------|-------|-----------|
| Throttle lift | < 0.9 (90%) | Detects initial lift-off; avoids noise from small pedaling |
| Brake application | > 0.05 (5%) | Ignores sensor noise; detects committed braking |
| Brake off | < 0.01 (1%) | Brake fully released; near-zero to avoid noise floor |
| Throttle full | ≥ 0.95 (95%) | Driver is back to full power; allows for slight imprecision in pedal data |
| Exit merge tolerance | ≤ 3 m | If brake-off and full-throttle are within 3 m, treat as a single exit point |

All thresholds should be configurable via function parameters with these defaults.

## Testing

Before changing tests, read `docs/TESTING_LESSONS.md`.

### Unit Tests

Add tests to the existing `lap_comparator.py` test coverage. Use synthetic telemetry:

1. **Throttle-lift entry** — synthetic trace where throttle drops at a known distance before the apex; verify the algorithm reports entry at `s_lift`, not at `apex - 30`.
2. **Brake-based exit (brake off)** — synthetic trace where brake returns to 0 at a known distance after apex; verify the algorithm reports exit at that distance.
3. **Throttle-based exit (full throttle)** — synthetic trace where throttle reaches 100% at a known distance after apex; verify the algorithm reports exit at that distance.
4. **Separate exit phases** — synthetic trace where brake releases before throttle reaches full; verify both `exit_brake` and `exit_throttle` phases are reported with distinct distances.
5. **Merged exit** — synthetic trace where brake-off and full-throttle are within 3 m; verify a single `exit` phase is reported.
6. **Speed-fallback entry** — synthetic speed-only trace where speed peaks at a known distance before braking zone; verify entry detection from speed local maximum.
7. **Speed-only exit fallback** — synthetic trace without brake/throttle; verify exit falls back to `s_end_m`.
8. **Missing channels gracefully degrade** — if brake/throttle columns are absent, the algorithm still works with speed-only fallback and produces correct `minimum_speed` and `entry` results.

### Integration / Golden Test

Run the demo script and verify:
```bash
cd product/python && python3 demo_coach_slice01.py --verbose
```
- Entry distances should no longer be exactly `apex - 30`.
- Exit distances should no longer be exactly `apex + 30`.
- The output schema must remain compatible with the `LapComparisonFacts` structure (may add `exit_brake`/`exit_throttle` phase names).
- When an exit phase is reported, the demo output must include both the brake-off distance and the full-throttle distance so the coach can compare them. Example:
  ```json
  {
    "corner_id": "t3",
    "phases": {
      "exit_brake_distance_m": 1180.0,
      "exit_throttle_distance_m": 1182.0
    },
    ...
  }
  ```
  When the two distances coincide (within merge tolerance), only one distance is shown.
- `minimum_speed` phase should produce identical results to before.

### Manual Validation

Inspect Barcelona output and verify entry/exit distances match what a driver would expect:
- Entry should be near where throttle lifts off / braking begins.
- Exit-1 (brake off) should be near or past the apex.
- Exit-2 (full throttle) should be in the acceleration zone after the apex.

## Acceptance Criteria

- `compare_laps()` no longer uses fixed 30 m offsets for entry/exit.
- Entry uses throttle lift (preferred) or speed local maximum (fallback).
- Exit reports brake-off and full-throttle distances as separate phases when they differ, merged when they coincide within 3 m.
- Speed local maximum is never used as an exit marker.
- `minimum_speed` phase is unchanged.
- All existing tests pass.
- New tests cover throttle-lift entry, brake-off exit, full-throttle exit, merged exit, speed-only fallback.
- `npm run build` succeeds.
- `handoff.md` and `learnings.md` are created for this slice.

## Definition of Done

- [ ] Algorithm implemented in `lap_comparator.py` (or a helper module).
- [ ] Resampling extended to brake/throttle channels when present.
- [ ] Unit tests pass for throttle-lift entry, brake-off exit, full-throttle exit, speed-only fallback.
- [ ] Barcelona golden test updated and passes.
- [ ] Full test suite passes (`bash scripts/test-summary.sh`).
- [ ] Build succeeds (`npm run build`).
- [ ] `handoff.md` documents the algorithm, thresholds, and fallback behavior.
- [ ] `learnings.md` documents limitations and edge cases found.