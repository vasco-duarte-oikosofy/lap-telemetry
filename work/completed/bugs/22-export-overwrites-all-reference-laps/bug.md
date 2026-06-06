# Bug 22 — Reference-lap export rewrites ALL tracks and corrupts laps from restarted sessions

## Symptom

Running `dev/scripts/export_fastest_reference_laps.py` to export a reference
lap for one new session (Interlagos, 2026-06-06) rewrote the **entire**
`product/data/reference-laps/` folder. Two runs (2026-06-06 10:27 and 12:05)
left the curated set in this state:

- `autodromo-nazionale-monza_..._time_01.45.828.parquet` (committed, curated)
  **overwritten in place**: 5 290 rows → 10 695 rows (two different laps
  merged into one file).
- 11 new untracked files appeared, several of them garbage:
  - `circuit-de-barcelona_..._time_01.12.768.parquet` — a physically
    impossible lap time at Barcelona (real refs are 1:36s); 10 952 rows
    (~2.3 laps of frames).
  - duplicate near-misses next to curated refs (`bahrain-outer` 01.10.649
    *and* 01.10.814 next to curated 01.10.845; two new `paul-ricard---3a`
    files; a second Monza file at 01.46.041).
  - `algarve-international-circuit_vista-af-corse-2025-21-lm_...` — exported
    from a Ferrari (AF Corse) session, not the DKR Engineering #4 LMP3 the
    curated set is built around. The script picks the global fastest lap per
    track regardless of vehicle.

## Root cause

Three compounding design flaws in `export_fastest_reference_laps.py`:

### 1. Unscoped full re-export on every run

`main()` globs `session_*.parquet` across **all** of `dev/sessions/` and
`sessions/` and writes one reference file per track slug, every run. There is
no way to target a single session, and no protection for existing (curated,
committed) reference files. Any change in how lap times are computed — e.g.
the uncommitted switch to `authoritative_duration` — shifts the formatted
time by a few ms, which changes the output **filename**, so old refs are not
replaced but duplicated; when the time happens to match (Monza 01.45.828),
the curated file is silently **overwritten in place**.

### 2. Lap extraction by global `lap_number` mask (bug-19 pattern)

```python
mask = pc.equal(best_table.column("lap_number"), best_lap_num)
lap_table = best_table.filter(mask)
```

Sessions recorded **before** the bug-19 recorder fix (session_time_s
regression detection, commit window ≤ 2026-06) contain multiple stints in
one file with repeating lap numbers. The mask selects every stint's rows for
that lap number:

- `sessions/session_20260520T180234Z_autodromo-nazionale-monza_lmu.parquet`
  has 3 stints; `lap_number == 5` exists in stint 2 (5 290 rows, 1:45.828 —
  the curated lap) **and** stint 3 (5 405 rows). The export wrote
  5 290 + 5 405 = 10 695 rows into the 01.45.828 file: a "reference lap"
  whose distance trace rewinds to 0 halfway through.

This is exactly the corruption documented in bug 19 for
`SessionWriter._write_lap_snapshot`, reproduced independently in this script.

Note: `find_complete_laps` itself is segment-aware (it uses
`build_segments`), so the *time* it reports is for one segment — but the
*write* path then exports a different set of rows than the lap it timed.
The bogus Barcelona 1:12.768 entry comes from a restart-truncated segment
whose row count passed the 95 %-of-median filter in a session where the
median itself was skewed; its file too contains multiple merged segments.

### 3. No vehicle grouping

The fastest lap per **track** wins regardless of car. All Algarve sessions
were driven in AF Corse Ferraris, so the export emitted a `vista-af-corse`
reference into a folder otherwise curated for `dkr-engineering-4-elms25`.
Mixed-car session folders will silently cross-pollinate references.

## Impact

- Curated, committed reference laps silently corrupted (Monza) or shadowed
  by duplicates with slightly different times — the comparison app and
  coaching models load garbage multi-lap "references".
- Impossible lap times exported as references (Barcelona 1:12.768).

## Fix

`dev/scripts/export_fastest_reference_laps.py`:

1. Require an explicit single-combo scope: positional session file/dir args
   that must all resolve to ONE (track, vehicle) combo — the run aborts
   before writing otherwise. There is no bulk mode; a mandatory post-export
   audit verifies on disk that at most one reference changed and hard-fails
   the run if not.
2. Extract the lap by **segment slice** (`table.slice(start, len)`), not by
   `lap_number ==` mask, so restarted sessions can never merge stints.
3. Group candidates by `(track, vehicle)` instead of track only.
4. Sanity-check the chosen lap: segment wall-clock span (`session_time_s`
   max − min) must agree with the claimed lap time within tolerance;
   reject otherwise.
5. Only write when strictly faster than the existing reference for the same
   `(track, vehicle)`; delete the superseded file when replacing, skip (with
   a message) when not faster. Never overwrite a same-named file silently.

## Recovery

- `git restore product/data/reference-laps/autodromo-nazionale-monza_..._01.45.828.parquet`
- Delete the 11 untracked parquets written on 2026-06-06.
- Re-export the Interlagos session with the fixed script.
