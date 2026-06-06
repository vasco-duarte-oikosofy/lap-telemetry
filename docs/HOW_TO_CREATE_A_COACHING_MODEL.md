# How to Create (or Update) a Track Coaching Model

End-to-end procedure from raw session files to a named, verified coaching model ready for use by the live coach and `generate_utterance`.

For finer detail on individual steps, see also:
- [`dev/tools/README-REFERENCE-LAPS.md`](../dev/tools/README-REFERENCE-LAPS.md) — the reference-lap export script and its guards
- [`dev/scripts/EXTRACT_AND_STORE_REFERENCE_LAP.md`](../dev/scripts/EXTRACT_AND_STORE_REFERENCE_LAP.md) — naming convention, pitfalls, manual fallback
- [`dev/scripts/GENERATE_TRACK_COACHING_MODEL.md`](../dev/scripts/GENERATE_TRACK_COACHING_MODEL.md) — detection algorithm details and tuning flags

---

## Overview

A coaching model is a JSON file under `product/data/track-coaching/` that describes every corner of a circuit (apex distance, entry/exit zones, name). It is built from a **reference lap** — the fastest known clean lap for that track+car combination, stored under `product/data/reference-laps/`.

There are two pipelines. Pick the right one first:

| Situation | Pipeline |
|-----------|----------|
| Track+car has **no** coaching model yet | **A — New track** (steps 1–7 below) |
| Track+car **already has** a coaching model | **B — Update** (guarded updater; see "Pipeline B") |

### ⚠️ Cardinal rules (bugs 22, 23, 24)

1. **One (track, vehicle) per run.** We never export all reference laps at once. The export script refuses multi-combo targets and audits that at most one reference changed on disk.
2. **Never extract a lap by filtering on `lap_number`.** Sessions recorded across a sim restart repeat lap numbers; a `lap_number == N` filter merges two different laps into one file (this corrupted the Monza reference — bug 22). All lap selection is per contiguous *segment*; the scripts below do this for you.
3. **Curated models never lose hand-tuned content.** Re-running the generator on a track that already has a model **overwrites** corner names, manual apex sides, and manually added turns. Updates go through `update_reference_and_coaching_model.py`, which preserves them and aborts if corners don't reproduce.
4. **Never hand-copy files into `product/data/reference-laps/`.** The export script enforces naming, supersedes the old file, and runs the audit.

---

## Pipeline A — New track+car (no model exists yet)

### Step 1 — Find the fastest lap with the summary tool

Scan every session file for the target circuit. The fastest lap may be in any session, not necessarily the most recent one.

```powershell
# One session, lap by lap
lap-telemetry summary sessions/session_20260528T153431Z_circuit-de-la-sarthe_lmu.parquet

# All sessions of a circuit
Get-ChildItem sessions/session_*circuit-de-la-sarthe*.parquet | ForEach-Object {
    Write-Host "=== $($_.Name)"; lap-telemetry summary $_.FullName
}
```

Example output (La Sarthe, 2026-05-28):

```
 lap   frames     duration         s1         s2         s3   valid
-------------------------------------------------------------------
   2    11761     3:55.457          -          -          -     yes
   3    11729     3:54.917          -          -          -     yes
   6    11867     3:57.603     36.295     92.246    109.062     yes
```

Pick the fastest **valid** lap and sanity-check it: frames ≈ duration × 50 Hz (here 11 729 ≈ 234.9 s × 50 ✓), and the time is realistic for the circuit. Impossibly fast laps with mismatched frame counts are abandoned/cut laps — the export script in step 2 rejects them automatically, but don't be surprised when a "fast" summary line disappears there.

### Step 2 — Export the reference lap (guarded)

Pass the session file(s) — all of the **same** track and car — to the export script. It finds complete laps per segment, applies the authoritative-duration, wall-clock, and lap-coverage guards, writes one file, and audits the folder:

```powershell
python dev/scripts/export_fastest_reference_laps.py `
    sessions/session_*circuit-de-la-sarthe*.parquet
```

```
Track: circuit-de-la-sarthe  Vehicle: dkr-engineering-4-elms25  (10 sessions)
  Fastest: lap 3 in session_20260528T153431Z_circuit-de-la-sarthe_lmu.parquet -> 234.917s
  Exported 11729 rows -> product\data\reference-laps\circuit-de-la-sarthe_dkr-engineering-4-elms25_time_03.54.917.parquet

