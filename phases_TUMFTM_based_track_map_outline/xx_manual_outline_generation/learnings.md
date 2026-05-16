# Learnings — xx Manual Outline Generation (Automation Script)

## What surprised us

1. **generate_outline_module.js naming derived from filename, not track_name.** The script splits the JSON filename on hyphens (`-`) to derive the module name and export name. For example, `bahrain_outline.json` → `staticBahrain_outlineOutlineData.js` (underscore stays, hyphen splits). This means the "friendly" PascalCase export name (`BAHRAIN_OUTLINE_STATIC_OUTLINE`) comes from splitting `bahrain_outline` on `-`, giving just one part.

2. **Manifest already had manually-added aliases.** The existing `trackOutlineManifest.js` had entries like `['bahrain', ...]` and `['catalunya', ...]` that aren't in the outline JSON's `accepted_sim_track_names`. The script correctly adds all names from the JSON but doesn't generate ad-hoc aliases. Users can add those manually.

3. **The slugify function in the manifest hyphen-joins and strips non-alnum.** "Circuit de Barcelona-Catalunya" → `circuit-de-barcelona-catalunya`. Our Python `slugify()` matches the JS version exactly.

4. **Idempotency required careful tracking.** We needed to check both the import AND all map entries before declaring "no changes needed." Partial registration (import present but some entries missing) is a real scenario when the JSON gains new `accepted_sim_track_names`.

5. **The backup file (`trackOutlineManifest_backup.js`) is created before any modification** and used for rollback if the build step fails or manifest validation fails.

## What the next agent needs to know

- `scripts/register_outline.py` is the single entry point for registering a track outline
- It calls `node scripts/generate_outline_module.js` internally — you don't need to run that separately
- The script always generates the ES module (even if it already exists — it's idempotent overwrite)
- Track name keys in the OUTLINES map come from `accepted_sim_track_names` in the JSON, plus slugified LMU names
- Running the script on an already-registered outline is a safe no-op (detects and skips)