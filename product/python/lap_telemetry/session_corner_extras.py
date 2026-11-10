"""Per-corner channels that explain the speed: gear, brakes, steering, slip, line.

Slice 02 answers *where* time is lost. This module answers *why*: what the driver
was doing with their hands, feet and the electronics while they lost it.

Pure extraction. It does not rank, weight or interpret anything — slice 05 does
that — and it never invents a value: a missing column yields ``None``, and a flag
that never fires anywhere in the session is reported as unmeasurable rather than
as "0% TC", which would read as perfect traction.

Windows come from the phases the comparison core already detected (entry,
minimum speed, exit, straight end). When a phase was not emitted, the corner
model's own boundaries are used and ``window_source`` says so.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any, Iterable

import pyarrow as pa

from .coach.facts import CornerLoss


# A pedal below this is released; used for the trail-braking search.
BRAKE_ON = 0.05
# Steering changes below this are noise, not a correction.
STEERING_STEP = 0.02
# A channel sampled "at" a distance tolerates this much offset.
SAMPLE_TOLERANCE_M = 5.0
# Beyond this, a "slip angle" is a spin or a channel that is not a slip angle.
SLIP_SANE_MAX_DEG = 60.0
# Below this peak pressure the driver is not braking, so there is no trail to measure.
TRAIL_MIN_BRAKE_PEAK = 0.10


@dataclass
class CornerChannels:
    """One lap's raw channels, converted once and shared by every corner."""

    distance: list[float]
    gear: list[int] | None = None
    brake: list[float] | None = None
    steering: list[float] | None = None
    rear_slip: list[float] | None = None
    tc: list[bool] | None = None
    abs_: list[bool] | None = None
    lateral: list[float] | None = None
    # channel -> why it cannot be measured in this session
    unmeasurable: dict[str, str] = field(default_factory=dict)


@dataclass
class CornerExtras:
    """What the driver did through one corner, on one lap."""

    corner_id: str
    corner_name: str
    apex_distance_m: float
    window_source: str = "corner_model"
    gear_min: int | None = None
    gear_at_apex: int | None = None
    gear_at_exit: int | None = None
    brake_peak: float | None = None
    brake_area: float | None = None
    trail_brake_depth_m: float | None = None
    steering_reversals: int | None = None
    steering_rate_std: float | None = None
    rear_slip_max_deg: float | None = None
    rear_slip_exit_deg: float | None = None
    tc_duty: float | None = None
    abs_duty: float | None = None
    lateral_at_apex_m: float | None = None
    lateral_offset_m: float | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "corner_id": self.corner_id,
            "corner_name": self.corner_name,
            "apex_distance_m": self.apex_distance_m,
            "window_source": self.window_source,
        }
        for name in ("gear_min", "gear_at_apex", "gear_at_exit"):
            value = getattr(self, name)
            if value is not None:
                data[name] = int(value)
        for name in ("brake_peak", "brake_area", "trail_brake_depth_m",
                     "steering_rate_std", "rear_slip_max_deg", "rear_slip_exit_deg",
                     "tc_duty", "abs_duty", "lateral_at_apex_m", "lateral_offset_m"):
            value = getattr(self, name)
            if value is not None:
                data[name] = round(float(value), 3)
        if self.steering_reversals is not None:
            data["steering_reversals"] = self.steering_reversals
        return data


_FLAG_COLUMNS = {"tc_active": "tc", "abs_active": "abs_"}
_SLIP_COLUMNS = ("slip_angle_rl_deg", "slip_angle_rr_deg")


def _column(table: pa.Table, name: str, start: int | None = None,
            end: int | None = None) -> list | None:
    if name not in table.schema.names:
        return None
    values = table.column(name).to_pylist()
    return values[start:end] if start is not None or end is not None else values


