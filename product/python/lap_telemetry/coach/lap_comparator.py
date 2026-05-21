"""Lap comparison engine for deterministic coaching facts."""
from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq

from .entry_detection import find_entry_point, find_brake_point
from .exit_detection import find_exit_points
from .facts import PhaseDetectionThresholds, CornerLoss, LapComparisonFacts
from .js_pipeline import run_js_pipeline, delta_t_ms_to_seconds
from .resample import resample_column, compute_delta_time_trace
from .track_model import TrackCoachingModel, Corner


def compute_minimum_speed_per_corner(
    driver_speed: list[float],
    ref_speed: list[float],
    corner: Corner,
) -> tuple[float, float, float, float, float]:
    """Compute minimum speed, delta, and apex positions for a corner.

    Returns (driver_min_speed, ref_min_speed, speed_delta_kph,
             driver_apex_distance_m, reference_apex_distance_m).
    Positive speed_delta means driver was slower.
    """
    start_idx = int(corner.s_start_m)
    end_idx = min(int(corner.s_end_m) + 1, len(driver_speed))
    if start_idx >= len(driver_speed) or end_idx <= start_idx:
        return 0.0, 0.0, 0.0, float(start_idx), float(start_idx)

    driver_zone = driver_speed[start_idx:end_idx]
    driver_min = min(driver_zone)
    driver_apex_m = float(start_idx + driver_zone.index(driver_min))

    ref_zone = ref_speed[start_idx:end_idx]
    ref_min = min(ref_zone)
    ref_apex_m = float(start_idx + ref_zone.index(ref_min))

    return driver_min, ref_min, ref_min - driver_min, driver_apex_m, ref_apex_m


def find_straight_end_after_corner(
    corner_index: int,
    corners: list[Corner],
    driver_speed: list[float],
    driver_throttle: list[float] | None,
    driver_brake: list[float] | None,
    thresholds: PhaseDetectionThresholds = PhaseDetectionThresholds(),
    track_length: int = 0,
) -> int:
    """Find the distance where the straight after corner_index ends.

    This is the entry point of the next corner (throttle lift or brake onset).
    For the last corner, returns track_length - 1 (end of lap).
    """
    if corner_index >= len(corners) - 1:
        return track_length - 1 if track_length > 0 else 0
    next_corner = corners[corner_index + 1]
    entry_idx, _method = find_entry_point(
        driver_speed, driver_throttle, driver_brake,
        next_corner, thresholds,
    )
    return entry_idx


def _try_column(table, name: str) -> list[float] | None:
    """Extract a column from a Parquet table; return None if missing."""
    try:
        raw = table.column(name).to_pylist()
        return [v if v is not None else 0.0 for v in raw]
    except (KeyError, AttributeError):
        return None


