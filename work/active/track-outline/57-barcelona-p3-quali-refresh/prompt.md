# Slice 57 — Barcelona / Ginetta P3 qualifying reference refresh

Status: ✅ Complete — `672a12c` (data/runbooks); test-only refactors `a862a2f`, `053bf01`.

## Confirmed task

List the laps in `session_20261115T183239Z_circuit-de-barcelona_lmu_quali`,
find the fastest valid complete lap and, if faster, update only its reference
and existing coaching model through the guarded Pipeline B.

## Scope and execution

1. Scan this exact finalised session, confirm DKR Engineering #4:ELMS25 maps to
   Ginetta LMP3, and record segment boundaries, validity, timing and coverage.
   Reject the apparent 1:31.518 lap 6 because it ends at 4295 m, not the line.
2. Compare complete lap 4 (1:36.040) with the on-disk 1:36.319 reference. Preserve
   unrelated working-tree work. This supersedes the prior uncommitted race
   candidate, not its historical artifacts or other mission changes.
3. Read workflow/testing docs. Write failing latest-reference expectations in
   the existing Barcelona/P3 regression and preserve all twelve curated corner
   IDs/names/short names/sides and reviewed secondary zones.
4. Review detector matches and raw controls before export. Use the guarded
   updater with explicit reviewed preserved IDs and a 40 m geometry bound;
   never relax guards or regenerate the curated model to force a match.
5. Stabilize the historical-data tests that already fail against the race
   candidate, plus the loss-distance-sign example changed by the new PB:
   archive their committed 1:36.456 reference and original model in
   dev/fixtures/coach, and pin those numerical fixtures rather than changing
   assertions. Keep test-only refactors separate from behavior/data commit.
   Update remaining active demo/test pointers to the new reference as needed.
6. Per the user's updated instruction, validate only the changed reference
   against its selected source session: source-row identity, live (track, car) resolution,
   self/slower-lap comparison and idempotence. Barcelona's shared map comes
   from the Ferrari model: no outline/static-map/TinyPedal changes in this slice.
7. Run track-outline feature tests while developing, then full --pw tests and
   npm run build. This is a reference/model update, not a TinyPedal update.
8. Commit scoped changes on main, update PLAN with commit hash, write handoff
   and learnings, push and stop. Do not complete or modify other slices.

## Acceptance

- A lap list and reproducible rejection of incomplete lap 6 are recorded.
- Only the faster valid full lap replaces the reference, with mandatory export
  audit, authoritative 96.040 s metadata and 4790 exact source rows (lap 4).
- Model points to that reference; curation and reviewed retained zones survive.
- Historical numerical tests remain meaningful, without widened tolerances.
- Other combo data and all map/rotation/placement assets remain unchanged.
- Feature/full tests, validator and build pass; handoff/learnings and status exist.

Feature suite: `bash scripts/test-summary.sh --feature track-outline`