def corner_channels(
    table: pa.Table,
    *,
    start_row: int | None = None,
    end_row: int | None = None,
    unmeasurable: Iterable[str] = (),
) -> CornerChannels:
    """Convert the channels this module needs, once per table."""
    unusable = set(unmeasurable)
    gear = _column(table, "gear", start_row, end_row)
    slip_left = _column(table, "slip_angle_rl_deg", start_row, end_row)
    slip_right = _column(table, "slip_angle_rr_deg", start_row, end_row)
    rear_slip = None
    if (slip_left is not None or slip_right is not None) \
            and not unusable & {"slip_angle_rl_deg", "slip_angle_rr_deg"}:
        left = slip_left or [0.0] * len(_column(table, "lap_distance_m", start_row, end_row))
        right = slip_right or [0.0] * len(left)
        rear_slip = [max(abs(a or 0.0), abs(b or 0.0)) for a, b in zip(left, right)]

    return CornerChannels(
        distance=_column(table, "lap_distance_m", start_row, end_row) or [],
        gear=[int(g) if g is not None else 0 for g in gear] if gear is not None else None,
        brake=_column(table, "brake_norm", start_row, end_row),
        steering=_column(table, "steering_norm", start_row, end_row),
        rear_slip=rear_slip,
        tc=_column(table, "tc_active", start_row, end_row),
        abs_=_column(table, "abs_active", start_row, end_row),
        lateral=_column(table, "path_lateral_m", start_row, end_row),
        unmeasurable={name: reason for name, reason in _REASONS.items() if name in unusable},
    )


def phase_windows(
    corners: list,
    phases: list[CornerLoss],
) -> dict[str, dict[str, Any]]:
    """Turn the detected phases into one window per corner.

    The apex is the driver's own minimum-speed distance when it was detected,
    because that is where their gear and slip actually matter. Everything falls
    back to the corner model when the phase was not emitted.
    """
    windows: dict[str, dict[str, Any]] = {}
    for index, corner in enumerate(corners):
        windows[corner.id] = {
            "entry_m": None,
            "apex_m": float(corner.apex_s_m),
            "exit_m": None,
            "straight_end_m": float(corner.s_end_m),
            "next_start_m": (float(corners[index + 1].s_start_m)
                             if index + 1 < len(corners) else float(corner.s_end_m)),
            "source": "corner_model",
        }

    for item in phases:
        window = windows.get(item.corner_id)
        if window is None:
            continue
        if item.phase == "entry" and item.phase_distance_m is not None:
            window["entry_m"] = item.phase_distance_m
            window["source"] = "phases"
        elif item.phase == "minimum_speed":
            if item.driver_apex_distance_m is not None:
                window["apex_m"] = item.driver_apex_distance_m
            window["source"] = "phases"
        elif item.phase in ("exit", "exit_brake", "exit_throttle") \
                and item.phase_distance_m is not None:
            # Keep the furthest exit: the first exit phase to be released is the
            # one that matters for "gear at exit".
            if window["exit_m"] is None or item.phase_distance_m > window["exit_m"]:
                window["exit_m"] = item.phase_distance_m
            window["source"] = "phases"
        if item.gain_end_distance_m is not None:
            window["straight_end_m"] = max(window["straight_end_m"],
                                           item.gain_end_distance_m)
    return windows


def reference_windows(
    corners: list,
    phase_lists: Iterable[list[CornerLoss]],
) -> dict[str, dict[str, Any]]:
    """The reference's own windows, read off the driver comparisons.

    Every comparison reports where the *reference* entered, apexed and exited,
    so the reference never needs its own comparison run. Medians keep one odd
    detection from moving the window.
    """
    collected: dict[str, dict[str, list[float]]] = {}
    for phases in phase_lists:
        for item in phases:
            bucket = collected.setdefault(item.corner_id, {})
            if item.phase == "entry" and item.reference_phase_distance_m is not None:
                bucket.setdefault("entry", []).append(item.reference_phase_distance_m)
            elif item.phase == "minimum_speed" and item.reference_apex_distance_m is not None:
                bucket.setdefault("apex", []).append(item.reference_apex_distance_m)
            elif item.phase in ("exit", "exit_brake", "exit_throttle") \
                    and item.reference_phase_distance_m is not None:
                bucket.setdefault("exit", []).append(item.reference_phase_distance_m)
            if item.gain_end_distance_m is not None:
                bucket.setdefault("straight_end", []).append(item.gain_end_distance_m)

    windows: dict[str, dict[str, Any]] = {}
    for index, corner in enumerate(corners):
        bucket = collected.get(corner.id, {})
        windows[corner.id] = {
            "entry_m": statistics.median(bucket["entry"]) if bucket.get("entry") else None,
            "apex_m": statistics.median(bucket["apex"]) if bucket.get("apex")
            else float(corner.apex_s_m),
            "exit_m": statistics.median(bucket["exit"]) if bucket.get("exit") else None,
            "straight_end_m": max(bucket.get("straight_end") or [corner.s_end_m]),
            "next_start_m": (float(corners[index + 1].s_start_m)
                             if index + 1 < len(corners) else float(corner.s_end_m)),
            "source": "reference_phases" if bucket else "corner_model",
        }
    return windows


