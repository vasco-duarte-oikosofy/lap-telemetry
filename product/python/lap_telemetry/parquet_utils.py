"""Shared Parquet helpers for lap telemetry consumers."""
from __future__ import annotations

from typing import Any

import pyarrow as pa


SCORING_LAST_LAP_TIME_COL = "scoring_last_lap_time_s"
LAP_TIME_COL = "lap_time_s"


def build_segments(lap_col: list[int]) -> list[tuple[int, int, int]]:
    """Return contiguous (lap_number, start, end_exclusive) runs."""
    if not lap_col:
        return []
    segments: list[tuple[int, int, int]] = []
    prev = lap_col[0]
    start = 0
    for i in range(1, len(lap_col)):
        if lap_col[i] != prev:
            segments.append((prev, start, i))
            prev = lap_col[i]
            start = i
    segments.append((prev, start, len(lap_col)))
    return segments


def authoritative_duration(
    table: pa.Table,
    seg_start: int,
    seg_end: int,
    next_seg_start: int | None = None,
    next_seg_end: int | None = None,
    *,
    allow_same_segment_scoring: bool = False,
) -> float:
    """Return the best available lap duration for one segment.

    New recorder files carry ``scoring_last_lap_time_s`` from the simulator's
    scorer. For a completed lap in a multi-lap session, that value appears in
    the immediately following segment. Extracted single-lap reference files can
    carry the authoritative value inside the same segment; using that fallback
    is therefore opt-in so old/current final session segments do not steal the
    previous lap's scorer value.
    """
    lap_times = _column_slice(table, LAP_TIME_COL, seg_start, seg_end)
    fallback = max(
        (float(v) for v in lap_times if _is_positive_number(v)),
        default=0.0,
    )

    if SCORING_LAST_LAP_TIME_COL not in table.schema.names:
        return fallback

    if next_seg_start is not None and next_seg_end is not None:
        candidate = _max_positive(table, SCORING_LAST_LAP_TIME_COL, next_seg_start, next_seg_end)
        if _plausible(candidate, fallback):
            return candidate

    if allow_same_segment_scoring:
        candidate = _max_positive(table, SCORING_LAST_LAP_TIME_COL, seg_start, seg_end)
        if _plausible(candidate, fallback):
            return candidate

    return fallback


def _column_slice(table: pa.Table, name: str, start: int, end: int) -> list[Any]:
    return table.column(name).to_pylist()[start:end]


def _max_positive(table: pa.Table, name: str, start: int, end: int) -> float | None:
    values = _column_slice(table, name, start, end)
    positive = [float(v) for v in values if _is_positive_number(v)]
    return max(positive) if positive else None


def _is_positive_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and value > 0


def _plausible(candidate: float | None, fallback: float) -> bool:
    if candidate is None or fallback <= 0:
        return False
    return abs(candidate - fallback) <= 1.0
