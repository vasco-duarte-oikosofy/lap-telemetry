# Session debrief — Circuit de Barcelona / ginetta-lmp3

18 eligible laps, 16 clean · reference lap 1:36.040 · session best 1:36.759

## Headline

Your best lap was **1:36.759**, 0.719 s off the reference 1:36.040.
Across the 16 clean laps the median was 1:37.661 and the spread 3.041 s (sd 0.821 s); the speed envelope says **0.434 s** is sitting in repeatability alone.
The one to fix is **Twelve** — 0.644 s a lap, on every lap, with a wide spread, 36% of your average 1.801 s gap: *back on the throttle 16 m earlier*.

## Lap by lap

| seg | lap | time | vs reference | vs best | clean |
|---:|---:|---:|---:|---:|:---|
| 1 | 1 | 1:56.605 | +20.565 | +19.846 | traffic |
| 2 | 2 | 1:37.659 | +1.619 | +0.900 | yes |
| 3 | 3 | 1:37.361 | +1.321 | +0.601 | yes |
| 4 | 4 | 1:37.109 | +1.069 | +0.350 | yes |
| 5 | 5 | 1:37.050 | +1.010 | +0.290 | yes |
| 6 | 6 | 1:38.858 | +2.818 | +2.099 | yes |
| 7 | 7 | 1:37.663 | +1.623 | +0.904 | yes |
| 8 | 8 | 1:36.867 | +0.827 | +0.107 | yes |
| 9 | 9 | 1:38.016 | +1.976 | +1.257 | yes |
| 10 | 10 | 1:38.715 | +2.675 | +1.955 | yes |
| 11 | 11 | 1:37.429 | +1.389 | +0.670 | yes |
| 12 | 12 | 1:36.759 | +0.719 | +0.000 | yes |
| 13 | 13 | 1:37.924 | +1.884 | +1.164 | yes |
| 14 | 14 | 1:37.784 | +1.744 | +1.024 | yes |
| 15 | 15 | 1:43.551 | +7.511 | +6.792 | traffic |
| 16 | 16 | 1:39.800 | +3.760 | +3.041 | yes |
| 17 | 17 | 1:37.505 | +1.465 | +0.745 | yes |
| 18 | 18 | 1:38.957 | +2.917 | +2.198 | yes |

## Consistency

| metric | value |
|---|---:|
| clean laps | 16 |
| best | 1:36.759 |
| median | 1:37.661 |
| worst clean | 1:39.800 |
| mean vs reference | +1.801 s |
| spread | 3.041 s |
| standard deviation | 0.821 s |
| speed envelope | 1:36.326 |
| time available | 0.434 s |

The envelope is the fastest speed you reached in every metre of the lap, put end to end in one lap. It is **optimistic** by construction: it assumes the car changes speed instantly, so it is not a target for one lap — it is the size of the prize for repeating what you already did.

## What to change

1. **Twelve** — 0.644 s per lap (every lap, and erratic, 36% of the gap)  
   back on the throttle 16 m earlier
  
   brake release: 89.3 km/h against 109.9 km/h
2. **corner 8** — 0.444 s per lap (every lap, and erratic, 25% of the gap)  
   brake 16 m later
  
   exit: 137.4 km/h against 186.4 km/h
3. **Campsa** — 0.177 s per lap (every lap, and erratic, 10% of the gap)  
   carry 6 km/h more minimum speed
  
   minimum speed: 158.8 km/h against 164.7 km/h

The other 9 corners are in the appendix below.

## Rear stability

- **Repsol** — rear slip reaches 6.51 deg at the apex on segment 6 (lap 6) against the session's 1.74 deg clean-lap baseline and while still on the brake (4.87 deg with the brake applied).
- **No instability detected** at Elf, corner 2, Renault, Seat, corner 7, corner 8. Valid measurements inside the measured window, not a claim that the car is stable everywhere.

## Corners

| corner | apex m | min speed | ref | gear | ref gear | line offset m | verdict |
|---|---:|---:|---:|---:|---:|---:|:---|
| Elf | 842 | 115.3 | 113.0 | 2 | 2 | -0.48 | #12 fix |
| corner 2 | 940 | 137.1 | 141.7 | 2 | 2 | -0.20 | #11 fix |
| Renault | 1167 | 164.4 | 168.0 | 3 | 3 | -0.53 | #7 fix |
| Repsol | 1731 | 107.2 | 101.1 | 2 | 2 | +1.75 | #4 fix |
| Seat | 2143 | 82.2 | 82.8 | 1 | 1 | +0.77 | #9 fix |
| corner 7 | 2568 | 111.5 | 118.8 | 2 | 2 | -0.25 | #6 fix |
| corner 8 | 2850 | 151.6 | 184.8 | 4 | 4 | -1.31 | #2 fix |
| Campsa | 2923 | 158.8 | 164.7 | 4 | 4 | +0.18 | #3 fix |
| La Caixa | 3508 | 86.3 | 81.8 | 1 | 1 | -2.23 | #8 fix |
| Twelve | 3785 | 99.1 | 106.1 | 1 | 1 | -0.16 | #1 fix |
| Thirteen | 4033 | 175.8 | 178.1 | 4 | 3 | -0.30 | #10 fix |
| Fourteen | 4343 | 171.8 | 180.8 | 4 | 4 | -0.72 | #5 fix |

## Excluded laps

| seg | lap | duration | status | reason |
|---:|---:|---:|---|---|
| 0 | 0 | 140.4 s | out-lap | first segment of a stint |
| 19 | 19 | 4.7 s | incomplete | final segment of the session |

## Not measurable

- **ABS activity** (`abs_active`) — only 0 of 147549 samples are recorded, so a duty cannot be computed
- **rear grip fraction (left)** (`grip_fraction_rl`) — the sim publishes mGripFract as a constant 0.0 in every sample of this recording (checked on every LMU session on disk), so it cannot separate a sliding contact patch from grip
- **rear grip fraction (right)** (`grip_fraction_rr`) — the sim publishes mGripFract as a constant 0.0 in every sample of this recording (checked on every LMU session on disk), so it cannot separate a sliding contact patch from grip
- **rear slip angle (left)** (`slip_angle_rl_deg`) — the sim value is atan2 of two contact-patch velocities in the car frame, so it idles at ±180° on a straight and follows steering input (r=+0.52); a tyre slip angle needs the wheel's own heading, and no wheel heading is recorded
- **rear slip angle (right)** (`slip_angle_rr_deg`) — the sim value is atan2 of two contact-patch velocities in the car frame, so it idles at ±180° on a straight and follows steering input (r=+0.52); a tyre slip angle needs the wheel's own heading, and no wheel heading is recorded
- **traction control activity** (`tc_active`) — only 10596 of 147549 samples are recorded, so a duty cannot be computed

## How to read this

- **Reference lap** (1:36.040) is the curated fastest lap for this track and car. Every `vs reference` number is measured against it.
- **Session best** is your own fastest clean lap in this session. `vs best` says how repeatable you were; it says nothing about the target.
- **Clean laps** exclude traffic and mistakes. Only clean laps feed the consistency numbers and the priorities.
- **Excluded laps** were never analysed: an out-lap, an in-lap, a pit stop, an incomplete segment or a broken recording.
- Every number here also exists in the machine-readable `session_20261115T184452Z_circuit-de-barcelona_lmu_race_debrief.json` next to this file.
