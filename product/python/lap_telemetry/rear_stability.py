"""What the session's rear-slip measurements say, and what they may not claim.

Three states, never two: ``measured_instability`` (a lap above the car's own
envelope, cited with its segment), ``no_detected_instability`` (valid samples and
nothing above the envelope — explicitly *not* a claim of universal stability) and
``unknown`` (absent channels, dead channels, invalid samples, or too few measured
laps). The slip number itself comes from :mod:`lap_telemetry.rear_slip`; this
module only classifies it, so no surface can invent a different one.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any

from .rear_slip import (
    APEX_HALF_WINDOW_M,
    INSTABILITY_BASELINE_FACTOR,
    INSTABILITY_MIN_DEG,
    MIN_COVERAGE,
)

@dataclass
class RearStability:
    """What the session's own rear-slip measurements say about one corner."""

    corner_id: str
    corner_name: str
    state: str
    value_deg: float | None = None
    baseline_deg: float | None = None
    threshold_deg: float | None = None
    braking_deg: float | None = None
    brake_overlap: bool = False
    window: str = f"apex ±{APEX_HALF_WINDOW_M:.0f} m"
    metric: str = "rear slip angle"
    unit: str = "deg"
    source: str = "rear wheel ground velocities (atan2)"
    clean_laps: int = 0
    measured_laps: int = 0
    flagged: list[dict[str, Any]] = field(default_factory=list)
    reason: str = ""

    @property
    def measured(self) -> bool:
        return self.state == "measured_instability"

    @property
    def unknown(self) -> bool:
        return self.state == "unknown"

    @property
    def worst(self) -> dict[str, Any]:
        """The flagged observation the prose cites: the highest apex slip."""
        if not self.flagged:
            return {}
        return max(self.flagged, key=lambda item: item.get("apex_deg") or 0.0)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "corner_id": self.corner_id,
            "corner_name": self.corner_name,
            "state": self.state,
            "metric": self.metric,
            "unit": self.unit,
            "window": self.window,
            "source": self.source,
            "brake_overlap": self.brake_overlap,
            "clean_laps": self.clean_laps,
            "measured_laps": self.measured_laps,
            "flagged": self.flagged,
        }
        for name in ("value_deg", "baseline_deg", "threshold_deg", "braking_deg"):
            value = getattr(self, name)
            if value is not None:
                data[name] = round(float(value), 2)
        if self.reason:
            data["reason"] = self.reason
        return data


CLEAN_LAP_SUFFIX = ", a lap excluded as not clean"


def lap_phrase(flagged: dict[str, Any] | None) -> str:
    """``"segment 32 (lap 32), a lap excluded as not clean"``.

    Four surfaces quote this: the report sentence, the priority suggestion, the
    grounding block and the plan. Built once so they cannot disagree about
    whether an observation came from a clean lap.
    """
    if not flagged or flagged.get("segment_index") is None:
        return ""
    phrase = f"segment {flagged['segment_index']} (lap {flagged.get('lap_number')})"
    if flagged.get("clean") is False:
        phrase += CLEAN_LAP_SUFFIX
    return phrase


def _corner_extras(laps: list, corner_id: str) -> list[tuple[Any, Any]]:
    pairs = []
    for lap in laps:
        for extra in getattr(lap, "corners", []) or []:
            if extra.corner_id == corner_id:
                pairs.append((lap, extra))
    return pairs


def assess_corner(laps: list, corner_id: str, *,
                  unmeasurable: dict[str, str] | None = None) -> RearStability:
    """Classify one corner: measured instability, none detected, or unknown."""
    unmeasurable = unmeasurable or {}
    pairs = _corner_extras(laps, corner_id)
    name = pairs[0][1].corner_name if pairs else corner_id
    clean = [extra for lap, extra in pairs
             if getattr(lap, "clean", True) and extra.rear_slip_apex_deg is not None]
    clean_total = sum(1 for lap, _e in pairs if getattr(lap, "clean", True))

    def unknown(reason: str) -> RearStability:
        return RearStability(corner_id=corner_id, corner_name=name,
                             state="unknown", clean_laps=clean_total,
                             measured_laps=len(clean), reason=reason)

    absent = unmeasurable.get("wheel_ground_vel_lat_rl")
    if not clean_total:
        return unknown(absent or "no clean lap measured this corner")
    if not clean:
        return unknown(absent or "no rear-slip sample passed the validity checks in "
                                 "this corner on any clean lap")
    if len(clean) < MIN_COVERAGE * clean_total:
        return unknown(f"the rear slip angle is measurable on only {len(clean)} of "
                       f"{clean_total} clean laps")

    baseline = statistics.median([e.rear_slip_apex_deg for e in clean])
    threshold = max(INSTABILITY_MIN_DEG, INSTABILITY_BASELINE_FACTOR * baseline)
    flagged = []
    for lap, extra in pairs:
        value = extra.rear_slip_apex_deg
        if value is None or value < threshold:
            continue
        flagged.append({
            "segment_index": getattr(lap, "segment_index", None),
            "lap_number": getattr(lap, "lap_number", None),
            "clean": bool(getattr(lap, "clean", True)),
            "apex_deg": round(float(value), 2),
            "braking_deg": (round(float(extra.rear_slip_braking_deg), 2)
                            if extra.rear_slip_braking_deg is not None else None),
        })

    stability = RearStability(
        corner_id=corner_id, corner_name=name,
        state="measured_instability" if flagged else "no_detected_instability",
        baseline_deg=float(baseline), threshold_deg=float(threshold),
        clean_laps=clean_total, measured_laps=len(clean), flagged=flagged,
    )
    if flagged:
        worst = max(flagged, key=lambda item: item["apex_deg"])
        stability.value_deg = worst["apex_deg"]
        stability.braking_deg = worst["braking_deg"]
        stability.brake_overlap = (worst["braking_deg"] is not None
                                   and worst["braking_deg"] >= threshold)
    return stability


def assess_session(facts) -> dict[str, RearStability]:
    """Every corner of a session, keyed by corner id."""
    unmeasurable = getattr(facts.session, "unmeasurable_channels", {}) or {}
    return {corner.corner_id: assess_corner(facts.laps, corner.corner_id,
                                            unmeasurable=unmeasurable)
            for corner in facts.reference_corners}


def describe(stability: RearStability) -> str:
    """One sentence a driver reads, in the three states the contract allows.

    Every number here is a number the facts carry, so the model validator can
    check a reply that repeats it.
    """
    baseline = (f"the session's {stability.baseline_deg:.2f} deg clean-lap baseline"
                if stability.baseline_deg is not None else "no baseline")
    if stability.state == "unknown":
        return f"rear stability not measurable: {stability.reason}"
    if stability.state == "no_detected_instability":
        return (f"rear slip stays within the car's normal envelope here "
                f"(peak {stability.threshold_deg:.2f} deg threshold, {baseline}) "
                f"— no instability detected, which is not a claim that the car "
                f"is stable everywhere")
    worst = stability.worst
    where = f" on {lap_phrase(worst)}" if worst else ""
    phase = (f" and while still on the brake ({stability.braking_deg:.2f} deg with the "
             f"brake applied)" if stability.brake_overlap else
             " — the recording does not show the brake on during the slide, so it "
             "is not evidence of brake-induced oversteer")
    return (f"rear slip reaches {stability.value_deg:.2f} deg at the apex{where} "
            f"against {baseline}{phase}")
