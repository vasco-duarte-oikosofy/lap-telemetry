"""Table slicing and lap-duration helpers shared by comparison consumers.

These were inline in ``lap_comparator`` until the session debrief needed to
analyse a specific lap *segment* (a sim restart resets ``lap_number``, so a
lap number is not a unique lap identity). Keeping them here lets the
comparator and the session inventory share one definition of "which table
rows are this lap" and "how long was this lap", instead of two that drift.

Nothing in this module knows about coaching, corners or thresholds.
"""
from __future__ import annotations

import pyarrow as pa

from lap_telemetry.parquet_utils import authoritative_duration, build_segments


_SLOW_LAP_RATIO_THRESHOLD = 1.15
_SLOW_LAP_RATIO_EPSILON = 1e-9


def try_column(table: pa.Table, name: str) -> list[float] | None:
    """Extract a float column; return None when the column is missing.

    ``None`` cells become ``0.0`` so downstream phase detection can stay
    branch-free. Missing *columns* must stay distinguishable from all-zero
    data, hence ``None`` rather than a zero list.
    """
    try:
        raw = table.column(name).to_pylist()
        return [v if v is not None else 0.0 for v in raw]
    except (KeyError, AttributeError):
        return None


def duration_segment_for_lap(
    table: pa.Table,
    lap_number: int | None,
) -> tuple[int, int, int | None, int | None]:
    """Find the segment whose duration should describe this comparison lap.

    Returns ``(start, end, next_start, next_end)``. The next segment is needed
    because the true lap duration is the difference between consecutive
    telemetry lap-start ETs.
    """
    lap_numbers = table.column("lap_number").to_pylist()
    segments = build_segments(lap_numbers)
    if not segments:
        return (0, 0, None, None)

    selected_idx = 0
    if lap_number is not None:
        for idx, (seg_lap_number, _start, _end) in enumerate(segments):
            if seg_lap_number == lap_number:
                selected_idx = idx
                break

    _lap_num, start, end = segments[selected_idx]
    if selected_idx + 1 < len(segments):
        _next_lap, next_start, next_end = segments[selected_idx + 1]
        return (start, end, next_start, next_end)
    return (start, end, None, None)


def segment_duration(
    table: pa.Table,
    segment: tuple[int, int, int | None, int | None],
    *,
    allow_same_segment_scoring: bool = False,
) -> float:
    """Best available duration for a ``duration_segment_for_lap`` tuple."""
    start, end, next_start, next_end = segment
    return authoritative_duration(
        table,
        start,
        end,
        next_start,
        next_end,
        allow_same_segment_scoring=allow_same_segment_scoring,
    )


def is_implausibly_slow_lap(driver_lap_time: float, ref_lap_time: float) -> bool:
    """True when a "lap" is really a pit stop or a safety-car crawl."""
    if driver_lap_time <= 0 or ref_lap_time <= 0:
        return False
    return (
        (driver_lap_time / ref_lap_time)
        > (_SLOW_LAP_RATIO_THRESHOLD + _SLOW_LAP_RATIO_EPSILON)
    )


def strip_stale_boundary_frames(table: pa.Table, lap_length_m: float) -> pa.Table:
    """Drop cross-lap boundary frames that still carry the previous lap.

    The first frame(s) of a new lap sometimes report the previous lap's
    position (distance past half a lap) together with a negative
    ``lap_time_s``. Left in, they trip the head-partial coverage guard and
    produce phantom speeds at turn 1.
    """
    lap_times = table.column("lap_time_s").to_pylist()
    distances = table.column("lap_distance_m").to_pylist()
    keep = [
        not (lt < 0 and ld > lap_length_m * 0.5)
        for lt, ld in zip(lap_times, distances)
    ]
    if all(keep):
        return table
    return table.filter(keep)


def slice_segment(table: pa.Table, start: int, end: int) -> pa.Table:
    """Return the rows ``[start, end)`` of a session table.

    PyArrow's ``slice`` is offset+length, not offset+end; this wrapper keeps
    call sites honest about half-open ranges.
    """
    return table.slice(start, max(0, end - start))