def compare_laps(
    current_lap_path: Path | str,
    reference_lap_path: Path | str,
    track_model: TrackCoachingModel,
    thresholds: PhaseDetectionThresholds | None = None,
    top_n: int = 3,
) -> LapComparisonFacts:
    """Compare a current lap against a reference lap.

    Uses phase-detection (throttle lift / speed peak / brake release /
    full throttle) per corner. Delta-t computed via JS pipeline
    (product/web/js/pipeline.js) to match the web UI exactly.
    """
    if thresholds is None:
        thresholds = PhaseDetectionThresholds()

    current_table = pq.read_table(current_lap_path)
    ref_table = pq.read_table(reference_lap_path)

    current_dist = current_table.column("lap_distance_m").to_pylist()
    current_speed = current_table.column("speed_kph").to_pylist()
    current_lap_times = current_table.column("lap_time_s").to_pylist()

    ref_dist = ref_table.column("lap_distance_m").to_pylist()
    ref_speed = ref_table.column("speed_kph").to_pylist()
    ref_lap_times = ref_table.column("lap_time_s").to_pylist()

    driver_throttle = _try_column(current_table, "throttle_norm")
    driver_brake = _try_column(current_table, "brake_norm")

    max_dist = int(max(max(current_dist), max(ref_dist)))
    track_length = min(max_dist, int(track_model.lap_length_m))

    js_result = run_js_pipeline(
        driver_lap_time_s=current_lap_times,
        driver_lap_distance_m=current_dist,
        driver_speed_kph=current_speed,
        ref_lap_time_s=ref_lap_times,
        ref_lap_distance_m=ref_dist,
        ref_speed_kph=ref_speed,
        track_length=track_length,
        driver_throttle_norm=driver_throttle,
        driver_brake_norm=driver_brake,
    )

    delta_t = delta_t_ms_to_seconds(js_result["delta_t_ms"])
    driver_speed = js_result["driver_speed_kph"]
    ref_speed_grid = js_result["ref_speed_kph"]
    driver_throttle_grid = js_result["driver_throttle_norm"]
    driver_brake_grid = js_result["driver_brake_norm"]
    track_length = js_result["track_length"]

    driver_lap_time = max(t for t in current_lap_times if t is not None and t > 0)
    ref_lap_time = max(t for t in ref_lap_times if t is not None and t > 0)
    lap_time_delta = driver_lap_time - ref_lap_time

    lap_numbers = current_table.column("lap_number").to_pylist()
    lap_number = max(lap_numbers) if lap_numbers else 0

    corner_losses: list[CornerLoss] = []
    for corner_idx, corner in enumerate(track_model.corners):
        straight_end = find_straight_end_after_corner(
            corner_idx, track_model.corners,
            driver_speed, driver_throttle_grid, driver_brake_grid,
            thresholds, track_length,
        )

        # --- Minimum speed ---
        driver_min, ref_min, speed_delta, driver_apex_m, ref_apex_m = (
            compute_minimum_speed_per_corner(driver_speed, ref_speed_grid, corner)
        )
        if abs(speed_delta) > 0.5:
            if speed_delta > 0:
                loss_s = speed_delta / 100.0
            else:
                apex_idx = int(driver_apex_m)
                if 0 <= apex_idx < len(delta_t) and 0 <= straight_end < len(delta_t):
                    loss_s = delta_t[straight_end] - delta_t[apex_idx]
                else:
                    loss_s = speed_delta / 100.0

            corner_losses.append(CornerLoss(
                corner_id=corner.id, corner_name=corner.name,
                apex_distance_m=corner.apex_s_m, phase="minimum_speed",
                loss_s=loss_s, driver_value=driver_min,
                reference_value=ref_min, unit="km/h",
                confidence="high" if abs(speed_delta) > 2.0 else "medium",
                driver_apex_distance_m=driver_apex_m,
                reference_apex_distance_m=ref_apex_m,
                apex_offset_m=ref_apex_m - driver_apex_m,
                gain_end_distance_m=float(straight_end) if speed_delta < 0 else None,
            ))

        # --- Entry phase ---
        entry_idx, _method = find_entry_point(
            driver_speed, driver_throttle_grid, driver_brake_grid,
            corner, thresholds,
        )
        if 0 <= entry_idx < len(driver_speed):
            driver_entry_speed = driver_speed[entry_idx]
            ref_entry_speed = ref_speed_grid[entry_idx]
            entry_delta = ref_entry_speed - driver_entry_speed
            if abs(entry_delta) > 1.0:
                apex_idx = int(corner.apex_s_m)
                if entry_delta < 0:
                    if (0 <= entry_idx < len(delta_t)
                            and 0 <= apex_idx < len(delta_t)
                            and entry_idx < apex_idx):
                        loss_s = delta_t[apex_idx] - delta_t[entry_idx]
                    else:
                        loss_s = entry_delta / 100.0
                else:
                    loss_s = entry_delta / 100.0

                corner_losses.append(CornerLoss(
                    corner_id=corner.id, corner_name=corner.name,
                    apex_distance_m=corner.apex_s_m, phase="entry",
                    loss_s=loss_s, driver_value=driver_entry_speed,
                    reference_value=ref_entry_speed, unit="km/h",
                    confidence="medium",
                    phase_distance_m=float(entry_idx),
                    gain_end_distance_m=float(apex_idx) if entry_delta < 0 else None,
                ))

        # --- Exit phase(s) ---
        exit_points = find_exit_points(
            driver_brake_grid, driver_throttle_grid, corner, thresholds,
        )
        for phase_name, exit_idx in exit_points:
            if 0 <= exit_idx < len(driver_speed):
                driver_exit_speed = driver_speed[exit_idx]
                ref_exit_speed = ref_speed_grid[exit_idx]
                exit_delta = ref_exit_speed - driver_exit_speed
                if abs(exit_delta) > 1.0:
                    if exit_delta > 0:
                        loss_s = exit_delta / 100.0
                    else:
                        if (0 <= exit_idx < len(delta_t)
                                and 0 <= straight_end < len(delta_t)):
                            loss_s = delta_t[straight_end] - delta_t[exit_idx]
                        else:
                            loss_s = exit_delta / 100.0

                    corner_losses.append(CornerLoss(
                        corner_id=corner.id, corner_name=corner.name,
                        apex_distance_m=corner.apex_s_m, phase=phase_name,
                        loss_s=loss_s, driver_value=driver_exit_speed,
                        reference_value=ref_exit_speed, unit="km/h",
                        confidence="medium",
                        phase_distance_m=float(exit_idx),
                        gain_end_distance_m=float(straight_end) if exit_delta < 0 else None,
                    ))

    corner_losses.sort(key=lambda x: x.loss_s, reverse=True)
    losses = [c for c in corner_losses if c.loss_s > 0]
    gains = [c for c in corner_losses if c.loss_s < 0]
    top_losses = losses[:top_n]
    top_gains = sorted(gains, key=lambda x: x.loss_s)[:top_n]

    return LapComparisonFacts(
        type="lap_coaching_summary",
        track_id=track_model.track_id,
        lap_number=lap_number,
        lap_time_delta_s=lap_time_delta,
        top_losses=top_losses,
        top_gains=top_gains,
    )