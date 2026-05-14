# Phase 01b — s-based Cross-lap Alignment Handoff

## Status

✅ COMPLETE on branch `main`.

## What changed

### New Files
- **`web/js/sLookup.js`** (69 lines)
  - Exports `sLookup(lap, targetS)` — binary search + linear interpolation for cross-lap distance queries.
  - Exports `assertStrictlyMonotonic(distances, label)` — hard-fail assertion gated behind dev flag.
- **`scripts/test_01b_s_alignment.js`** (new)
  - Unit + integration test suite for s-lookup and debug overlay.
- **`phases/01b-s-alignment/prompt.md`**
- **`phases/01b-s-alignment/handoff.md`**
- **`phases/01b-s-alignment/learnings.md`**

### Modified Files
- **`web/js/appState.js`**
  - Added `features.mapSAlignment: false`
  - Added `devFeatures.devMapSAlignmentDebug: false` (dev-only, not in production UI)
  - Added `setDevFeatureFlag(name, value)` export
- **`web/js/debugHooks.js`**
  - Exposes `window.__devFeatures`
  - Added `window.__setDevFeatureFlag`
- **`web/js/main.js`**
  - Imports `devFeatures`, `setDevFeatureFlag`, `assertStrictlyMonotonic`
  - Stashes raw arrays (`currentLapARaw`, `currentLapBRaw`) for sLookup use
  - Passes `raw` to `lapA`/`lapB` and `showSAlignmentDebug` option to renderer
  - Calls `assertStrictlyMonotonic` on raw distances when `devMapSAlignmentDebug` is enabled
- **`web/js/trackHeatmapMap.js`**
  - Imports `sLookup`
  - Added `drawDebugTicks()` — renders crosshair ticks every 100m with s labels
  - `renderWalkingSkeleton` accepts `showSAlignmentDebug` option
- **`package.json`**
  - Wires `scripts/test_01b_s_alignment.js` into `npm test`

## Technical Approach

### sLookup
- Works on raw lap arrays (`s`, `x`, `z`, `throttle`, `brake`, ...).
- Binary search for the bracket `[lo, hi]` around `targetS`, then linearly interpolates all numeric channels.
- Bounds clamp: returns first sample for `targetS ≤ min(s)`, last sample for `targetS ≥ max(s)`.

### Debug Overlay
- Draws white tick marks every 100m on both laps using `sLookup`.
- Labels show `A 100`, `B 100`, etc.
- Only visible when `devMapSAlignmentDebug` is true; `mapSAlignment` is the master flag but invisible by itself.

### Monotonicity Guard
- `assertStrictlyMonotonic` throws a descriptive error with the violation index and values.
- Only called when `devMapSAlignmentDebug` is enabled, so production data never crashes the app.

## Test Results

All 11 Phase 01b assertions pass:
- **Scenario 1 (unit):** 8/8 — exact samples, interpolation, monotonicity, random property
- **Scenario 2 (assertion):** 2/2 — assertion fires on corrupted data, passes on good data
- **Scenario 3 (render):** 1/1 — debug ticks render white pixels on canvas

### Existing Tests
All prior test suites still pass (no regression).

## Acceptance Criteria

✅ `sLookup` returns correct interpolation at exact and intermediate positions
✅ `sLookup` is monotonic (ascending `s` → ascending sample index)
✅ Random property: interpolated `s` within float-epsilon of query
✅ Monotonicity assertion fires on deliberately-corrupted fixture
✅ Debug ticks render on canvas (automated), verified visually on real data (manual — see screenshot)

## Feature Flags

- `features.mapSAlignment`: default OFF — controls whether sLookup is wired into the system
- `devFeatures.devMapSAlignmentDebug`: default OFF — enables debug tick overlay + monotonicity hard-fail

Toggle in browser console:
```js
window.__setFeatureFlag('mapSAlignment', true)
window.__setDevFeatureFlag('devMapSAlignmentDebug', true)
```

## Verification

To verify manually:
1. Open `dist/compare.html` in a browser
2. Load a session file and compare two laps
3. In browser console: `window.__setDevFeatureFlag('devMapSAlignmentDebug', true)`
4. Click "Compare" button again
5. Observe: Small tick marks every 100m on both laps with `A`/`B` labels, aligned at corner entries/exits

## Deferred TODOs

- [ ] Phase 1c: wire sLookup into the actual dual-ribbon offset (side-by-side)
- [ ] Phase 1c: promote Lap B from polyline to ribbon (uses same `sLookup`)
- [ ] Phase 2: zoom/pan transform handling for sLookup queries
- [ ] Consider: upstream pipeline validation for monotonic `lap_distance_m` before it reaches the renderer
- [ ] Jitter fix: raw data sLookup gives smoother positions than resampled distance bins in high-curvature areas

## Commit History

```
feat: add s-based cross-lap alignment helper + debug overlay (Phase 01b)
- Create sLookup.js with binary search + linear interpolation
- Add assertStrictlyMonotonic with dev-only guard
- Add debug tick overlay in trackHeatmapMap.js
- Wire feature flags: mapSAlignment, devMapSAlignmentDebug
- Stash raw arrays in main.js for sLookup access
- Add Phase 01b test suite
```

**Handoff complete.**
