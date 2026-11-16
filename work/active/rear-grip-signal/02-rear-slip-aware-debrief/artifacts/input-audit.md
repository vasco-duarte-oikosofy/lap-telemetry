# Planning audit — latest Silverstone National P3 race

Input: `sessions/session_20261114T190410Z_silverstone-national-circuit_lmu_race.parquet`
Sidecar identifies `DKR Engineering #4:ELMS25`, Silverstone National Circuit,
race, 2026-11-14 19:04:10 UTC. The catalog resolves this car to `ginetta-lmp3`.

Read-only PyArrow inspection during slice preparation: 239,401 rows. Each of
these seven columns has 239,401 non-null samples:

| Column | Minimum | Maximum | Distinct values |
|---|---:|---:|---:|
| `grip_fraction_rl` | 0 | 0 | 1 |
| `grip_fraction_rr` | 0 | 0 | 1 |
| `wheel_ground_vel_lat_rl` | -2.948266 | 26.438931 | 95,895 |
| `wheel_ground_vel_lon_rl` | -69.667747 | 4.422362 | 95,470 |
| `wheel_ground_vel_lat_rr` | -3.053487 | 26.348495 | 95,875 |
| `wheel_ground_vel_lon_rr` | -69.610100 | 5.022150 | 95,454 |
| `yaw_rate_radps` | -1.733370 | 1.600647 | 96,870 |

These are whole-file ranges, including non-driving samples, **not** corner
measurements, validity checks or a claim of a slide. Non-null does not mean
physically validated. Constant-zero grip channels cannot independently confirm
rear stability. The varying ground-velocity/yaw fields are candidate evidence
for slice 01's calibration gates, not permission for slice 02 to bypass them.

## Existing debrief behavior

The saved debrief has 34 eligible laps, 32 clean, best 50.763 s, reference
50.392 s. Becketts advice is "hold the brake 20 m longer" (0.257 s recurring
loss; brake-release speed 104.6 vs 109.0 km/h).

The report lists both legacy rear slip-angle channels as unmeasurable. Product
code still does not consume the seven newer channels. `session_brief` does not
inject measured rear-slip facts; `session_priorities.suggest_change` uses
phase/gear/speed/trail comparisons without a rear-instability constraint.

The mission's slice-01 handoff predates this session and says a new recording
is required. A newer recording now exists; its calibration and a labelled
slide/control comparison remain unproven. No driver-labelled Silverstone slide
was supplied in this conversation.

## Reproduce the channel audit

From the repository root, use the project's Python interpreter:

```python
import pyarrow.parquet as pq
import pyarrow.compute as pc

path = "sessions/session_20261114T190410Z_silverstone-national-circuit_lmu_race.parquet"
names = ["grip_fraction_rl", "grip_fraction_rr",
         "wheel_ground_vel_lat_rl", "wheel_ground_vel_lon_rl",
         "wheel_ground_vel_lat_rr", "wheel_ground_vel_lon_rr",
         "yaw_rate_radps"]
table = pq.read_table(path, columns=names)
for name in names:
    col = table[name]
    print(name, len(col) - col.null_count, pc.min_max(col).as_py(),
          pc.count_distinct(col).as_py())
```

No session, curated data, production code, model configuration or existing
debrief output was changed by this planning audit.
