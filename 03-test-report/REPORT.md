# Phase 03 Test Report

Passed: 18
Failed: 0

| Status | Assertion | Detail |
|--------|-----------|--------|
| PASS | mapLegend feature flag is exposed | mapWalkingSkeleton, mapHeatmapSingleLap, mapSAlignment, mapDualRibbon, mapZoomPan, mapLegend, mapHover, mapLinkedHighlight, apexAnnotations, apexMetrics, apexMetricsUi |
| PASS | lap legend overlay exists in DOM |  |
| PASS | lap legend overlay is visible |  |
| PASS | lap legend has two swatches | 2 |
| PASS | ramp legend overlay exists in DOM |  |
| PASS | ramp legend overlay is visible |  |
| PASS | Lap A outer edge has accent color outline | {"r":76,"g":190,"b":241} |
| PASS | Lap A inner edge does NOT have accent color | {"r":13,"g":57,"b":41} |
| PASS | Lap B inner edge does NOT have accent color | {"r":12,"g":32,"b":65} |
| PASS | Lap B outer edge has accent color outline | {"r":248,"g":148,"b":2} |
| PASS | gap between ribbons remains dark | {"r":0,"g":5,"b":9} |
| PASS | ramp left end is colorForNet(-1) | {"r":10,"g":61,"b":145} |
| PASS | ramp middle is colorForNet(0) | {"r":42,"g":51,"b":64} |
| PASS | ramp right end is colorForNet(1) | {"r":15,"g":122,"b":46} |
| PASS | wheel zoom works with legends visible | 1 → 1.1617036742727436 |
| PASS | lap legend has pointer-events: none | none |
| PASS | ramp legend has pointer-events: none | none |
| PASS | phase-03 page screenshot written | 28729 bytes |