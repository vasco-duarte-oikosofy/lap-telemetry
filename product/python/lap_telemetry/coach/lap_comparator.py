"""Lap comparison engine for deterministic coaching facts."""
from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from .entry_detection import find_entry_point, find_brake_point
from .exit_detection import find_exit_points
from .facts import PartialLapError, PhaseDetectionThresholds, CornerLoss, LapComparisonFacts
from .js_pipeline import run_js_pipeline, delta_t_ms_to_seconds
from .lap_table import (
    duration_segment_for_lap,
    is_implausibly_slow_lap,
    segment_duration,
    strip_stale_boundary_frames,
    try_column,
)
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


def phase_window_bounds(corners: list[Corner], index: int) -> tuple[float, float | None]:
    """Return the phase-search bounds imposed by a corner's neighbours.

    Returns ``(entry_floor_m, exit_ceiling_m)``. A corner's entry may not be
    detected before the previous corner ends, and its exit may not be detected
    past the next corner's start. Monza's chained turns (Roggia 1/2 at
    2130/2131, Ascari 1/2/3) touch, so without these bounds each corner's
    windows reach into its neighbour (bug 32).

    ``exit_ceiling_m`` is ``None`` for the last corner, which has no successor.
    """
    corner = corners[index]
    entry_floor = corners[index - 1].s_end_m if index > 0 else 0.0
    exit_ceiling = None
    if index + 1 < len(corners):
        next_start = corners[index + 1].s_start_m
        # Ignore a successor that starts before this corner (lap wrap-around).
        if next_start > corner.s_start_m:
            exit_ceiling = next_start
    return entry_floor, exit_ceiling


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
        min_distance_m=corners[corner_index].s_end_m,
    )
    return entry_idx



