# Slice 30 — Silverstone International (new track outline)

Trajectory outline for the LMU **Silverstone International Circuit** layout
(2961 m, 8 corners), which has no TUMFTM centreline of its own: TUMFTM's
`Silverstone.csv` describes the GP layout.

Needed now because the map-turn-names mission wants a track that has both an
outline and curated corner names — Silverstone International has the cleanest
curated model in the repo (Abbey, Farm Curve, Village, The Link, Becketts,
Stowe, Vale, Club).

**Reference lap:** `silverstone-international-circuit_vista-af-corse-2026-21-lm_time_01.02.909.parquet`
(Ferrari 296 GT3, race lap 13, 2026-10-31).

1. Generate the trajectory outline per
   [`dev/scripts/GENERATE_TRAJECTORY_OUTLINE.md`](../../../dev/scripts/GENERATE_TRAJECTORY_OUTLINE.md).
2. Register it (ES module + manifest), rebuild `dist/compare.html`.
3. Update `docs/TRACK_OUTLINE_COVERAGE.md`.
4. Numeric QA against the TUMFTM GP outline; note where the layouts diverge.
5. Commit.

Visual QA in the app is the mission's usual second slice for a track; this
slice leaves `visual_qa.status` at `pending`.
