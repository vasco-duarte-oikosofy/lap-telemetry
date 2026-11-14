# Bug 36 — learnings

## The wrap is the data, not a defect

`lap_distance_m` is the sim's own `mLapDist`: it starts at whatever value the
axis had at the lap boundary (≈ track length) and wraps to ~0 shortly after the
start/finish line. Every committed reference lap in
`product/data/reference-laps/` has this shape (first row 4271–5798 m, min ≈ 0),
and `docs/specs/MAP_TURN_NAMES.md` already documents it for the turn-label bake,
which rolls the arrays at the single wrap point.

Consequence: a recorder-side "fix" is impossible to cash in. It would not repair
existing recordings, the curated reference laps, or the artifacts attached to
this bug. Any consumer that walks rows in file order must be written as if the
axis were an unordered set of distances.

## Two bugs were hiding in one function

`_trail_depth()` had two independent faults, and the first one masked the second:

1. `break` on the first row with `distance > end_m` — on a wrapped lap that is
   row 0, so the loop body never ran (89% of calls in the reported session).
2. The fallback `return end_m - apex_m` — "still on the brake at the bound" is a
   *lower bound we cannot see*, but it was returned as a measurement, and it is
   plausibly sized (13–59 m), so nothing downstream questioned it.

Fixing only (1) would have left the fallback firing for genuinely unmeasurable
corners; fixing only (2) would have made every wrapped corner `None`. Both had
to go.

## A passing test was asserting the bug

`test_session_corner_extras.py` asserted `tour.trail_brake_depth_m > 20` on the
Paul Ricard reference. That passed only through the fallback: the real trace has
`brake_norm == 0.0` from 0.01 m past la Tour's apex, i.e. the reference is
*off* the brake at the apex. The test had to be rewritten to the true value
(`< 2 m`). Lesson: when a number is only produced by a fallback, the test
covering it is testing the fallback, not the behaviour.

## `distance <= apex` is safe across the wrap

Filtering samples by distance (`distance <= apex` for "braked on the way in",
`apex < distance <= bound` for the trail window) is correct even on a wrapped
lap, because the axis is still a bijection onto the lap: the samples with small
distance are the ones driven *after* the wrap. Only *row order* is unreliable.
That is why the minimal fix is a sort, not a rotation of the arrays.

## Not fixed here

- Six laps of the reported session report `brake_peak = 0.0` at Repsol although
  the trace is non-zero; the bug doc guesses the same family of row-order /
  entry-detection assumptions. Not investigated — `_indices_in()` is already
  order-independent, so the cause is elsewhere (likely the detected entry
  landing past the apex and the `entry_m >= apex_m` fallback).
- Windows that straddle the wrap (a corner within a few metres of the
  start/finish line, where `apex < bound` fails because the bound wrapped to a
  small number) return `None`. The corner models do not place corners across
  the line today, so this is left alone.
