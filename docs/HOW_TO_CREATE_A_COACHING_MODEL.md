# How to Create a Track Coaching Model

End-to-end procedure from raw session files to a named, verified coaching model ready for use by the live coach and `generate_utterance`.

For finer detail on individual steps, see also:
- [`dev/scripts/EXTRACT_AND_STORE_REFERENCE_LAP.md`](../dev/scripts/EXTRACT_AND_STORE_REFERENCE_LAP.md) — multi-shard / multi-stint pitfalls
- [`dev/scripts/GENERATE_TRACK_COACHING_MODEL.md`](../dev/scripts/GENERATE_TRACK_COACHING_MODEL.md) — detection algorithm details and tuning flags

---

## Overview

A coaching model is a JSON file under `product/data/track-coaching/` that describes every corner of a circuit (apex distance, entry/exit zones, name). It is built from a **reference lap** — the fastest known clean lap for that track+car combination, stored under `product/data/reference-laps/`.

The full workflow is:

```
sessions/*.parquet
  → find fastest valid lap
  → extract single-lap parquet
  → store as reference lap
  → run corner detection
  → review diagnostics
  → rename corners in JSON
  → verify with --print-facts
```

---

## Step 1 — Find the fastest lap

Scan every session file for the target circuit. The fastest lap may be in any session, not necessarily the most recent one.

```powershell
# Scan a single session
python dev/scripts/explore_and_export_laps.py sessions/<session-file>.parquet

# Quick scan across all sessions for a circuit (replace track slug)
python -c "
import pyarrow.parquet as pq, pyarrow.compute as pc, pathlib

track = 'paul-ricard---3a'
target_s = None  # set to a float to filter near a known time
found = []

for s in sorted(pathlib.Path('sessions').glob(f'*{track}*lmu.parquet')):
    t = pq.read_table(s, columns=['lap_number', 'lap_time_s', 'lap_valid'])
    laps = {}
    for row in t.to_pylist():
        ln, lt, lv = row['lap_number'], row['lap_time_s'], row['lap_valid']
        if lt:
            laps[ln] = (lt, lv)
    for ln, (lt, lv) in sorted(laps.items()):
        if lv:
            found.append((s.name, ln, lt))

for fname, ln, lt in sorted(found, key=lambda x: x[2])[:10]:
    m, s2 = divmod(lt, 60)
    print(f'{int(m)}:{s2:06.3f}  lap={ln}  {fname}')
"
```

Pick the **fastest valid lap** (confirmed `lap_valid=True`, realistic time for the circuit).

> **Multi-stint sessions**: if the same `lap_number` appears in two stints, use `extract_reference_lap.py --segment 1` to list segments and pick the fastest segment manually. See `EXTRACT_AND_STORE_REFERENCE_LAP.md`.

---

## Step 2 — Extract the lap

Extract the chosen lap to a single-lap parquet using `extract_reference_lap.py`, or use the inline one-liner if you just need to filter by lap number quickly:

```powershell
# Via the extraction script (preferred — handles multi-stint automatically)
python dev/scripts/extract_reference_lap.py sessions/<session-file>.parquet `
    --lap <lap-number> `
    --out sessions/tmp_ref_lap.parquet

# Or inline (simple single-stint sessions)
python -c "
import pyarrow.parquet as pq, pyarrow.compute as pc, pathlib
t = pq.read_table('sessions/<session-file>.parquet')
lap = t.filter(pc.equal(t.column('lap_number'), <lap-number>))
pq.write_table(lap, pathlib.Path('sessions/tmp_ref_lap.parquet'))
print(f'Extracted {len(lap)} rows')
"
```

Verify the lap time:

```powershell
python -c "
import pyarrow.parquet as pq
t = pq.read_table('sessions/tmp_ref_lap.parquet')
lt = max(t.column('lap_time_s').to_pylist())
m, s = divmod(lt, 60)
print(f'{int(m)}:{s:06.3f}')
"
```

---

## Step 3 — Store the reference lap

