# Barcelona Outline Pipeline — Learnings

## What surprised us

1. **bacinger/f1-circuits GeoJSON worked out of the box** — The centerline data from this repo aligned cleanly with our simulator trajectory data using ICP. The mean error of ~18 sim-units is acceptable for visual context.

2. **UTM projection not strictly necessary** — We initially planned to use proper UTM zone 31T projection, but the simplified Transverse Mercator formula was sufficient since ICP handles scale/rotation/translation automatically. The relative geometry is what matters for alignment.

3. **Constant width estimation is visually acceptable** — Using 6m per side (12m total) for the entire track produces a reasonable visual outline. Barcelona-Catalunya is a wide F1 track, and this width looks correct at start/finish and through the main corners.

4. **Trajectory JSON had wrong track name** — The existing `trajectory-circuit-de-barcelona.json` was labeled as "Spa-Francorchamps" from a previous run. We fixed this by passing `--sim-track-name` to the alignment script.

## Technical notes

- **ICP flip combinations**: The `--try-all-flips` flag is essential. For Barcelona, the "none" flip configuration won with mean error 18.44, while other flips had errors >190.

- **150 centerline points** from bacinger is sufficient — ICP resamples internally to match trajectory density.

- **Scale factor ~0.825** indicates the bacinger GPS-derived centerline is larger than the simulator coordinate system, which makes sense (real-world meters vs sim units).

## For the next agent

- Visual QA is still pending — open `tools/manual_outline_align.html` to verify landmarks:
  - Start/finish straight alignment
  - Turn 1 (tight right after long straight)
  - Camp corner (tight left hairpin at far end)
  - Back straight length and orientation
  - Turn 10 / chicane area

- If widths need refinement, measure from Google Maps satellite at 3-5 reference points and interpolate.

- If bacinger centerline proves wrong for LMU's specific Barcelona layout variant, try OSM Overpass extraction or remove outline and render trajectory-only.
