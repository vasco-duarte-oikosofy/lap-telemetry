"""Lap comparison engine for deterministic coaching facts."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from .track_model import TrackCoachingModel, Corner


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


# ---------------------------------------------------------------------------
# Resampling
# ---------------------------------------------------------------------------

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

    sorted_pairs = sorted(zip(distances, values), key=lambda x: x[0])
    xs = [p[0] for p in sorted_pairs]
    ys = [p[1] if p[1] is not None else 0.0 for p in sorted_pairs]

    def interp(x: float) -> float:
        if x <= xs[0]:
            return ys[0]
        if x >= xs[-1]:
            return ys[-1]
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


# ---------------------------------------------------------------------------
# Minimum speed (unchanged algorithm)
# ---------------------------------------------------------------------------

def compute_minimum_speed_per_corner(
    driver_speed: list[float],
    ref_speed: list[float],
    corner: Corner,
) -> tuple[float, float, float, float, float]:
    """Compute minimum speed, delta, and apex positions for a corner.

    Returns (driver_min_speed, ref_min_speed, speed_delta_kph,
             driver_apex_distance_m, reference_apex_distance_m).
    Positive speed_delta means driver was slower.
    Apex distances are the lap-distance positions where each lap
    reaches its minimum speed within the corner zone.
    """
    start_idx = int(corner.s_start_m)
    end_idx = min(int(corner.s_end_m) + 1, len(driver_speed))

    if start_idx >= len(driver_speed) or end_idx <= start_idx:
        return 0.0, 0.0, 0.0, float(start_idx), float(start_idx)

    driver_zone = driver_speed[start_idx:end_idx]
    driver_min = min(driver_zone)
    driver_min_offset = driver_zone.index(driver_min)
    driver_apex_m = float(start_idx + driver_min_offset)

    ref_zone = ref_speed[start_idx:end_idx]
    ref_min = min(ref_zone)
    ref_min_offset = ref_zone.index(ref_min)
    ref_apex_m = float(start_idx + ref_min_offset)

    return driver_min, ref_min, ref_min - driver_min, driver_apex_m, ref_apex_m


# ---------------------------------------------------------------------------
# Entry phase detection
# ---------------------------------------------------------------------------

def find_entry_point(
    speed: list[float],
    throttle: list[float] | None,
    brake: list[float] | None,
    corner: Corner,
    thresholds: PhaseDetectionThresholds = PhaseDetectionThresholds(),
) -> tuple[int, str]:
    """Find the entry phase distance for a corner.

    Walks backward from apex toward s_start_m using throttle (preferred)
    or speed local maximum (fallback) to determine where corner entry begins.

    Returns (distance_m, detection_method) where detection_method is one of
    'throttle_lift', 'speed_peak', or 'zone_start'.
    """
    start_idx = max(0, int(corner.s_start_m))
    apex_idx = min(int(corner.apex_s_m), len(speed) - 1)

    if apex_idx <= start_idx:
        return start_idx, "zone_start"

    # --- Throttle lift (preferred) ---
    if throttle is not None:
        # Scan from zone start toward apex. Find the first index where
        # throttle drops below threshold *after* being at or above it
        # (i.e. find the transition from full-throttle straight to lift-off).
        was_full_throttle = False
        for i in range(start_idx, apex_idx + 1):
            if i >= len(throttle):
                break
            if throttle[i] >= thresholds.throttle_lift:
                was_full_throttle = True
            elif was_full_throttle:
                return i, "throttle_lift"

    # --- Speed local maximum (fallback) ---
    zone_speeds = speed[start_idx:apex_idx + 1]
    if zone_speeds:
        max_val = max(zone_speeds)
        max_offset = zone_speeds.index(max_val)
        return start_idx + max_offset, "speed_peak"

    return start_idx, "zone_start"


def find_brake_point(
    brake: list[float] | None,
    corner: Corner,
    thresholds: PhaseDetectionThresholds = PhaseDetectionThresholds(),
) -> int | None:
    """Find the brake application point (secondary entry fact).

    Walks from s_start_m toward apex; returns the first index where brake
    rises above the threshold after being at or below it, or None.
    """
    if brake is None:
        return None

    start_idx = max(0, int(corner.s_start_m))
    apex_idx = min(int(corner.apex_s_m), len(brake) - 1)

    was_no_brake = False
    for i in range(start_idx, apex_idx + 1):
        if brake[i] <= thresholds.brake_apply:
            was_no_brake = True
        elif was_no_brake:
            return i

    return None


# ---------------------------------------------------------------------------
# Exit phase detection
# ---------------------------------------------------------------------------

def find_exit_points(
    brake: list[float] | None,
    throttle: list[float] | None,
    corner: Corner,
    thresholds: PhaseDetectionThresholds = PhaseDetectionThresholds(),
) -> list[tuple[str, int]]:
    """Find exit phase distances for a corner.

    Walks forward from apex toward s_end_m using brake and throttle
    channels to detect brake release (exit_brake) and full-throttle
    (exit_throttle) points.

    Returns list of (phase_name, distance_m).
    When both are detected and within merge tolerance, emits a single
    "exit" at the midpoint.  When only one channel is available, emits
    "exit" at that point.  Falls back to s_end_m when neither is found.
    """
    apex_idx = max(0, int(corner.apex_s_m))
    end_idx = min(int(corner.s_end_m), len(brake or throttle or []) - 1 if (brake or throttle) else int(corner.s_end_m))

    exit_brake_s: int | None = None
    exit_throttle_s: int | None = None

    # --- Brake release (exit-1) ---
    if brake is not None:
        end_idx_brake = min(int(corner.s_end_m), len(brake) - 1)
        was_braking = False
        for i in range(apex_idx, end_idx_brake + 1):
            if brake[i] > thresholds.brake_apply:
                was_braking = True
            if was_braking and brake[i] < thresholds.brake_off:
                exit_brake_s = i
                break

    # --- Full throttle (exit-2) ---
    if throttle is not None:
        end_idx_throttle = min(int(corner.s_end_m), len(throttle) - 1)
        was_partial = False
        for i in range(apex_idx, end_idx_throttle + 1):
            if throttle[i] < thresholds.throttle_full:
                was_partial = True
            if was_partial and throttle[i] >= thresholds.throttle_full:
                exit_throttle_s = i
                break

    # Merge logic
    if exit_brake_s is not None and exit_throttle_s is not None:
        if abs(exit_brake_s - exit_throttle_s) <= thresholds.exit_merge_tolerance_m:
            mid = round((exit_brake_s + exit_throttle_s) / 2)
            return [("exit", mid)]
        return [("exit_brake", exit_brake_s), ("exit_throttle", exit_throttle_s)]

    if exit_brake_s is not None:
        return [("exit", exit_brake_s)]
    if exit_throttle_s is not None:
        return [("exit", exit_throttle_s)]

    # Neither channel detected → fall back to zone boundary
    return [("exit", int(corner.s_end_m))]


# ---------------------------------------------------------------------------
# Legacy helpers (kept for backward compatibility with other callers)
# ---------------------------------------------------------------------------

def compute_corner_entry_loss(
    driver_speed: list[float],
    ref_speed: list[float],
    corner: Corner,
    entry_length_m: float = 30.0,
) -> tuple[float, float, float]:
    """Compute entry speed loss using a fixed offset (legacy)."""
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
    """Compute exit speed loss using a fixed offset (legacy)."""
    exit_idx = int(corner.apex_s_m + exit_length_m)
    if exit_idx < 0 or exit_idx >= len(driver_speed):
        return 0.0, 0.0, 0.0
    driver_exit = driver_speed[exit_idx]
    ref_exit = ref_speed[exit_idx]
    return driver_exit, ref_exit, ref_exit - driver_exit


# ---------------------------------------------------------------------------
# Column extraction helper
# ---------------------------------------------------------------------------

def _try_column(table, name: str) -> list[float] | None:
    """Extract a column from a Parquet table; return None if missing."""
    try:
        raw = table.column(name).to_pylist()
        return [v if v is not None else 0.0 for v in raw]
    except (KeyError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Main comparison
# ---------------------------------------------------------------------------

def compare_laps(
    current_lap_path: Path | str,
    reference_lap_path: Path | str,
    track_model: TrackCoachingModel,
    thresholds: PhaseDetectionThresholds | None = None,
) -> LapComparisonFacts:
    """Compare a current lap against a reference lap.

    Uses the phase-detection algorithm to find entry (throttle lift /
    speed peak) and exit (brake release / full throttle) distances per
    corner, instead of fixed 30 m offsets.

    Args:
        current_lap_path: Path to current lap Parquet file.
        reference_lap_path: Path to reference lap Parquet file.
        track_model: Track coaching model with corner definitions.
        thresholds: Phase detection thresholds (uses defaults if None).

    Returns:
        LapComparisonFacts with top losses and gains.
    """
    if thresholds is None:
        thresholds = PhaseDetectionThresholds()

    # Load both laps
    current_table = pq.read_table(current_lap_path)
    ref_table = pq.read_table(reference_lap_path)

    # Extract mandatory columns
    current_dist = current_table.column("lap_distance_m").to_pylist()
    current_speed = current_table.column("speed_kph").to_pylist()
    current_lap_times = current_table.column("lap_time_s").to_pylist()

    ref_dist = ref_table.column("lap_distance_m").to_pylist()
    ref_speed = ref_table.column("speed_kph").to_pylist()
    ref_lap_times = ref_table.column("lap_time_s").to_pylist()

    # Extract optional pedal channels
    driver_throttle = _try_column(current_table, "throttle_norm")
    driver_brake = _try_column(current_table, "brake_norm")
    # Reference pedal channels are not used for phase detection but
    # could be in a future slice; resample them for consistency.

    # Determine track length and resample
    max_dist = int(max(max(current_dist), max(ref_dist)))
    track_length = min(max_dist, int(track_model.lap_length_m))

    # Resample onto common 1 m grid
    driver_speed = resample_column(current_dist, current_speed, track_length)
    ref_speed_grid = resample_column(ref_dist, ref_speed, track_length)

    driver_throttle_grid: list[float] | None = None
    driver_brake_grid: list[float] | None = None
    if driver_throttle is not None:
        driver_throttle_grid = resample_column(current_dist, driver_throttle, track_length)
    if driver_brake is not None:
        driver_brake_grid = resample_column(current_dist, driver_brake, track_length)

    # Compute lap time delta
    driver_lap_time = max(t for t in current_lap_times if t is not None and t > 0)
    ref_lap_time = max(t for t in ref_lap_times if t is not None and t > 0)
    lap_time_delta = driver_lap_time - ref_lap_time

    # Get lap number
    lap_numbers = current_table.column("lap_number").to_pylist()
    lap_number = max(lap_numbers) if lap_numbers else 0

    # Analyze each corner
    corner_losses: list[CornerLoss] = []
    for corner in track_model.corners:
        # --- Minimum speed ---
        driver_min, ref_min, speed_delta, driver_apex_m, ref_apex_m = compute_minimum_speed_per_corner(
            driver_speed, ref_speed_grid, corner
        )
        if speed_delta > 0.5:
            corner_losses.append(CornerLoss(
                corner_id=corner.id,
                corner_name=corner.name,
                apex_distance_m=corner.apex_s_m,
                phase="minimum_speed",
                loss_s=speed_delta / 100.0,
                driver_value=driver_min,
                reference_value=ref_min,
                unit="km/h",
                confidence="high" if speed_delta > 2.0 else "medium",
                driver_apex_distance_m=driver_apex_m,
                reference_apex_distance_m=ref_apex_m,
            ))

        # --- Entry phase (algorithm-driven) ---
        entry_idx, _method = find_entry_point(
            driver_speed, driver_throttle_grid, driver_brake_grid,
            corner, thresholds,
        )
        if 0 <= entry_idx < len(driver_speed):
            driver_entry_speed = driver_speed[entry_idx]
            ref_entry_speed = ref_speed_grid[entry_idx]
            entry_delta = ref_entry_speed - driver_entry_speed
            if abs(entry_delta) > 1.0:
                corner_losses.append(CornerLoss(
                    corner_id=corner.id,
                    corner_name=corner.name,
                    apex_distance_m=corner.apex_s_m,
                    phase="entry",
                    loss_s=entry_delta / 100.0,
                    driver_value=driver_entry_speed,
                    reference_value=ref_entry_speed,
                    unit="km/h",
                    confidence="medium",
                    phase_distance_m=float(entry_idx),
                ))

        # --- Exit phase(s) (algorithm-driven) ---
        exit_points = find_exit_points(
            driver_brake_grid, driver_throttle_grid,
            corner, thresholds,
        )
        for phase_name, exit_idx in exit_points:
            if 0 <= exit_idx < len(driver_speed):
                driver_exit_speed = driver_speed[exit_idx]
                ref_exit_speed = ref_speed_grid[exit_idx]
                exit_delta = ref_exit_speed - driver_exit_speed
                if abs(exit_delta) > 1.0:
                    corner_losses.append(CornerLoss(
                        corner_id=corner.id,
                        corner_name=corner.name,
                        apex_distance_m=corner.apex_s_m,
                        phase=phase_name,
                        loss_s=exit_delta / 100.0,
                        driver_value=driver_exit_speed,
                        reference_value=ref_exit_speed,
                        unit="km/h",
                        confidence="medium",
                        phase_distance_m=float(exit_idx),
                    ))

    # Sort by loss magnitude
    corner_losses.sort(key=lambda x: x.loss_s, reverse=True)

    # Split into losses and gains
    losses = [c for c in corner_losses if c.loss_s > 0]
    gains = [c for c in corner_losses if c.loss_s < 0]

    top_losses = losses[:3]
    top_gains = sorted(gains, key=lambda x: x.loss_s)[:3]

    return LapComparisonFacts(
        type="lap_coaching_summary",
        track_id=track_model.track_id,
        lap_number=lap_number,
        lap_time_delta_s=lap_time_delta,
        top_losses=top_losses,
        top_gains=top_gains,
    )