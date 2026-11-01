#!/usr/bin/env python3
"""Bug 32 — chained corners must not collapse into one.

Monza has turns that touch: ``Roggia 1.s_end_m = 2130`` /
``Roggia 2.s_start_m = 2131`` (same for Ascari 1/2 and 2/3). Every phase
window used to be a fixed offset from one corner's own zone, so:

* ``find_entry_point`` looked back 200 m from Roggia 2's zone start and found
  *Roggia 1's* brake point → the driver was told they braked 200 m too early
  for Roggia 2 (impossible: the whole zone is 78 m long).
* ``find_exit_points`` searched 50 m past Roggia 1's zone end and reported its
  exit inside Roggia 2.
* ``CornerExitDetector`` only fires when the car is outside *all* corners, so
  with a 1 m gap between two zones Roggia 1 was never reported at all.

These tests use a synthetic 3 km lap with two touching corners so the
distances are known and no recorded session is needed.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "product" / "python"))

from lap_telemetry.coach.entry_detection import find_entry_point
from lap_telemetry.coach.exit_detection import find_exit_points
from lap_telemetry.coach.corner_exit_detector import CornerExitDetector
from lap_telemetry.coach.lap_comparator import compare_laps
from lap_telemetry.coach.track_model import Corner, TrackCoachingModel


pass_count = 0
fail_count = 0


def ok(condition: bool, label: str) -> None:
    global pass_count, fail_count
    if condition:
        pass_count += 1
        print(f"  [PASS] {label}")
    else:
        fail_count += 1
        print(f"  [FAIL] {label}")


# ── Synthetic two-corner lap ───────────────────────────────────────────────────
# Corner 1: 1000 → 1200 (apex 1100). Corner 2: 1201 → 1300 (apex 1250).
# They touch, exactly like Roggia 1 / Roggia 2 (2130 / 2131).

LAP_M = 3000
C1 = Corner(id="c1", name="Corner One", s_start_m=1000.0, apex_s_m=1100.0,
            s_end_m=1200.0, apex_side="right")
C2 = Corner(id="c2", name="Corner Two", s_start_m=1201.0, apex_s_m=1250.0,
            s_end_m=1300.0, apex_side="left")


def _interp(d: float, a: float, b: float, va: float, vb: float) -> float:
    if d <= a:
        return va
    if d >= b:
        return vb
    return va + (vb - va) * (d - a) / (b - a)


def _speed_at(d: int, top: float, apex1: float, apex2: float, peak: float,
              mid: float = 160.0) -> float:
    points = [
        (0.0, top), (1000.0, top), (1100.0, apex1), (1200.0, mid),
        (1205.0, peak), (1250.0, apex2), (1300.0, 150.0), (1400.0, 220.0),
        (float(LAP_M - 1), 250.0),
    ]
    for (a, va), (b, vb) in zip(points, points[1:]):
        if a <= d <= b:
            return _interp(d, a, b, va, vb)
    return 250.0


def _write_lap(path: Path, *, top: float, apex1: float, apex2: float, peak: float,
               mid: float, reference: bool) -> None:
    """Write one synthetic lap.

    The driver lifts at 1010 m for corner 1 and only picks up (partly) after
    corner 2 — it never reaches 0.9 throttle in between. The reference reaches
    full throttle at 1150 m and lifts again at 1210 m for corner 2, so its own
    corner-2 entry is detectable at 1210 m.
    """
    dist = [float(d) for d in range(LAP_M)]
    speed = [_speed_at(int(d), top, apex1, apex2, peak, mid) for d in dist]

    times: list[float] = []
    t = 0.0
    for s in speed:
        times.append(t)
        t += 3.6 / s  # seconds per metre

    if reference:
        throttle = [
            1.0 if d < 995 else 0.0 if d < 1150 else 1.0 if d < 1210
            else 0.0 if d < 1261 else 1.0
            for d in dist
        ]
        brake = [0.8 if 1020 <= d <= 1180 else 0.0 for d in dist]
    else:
        throttle = [1.0 if d < 1010 else 0.0 if d < 1271 else 1.0 for d in dist]
        # Brake released at 1216 m — inside corner 2's zone.
        brake = [0.8 if 1020 <= d <= 1215 else 0.0 for d in dist]

    table = pa.table({
        "lap_number": pa.array([0] * LAP_M, pa.int64()),
        "lap_time_s": pa.array(times, pa.float64()),
        "lap_distance_m": pa.array(dist, pa.float64()),
        "speed_kph": pa.array(speed, pa.float64()),
        "throttle_norm": pa.array(throttle, pa.float64()),
        "brake_norm": pa.array(brake, pa.float64()),
        "session_time_s": pa.array([1000.0 + v for v in times], pa.float64()),
    })
    pq.write_table(table, path)


def _model() -> TrackCoachingModel:
    return TrackCoachingModel(
        schema_version="1", track_id="synthetic-chained", layout_id="synthetic",
        lap_length_m=float(LAP_M), corners=[C1, C2],
    )


# ── 1. Entry window must not reach into the previous corner ──────────────────


def test_entry_window_bounded_by_previous_corner() -> None:
    """A chained corner's entry may never be detected before the previous corner ends."""
    n = 1600
    throttle = [1.0] * n
    for i in range(1010, n):
        throttle[i] = 0.3          # never back to full throttle (the real driver)
    speed = [_speed_at(min(i, LAP_M - 1), 250.0, 100.0, 105.0, 165.0) for i in range(n)]

    unbounded, _ = find_entry_point(speed, throttle, None, C2)
    bounded, method = find_entry_point(speed, throttle, None, C2,
                                       min_distance_m=C1.s_end_m)

    ok(unbounded < C1.s_end_m,
       f"without a bound the entry is stolen from corner 1 (entry={unbounded} < {C1.s_end_m:.0f})")
    ok(bounded >= C1.s_end_m,
       f"bounded entry {bounded} >= previous corner end {C1.s_end_m:.0f} (method={method})")