def _indices_in(channels: CornerChannels, low_m: float, high_m: float) -> list[int]:
    return [i for i, d in enumerate(channels.distance) if low_m <= d <= high_m]


def _sample_at(channels: CornerChannels, values: list | None, at_m: float) -> Any:
    """The sample nearest ``at_m``, or ``None`` when the channel is absent."""
    if values is None or not channels.distance:
        return None
    best_index = min(range(len(channels.distance)),
                     key=lambda i: abs(channels.distance[i] - at_m))
    if abs(channels.distance[best_index] - at_m) > SAMPLE_TOLERANCE_M:
        return None
    return values[best_index]


def _gear_near(gear: list[int], distances: list[float], at_m: float,
               tolerance_m: float = 20.0) -> int | None:
    """The engaged gear nearest a distance.

    The game reports gear 0 mid-shift, and an apex is exactly where a downshift
    lands, so the nearest *engaged* gear within 20 m is used instead of
    refusing the fact.
    """
    candidates = [(abs(d - at_m), g) for d, g in zip(distances, gear)
                  if g and abs(d - at_m) <= tolerance_m]
    if not candidates:
        return None
    return min(candidates, key=lambda c: c[0])[1]


def _duty(flags: list[bool] | None, indices: list[int]) -> float | None:
    """Fraction of *known* samples where the flag is true."""
    if flags is None or not indices:
        return None
    known = [flags[i] for i in indices if flags[i] is not None]
    if not known:
        return None
    return sum(1 for value in known if value) / len(known)


def _steering_stats(steering: list[float] | None, distances: list[float],
                    indices: list[int]) -> tuple[int | None, float | None]:
    """Count direction changes and the spread of the per-metre change."""
    if steering is None or len(indices) < 3:
        return None, None
    rates: list[float] = []
    reversals = 0
    last_sign = 0
    for previous, current in zip(indices, indices[1:]):
        step = steering[current] - steering[previous]
        if abs(step) < STEERING_STEP:
            continue
        span = distances[current] - distances[previous]
        if span > 0:
            rates.append(step / span)
        sign = 1 if step > 0 else -1
        if last_sign and sign != last_sign:
            reversals += 1
        last_sign = sign
    if not rates:
        return reversals, None
    return reversals, statistics.pstdev(rates)


def _brake_area(brake: list[float], indices: list[int],
                distances: list[float]) -> float | None:
    if len(indices) < 2:
        return None
    total = 0.0
    for previous, current in zip(indices, indices[1:]):
        span = distances[current] - distances[previous]
        if span <= 0:
            continue
        total += (brake[previous] + brake[current]) / 2.0 * span
    return total


def _trail_depth(brake: list[float] | None, distances: list[float],
                 apex_m: float, end_m: float) -> float | None:
    """How far past the apex the brake stays on, up to the first release.

    The first release matters, not the last braking sample before some distant
    bound: a driver who releases at the apex and then brakes for the *next*
    corner must report 0 m, not the distance to that corner (which produced a
    220 m "trail-brake depth" at Village — la Tour's braking zone).
    """
    if brake is None:
        return None
    braked_before = any(
        pressure is not None and pressure > BRAKE_ON
        for distance, pressure in zip(distances, brake) if distance <= apex_m
    )
    if not braked_before:
        return None
    for distance, pressure in zip(distances, brake):
        if distance <= apex_m or pressure is None:
            continue
        if distance > end_m:
            break
        if pressure <= BRAKE_ON:
            # Released (or never applied) past the apex: 0 m or a few metres.
            return max(0.0, distance - apex_m)
    # Still on the brake at the bound: that is the depth, as far as we can see.
    return max(0.0, end_m - apex_m)


