# Session debrief — Silverstone National Circuit / ginetta-lmp3

16 eligible laps, 15 clean · reference lap 0:50.392 · session best 0:50.392

## Headline

Your best lap was **0:50.392**, 0.000 s off the reference 0:50.392.
Across the 15 clean laps the median was 0:50.782 and the spread 1.937 s (sd 0.592 s); the speed envelope says **0.000 s** is sitting in repeatability alone.
The one to fix is **Becketts** — 0.376 s a lap, on every lap, with a wide spread, 59% of your average 0.636 s gap: *hold the brake 14 m longer*.

## Lap by lap

| seg | lap | time | vs reference | vs best | clean |
|---:|---:|---:|---:|---:|:---|
| 1 | 1 | 0:52.329 | +1.937 | +1.937 | yes |
| 2 | 2 | 0:51.596 | +1.204 | +1.203 | yes |
| 3 | 3 | 0:52.049 | +1.657 | +1.657 | yes |
| 4 | 4 | 0:51.464 | +1.072 | +1.072 | yes |
| 5 | 5 | 0:51.242 | +0.850 | +0.850 | yes |
| 6 | 6 | 0:50.782 | +0.390 | +0.390 | yes |
| 7 | 7 | 0:50.858 | +0.466 | +0.466 | yes |
| 8 | 8 | 0:53.297 | +2.905 | +2.905 | traffic |
| 9 | 9 | 0:51.355 | +0.963 | +0.963 | yes |
| 10 | 10 | 0:50.415 | +0.023 | +0.023 | yes |
| 11 | 11 | 0:50.516 | +0.124 | +0.124 | yes |
| 12 | 12 | 0:50.526 | +0.134 | +0.134 | yes |
| 13 | 13 | 0:50.710 | +0.318 | +0.318 | yes |
| 14 | 14 | 0:50.602 | +0.210 | +0.210 | yes |
| 15 | 15 | 0:50.587 | +0.195 | +0.195 | yes |
| 16 | 16 | 0:50.392 | +0.000 | +0.000 | yes |

## Consistency

| metric | value |
|---|---:|
| clean laps | 15 |
| best | 0:50.392 |
| median | 0:50.782 |
| worst clean | 0:52.329 |
| mean vs reference | +0.636 s |
| spread | 1.937 s |
| standard deviation | 0.592 s |
| speed envelope | 0:50.443 |
| time available | 0.000 s |

The envelope is the fastest speed you reached in every metre of the lap, put end to end in one lap. It is **optimistic** by construction: it assumes the car changes speed instantly, so it is not a target for one lap — it is the size of the prize for repeating what you already did.

## What to change

1. **Becketts** — 0.376 s per lap (every lap, and erratic, 59% of the gap)  
   hold the brake 14 m longer
  
   brake release: 101.6 km/h against 110.4 km/h
2. **Copse** — 0.162 s per lap (every lap, and erratic, 26% of the gap)  
   hold the brake 26 m past the apex and brake 9 m later
  
   throttle: 192.5 km/h against 202.8 km/h
3. **Brooklands** — 0.115 s per lap (every lap, and erratic, 18% of the gap)  
   hold the brake 32 m longer and carry 2 km/h more speed onto the straight
  
   brake release: 112.1 km/h against 118.2 km/h

The other 2 corners are in the appendix below.

## Corners

| corner | apex m | min speed | ref | gear | ref gear | line offset m | verdict |
|---|---:|---:|---:|---:|---:|---:|:---|
| Copse | 359 | 193.2 | 201.0 | 5 | 5 | -0.49 | #2 fix |
| Maggots | 828 | 240.1 | 243.3 | 5 | 5 | -0.42 | — |
| Becketts | 1068 | 103.9 | 108.5 | 2 | 2 | +0.00 | #1 fix |
| Brooklands | 1921 | 115.0 | 115.7 | 2 | 2 | +0.00 | #3 fix |
| Luffield | 2102 | 92.5 | 93.5 | 1 | 1 | -0.03 | #4 fix |
| Woodcote | 2469 | 188.8 | 190.6 | 4 | 4 | -0.33 | #5 fix |

## Excluded laps

| seg | lap | duration | status | reason |
|---:|---:|---:|---|---|
| 0 | 0 | 100.8 s | out-lap | first segment of a stint |
| 17 | 17 | 25.6 s | in-lap | duration 0.50x the session yardstick |
| 18 | 18 | 4.5 s | incomplete | final segment of the session |

## Not measurable

- **ABS activity** (`abs_active`) — only 0 of 49626 samples are recorded, so a duty cannot be computed
- **rear slip angle (left)** (`slip_angle_rl_deg`) — values wrap at ±180° and do not track turn rate or braking; not a slip angle as recorded
- **rear slip angle (right)** (`slip_angle_rr_deg`) — values wrap at ±180° and do not track turn rate or braking; not a slip angle as recorded
- **traction control activity** (`tc_active`) — only 1952 of 49626 samples are recorded, so a duty cannot be computed

## How to read this

- **Reference lap** (0:50.392) is the curated fastest lap for this track and car. Every `vs reference` number is measured against it.
- **Session best** is your own fastest clean lap in this session. `vs best` says how repeatable you were; it says nothing about the target.
- **Clean laps** exclude traffic and mistakes. Only clean laps feed the consistency numbers and the priorities.
- **Excluded laps** were never analysed: an out-lap, an in-lap, a pit stop, an incomplete segment or a broken recording.
- Every number here also exists in the machine-readable `session_20261111T185406Z_silverstone-national-circuit_lmu_practice_debrief.json` next to this file.
