# Barcelona Outline Pipeline — Handoff

## State on disk

### New files created

1. **`data/track-outlines/circuit-de-barcelona.json`** — Schema v1 outline with:
   - 150-point centerline from bacinger/f1-circuits es-1991.geojson
   - Left and right boundaries computed from 6m per side width estimate
   - ICP alignment parameters (scale: 0.825, rotation: -8.39°, translation: [-206, 38])
   - `visual_qa.status: "pending"`

2. **`data/track-outlines/alignment-artifacts/circuit-de-barcelona/bacinger-barcelona.json`** — Intermediate bacinger centerline converted to metric coordinates (UTM zone 31, centered at origin).

3. **`data/track-outlines/alignment-artifacts/circuit-de-barcelona/es-1991-raw.geojson`** — Raw GeoJSON downloaded from bacinger/f1-circuits.

4. **`scripts/convert_bacinger_to_metric.py`** — Python script to convert GeoJSON lon/lat to local metric coordinates.

5. **`web/js/staticCircuitBarcelonaOutlineData.js`** — ES module export of the outline (regenerated via `generate_outline_module.js`).

### Existing files updated

- **`web/js/trackOutlineManifest.js`** — Already had `CIRCUIT_BARCELONA_STATIC_OUTLINE` wired up; no changes needed.

## Feature flags / live status

- **Static outline rendering**: ACTIVE for Barcelona
- The manifest already maps `circuit-de-barcelona`, `barcelona-catalunya`, and `catalunya` slugs to the Barcelona outline.
- No feature flags need to be toggled.

## New helpers

- **`scripts/convert_bacinger_to_metric.py`**: Reusable for any bacinger/f1-circuits GeoJSON conversion. Usage:
  ```bash
  python3 scripts/convert_bacinger_to_metric.py <input.geojson> [output.json]
  ```

## Deferred TODOs

1. **[ ] Visual QA** — Open `tools/manual_outline_align.html` and verify:
   - Start/finish straight alignment
   - Turn 1 (tight right after long straight)
   - Camp corner (tight left hairpin at far end)
   - Back straight length and orientation
   - Turn 10 / chicane area
   
   If alignment is off, manually adjust and re-export. Update `visual_qa.status` to `"accepted"`.

2. **[ ] Width refinement (optional)** — If visual QA reveals width issues:
   - Measure actual track width from Google Maps satellite at 3-5 points
   - Interpolate widths across the centerline
   - Regenerate outline with `auto_align_outline.js`

3. **[ ] Layout variant verification** — Confirm that bacinger's `es-1991` (modern F1 layout) matches LMU's Barcelona layout. If LMU uses a vintage or MotoGP variant, the centerline will not match and we need a different source.

## Test status

- `bash scripts/test-summary.sh` — **731 assertions pass**
- `npm run build` — **Succeeds**, `dist/compare.html` is current

## Rollback plan

If bacinger centerline proves wrong for LMU's Barcelona layout:

1. Revert `data/track-outlines/circuit-de-barcelona.json` to the previous TUMFTM-based version (if still available in git history).
2. Try OSM Overpass extraction for the exact layout LMU uses.
3. If no data source matches, remove the Barcelona outline and let the app render trajectory-only (graceful fallback — the app already handles missing outlines).