def extract_corner_extras(
    channels: CornerChannels,
    corner,
    window: dict[str, Any] | None = None,
    reference: CornerChannels | None = None,
) -> CornerExtras:
    """Measure one corner on one lap."""
    window = window or {}
    zone = _indices_in(channels, corner.s_start_m, corner.s_end_m)
    apex_m = float(window.get("apex_m") or corner.apex_s_m)
    entry_m = window.get("entry_m")
    exit_m = window.get("exit_m")
    straight_end_m = float(window.get("straight_end_m") or corner.s_end_m)

    extras = CornerExtras(
        corner_id=corner.id,
        corner_name=corner.display_name,
        apex_distance_m=float(corner.apex_s_m),
        window_source=str(window.get("source") or "corner_model"),
    )

    if channels.gear is not None and zone:
        gears = [channels.gear[i] for i in zone if channels.gear[i] > 0]
        if gears:
            extras.gear_min = min(gears)
        extras.gear_at_apex = _gear_near(channels.gear, channels.distance, apex_m)
        if exit_m is not None:
            extras.gear_at_exit = _gear_near(channels.gear, channels.distance, float(exit_m))

    # A detected entry that lands after the apex is a detection artefact (the
    # driver only lifted once past the model's apex); fall back to the zone.
    if entry_m is not None and float(entry_m) >= apex_m:
        entry_m = None

    if channels.brake is not None:
        # Braking for a corner starts before the model's corner zone: use the
        # detected entry, and only fall back to the zone when there is none.
        brake_window = (_indices_in(channels, float(entry_m), apex_m)
                        if entry_m is not None else zone)
        pressures = [channels.brake[i] for i in brake_window
                     if channels.brake[i] is not None]
        if pressures:
            extras.brake_peak = max(pressures)
        if entry_m is not None:
            area = _brake_area(channels.brake,
                               _indices_in(channels, float(entry_m), apex_m),
                               channels.distance)
            extras.brake_area = area
        # Trail braking is bounded by the release, the detected exit, the
        # corner's own end and the next corner's start, and it only exists if
        # the driver braked at all on the way in.
        trail_bound = min(
            float(exit_m) if exit_m is not None else float(corner.s_end_m),
            float(corner.s_end_m),
            float(window.get("next_start_m") or corner.s_end_m),
            straight_end_m,
        )
        if (extras.brake_peak or 0.0) >= TRAIL_MIN_BRAKE_PEAK:
            extras.trail_brake_depth_m = _trail_depth(
                channels.brake, channels.distance, apex_m, trail_bound)

    if channels.steering is not None:
        reversals, rate_std = _steering_stats(channels.steering, channels.distance, zone)
        extras.steering_reversals = reversals
        extras.steering_rate_std = rate_std

    if channels.rear_slip is not None:
        if zone:
            slips = [channels.rear_slip[i] for i in zone
                     if channels.rear_slip[i] is not None]
            if slips:
                extras.rear_slip_max_deg = max(slips)
        if exit_m is not None:
            extras.rear_slip_exit_deg = _sample_at(channels, channels.rear_slip, exit_m)

    if "tc_active" not in channels.unmeasurable:
        extras.tc_duty = _duty(channels.tc, zone)
    if "abs_active" not in channels.unmeasurable:
        extras.abs_duty = _duty(channels.abs_, zone)

    if channels.lateral is not None:
        lateral = _sample_at(channels, channels.lateral, apex_m)
        extras.lateral_at_apex_m = lateral
        if reference is not None and reference.lateral is not None:
            reference_lateral = _sample_at(reference, reference.lateral, apex_m)
            if lateral is not None and reference_lateral is not None:
                extras.lateral_offset_m = lateral - reference_lateral

    return extras


