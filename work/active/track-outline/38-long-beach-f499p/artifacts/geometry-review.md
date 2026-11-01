# Official numbering and geometry review

## Sources

- Official organiser circuit map: https://www.gplb.com/circuit-map
- Map image served by that page at review time (2027 event edition):
  https://cdn.prod.website-files.com/632dd22ed2e44b7de90774a3/6ac96520fc56c365a8cebfd6_2027-Circuit-Map.jpg
- Official numbered layout: 1–11. Sponsor/hospitality labels change by year;
  stable official Turn 1 … Turn 11 names are retained rather than inventing names.
- Layout checked against the recorded LMU position trace. Apex sides calibrated
  from negative steering at known left Turn 1; Turn 8 and Turn 11 are right.
- No compatible external width data exists in this checkout. Outline uses
  reference position geometry and a synthetic 5 m shell, not actual street walls.

## Reference selection

- Guard-approved lap 10: 75.888671875 s (filename rounds to 1:15.889), 3782 rows.
- Lap 4 displays 1:15.735 but contains -203.8 m garage teleport frames and
  reaches only 1217.7 m of the 3185.3 m lap. Rejected, never exported.
- All reference-folder validation passes: 33 references, zero failures.

## Per-turn review

| Official turn | Start / apex / end (m) | Side | Target | Mean steering near apex | Mean speed near apex |
|---|---|---|---|---:|---:|
| Turn 1 | 534 / 730 / 753 | left | reference-driven | -0.292 | 98.7 km/h |
| Turn 2 | 821 / 909 / 925 | right | reference-driven | 0.470 | 64.2 km/h |
| Turn 3 | 940 / 950 / 990 | left | 100% (flat) | -0.135 | 99.3 km/h |
| Turn 4 | 998 / 1063 / 1071 | right | reference-driven | 0.206 | 87.4 km/h |
| Turn 5 | 1136 / 1204 / 1222 | right | reference-driven | 0.307 | 88.6 km/h |
| Turn 6 | 1472 / 1606 / 1644 | left | reference-driven | -0.235 | 86.3 km/h |
| Turn 7 | 1680 / 1725 / 1760 | left | 100% (flat) | -0.084 | 155.8 km/h |
| Turn 8 | 1799 / 1920 / 1943 | right | reference-driven | 0.296 | 98.9 km/h |
| Turn 9 | 2396 / 2540 / 2567 | right | reference-driven | 0.287 | 99.3 km/h |
| Turn 10 | 2620 / 2690 / 2760 | left | reference-driven | -0.417 | 113.4 km/h |
| Turn 11 | 2761 / 2821 / 2834 | right | reference-driven | 1.000 | 37.5 km/h |

The generator found only 8 braking events (`raw-detection.txt`). Flat T3 and
T7 were added from their steering/position geometry, with real spans (50 m
and 80 m) and full-throttle/no-brake confirmation. The combined last event
was split into left T10 (2620/2690/2760 m) and right hairpin T11
(2761/2821/2834 m). No flat turn is a zero-width marker or a borrowed apex.

The screenshot is automated render evidence, not a pixel golden or user live
approval. It shows the committed reference replayed under the source session
filename in the built standalone file:// bundle, exercising actual filename-only
track resolution and map rendering.
