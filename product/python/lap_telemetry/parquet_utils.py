"""Shared Parquet helpers for lap telemetry consumers."""
from __future__ import annotations

import math
from typing import Any

import pyarrow as pa


SCORING_LAST_LAP_TIME_COL = "scoring_last_lap_time_s"
LAP_TIME_COL = "lap_time_s"
SESSION_TIME_COL = "session_time_s"
# Written into extracted reference-lap parquet schema metadata by the exporter.
AUTHORITATIVE_META_KEY = b"authoritative_lap_time_s"


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

    Priority:
      1. Explicit ``authoritative_lap_time_s`` schema metadata (extracted
         reference-lap files).
      2. Telemetry lap-start ET difference between this segment and the next
         (the TinyPedal method: consecutive ``lmuTeleVeh.mLapStartET``). This
         is the true in-game lap time. Our recorder stores
         ``session_time_s - lap_time_s == mLapStartET``, so it is recoverable.
      3. Legacy fallback: ``scoring_last_lap_time_s`` (``mLastLapTime``) from
         the next segment. This value lags by one lap on some tracks/sessions
         (Road Atlanta) and can be ~0.5 s high; only used when the telemetry
         clock is unavailable.
      4. ``max(lap_time_s)`` of this segment (undercounts by the last partial
         sample, typically <0.1 s).
    """
    lap_times = _column_slice(table, LAP_TIME_COL, seg_start, seg_end)
    fallback = max(
        (float(v) for v in lap_times if _is_positive_number(v)),
        default=0.0,
    )

    explicit = _metadata_duration(table)
    if explicit is not None:
        return explicit

    if next_seg_start is not None and next_seg_end is not None:
        telemetry = _telemetry_duration(
            table, seg_start, seg_end, next_seg_start, next_seg_end
        )
        if telemetry is not None and _plausible(telemetry, fallback):
            return telemetry

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


def _telemetry_duration(
    table: pa.Table,
    seg_start: int,
    seg_end: int,
    next_seg_start: int,
    next_seg_end: int,
) -> float | None:
    """Lap duration from consecutive telemetry lap-start ETs (TinyPedal method)."""
    start = _lap_start_et(table, seg_start, seg_end)
    if start is None:
        return None
    next_start = _lap_start_et(table, next_seg_start, next_seg_end)
    if next_start is None:
        return None
    duration = next_start - start
    return duration if math.isfinite(duration) and duration > 0 else None


def _lap_start_et(table: pa.Table, seg_start: int, seg_end: int) -> float | None:
    """Reconstruct the telemetry ``mLapStartET`` for a segment.

    ``lap_time_s = scoring mCurrentET - telemetry mLapStartET`` and
    ``session_time_s = scoring mCurrentET``, so their difference is the
    telemetry lap-start ET (constant within a lap). Median is robust against
    the stale cross-lap boundary frame.
    """
    if SESSION_TIME_COL not in table.schema.names:
        return None
    session = _column_slice(table, SESSION_TIME_COL, seg_start, seg_end)
    lap = _column_slice(table, LAP_TIME_COL, seg_start, seg_end)
    starts = [
        float(s) - float(l)
        for s, l in zip(session, lap)
        if _is_number(s) and _is_number(l)
    ]
    if not starts:
        return None
    starts.sort()
    return starts[len(starts) // 2]


def _metadata_duration(table: pa.Table) -> float | None:
    raw = (table.schema.metadata or {}).get(AUTHORITATIVE_META_KEY)
    if raw is None:
        return None
    try:
        value = float(raw.decode() if isinstance(raw, bytes) else raw)
    except (ValueError, TypeError):
        return None
    return value if value > 0 else None


def _column_slice(table: pa.Table, name: str, start: int, end: int) -> list[Any]:
    return table.column(name).to_pylist()[start:end]


def _max_positive(table: pa.Table, name: str, start: int, end: int) -> float | None:
    values = _column_slice(table, name, start, end)
    positive = [float(v) for v in values if _is_positive_number(v)]
    return max(positive) if positive else None


def _is_positive_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and value > 0


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(float(value))


def _plausible(candidate: float | None, fallback: float) -> bool:
    if candidate is None or fallback <= 0:
        return False
    return abs(candidate - fallback) <= 1.0
