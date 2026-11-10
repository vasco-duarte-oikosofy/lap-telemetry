"""Resolve what a session debrief needs: a reference lap and a coaching model.

The live coach resolves these per frame; a debrief resolves them once per
session. Both go through the same (track, car) matching so a livery never falls
back to another car's data (bug 27).

The reference parquet is read **once** here and handed to every lap comparison;
nineteen laps must not re-read and re-duration the same file nineteen times.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from .coach.car_catalog import canonical_car_slug
from .coach.lap_table import duration_segment_for_lap, segment_duration
from .coach.reference_resolver import resolve_reference_lap
from .coach.track_model import TrackCoachingModel, load_track_coaching_model
from .coach.track_model_resolver import resolve_track_model
from .session_source import SessionSource

_GUIDE = "docs/HOW_TO_CREATE_A_COACHING_MODEL.md"

# <track>_<vehicle>_time_<mm>.<ss>.<mmm>.parquet — the export's certified time.
_REF_TIME_RE = re.compile(r"_time_(\d+)\.(\d+)\.(\d+)\.parquet$")


class DebriefInputError(Exception):
    """Raised when a session cannot be matched to reference data."""


@dataclass
class DebriefInputs:
    """Everything the analysis needs for one session."""

    track: str
    vehicle_name: str
    car_slug: str | None
    reference_path: Path
    reference_table: pa.Table
    reference_lap_time_s: float
    track_model_path: Path
    track_model: TrackCoachingModel

    @property
    def reference_file(self) -> str:
        return self.reference_path.name

    @property
    def track_model_file(self) -> str:
        return self.track_model_path.name


def reference_lap_time_from_name(path: Path | str) -> float | None:
    """The lap time encoded in a reference file's name, in seconds."""
    match = _REF_TIME_RE.search(Path(path).name)
    if not match:
        return None
    minutes, seconds, millis = (int(g) for g in match.groups())
    return minutes * 60 + seconds + millis / 1000.0


def reference_lap_time_s(table: pa.Table, path: Path | str) -> float:
    """The certified lap time of a reference lap.

    An extracted reference is a single segment, so the telemetry-clock method
    (difference between consecutive lap-start ETs) is unavailable and
    ``authoritative_duration`` falls back to the scorer's ``mLastLapTime``,
    which lags by a lap and reads up to a second high. Twelve files carry an
    ``authoritative_lap_time_s`` metadata stamp; for the rest the filename is
    the value the export certified and ``validate_reference_laps.py`` checks.
    Re-deriving instead would shift every lap delta by up to a second.
    """
    derived = segment_duration(
        table,
        duration_segment_for_lap(table, None),
        allow_same_segment_scoring=True,
    )
    if table.schema.metadata and b"authoritative_lap_time_s" in table.schema.metadata:
        return derived
    return reference_lap_time_from_name(path) or derived


def resolve_debrief_inputs(
    session: SessionSource,
    *,
    track: str | None = None,
    vehicle_name: str | None = None,
    reference: Path | str | None = None,
    track_model_path: Path | str | None = None,
) -> DebriefInputs:
    """Resolve the reference lap and coaching model for a session's combo."""
    track_name = track or session.track
    vehicle = vehicle_name or session.vehicle_name
    if not track_name:
        raise DebriefInputError(
            "session sidecar has no track name; pass --track to name the circuit"
        )

    reference_path = Path(reference) if reference else resolve_reference_lap(
        track_name, vehicle_name=vehicle
    )
    if reference_path is None or not reference_path.exists():
        raise DebriefInputError(
            f"no reference lap for track '{track_name}'"
            + (f" and car '{vehicle}'" if vehicle else "")
            + f". Export one first — see {_GUIDE}."
        )

    model_path = (
        Path(track_model_path) if track_model_path
        else resolve_track_model(track_name, vehicle_name=vehicle)
    )
    if model_path is None or not model_path.exists():
        raise DebriefInputError(
            f"no coaching model for track '{track_name}'"
            + (f" and car '{vehicle}'" if vehicle else "")
            + f". Create one first — see {_GUIDE}."
        )

    reference_table = pq.read_table(reference_path)
    reference_lap_time = reference_lap_time_s(reference_table, reference_path)
    if reference_lap_time <= 0:
        raise DebriefInputError(
            f"reference lap {reference_path.name} has no usable duration"
        )

    return DebriefInputs(
        track=track_name,
        vehicle_name=vehicle or "",
        car_slug=canonical_car_slug(vehicle) if vehicle else None,
        reference_path=reference_path,
        reference_table=reference_table,
        reference_lap_time_s=reference_lap_time,
        track_model_path=model_path,
        track_model=load_track_coaching_model(model_path),
    )
