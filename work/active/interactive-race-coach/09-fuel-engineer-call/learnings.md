# Slice 09 — Learnings

## Gating on computed facts, not raw frames

The `LiveFuelFactGenerator` receives raw frames but immediately converts them
to `FuelFacts` before applying any filtering. This keeps the condition logic
purely in terms of the domain model (status, margins) rather than raw telemetry,
which makes testing with `_FakeFuelFactGenerator` straightforward: inject canned
facts, verify the gate logic independently of `compute_fuel_facts()`.

## The ≤ 3-lap margin check needs direction

The spec says "laps_of_fuel_remaining and race_laps_remaining differ by ≤ 3",
but a driver with 10 laps of fuel and 8 laps to go doesn't need a warning.
The implemented check is `race_laps_remaining - laps_of_fuel_remaining <= 3`,
i.e. the car is running *close to empty relative to the race distance*. A
large fuel surplus correctly produces no call.

## fuel_calls is a bool, not a CoachMode

Adding a separate boolean rather than a new CoachMode keeps backward
compatibility: existing `--coach-mode` flags are unaffected. The fuel call
fires independently of whether the session is LAP, TURN, or ALL mode.

## LapCompleted already carries frames

`LapDetector._emit_lap_completed` freezes `list(self.current_lap_frames)` into
`LapCompleted.frames` before emitting the event. `CoachTap._on_lap_completed`
receives them directly via `event.frames` — no need to access
`self._detector.current_lap_frames` as a fallback.
