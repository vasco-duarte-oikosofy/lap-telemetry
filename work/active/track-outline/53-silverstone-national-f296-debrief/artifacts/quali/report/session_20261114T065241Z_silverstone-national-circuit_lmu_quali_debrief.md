# Session debrief — Silverstone National Circuit / ferrari-296-gt3

9 eligible laps, 9 clean · reference lap 0:54.295 · session best 0:54.295

## Headline

Your best lap was **0:54.295**, 0.000 s *under* the reference 0:54.295.
Across the 9 clean laps the median was 0:54.764 and the spread 2.115 s (sd 0.659 s); the speed envelope says **0.000 s** is sitting in repeatability alone.
The one to fix is **Copse** — 0.216 s a lap, on every lap, with a wide spread, 31% of your average 0.688 s gap: *carry 6 km/h more speed onto the straight*.

## Lap by lap

| seg | lap | time | vs reference | vs best | clean |
|---:|---:|---:|---:|---:|:---|
| 1 | 1 | 0:56.410 | +2.115 | +2.115 | yes |
| 2 | 2 | 0:55.657 | +1.362 | +1.363 | yes |
| 3 | 3 | 0:55.376 | +1.081 | +1.082 | yes |
| 4 | 4 | 0:54.796 | +0.501 | +0.501 | yes |
| 5 | 5 | 0:54.657 | +0.362 | +0.362 | yes |
| 6 | 6 | 0:54.354 | +0.059 | +0.059 | yes |
| 7 | 7 | 0:54.535 | +0.240 | +0.241 | yes |
| 8 | 8 | 0:54.295 | -0.000 | +0.000 | yes |
| 10 | 10 | 0:54.764 | +0.469 | +0.469 | yes |

## Consistency

| metric | value |
|---|---:|
| clean laps | 9 |
| best | 0:54.295 |
| median | 0:54.764 |
| worst clean | 0:56.410 |
| mean vs reference | +0.688 s |
| spread | 2.115 s |
| standard deviation | 0.659 s |
| speed envelope | 0:54.676 |
| time available | 0.000 s |

The envelope is the fastest speed you reached in every metre of the lap, put end to end in one lap. It is **optimistic** by construction: it assumes the car changes speed instantly, so it is not a target for one lap — it is the size of the prize for repeating what you already did.

## What to change

1. **Copse** — 0.216 s per lap (every lap, and erratic, 31% of the gap)  
   carry 6 km/h more speed onto the straight
  
   brake release: 161.8 km/h against 166.4 km/h
2. **Luffield** — 0.216 s per lap (every lap, and erratic, 31% of the gap)  
   carry 3 km/h more minimum speed and brake 18 m later
  
   minimum speed: 83.1 km/h against 86.1 km/h
3. **Becketts** — 0.184 s per lap (every lap, and erratic, 27% of the gap)  
   brake 36 m later and carry 5 km/h more minimum speed
  
   braking point: 229.4 km/h against 231.9 km/h

The other 3 corners are in the appendix below.

## Corners

| corner | apex m | min speed | ref | gear | ref gear | line offset m | verdict |
|---|---:|---:|---:|---:|---:|---:|:---|
| Copse | 368 | 165.7 | 164.4 | 4 | 4 | -0.40 | #1 fix |
| Maggots | 828 | 224.5 | 226.9 | 5 | 5 | -0.65 | #6 fix |
| Becketts | 1046 | 92.6 | 97.5 | 2 | 2 | -0.40 | #3 fix |
| Brooklands | 1925 | 103.5 | 103.1 | 2 | 2 | +0.77 | #5 fix |
| Luffield | 2092 | 83.1 | 86.1 | 1 | 1 | +0.15 | #2 fix |
| Woodcote | 2469 | 177.4 | 179.0 | 4 | 4 | +1.04 | #4 fix |

## Excluded laps

| seg | lap | duration | status | reason |
|---:|---:|---:|---|---|
| 0 | 0 | 91.2 s | out-lap | first segment of a stint |
| 9 | 9 | 67.1 s | pit-lap | duration 1.22x the session yardstick |
| 11 | 11 | 39.8 s | incomplete | final segment of the session |

## Not measurable

- **ABS activity** (`abs_active`) — only 677 of 34415 samples are recorded, so a duty cannot be computed
- **rear slip angle (left)** (`slip_angle_rl_deg`) — values wrap at ±180° and do not track turn rate or braking; not a slip angle as recorded
- **rear slip angle (right)** (`slip_angle_rr_deg`) — values wrap at ±180° and do not track turn rate or braking; not a slip angle as recorded
- **traction control activity** (`tc_active`) — only 2359 of 34415 samples are recorded, so a duty cannot be computed

## How to read this

- **Reference lap** (0:54.295) is the curated fastest lap for this track and car. Every `vs reference` number is measured against it.
- **Session best** is your own fastest clean lap in this session. `vs best` says how repeatable you were; it says nothing about the target.
- **Clean laps** exclude traffic and mistakes. Only clean laps feed the consistency numbers and the priorities.
- **Excluded laps** were never analysed: an out-lap, an in-lap, a pit stop, an incomplete segment or a broken recording.
- Every number here also exists in the machine-readable `session_20261114T065241Z_silverstone-national-circuit_lmu_quali_debrief.json` next to this file.
