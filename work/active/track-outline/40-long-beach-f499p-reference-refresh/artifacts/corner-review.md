# Reviewed geometry refresh

New guarded reference: lap 7, **74.871093750 s**, replacing **75.888671875 s**
(lap 10 of the earlier recording). Exact gain **1.017578125 s**.
All 3731 selected rows are valid. Full session scan is in session-scan.txt.

| Turn | Old start / apex / end (m) | New start / apex / end (m) | Policy | Largest move |
|---|---|---|---|---:|
| 1 | 534 / 730 / 753 | 549 / 729 / 749 | Refreshed | 15 m |
| 2 | 821 / 909 / 925 | 819 / 910 / 935 | Refreshed | 10 m |
| 3 | 940 / 950 / 990 | 940 / 950 / 990 | Preserved flat | 0 m |
| 4 | 998 / 1063 / 1071 | 996 / 1045 / 1092 | Refreshed | 21 m |
| 5 | 1136 / 1204 / 1222 | 1136 / 1203 / 1224 | Refreshed | 2 m |
| 6 | 1472 / 1606 / 1644 | 1484 / 1612 / 1642 | Refreshed | 12 m |
| 7 | 1680 / 1725 / 1760 | 1680 / 1725 / 1760 | Preserved flat | 0 m |
| 8 | 1799 / 1920 / 1943 | 1796 / 1929 / 1935 | Refreshed | 9 m |
| 9 | 2396 / 2540 / 2567 | 2392 / 2543 / 2570 | Refreshed | 4 m |
| 10 | 2620 / 2690 / 2760 | 2620 / 2690 / 2760 | Preserved left-hand split | 0 m |
| 11 | 2761 / 2821 / 2834 | 2761 / 2821 / 2834 | Preserved right hairpin split | 0 m |

The new lap confirms the retained flat geometry, not just its old flags:

- T3, 940–990 m: 79 raw rows; minimum throttle 1.0, maximum brake 0.0,
  mean steering -0.10546 (left).
- T7, 1680–1760 m: 93 rows; minimum throttle 1.0, maximum brake 0.0,
  mean steering -0.06002 (left).
- T10 zone mean steering -0.20447 (left); T11 +0.62062 (right).
  The raw detector again merges these into one event (apex 2828 m), so retaining
  the reviewed split is deliberate. Its 2828 m minimum is inside the T11 zone.

The unsafe default preview would let T3 steal T4, shift T4 onto T5, and let T10
steal T11. Explicit preservation leaves those events available to their true
neighbours. Seven matched corners pass the 25 m guard; the largest change is
T4 exit (+21 m). All corner fields other than those seven geometric triples
are unchanged; all four retained corner dictionaries are byte-value equivalent.

Map anchors were recomputed from this new lap using the updated apices. The
500-point centerline and both boundary arrays remain exactly unchanged. Their
original geometry source is pinned to Git revision 90c6e6e; current turn-anchor
provenance points at the new reference. TinyPedal fractions use the unchanged
3185.3 m simulator axis and only Long Beach's packaged file was republished.