def compare_lap_tables(
    driver_table: pa.Table,
    reference_table: pa.Table,
    track_model: TrackCoachingModel,
    *,
    driver_lap_time_s: float,
    reference_lap_time_s: float,
    thresholds: PhaseDetectionThresholds | None = None,
    top_n: int | None = 3,
) -> LapComparisonFacts:
    """Compare one lap's rows against the reference table.

    This is the single implementation of the analysis. ``compare_laps`` wraps
    it for a Parquet path and a lap number; the session debrief wraps it for a
    lap *segment*, which is the only correct identity when a sim restart resets
    ``lap_number`` mid-recording.

    Args:
        driver_table: Rows of exactly one lap.
        reference_table: Rows of the reference lap.
        track_model: Corner definitions and track length.
        driver_lap_time_s: Authoritative duration of the driver's lap.
        reference_lap_time_s: Authoritative duration of the reference lap.
        thresholds: Phase detection thresholds (default if None).
        top_n: Number of losses and gains to return, or ``None`` for every one.
    """
    if thresholds is None:
        thresholds = PhaseDetectionThresholds()

    current_table = strip_stale_boundary_frames(driver_table, track_model.lap_length_m)

    # Guard against partial-lap data before the expensive JS pipeline.
    _guard_dist = current_table.column("lap_distance_m").to_pylist()
    if not _guard_dist:
        raise PartialLapError("no frames for requested lap")
    if min(_guard_dist) > track_model.lap_length_m * 0.10:
        raise PartialLapError(
            f"lap starts at {min(_guard_dist):.0f}m — "
            f"tail-partial shard (threshold {track_model.lap_length_m * 0.10:.0f}m)"
        )
    if max(_guard_dist) < track_model.lap_length_m * 0.80:
        raise PartialLapError(
            f"lap ends at {max(_guard_dist):.0f}m — "
            f"head-partial or session-end (threshold {track_model.lap_length_m * 0.80:.0f}m)"
        )

    ref_table = reference_table
    driver_lap_time = driver_lap_time_s
    ref_lap_time = reference_lap_time_s
    if is_implausibly_slow_lap(driver_lap_time, ref_lap_time):
        ratio = driver_lap_time / ref_lap_time
        raise PartialLapError(
            f"lap duration {driver_lap_time:.1f}s is {ratio * 100:.0f}% of "
            f"reference {ref_lap_time:.1f}s — likely pitstop or safety-car lap"
        )

    current_dist = current_table.column("lap_distance_m").to_pylist()
    current_speed = current_table.column("speed_kph").to_pylist()
    current_lap_times = current_table.column("lap_time_s").to_pylist()

    ref_dist = ref_table.column("lap_distance_m").to_pylist()
    ref_speed = ref_table.column("speed_kph").to_pylist()
    ref_lap_times = ref_table.column("lap_time_s").to_pylist()

    driver_throttle = try_column(current_table, "throttle_norm")
    driver_brake = try_column(current_table, "brake_norm")
    ref_throttle = try_column(ref_table, "throttle_norm")
    ref_brake = try_column(ref_table, "brake_norm")

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
        ref_throttle_norm=ref_throttle,
        ref_brake_norm=ref_brake,
    )

    delta_t = delta_t_ms_to_seconds(js_result["delta_t_ms"])
    driver_speed = js_result["driver_speed_kph"]
    ref_speed_grid = js_result["ref_speed_kph"]
    driver_throttle_grid = js_result["driver_throttle_norm"]
    driver_brake_grid = js_result["driver_brake_norm"]
    ref_throttle_grid = js_result.get("ref_throttle_norm")
    ref_brake_grid = js_result.get("ref_brake_norm")
    track_length = js_result["track_length"]

    lap_time_delta = driver_lap_time - ref_lap_time

    lap_numbers = current_table.column("lap_number").to_pylist()
    lap_number = max(lap_numbers) if lap_numbers else 0

    corner_losses: list[CornerLoss] = []
    for corner_idx, corner in enumerate(track_model.corners):
        entry_floor, exit_ceiling = phase_window_bounds(track_model.corners, corner_idx)
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
            apex_idx = int(driver_apex_m)
            if (0 <= apex_idx < len(delta_t)
                    and 0 <= straight_end < len(delta_t)):
                loss_s = delta_t[straight_end] - delta_t[apex_idx]
            else:
                loss_s = speed_delta / 100.0

            corner_losses.append(CornerLoss(
                corner_id=corner.id, corner_name=corner.display_name,
                apex_distance_m=corner.apex_s_m, phase="minimum_speed",
                loss_s=loss_s, driver_value=driver_min,
                reference_value=ref_min, unit="km/h",
                confidence="high" if abs(speed_delta) > 2.0 else "medium",
                driver_apex_distance_m=driver_apex_m,
                reference_apex_distance_m=ref_apex_m,
                apex_offset_m=ref_apex_m - driver_apex_m,
                gain_end_distance_m=float(straight_end),
                target_throttle_pct=corner.target_throttle_pct,
            ))

        # --- Entry phase ---
        entry_idx, _method = find_entry_point(
            driver_speed, driver_throttle_grid, driver_brake_grid,
            corner, thresholds, min_distance_m=entry_floor,
        )
        # Detect reference entry point for distance delta
        ref_entry_idx = None
        entry_distance_delta_m = None
        reference_phase_distance_m = None
        if ref_throttle_grid is not None or ref_brake_grid is not None:
            ref_entry_idx_raw, _ = find_entry_point(
                ref_speed_grid, ref_throttle_grid, ref_brake_grid,
                corner, thresholds, min_distance_m=entry_floor,
            )
            if 0 <= ref_entry_idx_raw < len(ref_speed_grid):
                ref_entry_idx = ref_entry_idx_raw
                entry_distance_delta_m = float(ref_entry_idx - entry_idx)
                reference_phase_distance_m = float(ref_entry_idx)

        if 0 <= entry_idx < len(driver_speed):
            driver_entry_speed = driver_speed[entry_idx]
            ref_entry_speed = ref_speed_grid[entry_idx]
            entry_delta = ref_entry_speed - driver_entry_speed
            if abs(entry_delta) > 1.0:
                apex_idx = int(corner.apex_s_m)
                if (0 <= entry_idx < len(delta_t)
                        and 0 <= apex_idx < len(delta_t)
                        and entry_idx < apex_idx):
                    loss_s = delta_t[apex_idx] - delta_t[entry_idx]
                else:
                    loss_s = entry_delta / 100.0

                corner_losses.append(CornerLoss(
                    corner_id=corner.id, corner_name=corner.display_name,
                    apex_distance_m=corner.apex_s_m, phase="entry",
                    loss_s=loss_s, driver_value=driver_entry_speed,
                    reference_value=ref_entry_speed, unit="km/h",
                    confidence="medium",
                    phase_distance_m=float(entry_idx),
                    gain_end_distance_m=float(apex_idx),
                    entry_distance_delta_m=entry_distance_delta_m,
                    reference_phase_distance_m=reference_phase_distance_m,
                    target_throttle_pct=corner.target_throttle_pct,
                ))

        # --- Exit phase(s) ---
        exit_points = find_exit_points(
            driver_brake_grid, driver_throttle_grid, corner, thresholds,
            max_distance_m=exit_ceiling,
        )
        # Detect reference exit points for distance delta
        ref_exit_by_phase: dict[str, int] = {}
        if ref_brake_grid is not None or ref_throttle_grid is not None:
            ref_exit_points = find_exit_points(
                ref_brake_grid, ref_throttle_grid, corner, thresholds,
                max_distance_m=exit_ceiling,
            )
            ref_exit_by_phase = {phase: dist for phase, dist in ref_exit_points}

        for phase_name, exit_idx in exit_points:
            exit_distance_delta_m = None
            ref_phase_distance_m = None
            if ref_exit_by_phase:
                ref_exit_idx = ref_exit_by_phase.get(phase_name)
                # Fallback: driver has merged "exit" but ref has split phases
                if ref_exit_idx is None and phase_name == "exit":
                    ref_dists = list(ref_exit_by_phase.values())
                    ref_exit_idx = min(ref_dists, key=lambda d: abs(d - exit_idx))
                # Fallback: driver has split phase but ref has merged "exit"
                if ref_exit_idx is None and phase_name in ("exit_brake", "exit_throttle") \
                        and "exit" in ref_exit_by_phase:
                    ref_exit_idx = ref_exit_by_phase["exit"]
                if ref_exit_idx is not None:
                    exit_distance_delta_m = float(ref_exit_idx - exit_idx)
                    ref_phase_distance_m = float(ref_exit_idx)

            if 0 <= exit_idx < len(driver_speed):
                driver_exit_speed = driver_speed[exit_idx]
                ref_exit_speed = ref_speed_grid[exit_idx]
                exit_delta = ref_exit_speed - driver_exit_speed
                if abs(exit_delta) > 1.0:
                    if (0 <= exit_idx < len(delta_t)
                            and 0 <= straight_end < len(delta_t)):
                        loss_s = delta_t[straight_end] - delta_t[exit_idx]
                    else:
                        loss_s = exit_delta / 100.0

                    corner_losses.append(CornerLoss(
                        corner_id=corner.id, corner_name=corner.display_name,
                        apex_distance_m=corner.apex_s_m, phase=phase_name,
                        loss_s=loss_s, driver_value=driver_exit_speed,
                        reference_value=ref_exit_speed, unit="km/h",
                        confidence="medium",
                        phase_distance_m=float(exit_idx),
                        gain_end_distance_m=float(straight_end),
                        exit_distance_delta_m=exit_distance_delta_m,
                        reference_phase_distance_m=ref_phase_distance_m,
                        target_throttle_pct=corner.target_throttle_pct,
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

def compare_laps(
    current_lap_path: Path | str,
    reference_lap_path: Path | str,
    track_model: TrackCoachingModel,
    thresholds: PhaseDetectionThresholds | None = None,
    top_n: int | None = 3,
    lap_number: int | None = None,
) -> LapComparisonFacts:
    """Compare one lap of a Parquet file against a reference lap.

    Phase detection (throttle lift / brake release / full throttle) and the
    delta-t trace come from ``product/web/js/pipeline.js``, so the numbers match
    the web UI exactly.

    ``lap_number`` selects the lap by lap number, which is only a valid identity
    when the file holds a single stint or a one-lap shard — a sim restart resets
    lap numbering mid-recording. The session debrief therefore calls
    ``compare_lap_tables`` directly with a lap segment.
    """
    full_current_table = pq.read_table(current_lap_path)
    current_table = full_current_table
    if lap_number is not None:
        lap_numbers = full_current_table.column("lap_number").to_pylist()
        current_table = full_current_table.filter([ln == lap_number for ln in lap_numbers])

    ref_table = pq.read_table(reference_lap_path)
    return compare_lap_tables(
        current_table,
        ref_table,
        track_model,
        driver_lap_time_s=segment_duration(
            full_current_table,
            duration_segment_for_lap(full_current_table, lap_number),
        ),
        reference_lap_time_s=segment_duration(
            ref_table,
            duration_segment_for_lap(ref_table, None),
            allow_same_segment_scoring=True,
        ),
        thresholds=thresholds,
        top_n=top_n,
    )
