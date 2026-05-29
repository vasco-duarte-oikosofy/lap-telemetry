"""Tests for bug 11: frames_to_parquet schema completeness guard.

Asserts that frames_to_parquet produces a table whose column set exactly
matches _SCHEMA field names — so future schema additions fail here rather
than crashing at runtime.
"""
import math
import tempfile
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from lap_telemetry.recorder.writer import _SCHEMA
from lap_telemetry.recorder.connect import Frame
from lap_telemetry.coach.frames_to_parquet import frames_to_parquet


def _make_frame(**overrides) -> Frame:
    defaults = dict(
        sim="lmu",
        session_time_s=123.0,
        lap_number=2,
        lap_distance_m=500.0,
        lap_time_s=45.0,
        speed_kph=200.0,
        throttle_norm=0.8,
        brake_norm=0.0,
        steering_norm=0.1,
        gear=4,
        engine_rpm=8000.0,
        lap_valid=True,
        pos_x_m=10.0,
        pos_y_m=0.0,
        pos_z_m=20.0,
        last_sector_1_s=math.nan,
        last_sector_2_s=math.nan,
        slip_angle_fl_deg=0.5,
        slip_angle_fr_deg=0.5,
        slip_angle_rl_deg=0.3,
        slip_angle_rr_deg=0.3,
        abs_active=None,
        tc_active=None,
        in_realtime=True,
        paused=False,
        track_name="bahrain-outer-circuit",
        vehicle_name="dkr-engineering-4",
        player_scor_index=0,
        scoring_lap_start_et_s=78.0,
        scoring_last_lap_time_s=95.123,
        scoring_time_into_lap_s=45.0,
        scoring_total_laps=3,
    )
    defaults.update(overrides)
    return Frame(**defaults)


def test_frames_to_parquet_schema_matches_schema_exactly():
    """Column set must exactly match _SCHEMA — no extras, no omissions."""
    frame = _make_frame()
    path = frames_to_parquet([frame])
    try:
        table = pq.read_table(path)
        expected = {f.name for f in _SCHEMA}
        actual = set(table.schema.names)
        missing = expected - actual
        extra = actual - expected
        assert not missing, f"frames_to_parquet output missing columns: {missing}"
        assert not extra, f"frames_to_parquet output has unexpected extra columns: {extra}"
    finally:
        path.unlink(missing_ok=True)


def test_frames_to_parquet_schema_order_matches():
    """Column order must match _SCHEMA field order."""
    frame = _make_frame()
    path = frames_to_parquet([frame])
    try:
        table = pq.read_table(path)
        expected = [f.name for f in _SCHEMA]
        assert list(table.schema.names) == expected
    finally:
        path.unlink(missing_ok=True)


def test_frames_to_parquet_distance_to_track_edge_computed():
    """distance_to_track_edge_m is derived, not read directly from frame."""
    frame = _make_frame(track_edge_m=3.0, path_lateral_m=1.0)
    path = frames_to_parquet([frame])
    try:
        table = pq.read_table(path)
        val = table.column("distance_to_track_edge_m")[0].as_py()
        assert abs(val - 2.0) < 0.001
    finally:
        path.unlink(missing_ok=True)


def test_frames_to_parquet_distance_to_track_edge_null_when_missing():
    """distance_to_track_edge_m is null when track_edge_m or path_lateral_m is None."""
    frame = _make_frame(track_edge_m=None, path_lateral_m=None)
    path = frames_to_parquet([frame])
    try:
        table = pq.read_table(path)
        val = table.column("distance_to_track_edge_m")[0].as_py()
        assert val is None
    finally:
        path.unlink(missing_ok=True)
