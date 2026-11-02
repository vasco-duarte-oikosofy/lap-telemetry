# Paul Ricard 1A / P3 — actual layout, official names and complete flat spans

## Sources

- Official circuit infrastructure page:
  https://www.circuitpaulricard.com/fr/circuit/pistes-et-infrastructures
- Official all-configurations corner plan linked from that page:
  https://www.circuitpaulricard.com/images/2023/10/02/turnlocation.svg
  Rendered copy: official-corner-plan.png.
- Geometry/signals: race lap 10, 106.833862305 s, source session
  session_20261101T190458Z_paul-ricard---1a_lmu_race (frozen 84 closed shards).
  reference-telemetry.png shows position trace with metre labels and real
  speed/throttle/brake/steering signals. No external boundaries were invented.

This is original 1A, not V2-Short or 3A: the first Verrerie bends are shallow
and flat-out, Mistral is uninterrupted (no chicane), and the full double-right
Beausset loop is present. Simulator distance axis is 5696.9 m. The nominal
real circuit length and noisy geometric trace length are NOT that axis.

## Reviewed zones

| ID | Official name (subdivided where necessary) | Start / apex / end m | Side | Target |
|---|---|---|---|---|
| verrerie_1 | S de la Verrerie 1 | 560 / 607 / 710 | left | 100% |
| verrerie_2 | S de la Verrerie 2 | 785 / 852 / 970 | right | 100% |
| hotel_1 | Virage de l'Hôtel 1 | 1102 / 1279 / 1298 | right | reference |
| hotel_2 | Virage de l'Hôtel 2 | 1305 / 1360 / 1405 | left | reference |
| camp | Virage du Camp | 1406 / 1480 / 1496 | right | reference |
| sainte_baume | Virage de la Sainte-Baume | 1544 / 1600 / 1640 | right | reference |
| mistral | Ligne Droite du Mistral (entry bend) | 1780 / 1841 / 1910 | left | 100% |
| signes | Courbe de Signes | 3674 / 3871 / 3880 | right | reference |
| beausset_1 | Double Droite du Beausset 1 | 4053 / 4265 / 4330 | right | reference |
| beausset_2 | Double Droite du Beausset 2 | 4331 / 4394 / 4431 | right | reference |
| bendor | Virage de Bendor | 4569 / 4732 / 4769 | left | reference |
| garlaban | Courbe du Garlaban | 4810 / 4846 / 5070 | right | 100% |
| lac | Virage du Lac | 5082 / 5227 / 5310 | left | reference |
| pont | Virage du Pont | 5311 / 5377 / 5398 | right | reference |

The circuit plan calls the final left bend **Virage du Lac**, not the older
model's Tour label; Garlaban is not "Garalaban". Other layouts were NOT edited.
Signes is a known right-hander and calibrates positive steering as right;
every one of these 14 apex windows agrees with its physical turn direction.

All four flat zones have minimum throttle **1.0**, maximum brake **0.0** over
their whole span. Their apex steering peaks are approximately -0.089, +0.117,
-0.205, +0.095 respectively, confirming actual bends, not straight-line markers.
No zone is degenerate, and no neighbouring zones overlap.

Six raw detector events cannot stand in for these corners. One merges Hotel 1,
Hotel 2 and Camp; another merges the two Beausset apices; the last merges Lac
and Pont. Those are intentionally split from real speed minima/steering changes.
Hotel 1 and Hotel 2 do not become flat targets just because they are split:
reference throttle pickup is partial between those corners (and before Camp).

There are **14 coaching zones**, including two subdivisions of the same
Double Droite du Beausset, not 14 uniquely named official physical turns.
Map numbers follow model ordinals as specified in MAP_TURN_NAMES.md. Do not
mistake them for the all-configurations circuit plan's T-list: T8/T9 are unused
Mistral chicanes here. Full official names stay in model/map data; spoken/map
aliases are independent (map Ste-Baume versus spoken Sainte-Baume).

## Automated render evidence and limits

The built standalone file:// compare paints all 14 named zones and the actual
three-part outline; see compare-outline.png. TinyPedal's real recorded 1A map
was tested at 400/600 px and 0/90 degrees with actual label-vs-labels-off pixel
checks. Every placed label is non-overlapping and on-canvas.

TinyPedal's intentionally larger type degrades on this dense track: 400px/0°
shows 14 labels (Camp number-only); 400px/90° shows 13 (Bendor omitted);
600px shows all 14 in both orientations (Sainte-Baume number-only at 0°).
At 600px/90° all 14 names fit. Those are published small-overlay constraints,
not missing packaged data. Geometry/names were not distorted to hide them;
full name data is present for every zone. Live/by-eye approval remains pending.
