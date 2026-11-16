# Slice 56 — Barcelona / Ginetta P3 latest race refresh

## Status and scope

✅ Completed — **superseded, no net data change**. User requested the previous
Barcelona/P3 race's fastest lap, then a reference/model refresh for that combo.
Latest matching race is
`session_20261115T124448Z_circuit-de-barcelona_lmu_race` (DKR Engineering
#4:ELMS25 / ginetta-lmp3).

Race lap 16 → **1:36.319** (4791 rows, valid) beat the 1:36.456 reference and
was exported into the work tree, but slice 57 then found a faster qualifying lap
(1:36.040, commit `672a12c`) and its guarded export deleted the race reference
before this slice could commit. The race is therefore **not** the current
reference; this slice is closed on its evidence (`handoff.md`, `learnings.md`,
`artifacts/`) with `product/data/` untouched. See `handoff.md` for the full
provenance. Rear-slip work never started here.

## Goal

Find the fastest complete valid segment in that race. If it beats the current
1:36.456 reference, update this combo's reference and existing coaching model
through Pipeline B while retaining all curated corner metadata and reviewed
flat/compound zones. Never regenerate the model or select by lap-number filter.

## Execution order

1. Read the guarded reference/model workflow, testing lessons, and nearby
   completed reference-refresh slices. Confirm track/car identity and record
   hashes of current assets.
2. The sidecar is currently `in_progress: true`, with no canonical parquet.
   Freeze numerically ordered **closed** part shards (exclude the highest,
   potentially open one), verifying hashes remain stable during the read.
   Do not combine cumulative snapshots with parts. Collapse only exact
   consecutive duplicate rows. Save merged input/sidecar under gitignored
   `var/tmp/barcelona-p3-race-refresh/`, keeping the canonical session basename;
   record a source manifest under this slice's `artifacts/`.
3. Run the summary and segment-aware candidate scan. Validate the winning lap's
   duration, validity, coverage and row count; record any excluded incomplete
   tail. If no faster valid complete lap exists, retain existing assets.
4. Review new detected geometry against existing named corners and actual
   controls. Explicitly preserve unmatched/compound zones with signal evidence;
   do not silently merge curated turns or raise delta bounds to force a match.
5. Write a failing combo asset regression before production data updates. Use
   a thin Node wrapper (`runPython`, PASS/FAIL protocol) and register it in
   `package.json` main tests and `testFeatures.track-outline`. Retain both
   infrastructure guards; affected comparison/short-name/delta-time tests
   already in the shared suites must remain covered.
6. Use `update_reference_and_coaching_model.py --session <frozen input>
   --track-id circuit-de-barcelona`, adding reviewed `--preserve-geometry` and
   `--max-geometry-delta-m` options as needed. Require the delegated export's
   single-combo audit. Update tests pointing at the superseded reference,
   without weakening their behavioral invariants.
7. Validate the whole reference folder, compare against a known slower segment
   and itself, check resolution by track/car and prove idempotence. Audit that
   no unrelated references/models/source shards changed. Leave the map/labels
   unchanged unless a shared contract actually requires regenerated anchors;
   stop and document any unexpected scope expansion.
8. Run `bash scripts/test-summary.sh --feature track-outline` and
   `--feature session-debrief`, full `--pw` suite, and `npm run build`.
9. Write handoff/learnings and artifact evidence. Commit on `main`, update
   `PLAN.md` with the completion hash, push and stop. Do not start rear-slip
   work or include its pre-existing planning edits/runtime log.

## Acceptance

- [x] Fastest lap stated with source session/segment, authoritative time and
      validity/coverage evidence; only a faster valid full lap may replace ref.
      — race lap 16 @ 96.319 s, 4791 rows, valid (`artifacts/lap-scan.txt`);
      not the current reference any more, because 96.040 is faster.
- [x] Frozen source is reproducible from stable closed shards; original
      recording and open tail are not modified.
      — `part0..part94` (part95 excluded), `artifacts/source-manifest.json`.
- [x] Single-combo guarded export, aligned model reference path/time, and
      reviewed geometry; every original corner/curated field retained.
      — `AUDIT: 1 reference lap changed … OK`; only Turn 3 — Renault refreshed,
      11 corners preserved (`artifacts/guarded-update.txt`).
- [x] No unrelated assets changed; any intentionally retained geometry and
      limitations are documented rather than hidden by permissive matching.
      — `artifacts/guarded-review-abort.txt` + `artifacts/controls-review.json`
      record the 8 guard flags and why each was preserved;
      `artifacts/closure-audit.txt` shows `product/`, `dist/`, `web/` clean.
- [x] Reference validator, feature suites, full suite and build pass.
      — validator 38/0; `track-outline` and `session-debrief` ALL PASS; build OK.
      Full `--pw`: 1 **pre-existing** failure, `test_repo_reorg_root_cleanup.js`
      rejecting the `.agents` root added by remote commit `15dc971` — unrelated,
      left for its own slice.
- [x] Handoff/learnings, artifacts and completed PLAN row with commit exist.

## Non-goals

No detector/coaching algorithm changes, rear-slip analysis, schema changes,
renaming/reclassification of existing corners, setup advice or TinyPedal work.
