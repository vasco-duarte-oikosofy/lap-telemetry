---
name: update-coach
description: Turn "the session I just ran" (track + car in any order, plus when — just now, 1h ago, yesterday) into a guarded reference-lap and coaching-model update, but only when that session contains a lap faster than the reference already on disk. Use when the user says a session was faster, asks to update the reference lap or coaching model from a recent run, or names a recording by car/track/time. Handles both new combos (no reference yet) and curated tracks that already have a model.
---

# /update_coach — reference lap + coaching model, only when you went faster

Turns a loose description of a recording into a guarded update of
`product/data/reference-laps/` and `product/data/track-coaching/`.

**The rule that defines this skill: nothing is written unless the referenced
session contains a lap faster than the fastest lap currently on disk for that
(track, car) combo.** If it isn't faster, the answer is a report and no writes.

Run every command below from the repo root.

## What you are told

Anything in this shape, in any order:

- a **track** and/or a **car** (`Barcelona`, `Ginetta`, `DKR #4`, `ginetta-lmp3`)
- **when** — `just now`, `1h ago`, `yesterday`, `this morning`, or an explicit
  `sessions/session_*.parquet`
- nothing else. Never ask for a lap number, a session file path, or a time.

Translate "when" into an age window (`--within 30m`, `2h`, `1d`) — never do the
date arithmetic yourself, and never pass a bare timestamp guess.

## Step 1 — resolve the session and decide (never skip this)

```bash
python .agents/skills/update-coach/scripts/find_candidate_session.py \
    --track "<track or omit>" --car "<car or omit>" --within <window> --json
```

This is the gate. It discovers recordings (grouping `.partN` shards, ignoring
`.snapN` snapshots), matches track/car text either way round, applies the age
window, collapses everything to **one** (track, car) combo, finds the fastest
complete lap with the same segment guards the exporter uses, and compares it
with the reference on disk.

Read the `VERDICT` line and the exit code — the **exit code is the decision**,
not your reading of the times:

| Verdict | Exit | What it means | What you do |
|---|---|---|---|
| `FASTER` | 0 | Session lap beats the current reference by >1 ms | Continue to step 2 |
| `NO_REFERENCE` | 0 | No reference on disk for this combo | Continue to step 3 (pipeline A) |
| `NOT_FASTER` | 3 | Existing reference is at least as fast | Report and **stop**. No writes, no commits |
| `AMBIGUOUS` | 2 | Candidates span several combos | Ask the user which one. Do not guess |
| `NO_SESSION` | 2 | Nothing matches | Ask for a wider window, or confirm the track/car |
| `NO_LAPS` | 2 | No complete lap survived the guards | Report it. Out-laps only is not a session |

Also read from the output:

- `catalog_slug` — if it says `MISSING`, the car is not in
  `product/data/vehicle_catalog.json`. Add the entry **first** (bug 27), then
  rerun; otherwise the live coach cannot resolve this car's data.
- `pipeline` — `B` when a curated coaching model already exists, `A` when not.
- the printed candidate list — if the window caught more recordings than the
  user meant (e.g. a race *and* a practice), say so and narrow with `--track` /
  `--car` rather than picking one silently.

Only pass a session's own files directly when the user names a file:

```bash
python .agents/skills/update-coach/scripts/find_candidate_session.py \
    --session sessions/session_20261114T064918Z_circuit-de-barcelona_lmu_practice.parquet --json
```

**Short circuits**: laps under 60 s are rejected by default. For a circuit whose
real laps are shorter (Silverstone National ≈ 51 s in LMP3), add
`--min-lap-time-s 30` **both here and in step 2**, or the gate will say
`NO_LAPS` for a genuine fast lap.

## Step 2 — update reference + model (pipeline B: curated track)

The updater re-checks the curated corners against the new lap *before* writing,
and aborts with no changes if any corner fails to reproduce. Pass the same
`--session` files the gate used and the `track` slug it printed:

```bash
python dev/scripts/update_reference_and_coaching_model.py \
    --session <session files from step 1> \
    --track-id <track slug from step 1>
```

What it guarantees (do not re-implement these yourself):

