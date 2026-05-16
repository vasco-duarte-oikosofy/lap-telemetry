# Handoff — xx Manual Outline Generation (Automation Script)

## State on disk

### New file
- `scripts/register_outline.py` — Single-command script that:
  1. Validates the outline JSON (schema, required fields, centerline structure)
  2. Generates the ES module via `node scripts/generate_outline_module.js`
  3. Creates a backup of `web/js/trackOutlineManifest.js`
  4. Adds import statement and OUTLINES map entries to the manifest
  5. Rebuilds `dist/compare.html` via `npm run build`
  6. Validates the manifest after modification (checks exports still present)
  7. Rolls back from backup if build or validation fails

### Modified file
- `tools/README-GENERATE-OUTLINE.md` — Updated to replace manual "Regenerate ES module" + "Register in Manifest" sections with single `python3 scripts/register_outline.py` command

### No changes to
- `web/js/trackOutlineManifest.js` — Not modified (restored to original after testing)
- `web/js/static*OutlineData.js` — Not modified
- Any test files or source code

## Usage

```bash
# Register a new track outline (all-in-one)
python3 scripts/register_outline.py data/track-outlines/bahrain_outline.json

# Already-registered outlines are idempotent no-ops
python3 scripts/register_outline.py data/track-outlines/bahrain_outline.json
# → ℹ️  Outline already registered in manifest
# → ℹ️  ES module up-to-date
# → ℹ️  No changes needed
```

## Output example (new track)

```
📋 Validating circuit-de-barcelona.json...
✅ Outline JSON is valid

📦 Generating ES module for 'Circuit de Barcelona-Catalunya'...
✅ Generated ES module: web/js/staticCircuitBarcelonaOutlineData.js
   Export name: CIRCUIT_BARCELONA_STATIC_OUTLINE

📝 Updating manifest...
✅ Backed up manifest to trackOutlineManifest_backup.js
✅ Added import to manifest
✅ Added 2 entries to OUTLINES map:
   - circuit-de-barcelona
   - circuit-de-barcelona-catalunya

🔍 Validating updated manifest...
✅ Manifest validation passed

🔨 Rebuilding dist/compare.html...
✅ Rebuilt dist/compare.html

============================================================
✅ Generated ES module: web/js/staticCircuitBarcelonaOutlineData.js
✅ Updated manifest: web/js/trackOutlineManifest.js
✅ Added 2 entries to OUTLINES map
✅ Rebuilt dist/compare.html
============================================================
```

## Validation

The script validates:
- `schema_version` (must be int)
- `track_name`, `sim_track_name`, `coordinate_system`, `units` (must be strings)
- `track_name_mapping.canonical_sim_track_name` (must be string)
- `track_name_mapping.accepted_sim_track_names` (must be list of strings, no duplicates)
- `centerline` (must be list of {x, y} objects, at least 2 points)
- Optional fields: `layout_name`, `alignment`, `visual_qa`, `caveats`

## Track name keys registered in OUTLINES map

Sources (in priority order, deduplicated):
1. `track_name_mapping.canonical_sim_track_name`
2. `track_name_mapping.accepted_sim_track_names`
3. Slugified `track_name_mapping.canonical_lmu_track_name` (if present)
4. Slugified `track_name_mapping.accepted_lmu_track_names` (if present)

## Feature flags on disk

No changes to feature flags.

## Deferred

- No test file for `register_outline.py` yet (could be added as a shell script that validates the exit codes and output messages)
- No support for removing/unregistering a track outline