# Slice 13 — Monza Curva Grande Circuit (new track, full combo)

Full track support for the LMU "Monza Curva Grande Circuit" layout from the
practice session `sessions/session_20261031T065746Z_monza-curva-grande-circuit_lmu_practice.parquet`
(car `DKR Engineering #4:ELMS25`, Ginetta LMP3 — the "P3" car). No reference
lap, coaching model or outline existed for this (track, car) combo.

1. Export + validate the reference lap (guarded scripts).
2. Generate + curate the coaching model using the **official Monza turn names**
   for every turn, and add the geometry of the **flat turns** (Curva Grande,
   Curva del Serraglio) that the throttle/brake detector cannot see.
3. Generate a trajectory track outline, register it, rebuild the bundle.
4. Update `docs/TRACK_OUTLINE_COVERAGE.md`.
5. Verify with `--print-facts` and the resolvers; commit.

Carried over from slices 34/35/36: apex sides from the reference lap's
steering/curvature (calibrated against two known corners), flat corners need
manual geometry, and the whole app load path must be checked — not just the
manifest lookup.