AUDIT: 1 reference lap changed (added: [...], superseded: []). OK.
```

A run is only valid if it ends with an `AUDIT:` line reporting 0 or 1 changed laps. The output file name follows the convention automatically:

```
product/data/reference-laps/<track-slug>_<car-id>_time_<MM>.<SS>.<mmm>.parquet
```

### Step 3 — Validate the reference-lap folder

```powershell
python dev/scripts/validate_reference_laps.py
```

```
OK    circuit-de-la-sarthe_dkr-engineering-4-elms25_time_03.54.917.parquet
      * source: session_20260528T153431Z_circuit-de-la-sarthe_lmu.parquet
...
15 reference laps checked, 0 failures.
```

Every reference must be a single contiguous lap whose duration matches its filename, traced to a source session on the same track in the same car. Fix any `FAIL` before continuing.

### Step 4 — Generate the coaching model

**Only for tracks without an existing model** (cardinal rule 3 — for updates, jump to Pipeline B).

```powershell
python dev/scripts/generate_track_coaching_model_from_reference.py `
  --reference-lap "product/data/reference-laps/circuit-de-la-sarthe_dkr-engineering-4-elms25_time_03.54.917.parquet" `
  --track-id "circuit-de-la-sarthe" `
  --layout-id "lmu-default" `
  --car-id "dkr-engineering-4-elms25" `
  --out "product/data/track-coaching/circuit-de-la-sarthe_dkr-engineering-4-elms25.json" `
  --diagnostics-out "product/data/track-coaching/circuit-de-la-sarthe_dkr-engineering-4-elms25.diagnostics.txt"
```

```
Detected 17 corners via throttle_brake_v1 for car dkr-engineering-4-elms25
```

### Step 5 — Review the diagnostics

Open `product/data/track-coaching/<track-slug>_<car-id>.diagnostics.txt`. Each line is one detected corner:

```
t9 apex=7722m start=7539m end=7758m min=80.6kph entry=84.0kph exit=93.3kph drop=94.8kph ...
```

Check:
- **Corner count** matches your knowledge of the circuit.
- **Apex distances** are plausible (cross-reference a lap map or GPS trace).
- **Min speeds** are realistic for each corner type (hairpin vs high-speed kink).
- **Fast chicanes** — brief throttle lifts may split one complex into two entries (merge them manually in the JSON).
- **Flat/high-speed corners** — very small speed drops (< 5 kph) may not be detected even if a real corner exists there. Add them manually in Step 6.

### Step 6 — Rename corners and fix zones

Auto-generated names are `"turn 1"`, `"turn 2"`, … Replace them with real corner names and fix any zone boundaries that the detector got wrong. Use a Python script to edit the JSON cleanly:

```python
import json, pathlib

path = pathlib.Path("product/data/track-coaching/<track-slug>_<car-id>.json")
m = json.loads(path.read_text(encoding="utf-8"))

def corner(id, name, start, apex, end, side="right"):
    return {
        "id": id, "name": name,
        "s_start_m": float(start), "apex_s_m": float(apex), "s_end_m": float(end),
        "apex_side": side, "apex_side_source": "manual",
    }

m["corners"] = [
    corner("t1",               "turn 1",               511,  517,  527),
    corner("signes",           "Signes",               1736, 1855, 1876),
    corner("beausset_1",       "Beausset 1",           2124, 2243, 2243),
    corner("beausset_2",       "Beausset 2",           2288, 2435, 2440),
    corner("lepingle_de_bendor", "L'Epingle de Bendor", 2638, 2768, 2793),
    # Flat corner the detector missed — added manually:
    corner("s_du_village",     "S du Village",         2900, 2983, 3120),
    corner("virage_de_la_tour","Virage de la Tour",    3120, 3350, 3374),
    corner("virage_du_pont",   "Virage du Pont",       3369, 3425, 3453),
]

