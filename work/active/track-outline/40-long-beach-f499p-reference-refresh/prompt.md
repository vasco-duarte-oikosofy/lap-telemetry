# Slice 40 — Refresh Long Beach / Ferrari 499P reference and coaching model

**Status:** In progress. User requested the latest practice session's faster lap.

## Goal

Scan session_20261101T175418Z_grand-prix-of-long-beach_lmu_practice (Ferrari AF
Corse 2026 #50:LM). Replace the 1:15.889 reference only with its fastest guarded
complete clean lap, updating the existing curated model rather than regenerating
it. Preserve all 11 official names/IDs/aliases/sides and full flat T3/T7 zones.

## Execution

1. Use the finalized/recovered canonical file if available; otherwise freeze/merge
   only this session's closed partN shards in numeric order into an ignored
   derived file. Exclude overlapping snapN snapshots. Preserve original source
   files/sidecar and record hashes/provenance. The recorder recovered this session
   independently during read-only inspection, so the canonical file was used.
2. Scan segment-aware with guarded selection and authoritative timing. Inspect
   fastest-lap validity, distance coverage and detection/matching BEFORE writes.
3. Read testing lessons; write failing tests for the new reference/model state
   and any safety addition required to preserve reviewed corner geometry.
4. Use the existing paired updater/export audit. If nearest-event matching would
   steal a neighbour or collapse manual/flat zones, add the smallest explicit
   preservation control required by this refresh, with tests. No blanket matcher
   rewrite. Review proposed geometry; abort if unsafe rather than losing curation.
5. Refresh map anchors/targeted TinyPedal labels only if model apices changed;
   preserve all outline coordinates and every other track/model/ref/label file.
6. Validate all reference laps/provenance, run coach --print-facts on a real lap,
   feature/full --pw tests, TinyPedal QA as applicable and build. Commit scoped
   changes on native main/master branches, handoff/learnings and PLAN hashes.
7. Stop. No CPU-performance work or unrelated recording/log inspection.

## Boundaries

No raw lap-number filtering, abandoned/invalid reference, snapshot duplication,
original recording cleanup, model regeneration, default matcher semantics changes,
other track changes, or modification/inspection of coach-race.log.