def extract_all_corners(
    channels: CornerChannels,
    corners: list,
    windows: dict[str, dict[str, Any]],
    reference: CornerChannels | None = None,
) -> list[CornerExtras]:
    """Measure every corner of one lap (or of the reference)."""
    return [
        extract_corner_extras(channels, corner, windows.get(corner.id), reference)
        for corner in corners
    ]


_SLIP_REASON = ("values wrap at ±180° and do not track turn rate or braking; "
                "not a slip angle as recorded")
_REASONS: dict[str, str] = {
    "abs_active": "no usable samples in this recording",
    "tc_active": "no usable samples in this recording",
    "slip_angle_rl_deg": _SLIP_REASON,
    "slip_angle_rr_deg": _SLIP_REASON,
}


def unmeasurable_channels(table: pa.Table) -> dict[str, str]:
    """Channels this session cannot support, with the reason.

    Three separate traps, all observed on committed recordings:

    - A flag column can be entirely null (``abs_active`` on older references)
      or null almost everywhere (``tc_active`` on older references, where only
      the true samples were written). A duty computed over those is a lie.
    - A flag that is false on every frame of every lap is either a dead channel
      or a car that never needed it, and we cannot tell which. "0% TC" would
      read as "your traction control never intervened".
    - The slip columns wrap at ±180° and their magnitude is uncorrelated with
      lateral demand (r=0.04 against turn rate, and *lower* under braking than
      at constant throttle), so they are not slip angles as recorded. See
      ``_slip_is_usable``.
    """
    dead: dict[str, str] = {}
    for column in _FLAG_COLUMNS:
        values = _column(table, column)
        if values is None:
            dead[column] = "channel absent from this recording"
            continue
        known = [v for v in values if v is not None]
        if len(known) < len(values) * 0.5:
            dead[column] = (f"only {len(known)} of {len(values)} samples are "
                            f"recorded, so a duty cannot be computed")
        elif not any(bool(v) for v in known):
            dead[column] = "never active in this session (dead channel or unused)"
    for column in _SLIP_COLUMNS:
        values = _column(table, column)
        if values is None:
            dead[column] = "channel absent from this recording"
            continue
        if not _slip_is_usable(values):
            dead[column] = _SLIP_REASON
    return dead


def _slip_is_usable(values: list[float]) -> bool:
    """A slip angle is small; a channel that wraps at ±180° is something else.

    Both committed fixtures store values spanning ±180° with a median near
    ±140°, small sample-to-sample changes and occasional 360° wraps: that is a
    wrapped angle, and its magnitude tracks neither turn rate nor braking.
    Returning "maximum rear slip 179.9 deg" to a driver would be worse than
    returning nothing.
    """
    known = [abs(v) for v in values if v is not None]
    if not known:
        return False
    return max(known) <= SLIP_SANE_MAX_DEG


def median_of(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def mode_of(values: list[int]) -> int | None:
    counts: dict[int, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda kv: kv[1])[0]


def aggregate_corners(laps: list) -> dict[str, CornerExtras]:
    """One representative channel set per corner: dominant gear, median trail."""
    collected: dict[str, list[CornerExtras]] = {}
    for lap in laps:
        for extra in getattr(lap, "corners", []):
            collected.setdefault(extra.corner_id, []).append(extra)

    aggregated: dict[str, CornerExtras] = {}
    for corner_id, items in collected.items():
        first = items[0]
        gears = [i.gear_at_apex for i in items if i.gear_at_apex]
        trails = [i.trail_brake_depth_m for i in items if i.trail_brake_depth_m is not None]
        aggregated[corner_id] = CornerExtras(
            corner_id=corner_id,
            corner_name=first.corner_name,
            apex_distance_m=first.apex_distance_m,
            window_source=first.window_source,
            gear_at_apex=mode_of(gears),
            gear_at_exit=mode_of([i.gear_at_exit for i in items if i.gear_at_exit]),
            trail_brake_depth_m=median_of(trails),
            lateral_at_apex_m=median_of(
                [i.lateral_at_apex_m for i in items if i.lateral_at_apex_m is not None]),
        )
    return aggregated
