"""Build the facts for a whole session: every lap, every corner phase.

This module is assembly, not analysis. The per-lap numbers come from
``coach.lap_comparator.compare_lap_tables`` (the same core the live coach uses)
and the lap selection comes from ``session_laps``. Here we only decide *which*
rows form a lap, feed them in, and collect the results into one payload.

Lap identity is the contiguous segment. ``lap_number`` is not unique: the Paul
Ricard fixture has two different laps both numbered 1, with different durations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .coach.facts import CornerLoss, PartialLapError, corner_loss_to_dict
from .coach.lap_comparator import compare_lap_tables
from .coach.lap_table import slice_segment
from .lap_signals import yardstick_seconds
from .session_corner_extras import (
    CornerChannels,
    CornerExtras,
    corner_channels,
    extract_all_corners,
    phase_windows,
    reference_windows,
    unmeasurable_channels,
)
from .session_consistency import Consistency, build_consistency, speed_envelope_optimal
from .session_inputs import DebriefInputs
from .session_laps import LapRecord, LapStatus
from .session_priorities import Priority, build_priorities
from .session_source import SessionSource


SCHEMA_VERSION = "1"

# Phase names in the order a driver experiences them through a corner.
_PHASE_ORDER = {
    "entry": 0,
    "minimum_speed": 1,
    "exit_brake": 2,
    "exit": 3,
    "exit_throttle": 4,
}


@dataclass
class SessionSummary:
    """Session-level header: identity plus the two baselines."""

    stem: str
    track: str
    vehicle_name: str
    car_slug: str | None
    sample_rate_hz: float | None
    total_segments: int
    eligible_laps: int
    clean_laps: int
    yardstick_s: float
    reference_lap_s: float
    reference_file: str
    track_model_file: str
    # channel -> why it cannot be measured in this session
    unmeasurable_channels: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stem": self.stem,
            "track": self.track,
            "vehicle_name": self.vehicle_name,
            "car_slug": self.car_slug,
            "sample_rate_hz": self.sample_rate_hz,
            "total_segments": self.total_segments,
            "eligible_laps": self.eligible_laps,
            "clean_laps": self.clean_laps,
            "yardstick_s": round(self.yardstick_s, 3),
            "reference_lap_s": round(self.reference_lap_s, 3),
            "reference_file": self.reference_file,
            "track_model_file": self.track_model_file,
            "unmeasurable_channels": self.unmeasurable_channels,
        }


@dataclass
class LapFacts:
    """One analysed lap: its own identity, baseline delta and every phase."""

    segment_index: int
    lap_number: int
    lap_time_s: float
    delta_s: float
    clean: bool
    phases: list[CornerLoss] = field(default_factory=list)
    corners: list[CornerExtras] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_index": self.segment_index,
            "lap_number": self.lap_number,
            "lap_time_s": round(self.lap_time_s, 3),
            "delta_s": round(self.delta_s, 3),
            "clean": self.clean,
            "phases": [corner_loss_to_dict(p) for p in self.phases],
            "corners": [c.to_dict() for c in self.corners],
        }


@dataclass
class ExcludedLap:
    """A segment that was not analysed, and why."""

    segment_index: int
    lap_number: int
    duration_s: float
    status: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_index": self.segment_index,
            "lap_number": self.lap_number,
            "duration_s": round(self.duration_s, 3),
            "status": self.status,
            "reason": self.reason,
        }


@dataclass
class SessionDebriefFacts:
    """The whole debrief payload for one session."""

    session: SessionSummary
    laps: list[LapFacts] = field(default_factory=list)
    excluded: list[ExcludedLap] = field(default_factory=list)
    consistency: Consistency = field(default_factory=Consistency)
    reference_corners: list[CornerExtras] = field(default_factory=list)
    priorities: list[Priority] = field(default_factory=list)

    @property
    def type(self) -> str:
        return "session_debrief"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "schema_version": SCHEMA_VERSION,
            "session": self.session.to_dict(),
            "laps": [lap.to_dict() for lap in self.laps],
            "consistency": self.consistency.to_dict(),
            "reference_corners": [c.to_dict() for c in self.reference_corners],
            "priorities": [p.to_dict() for p in self.priorities],
            "excluded": [item.to_dict() for item in self.excluded],
        }


def excluded_laps(records: list[LapRecord]) -> list[ExcludedLap]:
    """Every segment that is not eligible, with the inventory's reason."""
    return [
        ExcludedLap(
            segment_index=r.segment_index,
            lap_number=r.lap_number,
            duration_s=r.duration_s,
            status=r.status,
            reason=r.reason,
        )
        for r in records
        if r.status != LapStatus.ELIGIBLE
    ]


