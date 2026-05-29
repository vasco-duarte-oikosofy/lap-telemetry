"""Lap comparison engine for deterministic coaching facts."""
from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq

from lap_telemetry.parquet_utils import authoritative_duration, build_segments

from .entry_detection import find_entry_point, find_brake_point
from .exit_detection import find_exit_points
from .facts import PartialLapError, PhaseDetectionThresholds, CornerLoss, LapComparisonFacts
from .js_pipeline import run_js_pipeline, delta_t_ms_to_seconds
from .resample import resample_column, compute_delta_time_trace
from .track_model import TrackCoachingModel, Corner


_SLOW_LAP_RATIO_THRESHOLD = 1.15
_SLOW_LAP_RATIO_EPSILON = 1e-9


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


def _duration_segment_for_lap(table, lap_number: int | None) -> tuple[int, int, int | None, int | None]:
    """Find the segment whose duration should describe this comparison lap."""
    lap_numbers = table.column("lap_number").to_pylist()
    segments = build_segments(lap_numbers)
    if not segments:
        return (0, 0, None, None)

    selected_idx = 0
    if lap_number is not None:
        for idx, (seg_lap_number, _start, _end) in enumerate(segments):
            if seg_lap_number == lap_number:
                selected_idx = idx
                break

    _lap_num, start, end = segments[selected_idx]
    if selected_idx + 1 < len(segments):
        _next_lap, next_start, next_end = segments[selected_idx + 1]
        return (start, end, next_start, next_end)
    return (start, end, None, None)


def _segment_duration(
    table,
    segment: tuple[int, int, int | None, int | None],
    *,
    allow_same_segment_scoring: bool = False,
) -> float:
    start, end, next_start, next_end = segment
    return authoritative_duration(
        table,
        start,
        end,
        next_start,
        next_end,
        allow_same_segment_scoring=allow_same_segment_scoring,
    )


def _is_implausibly_slow_lap(driver_lap_time: float, ref_lap_time: float) -> bool:
    if driver_lap_time <= 0 or ref_lap_time <= 0:
        return False
    return (
        (driver_lap_time / ref_lap_time)
        > (_SLOW_LAP_RATIO_THRESHOLD + _SLOW_LAP_RATIO_EPSILON)
    )


def compare_laps(
    current_lap_path: Path | str,
    reference_lap_path: Path | str,
    track_model: TrackCoachingModel,
    thresholds: PhaseDetectionThresholds | None = None,
    top_n: int = 3,
    lap_number: int | None = None,
) -> LapComparisonFacts:
    """Compare a current lap against a reference lap.

    Uses phase-detection (throttle lift / speed peak / brake release /
    full throttle) per corner. Delta-t computed via JS pipeline
    (product/web/js/pipeline.js) to match the web UI exactly.

    Args:
        current_lap_path: Path to Parquet with current session data.
        reference_lap_path: Path to reference lap Parquet.
        track_model: Track coaching model for corner definitions.
        thresholds: Phase detection thresholds (default if None).
        top_n: Number of top losses/gains to return.
        lap_number: If set, filter current_lap_path to only this lap number
            before comparison. This is used by the coach to read data from
            the session Parquet instead of the bus buffer.
    """
    if thresholds is None:
        thresholds = PhaseDetectionThresholds()

    full_current_table = pq.read_table(current_lap_path)
    current_table = full_current_table
    current_duration_segment = _duration_segment_for_lap(full_current_table, lap_number)

    # Filter to a specific lap number if requested (for Parquet-based coach path).
    if lap_number is not None:
        lap_numbers = full_current_table.column("lap_number").to_pylist()
        mask = [ln == lap_number for ln in lap_numbers]
        current_table = full_current_table.filter(mask)

    # Strip stale cross-lap boundary frames: the first frame(s) of a new lap
    # sometimes carry the previous lap's position (dist > halfway) with a
    # negative lap_time_s. These cause the head-partial coverage check to fire
    # incorrectly and produce phantom speed readings at turn 1.
    _lt = current_table.column("lap_time_s").to_pylist()
    _ld = current_table.column("lap_distance_m").to_pylist()
    stale_mask = [
        not (lt < 0 and ld > track_model.lap_length_m * 0.5)
        for lt, ld in zip(_lt, _ld)
    ]
    if not all(stale_mask):
        current_table = current_table.filter(stale_mask)

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

    ref_table = pq.read_table(reference_lap_path)
    ref_duration_segment = _duration_segment_for_lap(ref_table, None)
    driver_lap_time = _segment_duration(full_current_table, current_duration_segment)
    ref_lap_time = _segment_duration(
        ref_table,
        ref_duration_segment,
        allow_same_segment_scoring=True,
    )
    if _is_implausibly_slow_lap(driver_lap_time, ref_lap_time):
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

    driver_throttle = _try_column(current_table, "throttle_norm")
    driver_brake = _try_column(current_table, "brake_norm")
    ref_throttle = _try_column(ref_table, "throttle_norm")
    ref_brake = _try_column(ref_table, "brake_norm")

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
                corner_id=corner.id, corner_name=corner.name,
                apex_distance_m=corner.apex_s_m, phase="minimum_speed",
                loss_s=loss_s, driver_value=driver_min,
                reference_value=ref_min, unit="km/h",
                confidence="high" if abs(speed_delta) > 2.0 else "medium",
                driver_apex_distance_m=driver_apex_m,
                reference_apex_distance_m=ref_apex_m,
                apex_offset_m=ref_apex_m - driver_apex_m,
                gain_end_distance_m=float(straight_end),
            ))

        # --- Entry phase ---
        entry_idx, _method = find_entry_point(
            driver_speed, driver_throttle_grid, driver_brake_grid,
            corner, thresholds,
        )
        # Detect reference entry point for distance delta
        ref_entry_idx = None
        entry_distance_delta_m = None
        reference_phase_distance_m = None
        if ref_throttle_grid is not None or ref_brake_grid is not None:
            ref_entry_idx_raw, _ = find_entry_point(
                ref_speed_grid, ref_throttle_grid, ref_brake_grid,
                corner, thresholds,
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
                    corner_id=corner.id, corner_name=corner.name,
                    apex_distance_m=corner.apex_s_m, phase="entry",
                    loss_s=loss_s, driver_value=driver_entry_speed,
                    reference_value=ref_entry_speed, unit="km/h",
                    confidence="medium",
                    phase_distance_m=float(entry_idx),
                    gain_end_distance_m=float(apex_idx),
                    entry_distance_delta_m=entry_distance_delta_m,
                    reference_phase_distance_m=reference_phase_distance_m,
                ))

        # --- Exit phase(s) ---
        exit_points = find_exit_points(
            driver_brake_grid, driver_throttle_grid, corner, thresholds,
        )
        # Detect reference exit points for distance delta
        ref_exit_by_phase: dict[str, int] = {}
        if ref_brake_grid is not None or ref_throttle_grid is not None:
            ref_exit_points = find_exit_points(
                ref_brake_grid, ref_throttle_grid, corner, thresholds,
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
                        corner_id=corner.id, corner_name=corner.name,
                        apex_distance_m=corner.apex_s_m, phase=phase_name,
                        loss_s=loss_s, driver_value=driver_exit_speed,
                        reference_value=ref_exit_speed, unit="km/h",
                        confidence="medium",
                        phase_distance_m=float(exit_idx),
                        gain_end_distance_m=float(straight_end),
                        exit_distance_delta_m=exit_distance_delta_m,
                        reference_phase_distance_m=ref_phase_distance_m,
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