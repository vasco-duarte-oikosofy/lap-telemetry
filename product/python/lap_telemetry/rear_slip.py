"""A rear slip angle measured from the rear wheels' own ground velocities.

**Why not the recorded ``slip_angle_*`` columns.** They are
``atan2(mLateralPatchVel, mLongitudinalPatchVel)`` — two velocities in the *car*
frame — so they idle at ±180° on a straight and follow steering input. No
post-processing recovers a slip angle from them (``session_corner_extras``
refuses them, with the measurements behind the refusal).

**Why not ``mGripFract``.** The recorder carries ``grip_fraction_rl/rr``, but LMU
publishes ``mGripFract`` as a constant 0.0 in every sample of every recording on
this machine (all 20+ sessions checked, one distinct value). A constant zero is
a dead channel, not "the rear is gripping", so ``column_reasons`` refuses it.

**What this measures instead.** The recorder also carries the rear wheels'
ground velocities. A rear wheel's heading *is* the car's heading (toe aside), so
the angle between its ground velocity and its plane is the tyre slip angle:

    slip = atan2(lat, |lon|)

Measured on committed recordings (2026-11-15 Barcelona and Silverstone races):

- straight, constant speed: median |slip| 0.12–0.16° where a real sideslip is ~0,
- monotone in lateral acceleration: 0.12° below 0.3 g, 1.5° above 1.3 g,
- same sign as the yaw rate on 99.6–99.8% of rotating samples,
- corner apex medians 1.4–2.1° with clear single-lap outliers (4.4–5.0°).

Those four properties are pinned in ``dev/scripts/test_rear_slip_facts.py``.
This module is the only place a rear slip number is produced; it never converts
a missing or dead channel into a zero.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Any, Sequence

import pyarrow as pa

# Beyond this the sample is a spin or off the track, not a slip angle.
SLIP_SANE_MAX_DEG = 45.0
# Below this the speed is too low for atan2 to mean anything.
MIN_SPEED_KPH = 30.0
# Apex measurement window, either side of the driver's apex.
APEX_HALF_WINDOW_M = 15.0
PEAK_PERCENTILE = 0.95
BRAKE_ON = 0.05
# A corner needs this share of valid samples before it reports a number.
MIN_COVERAGE = 0.6
MIN_SAMPLES = 5
# If more than this share of a corner reads past the sane bound, the window
# contains a spin or an excursion and no slip number is trustworthy.
MAX_INSANE_SHARE = 0.10
# Instability: above this, and above the clean-lap baseline by a factor.
INSTABILITY_MIN_DEG = 3.0
INSTABILITY_BASELINE_FACTOR = 1.5

_GROUND_COLUMNS = (
    "wheel_ground_vel_lat_rl", "wheel_ground_vel_lon_rl",
    "wheel_ground_vel_lat_rr", "wheel_ground_vel_lon_rr",
)
_GRIP_COLUMNS = ("grip_fraction_rl", "grip_fraction_rr")


def _column(table: pa.Table, name: str) -> list | None:
    if name not in table.schema.names:
        return None
    return table.column(name).to_pylist()


def _finite(value: Any) -> bool:
    return value is not None and isinstance(value, (int, float)) \
        and math.isfinite(float(value))


def slip_series(table: pa.Table) -> list[float | None] | None:
    """Signed rear slip angle per sample, in degrees; ``None`` when unrecorded.

    The two rear wheels are averaged: they agree in sign almost everywhere, and
    a single number is what a driver can use. ``None`` per sample where the
    channels are absent or the ground velocity is degenerate.
    """
    lat_left = _column(table, "wheel_ground_vel_lat_rl")
    lon_left = _column(table, "wheel_ground_vel_lon_rl")
    lat_right = _column(table, "wheel_ground_vel_lat_rr")
    lon_right = _column(table, "wheel_ground_vel_lon_rr")
    if None in (lat_left, lon_left, lat_right, lon_right):
        return None
    series: list[float | None] = []
    for lat_a, lon_a, lat_b, lon_b in zip(lat_left, lon_left, lat_right, lon_right):
        if not all(_finite(v) for v in (lat_a, lon_a, lat_b, lon_b)):
            series.append(None)
            continue
        lat = 0.5 * (float(lat_a) + float(lat_b))
        lon = 0.5 * (float(lon_a) + float(lon_b))
        if abs(lon) < 1e-6:
            series.append(None)
            continue
        series.append(math.degrees(math.atan2(lat, abs(lon))))
    return series


def column_reasons(table: pa.Table) -> dict[str, str]:
    """Channels of this recording that cannot support a rear-grip claim, and why."""
    reasons: dict[str, str] = {}
    for name in _GRIP_COLUMNS:
        values = _column(table, name)
        if values is None:
            reasons[name] = "channel absent from this recording"
            continue
        known = [float(v) for v in values if _finite(v)]
        if not known:
            reasons[name] = "no usable samples in this recording"
        elif max(known) == min(known) and abs(max(known)) < 1e-6:
            reasons[name] = (
                "the sim publishes mGripFract as a constant 0.0 in every sample of "
                "this recording (checked on every LMU session on disk), so it cannot "
                "separate a sliding contact patch from grip")
    for name in _GROUND_COLUMNS:
        values = _column(table, name)
        if values is None:
            reasons[name] = "channel absent from this recording"
            continue
        known = [float(v) for v in values if _finite(v)]
        if not known:
            reasons[name] = "no usable samples in this recording"
        elif max(abs(v) for v in known) < 1e-6:
            reasons[name] = ("every sample is 0.0, so the channel is dead in this "
                             "recording")
    return reasons


@dataclass
class CornerRearSlip:
    """One lap's rear slip inside one corner."""

    apex_deg: float | None = None
    braking_deg: float | None = None
    peak_deg: float | None = None
    coverage: float = 0.0
    samples: int = 0
    reason: str = ""


