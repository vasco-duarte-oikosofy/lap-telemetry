# Handoff — Bug 17

## State on disk

- `product/web/js/pipeline.js` now computes a raw track-length estimate first, then ignores stale start-boundary frames (`lap_time_s < 0.5` and distance past half track) when annotating segment `minDist`, `maxDist`, and `duration`.
- `dev/scripts/test_bug17_js_stale_boundary_frame.js` covers both a synthetic stale-boundary partial lap and the real Bahrain Outer lap 19 repro.
- `package.json` registers the Bug 17 regression in the full script list and the `interactive-race-coach` feature suite.
- `product/dist/compare.html` was rebuilt with `npm run build`.

## Verification

- `node dev/scripts/test_bug17_js_stale_boundary_frame.js` passes.
- `bash scripts/test-summary.sh --feature interactive-race-coach` passes.
- `npm run build` succeeds.
- `bash scripts/test-summary.sh --pw` passes.

## Deferred

- Bug folder remains under `work/active/bugs/` pending user live-test confirmation before moving to `work/completed/bugs/`.
