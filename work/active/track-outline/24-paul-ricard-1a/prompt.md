# Slice 24 — Paul Ricard 1A / Ginetta P3: race reference, model and layout

Status: Complete. User explicitly confirmed NEW 1A assets, not changes to 3A.
See `handoff.md` for the committed state and `artifacts/full-suite.txt` for test evidence.

## Goal

Use the latest P3 race session session_20261101T190458Z_paul-ricard---1a_lmu_race
(DKR Engineering #4:ELMS25) to select the fastest complete valid guarded lap.
Create the combo reference, official-named coaching model including genuine flat
corners, and a distinct 1A trajectory outline with generated module/manifest.

## Execution

1. Freeze stable canonical data or numerically ordered closed shards to ignored
   scratch space. Never concatenate overlapping snapshots. Preserve recording and
   sidecar; record source hashes and segment-aware candidate scan/provenance.
2. Review actual 1A layout, official names, signal geometry and flat zones. Do not
   alias the shorter 3A or 1A-V2-Short layouts. Check vehicle catalog.
3. Read testing lessons; add failing reference/model/outline/resolver tests and
   register them in track-outline feature suite before writing production assets.
4. Export exactly one reference through the guarded script and mandatory audit;
   generate detector input only in scratch, then curate ALL official bends with
   full flat-corner spans, names/IDs/sides and appropriate spoken aliases.
5. Generate 500-point trajectory outline with explicitly synthetic +/-5m shell,
   same-axis lap_length_m and official turn anchors. Register exact layout only;
   build current standalone compare. Publish track-only TinyPedal labels if its
   recorded map is available, with real widget QA when applicable.
6. Validate reference folder and provenance, real-lap and self --print-facts,
   feature tests, full --pw suite, build and scope audit. Record automated render
   evidence without claiming live/by-eye approval. Commit on native branches,
   update PLAN status/hashes, write handoff/learnings and stop.

## Boundaries

No changes to existing Paul Ricard 3A/1A-V2-Short or other curated assets. No raw
lap_number filtering, unguarded reference copying, snapshot duplication, original
recording cleanup, global matcher rewrite, CPU work or coach-race.log inspection.