path.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
```

**Common adjustments:**

| Situation | Fix |
|-----------|-----|
| Two auto-entries for one complex | Merge: use outer `s_start_m` / `s_end_m`, pick the apex with the larger speed drop |
| Detector split a chicane | Merge the two entries |
| Flat corner not detected | Add manually with the correct zone and apex |
| Entry zone starts too late | Set `s_start_m` to where the driver's braking actually begins |
| `apex_side` unknown | Leave as `"right"` and mark for review |

Hand-tuned content added here is what Pipeline B protects: once a model is curated, the updater refuses to refresh it unless every curated corner reproduces on the new lap.

### Step 7 — Verify with --print-facts

Run a quick sanity check by comparing a known lap against the new reference. Extract the comparison lap with `extract_reference_lap.py` (segment-aware — never filter by `lap_number` yourself, cardinal rule 2):

```powershell
python dev/scripts/extract_reference_lap.py sessions/<session-file>.parquet `
    --lap <lap-number> --out sessions/tmp_check.parquet

python -m lap_telemetry.coach.generate_utterance --lap `
  --current-lap sessions/tmp_check.parquet `
  --reference-lap "product/data/reference-laps/<track-slug>_<car-id>_time_<MM>.<SS>.<mmm>.parquet" `
  --track-config "product/data/track-coaching/<track-slug>_<car-id>.json" `
  --print-facts

Remove-Item sessions/tmp_check.parquet
```

Check that:
- Corner IDs in `top_losses` / `top_gains` match real corner names.
- `lap_time_delta_s` is in the right ballpark for the lap you chose.
- No crash or `KeyError` — all corner IDs resolved correctly.

---

## Pipeline B — Updating an existing track (new fastest lap)

When a session contains a lap faster than the current reference for a track that **already has** a coaching model, use the guarded updater. It finds the fastest lap (same segment-based guards as the export script), dry-checks the curated corners against that lap **before writing anything**, delegates the reference export to `export_fastest_reference_laps.py` (inheriting its audit), and refreshes the model's corner geometry while preserving names, IDs, and manual apex sides:

```powershell
python dev/scripts/update_reference_and_coaching_model.py `
    --session sessions/session_20260529T180345Z_paul-ricard---3a_lmu.parquet `
    --track-id paul-ricard---3a
```

Successful update (Paul Ricard, 1:17.661 → 1:17.166):

```
Fastest lap in session(s): lap 6 @ 77.166s (... vehicle dkr-engineering-4-elms25)
Faster than existing reference - will export after corner check
Corner check: model has 9, lap yields 8 (8 matched)
...
Updated coaching model -> product\data\track-coaching\paul-ricard---3a_dkr-engineering-4-elms25.json
Corner geometry changes:
  Signes        1732.0  1865.0  1868.0  (was 1738.0 / 1829.0 / 1830.0)
  ...
```

### The corner-reproduction guard

If any curated corner has no matching braking event on the new lap (within 150 m of its apex), the updater **aborts with exit code 2 and changes nothing** — including the reference, which is deliberately checked first so the ref and model can never go out of sync:

```
Fastest lap in session(s): lap 22 @ 70.814s (... bahrain-outer-circuit ...)
Faster than existing reference - will export after corner check
Corner check: model has 6, lap yields 4 (4 matched)

ABORTED - curated corners not reproduced on this lap: turn 6, turn 8
No files were changed.
```

This happens on faster laps: lighter braking merges chicane corners or drops light-braking turns entirely (Bahrain Outer precedent — its 1:10.845 reference is intentionally kept over a real 1:10.814 lap for exactly this reason). Your options:

- **Leave the track as is** (default, and correct when the model encodes detail the new lap can't reproduce).
- `--allow-unmatched` — proceed; unmatched corners keep their old geometry (logged with a warning).

### Refreshing a model from an existing reference

If the reference is already correct and only the model needs re-syncing, skip discovery/export with `--ref`:

```powershell
python dev/scripts/update_reference_and_coaching_model.py `
    --ref product/data/reference-laps/paul-ricard---3a_dkr-engineering-4-elms25_time_01.17.166.parquet `
    --track-id paul-ricard---3a --allow-unmatched
```

The updater is idempotent: re-running it when nothing changed prints `Coaching model already up to date - nothing written.`

After any update, re-run `python dev/scripts/validate_reference_laps.py` (step 3) before committing.

---

## File summary

| File | Description |
|------|-------------|
| `product/data/reference-laps/<track>_<car>_time_<MM>.<SS>.<mmm>.parquet` | Single-lap reference parquet |
| `product/data/track-coaching/<track>_<car>.json` | Corner model (names, zones, apex distances) |
| `product/data/track-coaching/<track>_<car>.diagnostics.txt` | Auto-detection log (one line per corner) |

---

## Commit message convention

One track per commit (cardinal rule 1 means runs are per-track anyway):

```
feat(coaching): La Sarthe reference lap 03.54.917 + coaching model
```

Or for an update of an existing track:

```
ref: update Paul Ricard 3A reference lap 01.17.661 -> 01.17.166 + coaching model geometry
```
