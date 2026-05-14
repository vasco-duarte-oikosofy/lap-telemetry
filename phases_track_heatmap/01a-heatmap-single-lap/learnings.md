# Phase 01a — Learnings

- The existing `main.js` was already above the hard file ceiling, so this phase extracted panel configuration and debug hooks into focused modules before finishing.
- Browser-module tests can import `/js/colorRamp.js` and `/js/trackHeatmapMap.js` directly from the shared test server, avoiding full file-upload flows for unit and synthetic canvas checks.
- Drawing the ribbon in screen space keeps Phase 01a simple and makes the width constant for the current static fitted view; Phase 2 can revisit transform handling for zoom/pan.
