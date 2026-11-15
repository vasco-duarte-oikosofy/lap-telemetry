# Handoff — Barcelona/P3 qualifying reference refresh

## Delivered state

- Exact input: `sessions/session_20261115T183239Z_circuit-de-barcelona_lmu_quali.parquet`
  (finalised, DKR Engineering #4:ELMS25 / Ginetta LMP3).
- Fastest valid complete lap: **lap 4, 1:36.040**, authoritative unrounded
  duration 96.039978 s; contiguous rows [21361, 26151), 4790 rows.
- New reference:
  `product/data/reference-laps/circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.040.parquet`.
  The guarded export removed the on-disk 1:36.319 race candidate, improving by
  0.279 s. Git supersedes the last committed 1:36.456 reference (0.416 s faster).
- `product/data/track-coaching/circuit-de-barcelona_dkr-engineering-4-elms25.json`
  points to the new reference/time. Renault is now 1073/1167/1172 m; the other
  eleven complete curated corner objects are unchanged from the on-disk model.
  All twelve names, IDs, short names, sides and distance axis are retained.
  The diagnostics were refreshed from the new reference.
- No algorithm, reference schema, model schema or live feature flags changed.
  No outline, static map, bundle content or TinyPedal settings/labels changed.

## Why the apparent faster lap is rejected

Lap 6 displays 1:31.518 and valid flags but ends at 4295.19 m, 358 m before its
recorded maximum. The guarded coverage check excludes it. Laps 1–5 are valid
and complete; lap 0 is an out-lap and lap 7 a frozen/incomplete tail. The full
inventory and source hash are in `artifacts/lap-list.txt` and
`artifacts/candidate-review.md`.

## Geometry controls

Run through `update_reference_and_coaching_model.py --session <input>
--track-id circuit-de-barcelona --preserve-geometry t1 t2 t4 t5 t6 t7 t8 t9 t10
t11 t12 --max-geometry-delta-m 40`. Unreviewed matching first aborted with no
product writes; the reviewed run passed the mandatory single-reference audit.
The retained zones avoid missed secondary turns, overlapping Campsa geometry
and >40 m event-boundary changes. No blanket --allow-unmatched or relaxed bound.

## Tests and fixtures

- Existing Barcelona/P3 regression now pins the new reference, all twelve
  curation objects and exact source-row identity, plus lap-6 rejection when the
  local recording exists. Its Node wrapper/main-suite/feature registration ship.
- Historical numerical regressions use the original committed 1:36.456 lap/model
  under `dev/fixtures/coach`; assertions and tolerances are unchanged. Test-only
  refactor commits: `a862a2f` and `053bf01`.
- Active comparison/short-name/phase tests and demo defaults point at 1:36.040.
- Test-first: the latest-reference regression failed before export (9 failures).
- `--feature track-outline`: **1597 assertions / 36 scripts passed** (5 browser
  scripts excluded during development).
- Full `bash scripts/test-summary.sh --pw`: **3059 assertions / 101 scripts passed**.
- `npm run build`: successful; `product/dist/compare.html` current, no diff.
- Self comparison: 0.000 s; qualifying lap 3 versus new ref: +0.734 s.
- Re-running the guarded updater is idempotent: nothing written.
- Focused source/reference checks passed: exact winning rows, all-valid samples,
  complete coverage, authoritative timing and car-aware model/reference resolution.
- User removed the archive-wide validation requirement: runbooks now require only
  the changed reference and its selected source session. No more archive scans.
  The already-running historical audit had finished (38 refs, 0 failures) by the
  stop request; its log is retained but it is not a completion prerequisite.
- Scope hash audit confirms only this reference/model/diagnostics changed;
  other curated data, shared maps, TinyPedal labels and source files unchanged.

## Working-tree ownership and activation

The earlier race-refresh artifacts (slice 56), its README edit, rear-grip plan/
slice and runtime log were pre-existing and are not part of this delivery.
The old race candidate's temporary data remains under ignored var/tmp as needed;
it is not an active reference. No other slice was implemented or closed.

Restart the coach so any already-loaded reference/model is refreshed. The live
resolver still selects Barcelona/Ginetta P3 by track and car; Ferrari resolution
is unchanged. No TinyPedal reload is required for this reference-only update.
