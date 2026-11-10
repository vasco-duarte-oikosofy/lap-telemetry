"""Lap inventory for a recorded session.

One job: given a session Parquet (or its rotation shards), decide which
contiguous segments are real flying laps.

Lap identity is the **contiguous segment**, never ``lap_number`` alone: a sim
restart resets ``lap_number`` to 0 mid-recording, so filtering a whole file by
lap number silently concatenates two different stints.
"""
from __future__ import annotations

import json
import re
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from lap_telemetry.parquet_utils import authoritative_duration, build_segments


# A debrief needs this many eligible laps before spread and "recurring" mean
# anything. Below it, the coach would be inventing a pattern.
MIN_ELIGIBLE_LAPS = 5

# Duration band, relative to the session yardstick.
IN_LAP_RATIO = 0.85
PIT_LAP_RATIO = 1.20
# A lap within this ratio of the fastest eligible lap counts as representative
# for consistency statistics. Slower eligible laps stay in the loss analysis.
CLEAN_LAP_RATIO = 1.05

# Coverage band, relative to the longest distance seen in the session.
COVERAGE_START_MAX = 0.10
COVERAGE_END_MIN = 0.80

# A car below this speed for this long is in the pit lane, not racing.
PIT_STOP_SPEED_KPH = 3.0
PIT_STOP_MIN_S = 1.0

# Frame count must agree with the lap duration within this factor; outside it
# the duration or the row count is broken and the lap cannot be trusted.
FRAME_INTEGRITY_FACTOR = 2.0

_SHARD_RE = re.compile(r"^(session_.+)\.part(\d+)\.parquet$")


class LapStatus:
    """Classification of one contiguous lap segment."""

    ELIGIBLE = "eligible"
    OUT_LAP = "out-lap"
    IN_LAP = "in-lap"
    PIT_LAP = "pit-lap"
    INCOMPLETE = "incomplete"
    SHORT = "short"
    INVALID = "invalid"


@dataclass
class LapRecord:
    """One contiguous lap segment of a session."""

    segment_index: int
    lap_number: int
    start_row: int
    end_row: int
    frames: int
    duration_s: float
    status: str
    reason: str = ""
    clean: bool = False
    valid_flag: bool | None = None

    @property
    def eligible(self) -> bool:
        return self.status == LapStatus.ELIGIBLE


@dataclass
class SessionSource:
    """A session table plus the metadata needed to describe it."""

    table: pa.Table
    meta: dict[str, Any] = field(default_factory=dict)
    shards: list[Path] = field(default_factory=list)
    stem: str = ""

    @property
    def track(self) -> str | None:
        return self.meta.get("track")

    @property
    def vehicle_name(self) -> str | None:
        return self.meta.get("vehicle_name")

    @property
    def sample_rate_hz(self) -> float | None:
        rate = self.meta.get("sample_rate_hz")
        return float(rate) if rate else None

    @property
    def shard_count(self) -> int:
        return len(self.shards) or 1


def _shard_group(path: Path) -> tuple[str, list[Path]]:
    """Resolve a session path (optionally a ``.partN.parquet``) to its shards."""
    match = _SHARD_RE.match(path.name)
    if match:
        stem = match.group(1)
        group = [
            p for p in path.parent.glob(f"{stem}.part*.parquet") if _SHARD_RE.match(p.name)
        ]
    else:
        stem = path.stem
        group = []

    if not group:
        return stem, [path]

    group.sort(key=lambda p: int(_SHARD_RE.match(p.name).group(2)))  # type: ignore[union-attr]
    return stem, group


