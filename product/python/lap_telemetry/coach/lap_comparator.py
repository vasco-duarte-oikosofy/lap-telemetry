"""Lap comparison engine for deterministic coaching facts."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from .track_model import TrackCoachingModel, Corner


@dataclass
class CornerLoss:
    """Loss/gain analysis for a single corner."""
    corner_id: str
    corner_name: str
    apex_distance_m: float
    phase: str  # "minimum_speed" | "entry" | "exit"
    loss_s: float  # positive = lost time, negative = gained
    driver_value: float
    reference_value: float
    unit: str
    confidence: str  # "high" | "medium" | "low"


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
        return {
            "type": self.type,
            "track_id": self.track_id,
            "lap_number": self.lap_number,
            "lap_time_delta_s": round(self.lap_time_delta_s, 3),
            "top_losses": [
                {
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
                for c in self.top_losses
            ],
            "top_gains": [
                {
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
                for c in self.top_gains
            ],
            "constraints": self.constraints,
        }


def resample_column(distances: list[float], values: list[float], max_dist: int) -> list[float]:
    """Resample a column onto a 1-meter distance grid using linear interpolation.

    Args:
        distances: Lap distance values in meters.
        values: Corresponding values to resample.
        max_dist: Maximum distance to resample to (exclusive).

    Returns:
        List of resampled values, one per meter.
    """
    if not distances:
        return []

    # Sort by distance
    sorted_pairs = sorted(zip(distances, values), key=lambda x: x[0])
    xs = [p[0] for p in sorted_pairs]
    ys = [p[1] if p[1] is not None else 0.0 for p in sorted_pairs]

    def interp(x: float) -> float:
        if x <= xs[0]:
            return ys[0]
        if x >= xs[-1]:
            return ys[-1]

        # Binary search for the right interval
        lo, hi = 0, len(xs) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if xs[mid] <= x:
                lo = mid
            else:
                hi = mid

        if xs[hi] == xs[lo]:
            return ys[lo]

        t = (x - xs[lo]) / (xs[hi] - xs[lo])
        return ys[lo] + t * (ys[hi] - ys[lo])

    return [interp(float(d)) for d in range(max_dist)]


def compute_minimum_speed_per_corner(
    driver_speed: list[float],
    ref_speed: list[float],
    corner: Corner,
) -> tuple[float, float, float]:
    """Compute minimum speed and delta for a corner.

    Args:
        driver_speed: Resampled driver speed array (kph).
        ref_speed: Resampled reference speed array (kph).
        corner: Corner definition.

    Returns:
        Tuple of (driver_min_speed, ref_min_speed, speed_delta_kph).
        Positive delta means driver was slower.
    """
    start_idx = int(corner.s_start_m)
    end_idx = min(int(corner.s_end_m) + 1, len(driver_speed))

    if start_idx >= len(driver_speed) or end_idx <= start_idx:
        return 0.0, 0.0, 0.0

    driver_min = min(driver_speed[start_idx:end_idx])
    ref_min = min(ref_speed[start_idx:end_idx])

    return driver_min, ref_min, ref_min - driver_min


def compute_corner_entry_loss(
    driver_speed: list[float],
    ref_speed: list[float],
    corner: Corner,
    entry_length_m: float = 30.0,
) -> tuple[float, float, float]:
    """Compute entry speed loss for a corner.

    Args:
        driver_speed: Resampled driver speed array (kph).
        ref_speed: Resampled reference speed array (kph).
        corner: Corner definition.
        entry_length_m: Length of entry zone to analyze.

    Returns:
        Tuple of (driver_entry_speed, ref_entry_speed, speed_delta_kph).
        Entry speed is measured at entry_length_m before apex.
    """
    entry_idx = int(corner.apex_s_m - entry_length_m)
    if entry_idx < 0 or entry_idx >= len(driver_speed):
        return 0.0, 0.0, 0.0

    driver_entry = driver_speed[entry_idx]
    ref_entry = ref_speed[entry_idx]

    return driver_entry, ref_entry, ref_entry - driver_entry


def compute_corner_exit_loss(
    driver_speed: list[float],
    ref_speed: list[float],
    corner: Corner,
    exit_length_m: float = 30.0,
) -> tuple[float, float, float]:
    """Compute exit speed loss for a corner.

    Args:
        driver_speed: Resampled driver speed array (kph).
        ref_speed: Resampled reference speed array (kph).
        corner: Corner definition.
        exit_length_m: Length of exit zone to analyze.

    Returns:
        Tuple of (driver_exit_speed, ref_exit_speed, speed_delta_kph).
        Exit speed is measured at exit_length_m after apex.
    """
    exit_idx = int(corner.apex_s_m + exit_length_m)
    if exit_idx < 0 or exit_idx >= len(driver_speed):
        return 0.0, 0.0, 0.0

    driver_exit = driver_speed[exit_idx]
    ref_exit = ref_speed[exit_idx]

    return driver_exit, ref_exit, ref_exit - driver_exit


def compare_laps(
    current_lap_path: Path | str,
    reference_lap_path: Path | str,
    track_model: TrackCoachingModel,
) -> LapComparisonFacts:
    """Compare a current lap against a reference lap.

    Args:
        current_lap_path: Path to current lap Parquet file.
        reference_lap_path: Path to reference lap Parquet file.
        track_model: Track coaching model with corner definitions.

    Returns:
        LapComparisonFacts with top losses and gains.
    """
    # Load both laps
    current_table = pq.read_table(current_lap_path)
    ref_table = pq.read_table(reference_lap_path)

    # Extract columns
    current_dist = current_table.column("lap_distance_m").to_pylist()
    current_speed = current_table.column("speed_kph").to_pylist()
    current_lap_times = current_table.column("lap_time_s").to_pylist()

    ref_dist = ref_table.column("lap_distance_m").to_pylist()
    ref_speed = ref_table.column("speed_kph").to_pylist()
    ref_lap_times = ref_table.column("lap_time_s").to_pylist()

    # Determine track length and resample
    max_dist = int(max(max(current_dist), max(ref_dist)))
    track_length = min(max_dist, int(track_model.lap_length_m))

    # Resample speeds onto common grid
    driver_speed = resample_column(current_dist, current_speed, track_length)
    ref_speed = resample_column(ref_dist, ref_speed, track_length)

    # Compute lap time delta
    driver_lap_time = max(t for t in current_lap_times if t is not None and t > 0)
    ref_lap_time = max(t for t in ref_lap_times if t is not None and t > 0)
    lap_time_delta = driver_lap_time - ref_lap_time

    # Get lap number from current lap
    lap_numbers = current_table.column("lap_number").to_pylist()
    lap_number = max(lap_numbers) if lap_numbers else 0

    # Analyze each corner
    corner_losses: list[CornerLoss] = []
    for corner in track_model.corners:
        # Minimum speed analysis
        driver_min, ref_min, speed_delta = compute_minimum_speed_per_corner(
            driver_speed, ref_speed, corner
        )

        if speed_delta > 0.5:  # Only report if loss > 0.5 kph
            corner_losses.append(CornerLoss(
                corner_id=corner.id,
                corner_name=corner.name,
                apex_distance_m=corner.apex_s_m,
                phase="minimum_speed",
                loss_s=speed_delta / 100.0,  # Rough conversion to time
                driver_value=driver_min,
                reference_value=ref_min,
                unit="km/h",
                confidence="high" if speed_delta > 2.0 else "medium",
            ))

        # Entry speed analysis
        driver_entry, ref_entry, entry_delta = compute_corner_entry_loss(
            driver_speed, ref_speed, corner
        )

        if entry_delta > 1.0:  # Only report if loss > 1 kph
            corner_losses.append(CornerLoss(
                corner_id=corner.id,
                corner_name=corner.name,
                apex_distance_m=corner.apex_s_m,
                phase="entry",
                loss_s=entry_delta / 100.0,
                driver_value=driver_entry,
                reference_value=ref_entry,
                unit="km/h",
                confidence="medium",
            ))

        # Exit speed analysis
        driver_exit, ref_exit, exit_delta = compute_corner_exit_loss(
            driver_speed, ref_speed, corner
        )

        if exit_delta > 1.0:  # Only report if loss > 1 kph
            corner_losses.append(CornerLoss(
                corner_id=corner.id,
                corner_name=corner.name,
                apex_distance_m=corner.apex_s_m,
                phase="exit",
                loss_s=exit_delta / 100.0,
                driver_value=driver_exit,
                reference_value=ref_exit,
                unit="km/h",
                confidence="medium",
            ))

    # Sort by loss magnitude
    corner_losses.sort(key=lambda x: x.loss_s, reverse=True)

    # Split into losses and gains
    losses = [c for c in corner_losses if c.loss_s > 0]
    gains = [c for c in corner_losses if c.loss_s < 0]

    # Take top 3 of each
    top_losses = losses[:3]
    top_gains = sorted(gains, key=lambda x: x.loss_s)[:3]  # Most negative first

    return LapComparisonFacts(
        type="lap_coaching_summary",
        track_id=track_model.track_id,
        lap_number=lap_number,
        lap_time_delta_s=lap_time_delta,
        top_losses=top_losses,
        top_gains=top_gains,
    )
