# Phase — Cleaning Old Features Replaced by TUMFTM Static Outline

> **Development convention:** work on `main`. This is a cleanup/refactoring phase.

## Goal

Remove feature-flag-gated code that the TUMFTM-based static outline now supersedes, and evaluate which apex features need reworking against the TUMFTM spike data.

This phase answers one question only:

> Which old outline/apex code can be safely deleted, and which apex features need adaptation to work with the TUMFTM-based visualization rather than the learned-boundary pipeline?

## Required reading

1. `AGENTS.md`
2. `TESTING_LESSONS.md`
3. `phases_TUMFTM_based_track_map_outline/PLAN`
4. `phases_TUMFTM_based_track_map_outline/02_runtime_static_outline_rendering/handoff.md`
5. `phases_TUMFTM_based_track_map_outline/02_runtime_static_outline_rendering/learnings.md`
6. `web/js/appState.js` — feature flags map
7. `web/js/staticTrackOutline.js` — the replacement renderer

Before writing a new test or fixing a failing test, read `TESTING_LESSONS.md`.

## Scope

### A. Remove `mapTrackOutline` feature flag and its code

`mapTrackOutline` gates `drawTrackOutline()` — a Phase 00.6 experiment that draws two offset polylines (magenta inner / cyan outer) at a hardcoded 15 m half-width around the trajectory. This is strictly worse than the TUMFTM static outline (real measured boundaries, accurate widths, schema-v1 artifact). Remove it.

**Affected files:**

| File | What to remove |
|------|---------------|
| `web/js/appState.js` | `mapTrackOutline: true` feature flag entry |
| `web/js/trackHeatmapController.js` | `showOutline: !!features.mapTrackOutline` in buildOpts, `features.mapTrackOutline` in `anyMapFeature` guard |
| `web/js/trackHeatmapMap.js` | `showOutline` option, `if (showOutline) { drawTrackOutline… }` block, console.log lines, import of `drawTrackOutline` |
| `web/js/trackHeatmapDrawing.js` | `drawTrackOutline()` export and `drawOffsetPolyline()` helper (only called by drawTrackOutline) |
| `web/js/debugHooks.js` | `'mapTrackOutline'` in feature-flag name check |
| `scripts/test_006_track_outline.js` | Entire test (exercises the removed feature) |
| `package.json` | Remove `test_006_track_outline.js` from test chain |
| `006-test-report/` | Delete directory if present |

After removal, the `anyMapFeature` guard already has `|| true` from Phase 02 (for the unconditional static outline). Simplify it — the `|| true` is now justified but should be replaced with a named check if one emerges; if not, leave the `|| true` with a comment explaining the static outline makes canvas always preferred.

### B. Remove `learnedTrackOutline` feature flag and its code

`learnedTrackOutline` gates `drawLearnedBoundaries()` — renders boundary polylines derived from the width-profile pipeline (offline Parquet analysis). The TUMFTM static outline provides better geometry from a curated external source. Remove it.

**Affected files:**

| File | What to remove |
|------|---------------|
| `web/js/appState.js` | `learnedTrackOutline: false` feature flag entry, `learnedBoundariesByLayout` Map export |
| `web/js/learnedOutline.js` | **Entire file** (`isBoundaryData`, `boundaryKey`, `drawLearnedBoundaries`, `findBoundaryData`) |
| `web/js/ui.js` | Import of `isBoundaryData`/`boundaryKey`/`learnedBoundariesByLayout`; the file-type detection that loads boundary JSON into `learnedBoundariesByLayout` |
| `web/js/trackHeatmapController.js` | Import of `findBoundaryData`; `showLearnedOutline` option; learned-boundaries resolution in `buildOpts`; `features.learnedTrackOutline` in `anyMapFeature` guard |
| `web/js/trackHeatmapMap.js` | `showLearnedOutline` option; `drawLearnedBoundaries` import and call; `learnedBoundaries` option key |
| `web/js/main.js` | `learnedBoundariesByLayout` import (from appState) and pass-through to debugHooks |
| `web/js/debugHooks.js` | `learnedBoundariesByLayout` and `'learnedTrackOutline'` in feature-flag check |
| `web/js/trackOutlineChannels.js` | Any `boundaryKey` import if present |
| `web/css/styles.css` | Styles for learned boundary rendering if any |
| `scripts/test_learned_outline_rendering.js` | Entire test |
| `scripts/test_boundary_smoothing.js` | Only if it exclusively tests the learned-boundary path (check first — may be CLI-only) |
| `scripts/test_boundary_width_inference.js` | Only if it exclusively tests the learned-boundary path (check first — may be CLI-only) |
| `package.json` | Remove `test_learned_outline_rendering.js` from test chain |
| `10-test-report/` | Delete directory if present |

