"""Track coaching model loader and validator."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Corner:
    """A corner zone in the track coaching model."""
    id: str
    name: str
    s_start_m: float
    apex_s_m: float
    s_end_m: float
    apex_side: str  # "left" | "right"
    target_throttle_pct: float | None = None  # 0–100, optional throttle target at apex

    def contains(self, distance_m: float) -> bool:
        """Check if a distance is within this corner zone.

        Handles wrap-around corners where apex/exit precede entry
        (e.g. decreasing-radius / late-braking corners).
        """
        if self.s_start_m <= self.s_end_m:
            return self.s_start_m <= distance_m <= self.s_end_m
        else:
            # Wrap-around: zone spans from entry to lap-length, then 0 to exit
            return distance_m >= self.s_start_m or distance_m <= self.s_end_m


@dataclass
class StraightZone:
    """A straight zone where speech is allowed."""
    id: str
    s_start_m: float
    s_end_m: float

    def contains(self, distance_m: float) -> bool:
        """Check if a distance is within this straight zone."""
        return self.s_start_m <= distance_m <= self.s_end_m


@dataclass
class TrackCoachingModel:
    """Track coaching model with corners and speech zones."""
    schema_version: str
    track_id: str
    layout_id: str
    lap_length_m: float
    corners: list[Corner] = field(default_factory=list)
    straight_zones: list[StraightZone] = field(default_factory=list)

    def get_corner_at(self, distance_m: float) -> Corner | None:
        """Get the corner at a given distance, or None if in a straight."""
        for corner in self.corners:
            if corner.contains(distance_m):
                return corner
        return None

    def get_straight_at(self, distance_m: float) -> StraightZone | None:
        """Get the straight zone at a given distance, or None if in a corner."""
        for zone in self.straight_zones:
            if zone.contains(distance_m):
                return zone
        return None

    def is_in_speech_zone(self, distance_m: float) -> bool:
        """Check if currently in a straight zone where speech is allowed."""
        return self.get_straight_at(distance_m) is not None


class TrackModelValidationError(ValueError):
    """Raised when track coaching model validation fails."""
    pass


def validate_corner(data: dict[str, Any], index: int) -> Corner:
    """Validate and create a Corner from raw data."""
    required = ["id", "name", "s_start_m", "apex_s_m", "s_end_m", "apex_side"]
    missing = [k for k in required if k not in data]
    if missing:
        raise TrackModelValidationError(f"Corner {index}: missing fields: {missing}")

    if data["apex_side"] not in ("left", "right"):
        raise TrackModelValidationError(
            f"Corner {data['id']}: apex_side must be 'left' or 'right', got {data['apex_side']}"
        )

    # s_end_m must be positive but may be less than s_start_m for
    # decreasing-radius / late-braking corners (apex before entry marker)
    if data["s_end_m"] <= 0:
        raise TrackModelValidationError(
            f"Corner {data['id']}: s_end_m must be positive, got {data['s_end_m']}"
        )
    # apex_s_m may be outside [s_start_m, s_end_m] for decreasing-radius
    # or late-braking corners where the apex occurs before the entry marker

    throttle = data.get("target_throttle_pct")
    if throttle is not None:
        throttle = float(throttle)
        if not (0 <= throttle <= 100):
            raise TrackModelValidationError(
                f"Corner {data['id']}: target_throttle_pct must be 0–100, got {throttle}"
            )

    return Corner(
        id=data["id"],
        name=data["name"],
        s_start_m=float(data["s_start_m"]),
        apex_s_m=float(data["apex_s_m"]),
        s_end_m=float(data["s_end_m"]),
        apex_side=data["apex_side"],
        target_throttle_pct=throttle,
    )


def validate_straight_zone(data: dict[str, Any], index: int) -> StraightZone:
    """Validate and create a StraightZone from raw data."""
    required = ["id", "s_start_m", "s_end_m"]
    missing = [k for k in required if k not in data]
    if missing:
        raise TrackModelValidationError(f"Straight zone {index}: missing fields: {missing}")

    if data["s_start_m"] >= data["s_end_m"]:
        raise TrackModelValidationError(
            f"Straight zone {data['id']}: s_start_m must be < s_end_m"
        )

    return StraightZone(
        id=data["id"],
        s_start_m=float(data["s_start_m"]),
        s_end_m=float(data["s_end_m"]),
    )


def load_track_coaching_model(path: Path | str) -> TrackCoachingModel:
    """Load and validate a track coaching model from JSON.

    Args:
        path: Path to the JSON file.

    Returns:
        Validated TrackCoachingModel.

    Raises:
        TrackModelValidationError: If the model is invalid.
        FileNotFoundError: If the file doesn't exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # Validate schema version
    if data.get("schema_version") != "1":
        raise TrackModelValidationError(
            f"Unsupported schema_version: {data.get('schema_version')}. Expected '1'."
        )

    # Validate required top-level fields
    required = ["track_id", "layout_id", "lap_length_m", "corners"]
    missing = [k for k in required if k not in data]
    if missing:
        raise TrackModelValidationError(f"Missing required fields: {missing}")

    # Validate corners
    corners = []
    for i, corner_data in enumerate(data["corners"]):
        corners.append(validate_corner(corner_data, i))

    # Validate straight zones (optional)
    straight_zones = []
    for i, zone_data in enumerate(data.get("straight_zones", [])):
        straight_zones.append(validate_straight_zone(zone_data, i))

    # Validate lap_length_m is positive
    if data["lap_length_m"] <= 0:
        raise TrackModelValidationError("lap_length_m must be positive")

    return TrackCoachingModel(
        schema_version=data["schema_version"],
        track_id=data["track_id"],
        layout_id=data["layout_id"],
        lap_length_m=float(data["lap_length_m"]),
        corners=corners,
        straight_zones=straight_zones,
    )
