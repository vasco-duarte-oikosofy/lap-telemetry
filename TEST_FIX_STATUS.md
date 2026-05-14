# Test hardening status

Scope: update the reviewed test files. `scripts/test_001_responsive.js` is now in scope per follow-up request.

Full suite command: `npm test`.

## Baseline

- [x] Baseline run complete: current `npm test` fails in `scripts/test_001_responsive.js` only. Per instruction, that file is out of scope.

## Fix checklist

1. [x] `scripts/test_zoom_bug.js`: replace below-fold fragile absolute `mouse.move()` drag with element-relative hover + fresh element access.
2. [x] `scripts/test_f8f9f10f11.js`: replace fragile absolute `mouse.move()` interactions with element-relative hover/drag patterns; re-acquire handles around re-renders.
3. [x] `scripts/validate-build.js`: replace absolute cursor move with `.hover()`.
4. [x] `scripts/test_file_picker_bug.js`: define missing `SESSIONS_DIR` constant.
5. [x] `scripts/test_m5.js`: replace generic DOM-only waits for `polyline` with panel/data-state waits where applicable.
6. [x] `scripts/test_m6.js`: remove always-passing sidecar assertion or make it meaningful using existing observable UI state.
7. [x] `scripts/test_001_responsive.js`: replace false pixel-diff claim with accurate automated baseline structural checks.
8. [x] `scripts/test_001_responsive.js`: make tested content width explicit instead of mixing viewport and container width.
9. [x] `scripts/test_001_responsive.js`: strengthen renderer overflow checks using viewport bounds and SVG bounds; document-level overflow is logged as diagnostic because non-renderer controls can overflow independently at 320px.
10. [x] `scripts/test_001_responsive.js`: capture browser console/page errors for every scenario/page.
11. [x] `scripts/test_001_responsive.js`: strengthen data/render waits beyond session-key and panel-count checks.
12. [x] `scripts/test_001_responsive.js`: replace brittle `viewBox !== 900` assertion with viewBox/rendered-width consistency checks.
13. [x] `scripts/test_001_responsive.js`: make saved screenshots explicit artifacts and verify files are written.
14. [x] `scripts/test_001_responsive.js`: prefer locators over `page.$` and add a fixture preflight check.

## Notes

- `scripts/test_m4.js` was not edited because it is a legacy standalone test for an older UI shape and is not in the current `npm test` suite.

## Run log

- Baseline: initial `npm test` exited 1 because `scripts/test_001_responsive.js` had 13 failures. All preceding suites passed.
- After creating this status file: `npm test` exited 0.
- After `scripts/test_zoom_bug.js`: `npm test` exited 0.
- After `scripts/test_f8f9f10f11.js`: `npm test` exited 0.
- After `scripts/validate-build.js`: `npm test` exited 0.
- After `scripts/test_file_picker_bug.js`: `npm test` exited 0.
- After `scripts/test_m5.js`: `npm test` exited 0.
- After `scripts/test_m6.js`: `npm test` exited 0.
- After replacing remaining test drag `mouse.move()` calls in changed zoom tests with locator-relative `.hover()`: `npm test` exited 0.
- After final status-note update: `npm test` exited 0.
- Before `scripts/test_001_responsive.js` changes: `npm test` exited 0.
- After first `scripts/test_001_responsive.js` hardening pass: `npm test` exited 1; new document-overflow assertion exposed 320px overflow from non-renderer controls, so the renderer-specific overflow assertion was narrowed and the document overflow kept as diagnostic detail.
- After requiring non-zero map SVG width: `npm test` exited 1; current map rendering can use canvas while SVG has zero width, so the assertion was changed to measure the visible map renderer (SVG or canvas).
- After final `scripts/test_001_responsive.js` fixes: `npm test` exited 0.
- After documenting new lessons in `TESTING_LESSONS.md`: `npm test` exited 0.
