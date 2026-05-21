# Learnings — Slice 01c: Determine Entry/Exit Phase Algorithm

## What surprised us

1. **macOS Unicode normalization trap.** First attempt at a Python-based search-and-replace silently corrupted a filename. On macOS, `Path.exists()` can return `False` for a path that differs by a single invisible character. Only byte-level inspection (`xxd` / `.hex()`) finds the mismatch.

2. **Exit brake-off detection needs a "was braking" gate.** Simply scanning forward from the apex for `brake < 0.01` would match immediately if the driver isn't braking at the apex. The algorithm must confirm `was_braking = True` first. Same pattern for throttle-full: must confirm `was_partial = True`.

3. **Entry throttle-lift detection walks FORWARD, not backward.** The physically meaningful lift point is where throttle first drops below threshold when scanning from the zone start toward the apex (the transition from full-throttle to lift-off).

4. **Exit brake/throttle often diverge by 5-20 m** (Barcelona turn 3: brake-off 1169m, full-throttle 1174m).

5. **Entry look-back is essential.** Braking zones regularly start 50-100m before `s_start_m`. Turn 6 at Barcelona: zone starts at 2502m but throttle lifts at ~2438m (64m before zone). Without 200m look-back, entry falls back to zone boundary where speed is already mid-corner.

6. **Apex offset is coaching-meaningful.** Driver apexes 9m later than reference at turn 3 → "you apexed late."

7. **Delta-time gains are dramatically different from the heuristic.** For Barcelona t5 exit: heuristic gives -0.01s, delta-time gives -0.065s (6.5x difference). The heuristic underestimates real gains because it only measures the speed advantage at one point, while the gain compounds down the entire straight.

8. **End of straight = next corner's entry point**, not the next corner's zone boundary. Zone boundaries can be 50-100m off from where the driver actually lifts off. Using `find_entry_point()` on the next corner gives the correct lift-off distance.

9. **`apex_offset_m` sign convention**: `ref_apex - driver_apex`. Positive = driver apexed earlier (at a shorter distance). Negative = driver apexed later (Barcelona t3: -9.0 means driver apexed 9m later than reference).

## Edge cases & limitations

- **Look-back for entry detection (fixed):** 200m look-back covers even long braking zones.
- **Multi-apex corners**: Single-apex model; chicanes/double-apex sweepers may misidentify transitions. Deferred.
- **Brake never applied at apex**: Exit brake-off detection falls through to throttle-full or zone-boundary fallback.
- **`loss_s = speed_delta / 100.0` heuristic remains for losses**: This is a ranking heuristic, not true time loss. Losses should eventually use delta-time.
- **Entry gains still use heuristic**: Entry gain algorithm needs reference entry detection. Deferred to 01c.3.

## Threshold defaults

| Threshold | Value | Rationale |
|-----------|-------|-----------|
| `throttle_lift` | 0.9 (90%) | Detects lift-off; avoids noise |
| `brake_apply` | 0.05 (5%) | Detects committed braking |
| `brake_off` | 0.01 (1%) | Brake fully released |
| `throttle_full` | 0.95 (95%) | Back to full power |
| `exit_merge_tolerance_m` | 3.0 m | Merge brake-off and full-throttle when within 3m |
| `look_back_m` | 200.0 m | Searches before s_start_m for throttle lift / braking |

## What's still heuristic

| Phase | Loss | Gain |
|-------|------|------|
| minimum_speed | `speed_delta / 100.0` | delta-time ✅ |
| exit | `speed_delta / 100.0` | delta-time ✅ |
| entry | `speed_delta / 100.0` | `speed_delta / 100.0` ❌ |