def load_session(path: Path | str) -> SessionSource:
    """Read a session, merging rotation shards in part order.

    The merge is in memory only: shards are an implementation detail of the
    recorder, not something the debrief should write back as a new file.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"session not found: {path}")

    stem, shards = _shard_group(path)
    tables = [pq.read_table(shard) for shard in shards]
    table = tables[0] if len(tables) == 1 else pa.concat_tables(tables)

    sidecar = path.parent / f"{stem}.json"
    meta: dict[str, Any] = {}
    if sidecar.exists():
        try:
            meta = json.loads(sidecar.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            meta = {}

    return SessionSource(table=table, meta=meta, shards=shards, stem=stem)


def _column(table: pa.Table, name: str) -> list[Any] | None:
    if name not in table.schema.names:
        return None
    return table.column(name).to_pylist()


def _sample_rate(table: pa.Table) -> float | None:
    """Derive the recording rate from the session clock, if present."""
    session_time = _column(table, "session_time_s")
    if not session_time or len(session_time) < 2:
        return None
    span = float(session_time[-1]) - float(session_time[0])
    if span <= 0:
        return None
    return (len(session_time) - 1) / span


def _stationary_seconds(
    speed: list[Any] | None,
    session_time: list[Any] | None,
    start: int,
    end: int,
) -> float:
    """Longest continuous stretch below pit-lane speed, in seconds."""
    if speed is None or session_time is None:
        return 0.0
    longest = 0.0
    run_start: float | None = None
    for i in range(start, end):
        below = speed[i] is not None and float(speed[i]) < PIT_STOP_SPEED_KPH
        if below:
            if run_start is None:
                run_start = float(session_time[i])
        elif run_start is not None:
            longest = max(longest, float(session_time[i]) - run_start)
            run_start = None
    if run_start is not None:
        longest = max(longest, float(session_time[end - 1]) - run_start)
    return longest


def _segment_durations(
    table: pa.Table,
    segments: list[tuple[int, int, int]],
) -> list[float]:
    durations: list[float] = []
    for idx, (_lap, start, end) in enumerate(segments):
        if idx + 1 < len(segments):
            _nl, next_start, next_end = segments[idx + 1]
            durations.append(authoritative_duration(table, start, end, next_start, next_end))
        else:
            durations.append(authoritative_duration(table, start, end))
    return durations


def _yardstick(durations: list[float]) -> float:
    """Median interior lap duration — out/in/pit outliers do not move it."""
    interior = [d for d in durations[1:-1] if d > 0]
    pool = interior or [d for d in durations if d > 0]
    return statistics.median(pool) if pool else 0.0


def _validity(table: pa.Table) -> tuple[list[Any] | None, bool]:
    """Return the ``lap_valid`` column and whether it discriminates."""
    values = _column(table, "lap_valid")
    if values is None:
        return None, False
    present = {v for v in values if v is not None}
    return values, len(present) > 1


def classify_laps(table: pa.Table, sample_rate_hz: float | None = None) -> list[LapRecord]:
    """Classify every contiguous lap segment of a session table."""
    lap_numbers = _column(table, "lap_number") or []
    segments = build_segments(lap_numbers)
    if not segments:
        return []

    durations = _segment_durations(table, segments)
    yardstick = _yardstick(durations)
    rate = sample_rate_hz or _sample_rate(table)

    distances = _column(table, "lap_distance_m")
    lap_length = 0.0
    if distances:
        for _lap, start, end in segments:
            zoom = [float(d) for d in distances[start:end] if d is not None]
            if zoom:
                lap_length = max(lap_length, max(zoom))

    speed = _column(table, "speed_kph")
    session_time = _column(table, "session_time_s")
    validity, validity_trusted = _validity(table)

    records: list[LapRecord] = []
    last_index = len(segments) - 1
    for idx, (lap_number, start, end) in enumerate(segments):
        duration = durations[idx]
        frames = end - start
        status = LapStatus.ELIGIBLE
        reason = ""
        valid_flag = None

        if idx == last_index:
            status = LapStatus.INCOMPLETE
            reason = "final segment of the session"
        elif lap_length > 0 and distances:
            zone = [float(d) for d in distances[start:end] if d is not None]
            if not zone or max(zone) < lap_length * COVERAGE_END_MIN:
                status = LapStatus.INCOMPLETE
                reason = f"lap ends at {max(zone) if zone else 0:.0f} m"
            elif min(zone) > lap_length * COVERAGE_START_MAX:
                status = LapStatus.INCOMPLETE
                reason = f"lap starts at {min(zone):.0f} m"

        if status == LapStatus.ELIGIBLE and (
            idx == 0 or (lap_number == 0 and segments[idx - 1][0] != 0)
        ):
            status = LapStatus.OUT_LAP
            reason = "first segment of a stint"

        if status == LapStatus.ELIGIBLE and rate and duration > 0:
            expected = duration * rate
            if frames < expected / FRAME_INTEGRITY_FACTOR:
                status = LapStatus.SHORT
                reason = f"{frames} frames for a {duration:.3f} s lap"
            elif frames > expected * FRAME_INTEGRITY_FACTOR:
                status = LapStatus.SHORT
                reason = f"{frames} frames for a {duration:.3f} s lap"

        if validity_trusted and validity is not None:
            zone_valid = validity[start:end]
            if any(v is False for v in zone_valid):
                valid_flag = False
                if status == LapStatus.ELIGIBLE:
                    status = LapStatus.INVALID
                    reason = "lap marked invalid by the sim"
            elif all(v is True for v in zone_valid):
                valid_flag = True

        if status == LapStatus.ELIGIBLE and yardstick > 0:
            ratio = duration / yardstick
            if ratio < IN_LAP_RATIO:
                status = LapStatus.IN_LAP
                reason = f"duration {ratio:.2f}x the session yardstick"
            else:
                stopped = _stationary_seconds(speed, session_time, start, end)
                if stopped >= PIT_STOP_MIN_S:
                    status = LapStatus.PIT_LAP
                    reason = f"stopped for {stopped:.1f} s"
                elif ratio > PIT_LAP_RATIO:
                    status = LapStatus.PIT_LAP
                    reason = f"duration {ratio:.2f}x the session yardstick"

        records.append(LapRecord(
            segment_index=idx,
            lap_number=lap_number,
            start_row=start,
            end_row=end,
            frames=frames,
            duration_s=duration,
            status=status,
            reason=reason,
            valid_flag=valid_flag,
        ))

    eligible = [r for r in records if r.eligible and r.duration_s > 0]
    if eligible:
        best = min(r.duration_s for r in eligible)
        for record in eligible:
            record.clean = record.duration_s <= best * CLEAN_LAP_RATIO

    return records


def _fmt_duration(seconds: float) -> str:
    minutes, secs = divmod(abs(seconds), 60)
    return f"{int(minutes)}:{secs:06.3f}"


def format_inventory(
    records: list[LapRecord],
    meta: dict[str, Any],
    *,
    shard_count: int = 1,
    yardstick_s: float | None = None,
) -> str:
    """Render the human-readable inventory printed by ``debrief --list``."""
    eligible = [r for r in records if r.eligible]
    clean = [r for r in eligible if r.clean]
    if yardstick_s is None:
        yardstick_s = _yardstick([r.duration_s for r in records])

    rate = meta.get("sample_rate_hz")
    rate_text = f"{float(rate):.1f} Hz" if rate else "unknown rate"

    lines = [
        f"session : {meta.get('stem', '?')}",
        f"track   : {meta.get('track') or '?'}",
        f"vehicle : {meta.get('vehicle_name') or '?'}",
        f"shards  : {shard_count}   rate: {rate_text}   yardstick: {_fmt_duration(yardstick_s)}",
        "",
        f"{'seg':>4}  {'lap':>3}  {'frames':>6}  {'duration':>11}  {'status':<10}  reason",
    ]
    for r in records:
        lines.append(
            f"{r.segment_index:>4}  {r.lap_number:>3}  {r.frames:>6}  "
            f"{_fmt_duration(r.duration_s):>11}  {r.status:<10}  {r.reason}"
        )

    summary = (
        f"\n{len(eligible)} of {len(records)} segments eligible "
        f"({len(clean)} clean)."
    )
    if len(eligible) < MIN_ELIGIBLE_LAPS:
        summary += (
            f" A debrief needs at least {MIN_ELIGIBLE_LAPS} eligible laps; "
            "this session is too short or too messy."
        )
    lines.append(summary)
    return "\n".join(lines)
