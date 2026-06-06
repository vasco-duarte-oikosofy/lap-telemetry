# Bug 23 — update_reference_and_coaching_model.py still extracts laps with the bug-22 pattern

## Symptom

`dev/scripts/update_reference_and_coaching_model.py` (the "update ref + model,
preserve corner names" helper used for the Fuji race update) duplicates the
lap-extraction logic that bug 22 fixed in `export_fastest_reference_laps.py` —
in its original, broken form. Running it against any session recorded across a
sim restart writes a corrupted reference lap and unconditionally deletes the
existing curated one.

`repro.py` demonstrates both failure modes against
`sessions/session_20260520T180234Z_autodromo-nazionale-monza_lmu.parquet`
(3 stints, repeated lap numbers — the same session that corrupted the Monza
reference in bug 22).

## Root cause

Three flaws, all in the extraction half of the script (the corner-merge half
is sound and was reused safely for the Paul Ricard 3A update):

1. **Global `lap_number ==` mask extraction** (step 3 of `main()`):
   `table.filter(pc.equal(table.column("lap_number"), best_lap_num))` selects
   every stint's rows for that lap number. On the Monza restart session,
   "lap 5" yields 10 695 rows (5 290 + 5 405 from two different laps) instead
   of the real 5 290-row lap — the exact corruption documented in bugs 19/22.

2. **Legacy timing via groupby-lap-number** (`find_fastest_lap`): takes
   `max(lap_time_s)` per lap *number*, not per segment. This undercounts
   (bug 10/13: mLapStartET resets before the last frames are written) and in
   multi-stint sessions collapses two different laps into one entry, hiding
   the faster stint — the documented pitfall in
   `EXTRACT_AND_STORE_REFERENCE_LAP.md`.

3. **No guards, destructive by default**: the old reference for the
   (track, vehicle) is deleted and the new file written with no
   faster-than-existing check, no wall-clock-span check, no lap-distance
   coverage check (abandoned laps pass — the Algarve 1:32.171 case), and no
   post-run single-change audit. It also refreshes the curated coaching model
   even when corners fail to reproduce on the new lap, silently keeping stale
   geometry — the situation the user has ruled must abort (Bahrain Outer
   precedent: curated models must never lose hand-tuned content).

## Fix

Remove the duplicated extraction entirely and make the script a thin,
guarded wrapper:

1. Candidate lap discovery uses `find_complete_laps` imported from
   `export_fastest_reference_laps.py` (segment slice + authoritative duration
   + wall-clock and lap-distance-coverage guards).
2. **All checks run before any write.** The corner dry-check (nearest-apex,
   ≤150 m) runs against the lap that will back the model; if any curated
   corner has no match, the script aborts with a report and changes nothing.
   `--allow-unmatched` opts into the old keep-stale-geometry behaviour.
3. The reference export itself is delegated to
   `export_fastest_reference_laps.py` as a subprocess, inheriting the
   single-combo scope guard, faster-only replacement, supersede-delete, and
   the mandatory single-change audit.
4. If the session has no lap faster than the existing reference, no export
   happens; the model is refreshed only if it is out of sync with the current
   reference, otherwise the script reports up-to-date and exits.
5. `--ref` mode skips discovery/export and refreshes the model from an
   explicit existing reference parquet (the manual split used for the
   Paul Ricard 3A update).

## Verification

- `repro.py` shows the legacy logic selecting a 10 695-row merged "lap" and
  the fixed path selecting the real 5 290-row segment.
- Fixed script run against the Paul Ricard session reports the reference and
  model are already up to date (no writes, audit 0).
- Fixed script run against the Bahrain Outer session with the faster
  1:10.814 lap **aborts before writing anything** because turns 6 and 8 of
  the curated model do not reproduce — encoding the Bahrain Outer rule.
