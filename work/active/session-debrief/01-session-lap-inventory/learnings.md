# Learnings — Slice 01: session lap inventory

- **The live coach's slow-lap guard is too loose for a debrief.** 1.15x
  (`is_implausibly_slow_lap`) is fine for "don't speak a nonsense summary",
  but a pit-stop lap of 90.7 s against a 79.5 s field is 1.14x and would have
  been analysed as a flying lap. Pit stops are now detected directly: a car
  below 3 km/h for a second or more. Duration alone cannot separate a pit lap
  from a traffic lap, and they need different treatment.
- **`lap_valid` is a per-frame column with per-session reliability.** Two real
  recordings disagree in opposite directions: one is all-`True` including an
  8896 s pit segment, another is all-`False` across laps that are obviously
  valid. Honouring it unconditionally deletes whole sessions. `classify_laps`
  only trusts the column when it contains both values, and reports `unknown`
  otherwise.
- **Frame count and lap duration can disagree badly in a committed fixture.**
  Segment 2 of the Paul Ricard session has 6235 frames (~124.7 s of wall time)
  but a 79.9 s authoritative duration. It is a real lap. So the integrity rule
  uses a 2x factor on purpose — tightening it to catch that 1.56x mismatch
  would reject a good lap. The rule exists for the other extreme: a
  10838-frame segment claiming 0.548 s.
- **The "last segment of the session" rule has to beat the data.** The final
  segment usually looks complete on distance, but its duration is derived from
  a next-segment lap-start ET that does not exist. `summary.py` already treats
  first and last as untimed; the inventory agrees and says why.
- **`--list` must not need a reference lap.** That is why the duration band is
  anchored on the median interior lap (a "session yardstick") rather than the
  curated reference. The median survives one 21.9 s in-lap, one 119 s pit lap
  and a 148-minute idle segment in the same file.
- **`pyarrow.Table.slice(offset, length)` is not `slice(start, end)`.** The
  new `slice_segment` wrapper exists only so slice 02 cannot get this wrong at
  a call site.
- **The hard line ceiling did its job.** `lap_comparator.py` was 422/437 and
  the segment work would have breached it. Extracting the table helpers first
  left it at 357 and made the inventory module a clean consumer instead of a
  copy of the comparator's internals.
- **Synthetic tables must be built at 50 Hz.** The first version of the test
  helper produced 10 Hz frames; the derived sample rate then came out at ~30 Hz
  and the frame-integrity rule silently stopped meaning anything. Tests that
  fabricate telemetry need to fabricate it at the real rate.
- **Four full-suite failures on this machine are pre-existing.** Verified by
  stashing this slice and re-running: `test_lap_duration_telemetry`,
  `test_lap_duration_surfaces` (need untracked recordings under `sessions/`),
  `test_turn_labels_parity` (needs a `../tinypedal/.venv` checkout) and
  `test_turn_labels_scale` (160/161 named turns). None are caused by the
  debrief work.
