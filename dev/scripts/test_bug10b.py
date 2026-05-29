"""Tests for bug 10b: scoring lap-timing fields persisted in Parquet.

These tests are written first (TDD). They fail before the implementation
and pass after.
"""
import math
import tempfile
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from lap_telemetry.recorder.writer import SessionWriter, _SCHEMA
from lap_telemetry.recorder.connect import Frame


NEW_COLUMNS = [
    "scoring_lap_start_et_s",
    "scoring_last_lap_time_s",
    "scoring_time_into_lap_s",
    "scoring_total_laps",
]


def _make_frame(**overrides) -> Frame:
    """Minimal valid Frame for writer tests."""
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


# ── 1. Schema contains the new columns ───────────────────────────────────────

def test_schema_has_new_columns():
    schema_names = {f.name for f in _SCHEMA}
    for col in NEW_COLUMNS:
        assert col in schema_names, f"_SCHEMA is missing column: {col}"


def test_new_columns_are_nullable():
    schema_map = {f.name: f for f in _SCHEMA}
    for col in NEW_COLUMNS:
        assert col in schema_map, f"column missing: {col}"
        assert schema_map[col].nullable, f"{col} should be nullable"


# ── 2. Frame dataclass has the new fields ─────────────────────────────────────

def test_frame_has_new_fields():
    frame = _make_frame()
    for col in NEW_COLUMNS:
        assert hasattr(frame, col), f"Frame missing field: {col}"


def test_frame_new_fields_default_to_none():
    """New fields must have a None default so old call-sites still compile."""
    # Build a Frame WITHOUT the new kwargs — should succeed with None defaults
    import inspect
    sig = inspect.signature(Frame)
    for col in NEW_COLUMNS:
        param = sig.parameters.get(col)
        assert param is not None, f"Frame.{col} not in signature"
        assert param.default is None, f"Frame.{col} should default to None"


# ── 3. Round-trip: values survive write → read ────────────────────────────────

def test_round_trip_new_columns():
    frame = _make_frame(
        scoring_lap_start_et_s=78.0,
        scoring_last_lap_time_s=95.123,
        scoring_time_into_lap_s=45.0,
        scoring_total_laps=3,
    )

    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        writer = SessionWriter(out_dir, sim="lmu", track="bahrain-outer-circuit", rate_hz=50.0)
        writer.append(frame)
        parquet_path, _ = writer.close()

        table = pq.read_table(parquet_path)
        col_names = set(table.schema.names)

        for col in NEW_COLUMNS:
            assert col in col_names, f"written parquet missing column: {col}"

        row = {name: table.column(name)[0].as_py() for name in NEW_COLUMNS}
        assert abs(row["scoring_lap_start_et_s"] - 78.0) < 0.001
        assert abs(row["scoring_last_lap_time_s"] - 95.123) < 0.001
        assert abs(row["scoring_time_into_lap_s"] - 45.0) < 0.001
        assert row["scoring_total_laps"] == 3


def test_frames_to_parquet_includes_new_columns():
    """frames_to_parquet must also cover all _SCHEMA columns (regression for bug-10b crash)."""
    from lap_telemetry.coach.frames_to_parquet import frames_to_parquet
    frame = _make_frame()
    path = frames_to_parquet([frame])
    try:
        table = pq.read_table(path)
        for col in NEW_COLUMNS:
            assert col in table.schema.names, f"frames_to_parquet output missing column: {col}"
    finally:
        path.unlink(missing_ok=True)


def test_round_trip_null_values():
    """When new fields are None, they write and read back as None."""
    frame = _make_frame(
        scoring_lap_start_et_s=None,
        scoring_last_lap_time_s=None,
        scoring_time_into_lap_s=None,
        scoring_total_laps=None,
    )

    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        writer = SessionWriter(out_dir, sim="rf2", track="monza", rate_hz=50.0)
        writer.append(frame)
        parquet_path, _ = writer.close()

        table = pq.read_table(parquet_path)
        for col in NEW_COLUMNS:
            assert table.column(col)[0].as_py() is None, f"{col} should be null"
