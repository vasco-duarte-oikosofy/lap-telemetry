# Handoff: Automate Outline Registration Script

**Phase:** xx_manual_outline_generation (automation)
**Priority:** High — prevents real deployment errors
**Created:** 2026-05-15

---

## Problem Statement

After generating a track outline, there are **two manual steps** required to make it visible in `dist/compare.html`:

1. **Regenerate ES module** — `node scripts/generate_outline_module.js <outline.json>`
2. **Register in manifest** — Manually edit `web/js/trackOutlineManifest.js`

These steps are easy to forget, leading to issues like:
- Bahrain outline generated but not showing in compare.html
- ES module containing old averaged data after switching to single-lap
- Confusion about why outline "doesn't work"

---

## Goal

Create a script that automates both steps with a single command:

```bash
python3 scripts/register_outline.py data/track-outlines/bahrain_outline.json
```
NOTE: for this task we will use Python as the scripting language

---

## Script Requirements

### Input
- Path to outline JSON file (e.g., `data/track-outlines/bahrain_outline.json`)


### Step 0: Validate the input file 
- check that the outline file as the expected format
- it names a track, and contains the other necessary components of this json file
- use the file ./data/track-outlines/bahrain_outline.json as an example to build the validator on
- do not repeat values from the file, only use it to assess the fields that need to be present in a valid track outline file
- if the validation step fail, output a clear, and detailed error message: e.g. what is missing, duplicates where none allowed, missing parts of a data structure, etc. 

### Step 1: Generate ES Module
- Run `node scripts/generate_outline_module.js <input>`
- This creates `web/js/static<TrackName>OutlineData.js`
- Capture the exported constant name (e.g., `BAHRAIN_INTERNATIONAL_CIRCUIT_STATIC_OUTLINE`)
- The constant name should be build from the input file's circuit name with CIRCUIT_STATIC_OUTLINE added as suffix

### Step 2: Update Manifest
- Read `web/js/trackOutlineManifest.js`
- Create a backup of this file `web/js/trackOutlineManifest_backup.js`
- Extract track metadata from the generated outline JSON, for example:
  - `track_name` → "Bahrain International Circuit"
  - `track_name_mapping.canonical_sim_track_name` → "bahrain-international-circuit"
  - `track_name_mapping.accepted_sim_track_names` → ["bahrain-international-circuit", "bahrain"]
- Generate slugified module name: `BAHRAIN_INTERNATIONAL_CIRCUIT_STATIC_OUTLINE`
- Generate import statement if not present:
  ```javascript
  import { BAHRAIN_INTERNATIONAL_CIRCUIT_STATIC_OUTLINE } from './staticBahrain_outlineOutlineData.js';
  ```
- Generate OUTLINES map entries if not present:
  ```javascript
  ['bahrain-international-circuit', BAHRAIN_INTERNATIONAL_CIRCUIT_STATIC_OUTLINE],
  ['bahrain', BAHRAIN_INTERNATIONAL_CIRCUIT_STATIC_OUTLINE],
  ```
- Use AST parsing or careful regex to insert without breaking existing code
- Preserve existing formatting and comments
- After generating the updates Manifest, validate/link the resulting file

### Step 3: Rebuild Bundle
- Run `npm run build`
- Verify build succeeds

### Output
- Print summary of changes made:
  ```
  ✅ Generated ES module: web/js/staticBahrain_outlineOutlineData.js
  ✅ Added import to manifest
  ✅ Added 2 entries to OUTLINES map:
     - bahrain-international-circuit
     - bahrain
  ✅ Rebuilt dist/compare.html
  ```
- Exit 0 on success, non-zero on failure

---

## Edge Cases

### Already Registered (Idempotent)
If outline is already in manifest, detect and skip:
```
ℹ️  Outline already registered in manifest
ℹ️  ES module up-to-date
ℹ️  No changes needed
```

### Track Name with Special Characters
Slugify properly:
- "Circuit de Barcelona-Catalunya" → `CIRCUIT_DE_BARCELONA_CATALUNYA_STATIC_OUTLINE`
- "Autodromo Enzo e Dino Ferrari" → `AUTODROMO_ENZO_E_DINO_FERRARI_STATIC_OUTLINE`

### Multiple Naming Variants
Support all accepted names from outline:
```json
{
  "track_name_mapping": {
    "accepted_sim_track_names": ["bahrain-international-circuit", "bahrain"]
  }
}
```
→ Register both variants in OUTLINES map

---

## Testing Checklist

- [ ] Test with Bahrain outline (already registered — should be no-op)
- [ ] Test with new track (should add import + map entries)
- [ ] Verify `dist/compare.html` shows outline after running
- [ ] Test idempotency (run twice — second run should make no changes)
- [ ] Test with track name containing special characters
- [ ] Test with multiple accepted name variants

---

## Documentation Updates

After script is created, update `tools/README-GENERATE-OUTLINE.md`:

### Replace These Sections:
- "Regenerate the ES module"
- "Register in Manifest (Required for compare.html)"

### With Single Command:
```markdown
### Register Outline (Single Command)

```bash
python3 scripts/register_outline.py data/track-outlines/bahrain_outline.json
```

This command:
1. Generates the ES module (`web/js/static<Track>OutlineData.js`)
2. Adds import statement to `web/js/trackOutlineManifest.js`
3. Registers track in OUTLINES map (all accepted name variants)
4. Rebuilds `dist/compare.html`

**Result:** Outline is immediately visible in compare.html — no manual steps needed.
```

---

## Implementation Notes

### Language Choice
- **Python** — Consistent with `explore_and_export_laps.py` and `average_trajectory_outline.py`
- **Node.js** — Consistent with `generate_outline_module.js` and `bundle.js`

- Python is used for the script, JS is the language used in the files we are editing, JSON is the format of the input and output files for the track data

### AST vs Regex
For editing `trackOutlineManifest.js`:
- **Preferred:** Use AST parser (e.g., `ast` for Python)
- **Fallback:** Careful regex with multiple safety checks

The manifest file has a predictable structure, so regex is acceptable if:
- Import insertion happens before first `import` or after last `import`
- OUTLINES map insertion happens before closing `])`
- Check for existing entries before adding

### File to Create
`scripts/register_outline.py`  

---

## Context / Why This Matters

This automation prevents a real error that occurred on 2026-05-15:

1. Generated Bahrain outline from averaged laps → had jitter
2. Switched to single-lap approach → updated `data/track-outlines/bahrain_outline.json`
3. **Forgot to regenerate ES module** → `staticBahrain_outlineOutlineData.js` still had old averaged data
4. **Forgot to register in manifest** → outline didn't show in compare.html
5. Spent 30+ minutes debugging "why doesn't outline show?"

Automating these steps eliminates this entire class of errors.

---

## Acceptance Criteria

- [ ] Script exists at `scripts/register_outline.py` (or `.js`)
- [ ] Running script on new outline makes it visible in compare.html
- [ ] Running script twice is idempotent (no duplicate entries)
- [ ] README updated with single-command workflow
- [ ] All existing tests pass
- [ ] `npm run build` succeeds after script runs

---

## Related Files

- `tools/README-GENERATE-OUTLINE.md` — Update with new workflow
- `web/js/trackOutlineManifest.js` — Target file for registration
- `scripts/generate_outline_module.js` — Called by new script
- `scripts/bundle.js` — Called by new script (via `npm run build`)

---

## Start Command

```bash
# Begin implementation
touch scripts/register_outline.py
```
