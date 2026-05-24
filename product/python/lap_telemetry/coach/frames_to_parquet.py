"""Convert a list of Frame objects to a temporary Parquet file.

This is a bridge so that ``compare_laps()`` (which reads Parquet) can be
used on live Frame data.  The temp file is written once per completed lap
(~2500 rows, ~50 KB) and should be cleaned up by the caller after
comparison.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from lap_telemetry.recorder.connect import Frame
from lap_telemetry.recorder.writer import _SCHEMA


def frames_to_parquet(frames: list[Frame], suffix: str = ".parquet") -> Path:
    """Write a list of Frames to a temporary Parquet file.

    The file uses the same schema as ``SessionWriter`` so that
    ``compare_laps()`` can read it directly.

    Args:
        frames: List of Frame objects to write.
        suffix: File suffix for the temp file (default ``.parquet``).

    Returns:
        Path to the temporary Parquet file.  The caller is responsible
        for deleting this file when done (e.g. after ``compare_laps()``
        completes).
    """
    # Build column arrays matching the SessionWriter schema.
    session_time_s = [f.session_time_s for f in frames]
    lap_number = [f.lap_number for f in frames]
    lap_distance_m = [f.lap_distance_m for f in frames]
    lap_time_s = [f.lap_time_s for f in frames]
    speed_kph = [f.speed_kph for f in frames]
    throttle_norm = [f.throttle_norm for f in frames]
    brake_norm = [f.brake_norm for f in frames]
    steering_norm = [f.steering_norm for f in frames]
    gear = [f.gear for f in frames]
    engine_rpm = [f.engine_rpm for f in frames]
    lap_valid = [f.lap_valid for f in frames]
    pos_x_m = [f.pos_x_m for f in frames]
    pos_y_m = [f.pos_y_m for f in frames]
    pos_z_m = [f.pos_z_m for f in frames]
    last_sector_1_s = [f.last_sector_1_s for f in frames]
    last_sector_2_s = [f.last_sector_2_s for f in frames]
    slip_angle_fl_deg = [f.slip_angle_fl_deg for f in frames]
    slip_angle_fr_deg = [f.slip_angle_fr_deg for f in frames]
    slip_angle_rl_deg = [f.slip_angle_rl_deg for f in frames]
    slip_angle_rr_deg = [f.slip_angle_rr_deg for f in frames]
    abs_active = [f.abs_active for f in frames]
    tc_active = [f.tc_active for f in frames]
    raw_lap_distance_m = [f.raw_lap_distance_m for f in frames]
    path_lateral_m = [f.path_lateral_m for f in frames]
    track_edge_m = [f.track_edge_m for f in frames]
    distance_to_track_edge_m = [
        _distance_to_track_edge(f) for f in frames
    ]
    surface_type_fl = [f.surface_type_fl for f in frames]
    surface_type_fr = [f.surface_type_fr for f in frames]
    surface_type_rl = [f.surface_type_rl for f in frames]
    surface_type_rr = [f.surface_type_rr for f in frames]
    terrain_name_fl = [f.terrain_name_fl for f in frames]
    terrain_name_fr = [f.terrain_name_fr for f in frames]
    terrain_name_rl = [f.terrain_name_rl for f in frames]
    terrain_name_rr = [f.terrain_name_rr for f in frames]
    # Fuel and race-state columns (slice 08)
    fuel_l = [f.fuel_l for f in frames]
    fuel_capacity_l = [f.fuel_capacity_l for f in frames]
    session_type = [f.session_type for f in frames]
    session_time_remaining_s = [f.session_time_remaining_s for f in frames]
    race_laps_total = [f.race_laps_total for f in frames]

    # Build column dicts matching _SCHEMA field names.
    columns = {
        "session_time_s": session_time_s,
        "lap_number": lap_number,
        "lap_distance_m": lap_distance_m,
        "lap_time_s": lap_time_s,
        "speed_kph": speed_kph,
        "throttle_norm": throttle_norm,
        "brake_norm": brake_norm,
        "steering_norm": steering_norm,
        "gear": gear,
        "engine_rpm": engine_rpm,
        "lap_valid": lap_valid,
        "pos_x_m": pos_x_m,
        "pos_y_m": pos_y_m,
        "pos_z_m": pos_z_m,
        "last_sector_1_s": last_sector_1_s,
        "last_sector_2_s": last_sector_2_s,
        "slip_angle_fl_deg": slip_angle_fl_deg,
        "slip_angle_fr_deg": slip_angle_fr_deg,
        "slip_angle_rl_deg": slip_angle_rl_deg,
        "slip_angle_rr_deg": slip_angle_rr_deg,
        "abs_active": abs_active,
        "tc_active": tc_active,
        "raw_lap_distance_m": raw_lap_distance_m,
        "path_lateral_m": path_lateral_m,
        "track_edge_m": track_edge_m,
        "distance_to_track_edge_m": distance_to_track_edge_m,
        "surface_type_fl": surface_type_fl,
        "surface_type_fr": surface_type_fr,
        "surface_type_rl": surface_type_rl,
        "surface_type_rr": surface_type_rr,
        "terrain_name_fl": terrain_name_fl,
        "terrain_name_fr": terrain_name_fr,
        "terrain_name_rl": terrain_name_rl,
        "terrain_name_rr": terrain_name_rr,
        "fuel_l": fuel_l,
        "fuel_capacity_l": fuel_capacity_l,
        "session_type": session_type,
        "session_time_remaining_s": session_time_remaining_s,
        "race_laps_total": race_laps_total,
    }

    table = pa.table(columns, schema=_SCHEMA)

    # Write to a temp file.
    tmp = tempfile.NamedTemporaryFile(
        suffix=suffix, prefix="coach_lap_", delete=False,
    )
    tmp_path = Path(tmp.name)
    tmp.close()
    pq.write_table(table, tmp_path, compression="snappy")
    return tmp_path


def _distance_to_track_edge(frame: Frame) -> float | None:
    if frame.track_edge_m is None or frame.path_lateral_m is None:
        return None
    return frame.track_edge_m - abs(frame.path_lateral_m)