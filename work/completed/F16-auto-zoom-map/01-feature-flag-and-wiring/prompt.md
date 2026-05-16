# Slice 01 — Feature flag and wiring

## Goal

Add the `mapAutoZoom` feature flag to `appState.js` and verify it appears in
the feature-flag dropdown and is toggleable from Playwright. This slice
produces no visual change — it wires the flag so that subsequent slices can
check it.

## Context

Feature flags live in `product/web/js/appState.js` in the `features` object.
The dropdown menu (`#feature-flag-menu`) is auto-populated by
`syncFeatureFlagMenu()` in `ui.js`, which iterates `Object.entries(features)`.
Flag changes are handled in `ui.js` via a `change` event listener that calls
`setFeatureFlag(name, value)`.

The `mapLinkedHighlight` flag already exists and must be enabled for
`mapAutoZoom` to have any effect (the highlight band defines the zoom target).
This dependency is enforced in the controller logic in later slices, not in
the flag system itself.

## Steps

1. **Add `mapAutoZoom: false` to `features` in `appState.js`.** Place it after
   `mapLinkedHighlight` since it depends on it. Keep the `false` default and
   the trailing comma style.

2. **Verify the dropdown auto-populates.** Run `npm run build` and open
   `product/dist/compare.html` in a browser. The dropdown should show
   `○ mapAutoZoom`. Toggling it should show `✓ mapAutoZoom`. No console
   errors.

3. **Write a Playwright test `dev/scripts/test_f16_auto_zoom.js`.** The test
   must:
   - Load the app with a session file.
   - Verify `window.__features.mapAutoZoom` is `false` on load.
   - Enable `mapLinkedHighlight` and `mapAutoZoom` via
     `window.__setFeatureFlag`.
   - Verify `window.__features.mapAutoZoom` is `true`.
   - Disable `mapAutoZoom` and verify it flips back to `false`.
   - Print `[PASS]` / `[FAIL]` for each assertion per the protocol.

   Use `// @parallel true` in the file header. Follow the same pattern as
   existing Playwright tests (start server, launch browser, assert, tear down).

4. **Run `bash scripts/test-summary.sh`.** Must pass with the new test
   included.

5. **Commit.**

## Acceptance

- `mapAutoZoom: false` appears in `appState.js` after `mapLinkedHighlight`.
- The feature-flag dropdown shows `○ mapAutoZoom` (off by default).
- Toggling the flag in the browser works (updates to `✓ mapAutoZoom`).
- `test_f16_auto_zoom.js` passes with ≥ 4 assertions covering flag state.
- Full suite passes: `ALL PASS`.
- Build succeeds: `npm run build`.
- `product/dist/compare.html` is current.

## Non-goals

- Do not implement any auto-zoom behaviour (that's slice 03).
- Do not add `computeSegmentBounds` (that's slice 02).
- Do not change existing tests or flags.