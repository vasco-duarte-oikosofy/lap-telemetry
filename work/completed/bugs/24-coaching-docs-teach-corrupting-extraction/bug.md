# Bug 24 — Coaching-model docs still teach the lap-extraction patterns that bugs 22/23 fixed

## Symptom

After the bug 22/23 fixes landed (guarded reference export, guarded
coaching-model updater), the instruction documents were audited. Two of them
actively instruct the reader to use the exact patterns those bugs removed:

### `docs/HOW_TO_CREATE_A_COACHING_MODEL.md` (the end-to-end procedure)

- **Step 1** "quick scan" snippet aggregates lap times per lap *number*
  (`laps[ln] = (lt, lv)`). On a session recorded across a sim restart, lap
  numbers repeat and this collapses two different laps into one entry —
  the bug 23 repro shows this picking lap 26 @ 106.155 s as "fastest" when
  the real fastest is lap 5 @ 105.828 s.
- **Step 2** recommends an "inline one-liner":
  `t.filter(pc.equal(t.column('lap_number'), <lap-number>))` — the literal
  global-mask extraction that merged 5 405 rows of another stint into the
  Monza reference (bugs 19/22/23). Its verification snippet uses
  `max(lap_time_s)`, the bug 10/13 undercount.
- **Step 3** instructs manual `Remove-Item` + `Copy-Item` into
  `product/data/reference-laps/` — bypassing the single-combo scope guard,
  the faster-only replacement, the abandoned-lap/coverage checks, and the
  mandatory single-change audit (bug 22's cardinal rule).
- **Step 7**'s comparison-lap extraction uses the same lap-number mask.
- It documents **no update path**: the only model command shown is
  `generate_track_coaching_model_from_reference.py`, which overwrites.
  Following the doc to "update" a curated track destroys hand-tuned corner
  names, manual apex sides, and extra turns. The guarded updater
  (`update_reference_and_coaching_model.py`, bug 23) is mentioned nowhere,
  and neither is the curated-model protection rule (abort when corners do
  not reproduce; Bahrain Outer precedent).

### `dev/scripts/GENERATE_TRACK_COACHING_MODEL.md`

- States: *"If a model already exists for the track+car, replacing it is
  safe — the script overwrites."* True only for a never-curated model; for a
  curated one this is exactly the unsafe operation the protection rule
  forbids.

### `dev/scripts/EXTRACT_AND_STORE_REFERENCE_LAP.md`, `dev/tools/README-REFERENCE-LAPS.md`

- Correct on the reference-lap side (bug 22 rules present) but stop at the
  reference: neither says that a track with an existing coaching model must
  have it refreshed via the guarded updater after a reference change.

## Root cause

The docs were written against the pre-bug-22 pipeline and were never part of
the definition-of-done for the script fixes. Bug 22 updated the two
reference-lap docs but did not audit the coaching-model docs, which embed
their own copies of the extraction logic as inline snippets — documentation
duplicating code logic rots exactly like duplicated code (bug 23 was the
same failure inside a script).

## What was changed (the fixes the docs must reflect)

- **Bug 22** (`export_fastest_reference_laps.py`): single (track, vehicle)
  scope per run, segment-slice extraction, authoritative timing, wall-clock
  and lap-distance-coverage guards (abandoned-lap rejection), faster-only
  replacement with supersede-delete, mandatory single-change audit;
  `validate_reference_laps.py` for post-export folder validation.
- **Bug 23** (`update_reference_and_coaching_model.py`): legacy extraction
  removed; export delegated to the bug 22 script; corner dry-check runs
  before any write and aborts if curated corners do not reproduce
  (`--allow-unmatched` to override, `--ref` to refresh from an existing
  reference).

## Why we are changing the docs

The documents are the operating manual for a destructive area
(`product/data/` is curated, committed data). As written they re-introduce
the corruption by hand even though the scripts are fixed: anyone following
HOW_TO step 2 on a restarted session writes a multi-stint reference lap, and
anyone following step 4 on a curated track erases its hand-tuned model. The
docs must describe the guarded pipeline as the only path, show worked
examples for each step, and present manual extraction only as a clearly
labelled fallback.

## Fix

1. `docs/HOW_TO_CREATE_A_COACHING_MODEL.md`: rewrite the pipeline steps
   around the summary tool + guarded export + validation + generation
   (new tracks) and add an "Updating an existing track" section documenting
   the guarded updater, the corner-reproduction abort, `--allow-unmatched`,
   and `--ref`, with worked examples (Paul Ricard update, Bahrain Outer
   abort). Remove the inline mask/groupby snippets.
2. `dev/scripts/GENERATE_TRACK_COACHING_MODEL.md`: scope the generator to
   tracks without a curated model; route updates to the updater.
3. `dev/scripts/EXTRACT_AND_STORE_REFERENCE_LAP.md` and
   `dev/tools/README-REFERENCE-LAPS.md`: add the follow-up step — if the
   track has a coaching model, refresh it with the updater.
