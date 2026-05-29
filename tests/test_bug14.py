"""Tests for bug 14: on_lap_flushed fires with the wrong shard after bug-12 fix.

Root cause: record.py called flush_shard() BEFORE append()ing the boundary frame,
so _completed_lap_numbers was empty at flush time. The callback fired on the
subsequent timer-shard (which holds lap N+1 data), causing the coach to read
zero rows for lap N.

Fix: writer.lap_completed(lap_num) lets the caller register a completed lap
explicitly before flushing; _notified_lap_numbers prevents double-firing via
the auto-detection in append().
"""
from __future__ import annotations

import math
import tempfile
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from lap_telemetry.recorder.connect import Frame
from lap_telemetry.recorder.writer import SessionWriter


def _frame(lap_number: int, session_time_s: float, lap_distance_m: float) -> Frame:
    return Frame(
        sim="lmu",
        session_time_s=session_time_s,
        lap_number=lap_number,
        lap_distance_m=lap_distance_m,
        lap_time_s=session_time_s % 80.0,
        speed_kph=150.0,
        throttle_norm=0.8,
        brake_norm=0.0,
        steering_norm=0.0,
        gear=4,
        engine_rpm=8000.0,
        lap_valid=True,
        pos_x_m=0.0,
        pos_y_m=0.0,
        pos_z_m=0.0,
        last_sector_1_s=math.nan,
        last_sector_2_s=math.nan,
        slip_angle_fl_deg=0.0,
        slip_angle_fr_deg=0.0,
        slip_angle_rl_deg=0.0,
        slip_angle_rr_deg=0.0,
        abs_active=None,
        tc_active=None,
        in_realtime=True,
        paused=False,
        track_name="bahrain-outer-circuit",
        vehicle_name="dkr-engineering-4",
        player_scor_index=0,
        scoring_lap_start_et_s=0.0,
        scoring_last_lap_time_s=None,
        scoring_time_into_lap_s=session_time_s % 80.0,
        scoring_total_laps=2,
    )


def test_on_lap_flushed_fires_on_correct_shard(tmp_path):
    """Callback fires exactly once for lap 1, on the shard that contains lap-1 rows."""
    notifications: list[tuple[Path, int, int]] = []

    def on_lap_flushed(shard_path: Path, lap_num: int) -> None:
        t = pq.read_table(shard_path)
        rows = sum(1 for ln in t.column("lap_number").to_pylist() if ln == lap_num)
        notifications.append((shard_path, lap_num, rows))

    writer = SessionWriter(tmp_path, "lmu", "bahrain-outer-circuit", 50.0,
                           on_lap_flushed=on_lap_flushed)

    for i in range(5):
        writer.append(_frame(1, float(i * 15), float(i * 700)))

    # Fixed record.py pattern: register before flush
    writer.lap_completed(1)
    writer.flush_shard()

    assert len(notifications) == 1, f"Expected 1 notification, got {len(notifications)}"
    _, lap_num, rows = notifications[0]
    assert lap_num == 1
    assert rows == 5, f"Expected 5 lap-1 rows in shard, got {rows}"

    writer.close()


def test_timer_flush_does_not_double_fire(tmp_path):
    """The 30-second timer flush must NOT re-fire on_lap_flushed for an already-notified lap."""
    notifications: list[tuple[int]] = []

    def on_lap_flushed(shard_path: Path, lap_num: int) -> None:
        notifications.append(lap_num)

    writer = SessionWriter(tmp_path, "lmu", "bahrain-outer-circuit", 50.0,
                           on_lap_flushed=on_lap_flushed)

    for i in range(5):
        writer.append(_frame(1, float(i * 15), float(i * 700)))

    writer.lap_completed(1)
    writer.flush_shard()
    assert notifications == [1]

    # Append lap-2 frames (this sets _completed_lap_numbers via auto-detection
    # unless the guard is in place)
    for i in range(5):
        writer.append(_frame(2, 75.0 + i * 15, float(i * 700)))

    # Timer-based flush: must NOT fire lap 1 again
    writer.flush_shard()
    assert notifications == [1], (
        f"on_lap_flushed double-fired: notifications={notifications}"
    )

    writer.close()


def test_no_notification_without_lap_completed(tmp_path):
    """Without calling lap_completed(), flush_shard() must not fire the callback.

    Backward-compat: callers that never call lap_completed() see the same
    behaviour as before (auto-detection only fires at the next lap boundary).
    """
    notifications: list[int] = []

    def on_lap_flushed(shard_path: Path, lap_num: int) -> None:
        notifications.append(lap_num)

    writer = SessionWriter(tmp_path, "lmu", "bahrain-outer-circuit", 50.0,
                           on_lap_flushed=on_lap_flushed)

    for i in range(5):
        writer.append(_frame(1, float(i * 15), float(i * 700)))

    # Flush without calling lap_completed — callback must NOT fire
    writer.flush_shard()
    assert notifications == [], f"Expected no notifications, got {notifications}"

    writer.close()