**Naming convention:**
```
product/data/reference-laps/<track-slug>_<car-id>_time_<MM>.<SS>.<mmm>.parquet
```

Examples:
- `paul-ricard---3a_dkr-engineering-4-elms25_time_01.18.596.parquet`
- `lusail-international-circuit_dkr-engineering-4-elms25_time_01.52.200.parquet`

Steps:
1. Delete the old reference lap file for this track+car (there must be at most one).
2. Copy the extracted lap to the new path.
3. Delete the temp file.

```powershell
# Delete old
Remove-Item "product/data/reference-laps/<track-slug>_<car-id>_time_<old-time>.parquet"

# Store new
Copy-Item sessions/tmp_ref_lap.parquet `
    "product/data/reference-laps/<track-slug>_<car-id>_time_<new-time>.parquet"

# Clean up
Remove-Item sessions/tmp_ref_lap.parquet
```

---

## Step 4 — Generate the coaching model

```powershell
python dev/scripts/generate_track_coaching_model_from_reference.py `
  --reference-lap "product/data/reference-laps/<track-slug>_<car-id>_time_<MM>.<SS>.<mmm>.parquet" `
  --track-id "<track-slug>" `
  --layout-id "<layout-id>" `
  --out "product/data/track-coaching/<track-slug>_<car-id>.json" `
  --diagnostics-out "product/data/track-coaching/<track-slug>_<car-id>.diagnostics.txt"
```

Paul Ricard 3A example:
```powershell
python dev/scripts/generate_track_coaching_model_from_reference.py --reference-lap "product/data/reference-laps/paul-ricard---3a_dkr-engineering-4-elms25_time_01.18.596.parquet" --track-id "paul-ricard---3a" --layout-id "3a" --out "product/data/track-coaching/paul-ricard---3a_dkr-engineering-4-elms25.json" --diagnostics-out "product/data/track-coaching/paul-ricard---3a_dkr-engineering-4-elms25.diagnostics.txt"
```

The script prints the number of detected corners and writes both files.

---

## Step 5 — Review the diagnostics

Open `product/data/track-coaching/<track-slug>_<car-id>.diagnostics.txt`. Each line is one detected corner:

```
t1 apex=517m start=511m end=527m min=59.7kph entry=61.9kph exit=65.1kph drop=90.5kph ...
```

Check:
- **Corner count** matches your knowledge of the circuit.
- **Apex distances** are plausible (cross-reference a lap map or GPS trace).
- **Min speeds** are realistic for each corner type (hairpin vs high-speed kink).
- **Fast chicanes** — brief throttle lifts may split one complex into two entries (merge them manually in the JSON).
- **Flat/high-speed corners** — very small speed drops (< 5 kph) may not be detected even if a real corner exists there. Add them manually in Step 6.

---

## Step 6 — Rename corners and fix zones

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

---

## Step 7 — Verify with --print-facts

Run a quick sanity check by comparing a known lap against the new reference using `--print-facts`. This confirms the model produces plausible losses/gains:

```powershell
# Extract a lap to compare (not the reference lap itself)
python -c "
import pyarrow.parquet as pq, pyarrow.compute as pc, pathlib
t = pq.read_table('sessions/<session-file>.parquet')
pq.write_table(t.filter(pc.equal(t.column('lap_number'), <lap-number>)), pathlib.Path('sessions/tmp_check.parquet'))
"

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

## File summary

| File | Description |
|------|-------------|
| `product/data/reference-laps/<track>_<car>_time_<MM>.<SS>.<mmm>.parquet` | Single-lap reference parquet |
| `product/data/track-coaching/<track>_<car>.json` | Corner model (names, zones, apex distances) |
| `product/data/track-coaching/<track>_<car>.diagnostics.txt` | Auto-detection log (one line per corner) |

---

## Commit message convention

```
feat(coaching): add Paul Ricard 3A coaching model (DKR LMP3, ref 1:18.596)
```

Or for a reference-lap update:

```
ref(paul-ricard-3a): update reference lap 1:19.010 → 1:18.596
```
