# Entry/Exit Distance Deltas: Brake and Throttle Phase-Transition Comparison

## Problem

The analysis currently detects phase transitions (throttle lift, brake
application, brake release, full throttle) **only on the driver's**
traces. It reports:

- `phase_distance_m` — where the *driver* lifted / braked / released / went full throttle
- `apex_offset_m` — where the driver apexed vs reference apexed (for `minimum_speed` only)

But it cannot say **"you braked 20 m later than reference"** or **"you
got back to full throttle 12 m earlier"** because the reference's phase
transition distances are unknown. This is the most actionable coaching
signal for entry and exit phases.

### What we have now

For `minimum_speed`, `apex_offset_m` already gives:
```json
"apex_offset_m": -9.0   // driver apexed 9 m later than reference
```

For `entry` and `exit` phases, we only have:
```json
"phase_distance_m": 1169.0   // driver released brakes here
```
No reference comparison. We can't say how much earlier or later.

### What we need

For **entry**: `entry_distance_delta_m` = reference entry distance − driver entry distance
- Positive → reference lifted later → driver lifted **earlier** (more cautious)
- Negative → reference lifted earlier → driver lifted **later** (carried more speed in)

For **exit**: `exit_distance_delta_m` = reference exit distance − driver exit distance
- Positive → reference exited later → driver exited **earlier** (better exit)
- Negative → reference exited earlier → driver exited **later** (slower exit)

## Solution

### 1. Extend JS pipeline to resample reference throttle/brake

Add `ref_throttle_norm` and `ref_brake_norm` to the JS pipeline input
and output. The reference pedal traces go through the same
`computeKeepIndices → resample` path as the driver traces.

### 2. Run phase detection on reference traces

Call `find_entry_point()` and `find_exit_points()` using the reference
throttle and brake grids. This produces:
- `ref_entry_idx` — where the reference lifted / braked
- `ref_exit_points` — where the reference released brakes / reached full throttle

### 3. Add `entry_distance_delta_m` and `exit_distance_delta_m` to `CornerLoss`

New fields:
- `entry_distance_delta_m: float | None` — populated for `entry` phase only
  - `ref_entry_idx - driver_entry_idx`
  - Positive = reference lifted later = driver lifted earlier (more cautious)
  - Negative = reference lifted earlier = driver lifted later (carried more speed)

- `exit_distance_delta_m: float | None` — populated for `exit`/`exit_brake`/`exit_throttle` phases
  - `ref_exit_idx - driver_exit_idx`
  - Positive = reference exited later = driver exited earlier (better exit)
  - Negative = reference exited earlier = driver exited later (slower exit)

Also add:
- `reference_phase_distance_m: float | None` — the reference's corresponding phase distance (shared by entry and exit)

### 4. Phase matching for exit

When driver has `exit_brake` / `exit_throttle` and reference has the
same phase types, match by phase name. When one is merged and the
other is split, use the closest matching phase.

### Sign conventions

| Phase | Field | Positive | Negative |
|-------|-------|----------|----------|
| entry | `entry_distance_delta_m` | Driver lifted earlier (cautious) | Driver lifted later (aggressive) |
| exit | `exit_distance_delta_m` | Driver exited earlier (better) | Driver exited later (worse) |

For coaching: the LLM prompt must interpret the sign per phase. A
positive `entry_distance_delta_m` means "you lifted X m earlier than
reference." A positive `exit_distance_delta_m` means "you got back to
full throttle X m earlier than reference." The same sign has opposite
coaching meaning depending on the phase.

### Example: Barcelona turn 5 exit

```json
{
  "phase": "exit",
  "phase_distance_m": 2158.0,
  "exit_distance_delta_m": 10.0,
  "reference_phase_distance_m": 2168.0
}
```

The driver reached full throttle at 2158 m, the reference at 2168 m.
Delta = 2168 − 2158 = +10. Positive = driver exited earlier = better.
The coaching message: "You got back to full throttle 10 m earlier in
turn 5."