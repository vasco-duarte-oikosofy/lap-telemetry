"""Audit an inventory classification against the telemetry it came from.

This is an *audit*, not a mirror of the classifier: it re-derives every
exclusion's justification from the raw table and asks whether the record
actually supports the stated reason. It exists because two real bugs had the
same shape — a rule confidently discarding a lap on evidence that did not
imply the conclusion:

1. a forward gap in ``lap_number`` (stuck lap 9 after a pause) read as a pit
   exit, discarding the fastest lap of the Lusail session;
2. ``segment_index == 0`` read as a pit exit even when the recording started
   with the car at 210 km/h, discarding the first lap of seven other sessions.

Neither was a wrong number; both were an unjustified classification. The
audit is deliberately generic so the next rule of that shape fails here.

Also provides ``synth_session`` (fabricated telemetry at 50 Hz) and
``random_sessions`` (seeded random sessions) so the invariants are exercised
over rule combinations no hand-written fixture covers.
"""
from __future__ import annotations

import random
import statistics
from typing import Any, Iterator

import pyarrow as pa

from lap_telemetry.parquet_utils import build_segments
from lap_telemetry.lap_signals import (
    FRAME_INTEGRITY_FACTOR,
    PIT_STOP_MIN_S,
    PIT_STOP_SPEED_KPH,
    START_WINDOW_S,
)
from lap_telemetry.session_laps import (
    CLEAN_LAP_RATIO,
    IN_LAP_RATIO,
    PIT_LAP_RATIO,
    RACING_START_SPEED_KPH,
    LapRecord,
    LapStatus,
)

LAP_M = 4000.0
RATE_HZ = 50.0


def synth_session(specs: list[dict]) -> pa.Table:
    """Build a session table from per-segment specs at 50 Hz.

    Each spec: ``lap_number``, ``duration_s``, ``frames``, and optionally
    ``covered_m``, ``stop_s`` (stationary time at the end of the segment),
    ``start_speed`` (speed during the first three seconds), ``valid``.
    """
    lap_number: list[int] = []
    session_time: list[float] = []
    lap_time: list[float] = []
    distance: list[float] = []
    speed: list[float] = []
    valid: list[bool] = []

    start_et = 100.0
    for spec in specs:
        frames = spec["frames"]
        duration = spec["duration_s"]
        covered = spec.get("covered_m", LAP_M)
        stop_s = spec.get("stop_s", 0.0)
        start_speed = spec.get("start_speed", 200.0)
        step = duration / max(1, frames)
        for i in range(frames):
            t = i * step
            lap_number.append(spec["lap_number"])
            lap_time.append(t)
            session_time.append(start_et + t)
            distance.append(covered * i / max(1, frames - 1))
            remaining = duration - t
            if remaining <= stop_s:
                speed.append(0.0)
            elif t < START_WINDOW_S:
                speed.append(start_speed)
            else:
                speed.append(200.0)
            valid.append(spec.get("valid", True))
        start_et += duration

    return pa.table({
        "lap_number": lap_number,
        "lap_time_s": lap_time,
        "session_time_s": session_time,
        "lap_distance_m": distance,
        "speed_kph": speed,
        "lap_valid": valid,
    })


# --- independent derivations (duplicated on purpose) ------------------------


def _segment_rows(records: list[LapRecord]) -> list[tuple[int, int, int]]:
    return [(r.lap_number, r.start_row, r.end_row) for r in records]


def _yardstick(records: list[LapRecord]) -> float:
    durations = [r.duration_s for r in records]
    interior = [d for d in durations[1:-1] if d > 0]
    pool = interior or [d for d in durations if d > 0]
    return statistics.median(pool) if pool else 0.0


def _stationary_s(table: pa.Table, start: int, end: int) -> float:
    speed = table.column("speed_kph").to_pylist()
    clock = table.column("session_time_s").to_pylist()
    longest = 0.0
    run_start: float | None = None
    for i in range(start, end):
        below = speed[i] is not None and float(speed[i]) < PIT_STOP_SPEED_KPH
        if below:
            if run_start is None:
                run_start = float(clock[i])
        elif run_start is not None:
            longest = max(longest, float(clock[i]) - run_start)
            run_start = None
    if run_start is not None:
        longest = max(longest, float(clock[end - 1]) - run_start)
    return longest


def _start_peak_speed(table: pa.Table, start: int, end: int) -> float | None:
    speed = table.column("speed_kph").to_pylist()
    clock = table.column("session_time_s").to_pylist()
    first = clock[start]
    peak: float | None = None
    for i in range(start, end):
        if float(clock[i]) - float(first) >= START_WINDOW_S:
            break
        if speed[i] is not None:
            peak = float(speed[i]) if peak is None else max(peak, float(speed[i]))
    return peak


