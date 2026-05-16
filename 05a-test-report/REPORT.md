# Phase 05a Test Report

Passed: 12
Failed: 0

| Status | Assertion | Detail |
|--------|-----------|--------|
| PASS | mapLinkedHighlight feature flag is exposed | mapWalkingSkeleton, mapHeatmapSingleLap, mapSAlignment, mapDualRibbon, mapZoomPan, mapLegend, mapHover, mapLinkedHighlight, apexAnnotations, apexMetrics, apexMetricsUi |
| PASS | start tick has bright pixels at s=400 | 23 bright pixels at x=203 |
| PASS | end tick has bright pixels at s=800 | 23 bright pixels at x=391 |
| PASS | pixel inside highlight at throttle zone stays green-dominant | {"r":60,"g":112,"b":75} |
| PASS | no visibleRange renders identically to baseline (no highlight) | 0 pixels differed |
| PASS | full-lap visibleRange is a no-op | 0 pixels differed |
| PASS | highlight render completes within 100ms | 1.80 ms |
| PASS | start tick at 500x200 is within 1px of expected s=400 position | found 202, expected 203 |
| PASS | end tick at 500x200 is within 1px of expected s=800 position | found 390, expected 391 |
| PASS | start tick at 300x150 is within 1px of expected s=400 position | found 122, expected 123 |
| PASS | end tick at 300x150 is within 1px of expected s=800 position | found 230, expected 231 |
| PASS | phase-05a page screenshot written | 31816 bytes |