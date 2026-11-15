# Qualifying candidate review

Source: `session_20261115T183239Z_circuit-de-barcelona_lmu_quali.parquet`
SHA256: `16e95d33c7edeb5158af778484c5b8a4a4e289138520fcf4257f870ed8d29fed`

| lap | rows | authoritative s | clock span s | distance min/max/end m | all valid | full coverage |
|---:|---:|---:|---:|---|---|---|
| 0 | 6776 | 139.493484 | 135.600 | 269.74/4650.81/4650.81 | True | False |
| 1 | 4895 | 98.144852 | 98.200 | 4.25/4651.75/4651.24 | True | True |
| 2 | 4862 | 97.432281 | 97.400 | 7.95/4660.25/4652.23 | True | True |
| 3 | 4828 | 96.774109 | 96.800 | 5.83/4653.18/4651.82 | True | True |
| 4 | 4790 | 96.039978 | 96.000 | 7.47/4652.84/4647.33 | True | True |
| 5 | 5447 | 109.363586 | 109.400 | 4.97/4652.63/4652.63 | True | True |
| 6 | 4582 | 91.518066 | 91.400 | 7.25/4653.58/4295.19 | True | False |
| 7 | 349 | 0.000000 | 0.000 | 4295.19/4295.19/4295.19 | True | False |

Winner: lap 4, 96.039978 s, rows [21361, 26151), 4790 rows.
Lap 6 ends 358 m before its recorded peak; its 91.518 s is not a complete lap.

Detector: `throttle_brake_v1`. Zones below use the existing curated model.

| id | curated entry/apex/exit | detected entry/apex/exit | maximum change m | min speed kph | min throttle | max brake |
|---|---|---|---:|---:|---:|---:|
| t1 | [820.0, 842.0, 869.0] | [653.0, 845, 872.0] | 167.0 | 113.04 | 0.000 | 0.414 |
| t2 | [909.0, 940.0, 972.0] | None | None | 141.74 | 0.659 | 0.000 |
| t3 | [1081.0, 1163.0, 1167.0] | [1073.0, 1167, 1172.0] | 8.0 | 167.99 | 0.278 | 0.000 |
| t4 | [1708.0, 1731.0, 1775.0] | [1593.0, 1729, 1784.0] | 115.0 | 101.13 | 0.000 | 0.328 |
| t5 | [2093.0, 2143.0, 2166.0] | [1988.0, 2137, 2169.0] | 105.0 | 82.76 | 0.000 | 0.204 |
| t6 | [2518.0, 2568.0, 2575.0] | [2436.0, 2555, 2595.0] | 82.0 | 118.82 | 0.000 | 0.327 |
| t7 | [2832.0, 2850.0, 2850.0] | None | None | 184.58 | 0.000 | 0.161 |
| t8 | [2851.0, 2923.0, 2925.0] | [2821.0, 2920, 2927.0] | 30.0 | 164.68 | 0.000 | 0.123 |
| t9 | [3496.0, 3508.0, 3525.0] | [3332.0, 3514, 3544.0] | 164.0 | 81.83 | 0.000 | 0.229 |
| t10 | [3782.0, 3785.0, 3846.0] | [3675.0, 3769, 3867.0] | 107.0 | 106.44 | 0.467 | 0.000 |
| t11 | [3989.0, 4033.0, 4034.0] | [4021.0, 4080, 4087.0] | 53.0 | 178.13 | 0.644 | 0.000 |
| t12 | [4337.0, 4343.0, 4343.0] | [4226.0, 4350, 4378.0] | 111.0 | 180.76 | 0.386 | 0.000 |

Decision: refresh only t3 (8/4/5 m entry/apex/exit changes). Preserve all other
eleven complete corner objects with --preserve-geometry, keeping a 40 m guard.
t2 and t7 are secondary turns without independent detected events. t8 would
start at 2821 m and overlap retained t7 ending at 2850 m. The other eight
matches exceed 40 m (mostly full-braking-event starts versus curated tight
corner windows); t11 also shifts apex by 47 m. The original windows still
contain the recorded corner controls/speed features. Preserve their reviewed
definitions rather than silently broadening or merging them on a PB refresh.
No --allow-unmatched, raised tolerance, renaming or reclassification is used.

The shared 14-turn Barcelona outline is Ferrari-model-backed, not this
12-corner P3 model. Leave map anchors and TinyPedal assets unchanged.
