"""Data structures for lap comparison coaching facts."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class PartialLapError(ValueError):
    """Raised when a lap's distance coverage is too incomplete for comparison."""


@dataclass
class PhaseDetectionThresholds:
    """Configurable thresholds for entry/exit phase detection.

    All thresholds operate on normalised 0–1 pedal traces unless noted.
    """

    throttle_lift: float = 0.9     # throttle < 0.9 → driver lifted
    brake_apply: float = 0.05     # brake > 0.05 → driver is braking
    brake_off: float = 0.01       # brake < 0.01 → brake fully released
    throttle_full: float = 0.95   # throttle ≥ 0.95 → back to full power
    exit_merge_tolerance_m: float = 3.0  # ≤ 3 m → merge exit phases
    exit_search_past_end_m: float = 50.0  # search up to 50 m past corner boundary for brake/throttle transitions


@dataclass
class CornerLoss:
    """Loss/gain analysis for a single corner phase."""
    corner_id: str
    corner_name: str
    apex_distance_m: float
    phase: str  # "minimum_speed" | "entry" | "exit" | "exit_brake" | "exit_throttle"
    loss_s: float  # positive = lost time, negative = gained
    driver_value: float
    reference_value: float
    unit: str
    confidence: str  # "high" | "medium" | "low"
    phase_distance_m: float | None = None  # distance where phase was measured; None = apex
    driver_apex_distance_m: float | None = None  # for minimum_speed: where driver hit min speed
    reference_apex_distance_m: float | None = None  # for minimum_speed: where reference hit min speed
    apex_offset_m: float | None = None  # for minimum_speed: ref_apex - driver_apex; positive = driver earlier
    gain_end_distance_m: float | None = None  # distance where measurement window stops (end of straight)
    entry_distance_delta_m: float | None = None  # for entry: ref_entry - driver_entry; positive = driver lifted later
    exit_distance_delta_m: float | None = None  # for exit: ref_exit - driver_exit; negative = driver exited earlier
    reference_phase_distance_m: float | None = None  # reference's corresponding phase distance
    target_throttle_pct: float | None = None  # corner's throttle target from model, if set


@dataclass
class LapComparisonFacts:
    """Structured facts from comparing two laps."""
    type: str
    track_id: str
    lap_number: int
    lap_time_delta_s: float
    top_losses: list[CornerLoss] = field(default_factory=list)
    top_gains: list[CornerLoss] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=lambda: {
        "max_words": 35,
        "style": "calm_concise_engineer"
    })

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        def _corner_dict(c: CornerLoss) -> dict[str, Any]:
            d: dict[str, Any] = {
                "corner_id": c.corner_id,
                "corner_name": c.corner_name,
                "apex_distance_m": c.apex_distance_m,
                "phase": c.phase,
                "loss_s": round(c.loss_s, 3),
                "driver_value": round(c.driver_value, 1),
                "reference_value": round(c.reference_value, 1),
                "unit": c.unit,
                "confidence": c.confidence,
            }
            if c.phase_distance_m is not None:
                d["phase_distance_m"] = round(c.phase_distance_m, 1)
            if c.driver_apex_distance_m is not None:
                d["driver_apex_distance_m"] = round(c.driver_apex_distance_m, 1)
            if c.reference_apex_distance_m is not None:
                d["reference_apex_distance_m"] = round(c.reference_apex_distance_m, 1)
            if c.apex_offset_m is not None:
                d["apex_offset_m"] = round(c.apex_offset_m, 1)
            if c.gain_end_distance_m is not None:
                d["gain_end_distance_m"] = round(c.gain_end_distance_m, 1)
            if c.entry_distance_delta_m is not None:
                d["entry_distance_delta_m"] = round(c.entry_distance_delta_m, 1)
            if c.exit_distance_delta_m is not None:
                d["exit_distance_delta_m"] = round(c.exit_distance_delta_m, 1)
            if c.reference_phase_distance_m is not None:
                d["reference_phase_distance_m"] = round(c.reference_phase_distance_m, 1)
            if c.target_throttle_pct is not None:
                d["target_throttle_pct"] = c.target_throttle_pct
            return d

        return {
            "type": self.type,
            "track_id": self.track_id,
            "lap_number": self.lap_number,
            "lap_time_delta_s": round(self.lap_time_delta_s, 3),
            "top_losses": [_corner_dict(c) for c in self.top_losses],
            "top_gains": [_corner_dict(c) for c in self.top_gains],
            "constraints": self.constraints,
        }