**Do NOT remove** the CLI-side boundary generation scripts (`scripts/test_compute_boundaries.js`, `scripts/test_center_path_export.js`, `scripts/test_width_profile_*.js`) or `web/js/trackHeatmapDrawing.js`'s other drawing exports (`drawPolyline`, `drawHoverTick`, etc.) — those are used by the canvas renderer for things other than the learned outline.

### C. Evaluate apex features — do NOT delete yet

The apex features are different from the outline features above. They process telemetry data to compute apex metrics (timing, distance, surface) — they are per-corner analysis, not track-boundary rendering. However:

- `apexAnnotations` (Phase 03) loads corner definitions from JSON files
- `apexMetrics` (Phase 04) computes apex metrics from telemetry + annotations
- `apexMetricsUi` (Phase 05) renders a metrics table

These currently use the *width-profile pipeline's* `raw_lap_distance_m`, `path_lateral_m`, and `track_edge_m` columns from the parquet. The TUMFTM spike data **does not change the parquet schema** — it's a visual outline only. So the apex features should still work with the existing telemetry data.

**Investigation needed:**

1. Do any apex modules import or depend on `learnedOutline.js` or `learnedBoundariesByLayout`? If yes, sever that dependency without removing apex functionality.
2. Do any apex tests fail after the removals in A and B? If yes, fix the imports/dependencies only — don't reduce apex test coverage.
3. After A and B are clean, verify all three apex feature flags still work by toggling them on in a test and confirming no crash.

**Do NOT remove** the apex feature flags, modules, or tests. They need adaptation, not deletion. Document what adaptation is needed in `learnings.md`.

### D. Clean up stale feature-flag references

After A and B removals, check and clean:

- `web/js/debugHooks.js` — remove dead flag names from the feature-flag validation
- `scripts/test_feature_flag_dropdown.js` — remove dead flag names from the dropdown test
- `package.json` — remove deleted test scripts from the test chain
- Any orphaned `*-test-report/` directories

## Testing expectation

After each removal:

1. Run `bash scripts/test-summary.sh` — all remaining tests must pass.
2. Run `npm run build` — must succeed.
3. Do NOT leave the test suite in a state where deleted test files are still referenced in `package.json`.

## Acceptance criteria

- `mapTrackOutline` flag and all code gated by it are removed.
- `learnedTrackOutline` flag and all code gated by it are removed.
- `learnedOutline.js` is deleted.
- `learnedBoundariesByLayout` is removed from `appState.js` and all consumers.
- No apex feature depends on removed outline code.
- All remaining apex tests still pass.
- `scripts/test_006_track_outline.js` and `scripts/test_learned_outline_rendering.js` are deleted and removed from `package.json`.
- Any stale test-report directories are deleted.
- `npm run build` succeeds.
- `bash scripts/test-summary.sh` shows all remaining tests passing.

## Required end artifacts

- `phases_TUMFTM_based_track_map_outline/cleaning_old_features/learnings.md`
- `phases_TUMFTM_based_track_map_outline/cleaning_old_features/handoff.md`
- Commits on `main` with `refactor:` prefix where appropriate.

## Stop condition

Stop after all removed code is gone, remaining tests are green, the build succeeds, and learnings/handoff are committed. Do not start redeveloping apex features in this phase.