# Slice 41 — Interlagos / Ginetta P3: faster race reference + model refresh

Status: ✅ Complete in `fe29da7` (encoding guard: `3050f77`).
Trigger: the driver ran a P3 race at Autódromo José Carlos Pace
(Interlagos) whose fastest lap beats the curated 1:30.354 reference.

## Goal

Use the new race session to (a) export the faster reference lap for
`(autodromo-jose-carlos-pace, dkr-engineering-4-elms25)` through the guarded
pipeline, and (b) refresh the curated coaching model from it without losing a
single curated name, ID, apex side or flat marker.

## Execution

1. Freeze the session's closed shards to ignored scratch; never concatenate the
   overlapping `snapN` snapshots. Record source hashes and segment-aware scan.
2. Run the guarded updater (`update_reference_and_coaching_model.py`), which
   delegates the export and refuses to lose curation: abort on unmatched
   corners, explicit `--preserve-geometry` for reviewed zones, geometry-delta
   guard before any write.
3. Justify every preserved corner from real brake/throttle/steering signals on
   both the old and the new reference lap.
4. Re-bake the outline turn anchors (the repo contract requires outline turns to
   match the model) while keeping the curated *display* labels.
5. Validate references, `--print-facts`, feature + full suites, build, scope audit.

## Boundaries

No other track's reference, model or outline may change. No `lap_number`
filtering. No edits to the recorder's live session files. TinyPedal is untouched
(it ships no Interlagos map, so there is nothing to label).
