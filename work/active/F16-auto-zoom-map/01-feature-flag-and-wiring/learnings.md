# Slice 01 Learnings — Feature flag and wiring

## What surprised me

1. **Playwright visibility and dropdown selects**: `page.selectOption()` requires the `<select>` element to pass Playwright's visibility check. The feature-flag menu is inside `#circuit-map-panel .map-controls`, and even after calling `__setFeatureFlagMenuEnabled(true)` to set `display: ''`, Playwright still considered the element "not visible". Solution: use `{ force: true }` on `selectOption()`. The existing `test_feature_flag_dropdown.js` test somehow avoided this — likely because it doesn't load a session file first, so the page layout is different.

2. **Flag ordering matters for readability**: The `mapAutoZoom` flag is placed immediately after `mapLinkedHighlight` in the `features` object, matching the dependency (auto-zoom only makes sense when linked highlight is enabled). This keeps the features object self-documenting.

3. **No visual changes at all**: This slice is purely wiring. The flag exists in state, appears in the dropdown, and can be toggled — but nothing reads it yet. Subsequent slices will check `features.mapAutoZoom` to gate behavior.