# ── 2. Exit window must not reach into the next corner ───────────────────────


def test_exit_window_bounded_by_next_corner() -> None:
    """A chained corner's exit may never be reported past the next corner's start."""
    n = 1600
    brake = [0.0] * n
    for i in range(1020, 1216):     # brake released at 1216 m, inside corner 2
        brake[i] = 0.8
    throttle = [0.0] * n

    unbounded = find_exit_points(brake, throttle, C1)
    bounded = find_exit_points(brake, throttle, C1, max_distance_m=C2.s_start_m)

    ok(unbounded[0][1] > C2.s_start_m,
       f"without a bound the exit lands inside corner 2 (exit={unbounded[0][1]} > {C2.s_start_m:.0f})")
    ok(bounded[0][1] <= C2.s_start_m,
       f"bounded exit {bounded[0][1]} <= next corner start {C2.s_start_m:.0f}")


# ── 3. compare_laps must wire both bounds (driver and reference) ─────────────


def test_comparator_does_not_steal_chained_corner_entry(tmpdir: Path) -> None:
    """Fact generation: corner 2's entry is never placed in corner 1's braking zone."""
    driver = tmpdir / "driver.parquet"
    reference = tmpdir / "reference.parquet"
    _write_lap(driver, top=250.0, apex1=100.0, apex2=105.0, peak=165.0, mid=155.0,
               reference=False)
    _write_lap(reference, top=245.0, apex1=105.0, apex2=110.0, peak=168.0, mid=162.0,
               reference=True)

    facts = compare_laps(driver, reference, _model(), top_n=50)
    corner2_entries = [c for c in facts.top_losses + facts.top_gains
                       if c.corner_id == "c2" and c.phase == "entry"]

    ok(len(corner2_entries) == 1,
       f"corner 2 has exactly one entry fact (got {len(corner2_entries)})")
    if not corner2_entries:
        return
    entry = corner2_entries[0]
    ok(entry.phase_distance_m >= C1.s_end_m,
       f"entry measured at {entry.phase_distance_m:.0f} m, not before corner 1's end {C1.s_end_m:.0f} m")
    ok(abs(entry.entry_distance_delta_m) <= 20.0,
       f"entry delta {entry.entry_distance_delta_m:+.0f} m is not a phantom ±200 m")


