"""Per-segment measurements used to classify laps.

Everything here answers a question about *one* contiguous segment, using only
the signals the recorder wrote: how long was it, how fast did the car enter it,
did the car stand still, does the frame count agree with the duration, and is
the sim's validity flag usable at all.

These are the raw measurements; the classification rules that combine them live
in ``session_laps``.
"""
from __future__ import annotations

import statistics
from typing import Any

import pyarrow as pa

from lap_telemetry.parquet_utils import authoritative_duration


# A car below this speed for this long is in the pit lane, not racing.
PIT_STOP_SPEED_KPH = 3.0
PIT_STOP_MIN_S = 1.0

# How long after a segment starts counts as "the entry".
START_WINDOW_S = 3.0

# Frame count must agree with the lap duration within this factor; outside it
# the duration or the row count is broken and the lap cannot be trusted.
FRAME_INTEGRITY_FACTOR = 2.0


def column_values(table: pa.Table, name: str) -> list[Any] | None:
    """Return a column as a Python list, or ``None`` when it is absent.

    ``None`` is meaningful: a missing channel must stay distinguishable from a
    channel that happens to be all zeroes.
    """
    if name not in table.schema.names:
        return None
    return table.column(name).to_pylist()


def sample_rate_hz(table: pa.Table) -> float | None:
    """Derive the recording rate from the session clock, if present."""
    clock = column_values(table, "session_time_s")
    if not clock or len(clock) < 2:
        return None
    span = float(clock[-1]) - float(clock[0])
    if span <= 0:
        return None
    return (len(clock) - 1) / span


def stationary_seconds(
    speed: list[Any] | None,
    clock: list[Any] | None,
    start: int,
    end: int,
) -> float:
    """Longest continuous stretch below pit-lane speed, in seconds."""
    if speed is None or clock is None:
        return 0.0
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


def entry_peak_speed(
    speed: list[Any] | None,
    clock: list[Any] | None,
    start: int,
    end: int,
) -> float | None:
    """Peak speed during the first ``START_WINDOW_S`` of a segment.

    A pit exit crawls for the whole window; a flying lap is already at racing
    speed. ``None`` means the channels needed to answer are missing.
    """
    if speed is None or clock is None or start >= end:
        return None
    first = clock[start]
    if first is None:
        return None
    peak: float | None = None
    for i in range(start, end):
        moment = clock[i]
        value = speed[i]
        if moment is None or value is None:
            continue
        if float(moment) - float(first) >= START_WINDOW_S:
            break
        velocity = float(value)
        peak = velocity if peak is None else max(peak, velocity)
    return peak


def segment_durations(
    table: pa.Table,
    segments: list[tuple[int, int, int]],
) -> list[float]:
    """Authoritative duration of every segment."""
    durations: list[float] = []
    for idx, (_lap, start, end) in enumerate(segments):
        if idx + 1 < len(segments):
            _nl, next_start, next_end = segments[idx + 1]
            durations.append(authoritative_duration(table, start, end, next_start, next_end))
        else:
            durations.append(authoritative_duration(table, start, end))
    return durations


def yardstick_seconds(durations: list[float]) -> float:
    """Median interior lap duration — out/in/pit outliers do not move it."""
    interior = [d for d in durations[1:-1] if d > 0]
    pool = interior or [d for d in durations if d > 0]
    return statistics.median(pool) if pool else 0.0


def validity_column(table: pa.Table) -> tuple[list[Any] | None, bool]:
    """Return ``(lap_valid, discriminates)``.

    Real recordings exist that are all-``True`` including a pit segment, and
    all-``False`` across valid laps. A constant column carries no information
    and must not be trusted.
    """
    values = column_values(table, "lap_valid")
    if values is None:
        return None, False
    return values, len({v for v in values if v is not None}) > 1