- one (track, vehicle) per run, and a post-run audit that at most one reference
  changed;
- the fastest **complete** lap, per contiguous segment — never a
  `lap_number` filter (bug 22);
- the new reference and the model geometry stay in sync, or nothing is written;
- corner names, IDs, manual apex sides and flat-corner markers are preserved.

If it aborts with `ABORTED - curated corners not reproduced on this lap` (exit
2): **stop and report.** The default is correct — a lighter braking lap merged
chicanes or dropped light-braking turns, and the curated model encodes detail
the new lap cannot reproduce (Bahrain Outer precedent). Offer the options, do
not choose for the user:

- leave the track as it is (usually right),
- `--preserve-geometry <corner-id> ...` for reviewed zones that should not be
  matched at all,
- `--allow-unmatched` only with explicit user approval, and say which corners
  keep their old geometry.

If it prints `Coaching model already up to date - nothing written.` the gate was
right and there is nothing to commit — say so.

## Step 3 — new combo (pipeline A only, when verdict is NO_REFERENCE)

Export, generate, then curate. Follow `docs/HOW_TO_CREATE_A_COACHING_MODEL.md`
"Pipeline A" exactly; the short form is:

```bash
python dev/scripts/export_fastest_reference_laps.py <session files>
python dev/scripts/generate_track_coaching_model_from_reference.py \
    --reference-lap <exported parquet> --track-id <track slug> --layout-id lmu-default \
    --car-id <vehicle slug> --out product/data/track-coaching/<track>_<car>.json \
    --diagnostics-out product/data/track-coaching/<track>_<car>.diagnostics.txt
```

Then review the diagnostics line by line, name the corners, and fix zones. An
auto-named model (`turn 1`, `turn 2`, …) is **not** a finished update — say
plainly that the names are placeholders the user must curate.

## Step 4 — validate only what changed

Validate the changed reference against its own source session. Do **not** run an
archive-wide scan (`validate_reference_laps.py`) unless the user asks.

- Confirm the run ended with `AUDIT: 1 reference lap changed ... OK.` (or
  `0` when nothing was superseded).
- Run the combo's focused regression where one exists:
  `bash scripts/test-summary.sh dev/scripts/test_barcelona_p3_reference.js`
  (see `package.json` → `testFeatures` for other combos).
- If refreshed apices moved, re-bake map anchors and re-export that one track's
  TinyPedal labels (`dev/scripts/export_turn_labels_for_tinypedal.py --track
  "<name>"`). Track-only, no side effects on other circuits.

## Step 5 — report, then commit

Report, in this order:

1. the gate verdict and the numbers (old reference time → new lap time, delta);
2. which files changed (reference parquet, coaching model JSON, diagnostics);
3. whether corner geometry moved, and which corners;
4. anything deferred (unmatched corners, placeholder names, map re-bake).

Commit only what this run changed, one combo per commit:

```
ref: update <Track> <car> reference lap <old> -> <new> + coaching model geometry
```

On `NOT_FASTER`: report the comparison and stop. A session that lost is a
useful answer — do not "refresh anyway" and do not start a neighbouring task.

## Hard rules

- **One combo per run.** Never loop over recordings, never batch several
  circuits into one invocation or one commit.
- **Never hand-copy** into `product/data/reference-laps/` or
  `product/data/track-coaching/`; always go through the guarded scripts.
- **Never widen the gate.** No `--allow-unmatched`, `--max-geometry-delta-m`
  bump, or `--min-lap-time-s` change without saying so and getting an OK.
- **Never fabricate the reference comparison** by eyeballing `lap-telemetry
  summary` output; the segment-aware gate is the only authority.
- If gate and updater disagree (e.g. the updater keeps the old reference), trust
  the updater, report the discrepancy, and leave the tree clean.

## Bundled scripts

- `scripts/find_candidate_session.py` — CLI: discovery → one combo → gate
  verdict as an exit code (`0` proceed, `3` not faster, `2` ask).
- `scripts/session_lookup.py` — discovery, timing and reference comparison
  helpers behind that CLI; no argparse, no writes.
- Tests: `dev/scripts/test_update_coach_resolver.py` (+ `.js` wrapper).