def test_comparator_does_not_push_chained_corner_exit(tmpdir: Path) -> None:
    """Fact generation: corner 1's exit is never reported inside corner 2."""
    driver = tmpdir / "driver.parquet"
    reference = tmpdir / "reference.parquet"
    _write_lap(driver, top=250.0, apex1=100.0, apex2=105.0, peak=165.0, mid=155.0,
               reference=False)
    _write_lap(reference, top=245.0, apex1=105.0, apex2=110.0, peak=168.0, mid=162.0,
               reference=True)

    facts = compare_laps(driver, reference, _model(), top_n=50)
    corner1_exits = [c for c in facts.top_losses + facts.top_gains
                     if c.corner_id == "c1"
                     and c.phase in ("exit", "exit_brake", "exit_throttle")]

    ok(len(corner1_exits) >= 1, f"corner 1 has an exit fact (got {len(corner1_exits)})")
    for fact in corner1_exits:
        ok(fact.phase_distance_m <= C2.s_start_m,
           f"corner 1 {fact.phase} at {fact.phase_distance_m:.0f} m, "
           f"not past corner 2's start {C2.s_start_m:.0f} m")


# ── 4. Exit detector must report both halves of a chained pair ──────────────


def _feed(detector: CornerExitDetector, start_m: int, end_m: int, seconds_per_m: float) -> None:
    for dist in range(start_m, end_m + 1):
        detector.feed(SimpleNamespace(
            lap_distance_m=float(dist),
            lap_number=1,
            session_time_s=dist * seconds_per_m,
            track_name="Synthetic",
            vehicle_name="Test Car",
        ))


def test_exit_detector_emits_both_chained_corners() -> None:
    """Crossing from corner 1 straight into corner 2 must emit an exit for corner 1.

    The global 8 s anti-chatter cooldown still gates rapid-fire notes (it is a
    speech-pacing policy, unchanged by this bug), so the feed is paced at
    0.1 s/m to keep the two exits outside the cooldown.
    """
    detector = CornerExitDetector(track_model=_model())
    events: list = []
    detector.on_corner_exited = events.append
    detector.notify_lap_completed()

    _feed(detector, 990, 1310, 0.1)

    ids = [(e.corner_id, round(e.exit_distance_m)) for e in events]
    ok([i for i, _ in ids] == ["c1", "c2"],
       f"both chained corners reported, got {ids}")
    ok(len(ids) == 2 and ids[0][1] == 1200,
       f"corner 1 reported at its own zone end 1200 m, got {ids[0] if ids else None}")
    ok(len(ids) == 2 and ids[1][1] >= 1300,
       f"corner 2 reported at/just past its zone end 1300 m, got {ids[1] if ids else None}")


def main() -> int:
    print("═══ Bug 32 — chained corners must not collapse ═══\n")

    test_entry_window_bounded_by_previous_corner()
    test_exit_window_bounded_by_next_corner()

    tmpdir = Path(tempfile.mkdtemp(prefix="bug32_"))
    try:
        test_comparator_does_not_steal_chained_corner_entry(tmpdir)
        test_comparator_does_not_push_chained_corner_exit(tmpdir)
    finally:
        for f in tmpdir.glob("*"):
            f.unlink()
        tmpdir.rmdir()

    test_exit_detector_emits_both_chained_corners()

    total = pass_count + fail_count
    print(f"\n  {pass_count}/{total} assertions passed")
    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
