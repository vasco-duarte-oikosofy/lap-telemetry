# Slice 42 — Road Atlanta / P3 (DKR Engineering LMP3): faster race reference + model refresh

Status: ✅ Complete in `8de8c23`
Trigger: the driver ran a Road Atlanta race today (2026-11-04, LMU ELMS) in the
P3 car `DKR Engineering #4:ELMS25`. Lap 17 beats the curated 1:16.304 reference
by 0.489 s (authoritative 1:15.815).

## Goal

Use today's P3 race to (a) export the faster reference lap for
`(michelin-raceway-road-atlanta, dkr-engineering-4-elms25)` through the guarded
pipeline, and (b) refresh the curated coaching model from it without losing a
single curated name, ID, apex side or flat marker.

## Execution

1. Freeze the in-progress race's closed shards to ignored scratch
   (`var/tmp/road-atlanta-p3/`); never concatenate the overlapping `snapN`
   snapshots. Record source hashes.
2. Run the guarded updater (`update_reference_and_coaching_model.py`): it
   delegates the export, and refuses to lose curation (aborts on unmatched
   corners, `--preserve-geometry` for reviewed zones, geometry-delta guard
   before any write).
3. Justify every preserved corner from real brake/throttle/steering signals on
   both the old and the new reference lap (`artifacts/signal-review.txt`).
4. Re-bake the outline turn anchors (repo contract: outline turns must match the
   model) while keeping the curated display labels.
5. Validate references, `--print-facts`, feature + full suites, build, scope
   audit, then write `handoff.md` / `learnings.md` and mark the PLAN row done.

## Boundaries

- No other track's reference, model or outline may change.
- No `lap_number` filtering (segment-based analysis only).
- No edits to the recorder's live session files.
- Every curated turn name (`Turn 1` … `Turn 12`, `Turn 4 (The Esses)`,
  `Turn 10A/B`) and every flat marker (`t4`, `t8`, `t9`, `t11`, `t12`) survives
  byte-identical.

## Acceptance

- `product/data/reference-laps/michelin-raceway-road-atlanta_dkr-engineering-4-elms25_time_01.15.815.parquet`
  exists and the exporter's audit reports exactly one reference changed.
- Coaching model points at it; names/IDs/apex sides/`target_throttle_pct` unchanged.
- `validate_reference_laps.py`: 0 failures.
- `bash scripts/test-summary.sh --feature track-outline --pw` and the full
  `--pw` suite exit 0; `npm run build` succeeds with a current `dist/compare.html`.