def _percentile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
    return ordered[index]


def _median_or_none(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def measure_corner(
    series: Sequence[float | None] | None,
    distance: Sequence[float | None] | None,
    brake: Sequence[float | None] | None,
    *,
    apex_m: float,
    entry_m: float | None,
    zone: tuple[float, float],
    speed: Sequence[float | None] | None = None,
    surface: Sequence[int | None] | None = None,
) -> CornerRearSlip:
    """Apex, braking-phase and peak rear slip for one corner on one lap."""
    if series is None or not distance:
        return CornerRearSlip(reason="the session does not record rear ground velocity")
    low, high = zone
    zone_indices = [i for i, d in enumerate(distance)
                    if _finite(d) and low <= float(d) <= high]
    if not zone_indices:
        return CornerRearSlip(reason="no samples inside the corner window")
    on_track = [i for i in zone_indices
                if surface is None or i >= len(surface) or surface[i] in (0, None)]
    if not on_track:
        on_track = zone_indices

    valid: list[tuple[int, float]] = []
    insane = 0
    for i in on_track:
        value = series[i] if i < len(series) else None
        if not _finite(value):
            continue
        if abs(float(value)) > SLIP_SANE_MAX_DEG:
            insane += 1
            continue
        if speed is not None and i < len(speed) and _finite(speed[i]) \
                and float(speed[i]) < MIN_SPEED_KPH:
            continue
        valid.append((i, float(value)))

    measured = CornerRearSlip(
        coverage=len(valid) / len(on_track),
        samples=len(valid),
        reason="" if valid else "no rear-slip sample passed the validity checks here",
    )
    if insane / len(on_track) > MAX_INSANE_SHARE:
        measured.apex_deg = measured.braking_deg = measured.peak_deg = None
        measured.reason = (f"{insane / len(on_track) * 100:.0f}% of this corner's samples "
                           f"read past the sane slip bound (spin or off-track)")
        return measured
    if not valid:
        return measured
    if measured.coverage < MIN_COVERAGE:
        measured.reason = (f"only {measured.coverage * 100:.0f}% of the corner has a "
                           f"valid rear-slip sample")
        return measured

    apex_window = [abs(value) for i, value in valid
                   if abs(float(distance[i]) - apex_m) <= APEX_HALF_WINDOW_M]
    if len(apex_window) >= MIN_SAMPLES:
        measured.apex_deg = _median_or_none(apex_window)

    if brake is not None and entry_m is not None:
        # Is the rear moving *while the driver is on the brake*? A high
        # percentile, not a median: the braking phase includes the straight-line
        # part of the braking zone, where nothing has happened yet.
        braking = [abs(value) for i, value in valid
                   if entry_m <= float(distance[i]) <= high
                   and i < len(brake) and _finite(brake[i])
                   and float(brake[i]) > BRAKE_ON]
        if len(braking) >= MIN_SAMPLES:
            measured.braking_deg = _percentile(braking, PEAK_PERCENTILE)

    measured.peak_deg = _percentile([abs(value) for _i, value in valid], PEAK_PERCENTILE)
    return measured


def attach_corners(table: pa.Table, extras: list, corners: list,
                   windows: dict[str, dict[str, Any]] | None = None) -> bool:
    """Measure every corner of one lap onto its ``CornerExtras``.

    Kept here, rather than in ``session_corner_extras``, because that module is
    already at its size ceiling and this is one job: turn two recorded velocity
    channels into a validated slip angle.
    """
    series = slip_series(table)
    if series is None:
        return False
    distance = _column(table, "lap_distance_m")
    brake = _column(table, "brake_norm")
    speed = _column(table, "speed_kph")
    surface = _column(table, "surface_type_rl")
    if distance is None:
        return False
    windows = windows or {}
    by_id = {extra.corner_id: extra for extra in extras}
    for corner in corners:
        extra = by_id.get(corner.id)
        if extra is None:
            continue
        window = windows.get(corner.id) or {}
        apex_m = float(window.get("apex_m") or corner.apex_s_m)
        entry_m = window.get("entry_m")
        entry_m = float(entry_m) if entry_m is not None else float(corner.s_start_m)
        if entry_m >= apex_m:
            entry_m = float(corner.s_start_m)
        measured = measure_corner(
            series, distance, brake, apex_m=apex_m, entry_m=entry_m,
            zone=(float(corner.s_start_m), float(corner.s_end_m)), speed=speed,
            surface=surface)
        extra.rear_slip_apex_deg = measured.apex_deg
        extra.rear_slip_braking_deg = measured.braking_deg
        extra.rear_slip_peak_deg = measured.peak_deg
        extra.rear_slip_coverage = measured.coverage
    return True