def audit_classification(
    table: pa.Table,
    records: list[LapRecord],
    *,
    sample_rate_hz: float | None = None,
) -> list[str]:
    """Return one human-readable line per unjustified classification."""
    problems: list[str] = []
    if not records:
        return problems

    names = set(table.schema.names)
    rate = sample_rate_hz
    if rate is None:
        clock = table.column("session_time_s").to_pylist()
        span = float(clock[-1]) - float(clock[0])
        rate = (len(clock) - 1) / span if span > 0 else None

    distances = table.column("lap_distance_m").to_pylist() if "lap_distance_m" in names else None
    lap_length = max((d for d in distances if d is not None), default=0.0) if distances else 0.0
    validity = table.column("lap_valid").to_pylist() if "lap_valid" in names else None
    validity_trusted = validity is not None and len({v for v in validity if v is not None}) > 1
    yardstick = _yardstick(records)
    segments = build_segments(table.column("lap_number").to_pylist())

    # The records must tile the table: no segment lost, none duplicated.
    if len(records) != len(segments):
        problems.append(f"{len(records)} records for {len(segments)} segments")
    for record, segment in zip(records, segments):
        if (record.start_row, record.end_row) != (segment[1], segment[2]):
            problems.append(f"seg {record.segment_index}: record rows do not match the segment")

    eligible = [r for r in records if r.status == LapStatus.ELIGIBLE]
    best = min((r.duration_s for r in eligible), default=None)

    for r in records:
        where = f"seg {r.segment_index} ({r.status})"
        if r.status != LapStatus.ELIGIBLE and not r.reason:
            problems.append(f"{where}: excluded without a reason")
        if r.status == LapStatus.ELIGIBLE and r.reason:
            problems.append(f"{where}: eligible with a reason")

        if r.clean and r.status != LapStatus.ELIGIBLE:
            problems.append(f"{where}: clean flag on a non-eligible lap")
        if r.status == LapStatus.ELIGIBLE and best is not None:
            expected_clean = r.duration_s <= best * CLEAN_LAP_RATIO
            if r.clean != expected_clean:
                problems.append(
                    f"{where}: clean={r.clean} but duration {r.duration_s:.3f} "
                    f"vs best {best:.3f}"
                )

        if r.status == LapStatus.OUT_LAP:
            boundary = r.segment_index == 0 or r.lap_number == 0
            peak = _start_peak_speed(table, r.start_row, r.end_row)
            if not boundary:
                problems.append(f"{where}: no stint boundary justifies an out-lap")
            if peak is not None and peak >= RACING_START_SPEED_KPH:
                problems.append(
                    f"{where}: entered at {peak:.1f} km/h — not a pit exit"
                )

        elif r.status == LapStatus.IN_LAP:
            if yardstick > 0 and r.duration_s >= yardstick * IN_LAP_RATIO:
                problems.append(
                    f"{where}: duration {r.duration_s:.3f} is not below "
                    f"{IN_LAP_RATIO} x {yardstick:.3f}"
                )

        elif r.status == LapStatus.PIT_LAP:
            stopped = _stationary_s(table, r.start_row, r.end_row)
            slow = yardstick > 0 and r.duration_s > yardstick * PIT_LAP_RATIO
            if stopped < PIT_STOP_MIN_S and not slow:
                problems.append(
                    f"{where}: stopped {stopped:.1f} s and duration "
                    f"{r.duration_s:.3f} is inside the band"
                )

        elif r.status == LapStatus.INCOMPLETE:
            is_last = r.segment_index == len(records) - 1
            zone = [float(d) for d in distances[r.start_row:r.end_row] if d is not None] if distances else []
            coverage_fails = bool(zone) and (
                max(zone) < lap_length * 0.80 or min(zone) > lap_length * 0.10
            )
            if not is_last and not coverage_fails:
                problems.append(f"{where}: complete coverage, not the final segment")

        elif r.status == LapStatus.SHORT:
            if not rate or r.duration_s <= 0:
                problems.append(f"{where}: cannot justify without a sample rate")
            else:
                ratio = r.frames / (r.duration_s * rate)
                if 1 / FRAME_INTEGRITY_FACTOR <= ratio <= FRAME_INTEGRITY_FACTOR:
                    problems.append(f"{where}: {r.frames} frames agree with the duration")

        elif r.status == LapStatus.INVALID:
            if not (validity_trusted and validity is not None):
                problems.append(f"{where}: validity column does not discriminate")
            elif not any(v is False for v in validity[r.start_row:r.end_row]):
                problems.append(f"{where}: no invalid frame in the segment")

        elif r.status != LapStatus.ELIGIBLE:
            problems.append(f"{where}: unknown status")

    return problems


# --- seeded random sessions -------------------------------------------------


def _random_specs(rng: random.Random) -> list[dict]:
    count = rng.randint(2, 9)
    specs: list[dict] = []
    lap = rng.choice([0, 1, 5, 9])
    base = rng.uniform(78.0, 82.0)
    for index in range(count):
        roll = rng.random()
        if roll < 0.10:
            lap = 0                              # sim restart
        elif roll < 0.20:
            lap += rng.randint(2, 3)             # gap / stuck numbering
        else:
            lap += 1

        duration = base + rng.uniform(-1.5, 1.5)
        kind = rng.random()
        if index == 0:
            duration = rng.choice([base, base * 1.8, base * 0.3])
        elif kind < 0.12:
            duration = base * rng.uniform(0.2, 0.7)      # in-lap
        elif kind < 0.24:
            duration = base * rng.uniform(1.25, 1.6)     # pit / out-lap crawl

        frames = int(round(duration * RATE_HZ))
        spec: dict[str, Any] = {
            "lap_number": lap,
            "duration_s": duration,
            "frames": frames,
            "start_speed": 200.0 if rng.random() > 0.35 else 0.5,
        }
        if index == 0 or lap == 0 or duration > base * 1.25:
            spec["start_speed"] = 0.5
        if rng.random() < 0.10:
            spec["covered_m"] = LAP_M * rng.uniform(0.1, 0.6)   # truncated
        if rng.random() < 0.10:
            spec["frames"] = max(1, int(frames * rng.choice([0.1, 3.0])))  # corrupt
        if rng.random() < 0.10:
            spec["stop_s"] = rng.uniform(1.2, 9.0)             # pit stop
        if rng.random() < 0.08:
            spec["valid"] = False
        specs.append(spec)
    return specs


def random_sessions(count: int = 60, seed: int = 20260101) -> Iterator[tuple[pa.Table, dict]]:
    """Yield ``(table, specs_context)`` pairs covering awkward rule overlaps."""
    rng = random.Random(seed)
    for _ in range(count):
        specs = _random_specs(rng)
        yield synth_session(specs), {"specs": specs}
