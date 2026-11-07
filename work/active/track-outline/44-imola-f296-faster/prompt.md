# Slice 44 — Imola / Ferrari 296 GT3: faster reference (1:46.173 → 1:45.534)

Status: ✅ Complete (see git log for this slice)
Trigger: a second Imola practice today (2026-11-07T12:55Z,
`session_20261107T125508Z_autodromo-enzo-e-dino-ferrari_lmu_practice.parquet`)
in the same car (`Vista AF Corse 2026 #21:LM`). Fastest complete lap: lap 6,
**1:45.534**, 0.639 s faster than the reference created in slice 43.

## Goal

Refresh the `(autodromo-enzo-e-dino-ferrari, ferrari-296-gt3)` reference and
coaching geometry from the faster lap without losing a single curated name, ID,
short name, apex side or flat marker.

## Execution

1. Guarded updater against the new session (it re-checks every curated corner
   before writing, delegates the export, audits the folder).
2. Justify every preserved corner from real signals across all six complete laps
   of the session (`artifacts/signal-review.txt`), not from one lap.
3. Verify curation byte-identical against `artifacts/model-before.json`,
   validate references, `--print-facts` from two other laps, feature + full
   suites, build, scope audit; write `handoff.md` / `learnings.md`, mark PLAN.

## Boundaries

- No other track's reference, model or outline may change.
- No `lap_number` filtering (segment-based analysis only).
- Every curated turn name, ID, short name, apex side and flat marker survives.
- The track outline is per-layout; it must stay byte-identical.

## Outcome (short)

| | Before | After |
|---|---|---|
| Reference | 1:46.173 | **1:45.534** (superseded file removed) |
| Corners refreshed | — | 7 (deltas ≤ 13 m on the apex) |
| Preserved | — | t1 Tamburello (unstable exit boundary) + Villeneuve 2, Acque 2, Alta 2 (compound second halves) |
| Outline | — | byte-identical |
