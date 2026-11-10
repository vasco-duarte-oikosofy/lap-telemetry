"""Lap inventory for a recorded session.

One job: given a session table, decide which contiguous segments are real
flying laps, and say why the others are not.

Lap identity is the **contiguous segment**, never ``lap_number`` alone: a sim
restart resets ``lap_number`` to 0 mid-recording, so filtering a whole file by
lap number silently concatenates two different stints.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa

from lap_telemetry.lap_signals import (
    FRAME_INTEGRITY_FACTOR,
    PIT_STOP_MIN_S,
    column_values,
    entry_peak_speed,
    sample_rate_hz as derive_sample_rate,
    segment_durations,
    stationary_seconds,
    validity_column,
    yardstick_seconds,
)
from lap_telemetry.parquet_utils import build_segments
from lap_telemetry.session_source import SessionSource, load_session


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

# A stint boundary only makes an out-lap if the car entered the lap slowly.
# Recordings that start with the car already on a flying lap have a segment 0
# at 200 km/h or more; those are real laps, not pit exits. Across the committed
# corpus the split is clean: 0.1-75 km/h versus 201-258 km/h.
RACING_START_SPEED_KPH = 100.0


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


def _coverage_failure(
    distances: list[Any] | None,
    start: int,
    end: int,
    lap_length_m: float,
) -> str | None:
    if not distances or lap_length_m <= 0:
        return None
    zone = [float(d) for d in distances[start:end] if d is not None]
    if not zone:
        return "no distance samples"
    if max(zone) < lap_length_m * COVERAGE_END_MIN:
        return f"lap ends at {max(zone):.0f} m"
    if min(zone) > lap_length_m * COVERAGE_START_MAX:
        return f"lap starts at {min(zone):.0f} m"
    return None


def classify_laps(table: pa.Table, sample_rate_hz: float | None = None) -> list[LapRecord]:
    """Classify every contiguous lap segment of a session table."""
    lap_numbers = column_values(table, "lap_number") or []
    segments = build_segments(lap_numbers)
    if not segments:
        return []

    durations = segment_durations(table, segments)
    yardstick = yardstick_seconds(durations)
    rate = sample_rate_hz or derive_sample_rate(table)

    distances = column_values(table, "lap_distance_m")
    lap_length = 0.0
    if distances:
        for _lap, start, end in segments:
            zone = [float(d) for d in distances[start:end] if d is not None]
            if zone:
                lap_length = max(lap_length, max(zone))

    speed = column_values(table, "speed_kph")
    clock = column_values(table, "session_time_s")
    validity, validity_trusted = validity_column(table)

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
        else:
            coverage = _coverage_failure(distances, start, end, lap_length)
            if coverage:
                status = LapStatus.INCOMPLETE
                reason = coverage

        if status == LapStatus.ELIGIBLE and (
            idx == 0 or (lap_number == 0 and segments[idx - 1][0] != 0)
        ):
            # A stint boundary is only an out-lap when the car entered the lap
            # from the pits. A recording that starts on a flying lap has a
            # segment 0 at racing speed and must keep that lap.
            peak = entry_peak_speed(speed, clock, start, end)
            if peak is None or peak < RACING_START_SPEED_KPH:
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
                stopped = stationary_seconds(speed, clock, start, end)
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