def _phase_sort_key(phase: CornerLoss) -> tuple[float, int, str]:
    return (
        phase.apex_distance_m,
        _PHASE_ORDER.get(phase.phase, len(_PHASE_ORDER)),
        phase.phase,
    )


def _analyse_lap(
    session: SessionSource,
    record: LapRecord,
    inputs: DebriefInputs,
    reference_channels: CornerChannels,
    unmeasurable: dict[str, str],
) -> LapFacts | ExcludedLap:
    """Analyse one lap, or explain why it could not be analysed."""
    lap_table = slice_segment(session.table, record.start_row, record.end_row)
    try:
        facts = compare_lap_tables(
            lap_table,
            inputs.reference_table,
            inputs.track_model,
            driver_lap_time_s=record.duration_s,
            reference_lap_time_s=inputs.reference_lap_time_s,
            top_n=None,  # the debrief needs every phase, not the live top three
            # The inventory already removed pit and in-laps; a lap that is merely
            # slow (traffic, a mistake) is real data the coach should see, and it
            # is already flagged not-clean.
            reject_implausibly_slow=False,
        )
    except PartialLapError as exc:
        return ExcludedLap(
            segment_index=record.segment_index,
            lap_number=record.lap_number,
            duration_s=record.duration_s,
            status="unanalysable",
            reason=str(exc),
        )

    phases = sorted(facts.top_losses + facts.top_gains, key=_phase_sort_key)
    windows = phase_windows(inputs.track_model.corners, phases)
    extras = extract_all_corners(
        corner_channels(lap_table, unmeasurable=unmeasurable),
        inputs.track_model.corners, windows, reference=reference_channels,
    )
    return LapFacts(
        segment_index=record.segment_index,
        lap_number=record.lap_number,
        lap_time_s=record.duration_s,
        delta_s=facts.lap_time_delta_s,
        clean=record.clean,
        phases=phases,
        corners=extras,
    )


def build_session_facts(
    session: SessionSource,
    records: list[LapRecord],
    inputs: DebriefInputs,
) -> SessionDebriefFacts:
    """Analyse every eligible lap and collect the session payload."""
    eligible = [r for r in records if r.status == LapStatus.ELIGIBLE]

    unmeasurable = unmeasurable_channels(session.table)
    reference_channels = corner_channels(
        inputs.reference_table, unmeasurable=unmeasurable)

    summary = SessionSummary(
        stem=session.stem,
        track=inputs.track,
        vehicle_name=inputs.vehicle_name,
        car_slug=inputs.car_slug,
        sample_rate_hz=session.sample_rate_hz,
        total_segments=len(records),
        eligible_laps=len(eligible),
        clean_laps=sum(1 for r in eligible if r.clean),
        yardstick_s=yardstick_seconds([r.duration_s for r in records]),
        reference_lap_s=inputs.reference_lap_time_s,
        reference_file=inputs.reference_file,
        track_model_file=inputs.track_model_file,
        unmeasurable_channels=unmeasurable,
    )

    laps: list[LapFacts] = []
    unanalysable: list[ExcludedLap] = []
    for record in eligible:
        result = _analyse_lap(session, record, inputs, reference_channels, unmeasurable)
        if isinstance(result, LapFacts):
            laps.append(result)
        else:
            unanalysable.append(result)

    reference_corners = extract_all_corners(
        reference_channels,
        inputs.track_model.corners,
        reference_windows(inputs.track_model.corners, [lap.phases for lap in laps]),
    )

    clean_records = [r for r in eligible if r.clean]
    envelope_s, _uncovered, _used = speed_envelope_optimal(
        session.table, clean_records, inputs.track_model.lap_length_m
    )

    return SessionDebriefFacts(
        session=summary,
        laps=laps,
        excluded=excluded_laps(records) + unanalysable,
        consistency=build_consistency(laps, envelope_s),
        reference_corners=reference_corners,
        priorities=build_priorities(laps, reference_corners),
    )
