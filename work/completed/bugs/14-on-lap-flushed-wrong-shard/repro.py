"""Repro for bug 14: on_lap_flushed fires with the wrong shard after bug-12 fix.

Run from project root:
    python work/active/bugs/14-on-lap-flushed-wrong-shard/repro.py

Expected output shows TWO failures:
  1. Boundary flush fires on_lap_flushed for lap 1 with a shard that has 0 lap-1 rows
     (the callback fires on the timer-shard, not the boundary-shard).
  2. The boundary-shard (which DOES contain lap-1 data) never triggers any callback.

After the fix both assertions at the bottom should pass.
"""
from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "product/python")

import pyarrow.parquet as pq

from lap_telemetry.recorder.connect import Frame
from lap_telemetry.recorder.writer import SessionWriter


# ---------------------------------------------------------------------------
# Minimal Frame factory
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Simulate the record.py loop — CURRENT (broken) behaviour
# ---------------------------------------------------------------------------

def simulate_record_loop_broken(out_dir: Path) -> list[tuple[Path, int]]:
    """Simulates the bug-12-fixed record.py loop (broken on_lap_flushed timing).

    Timeline:
      - 5 frames on lap 1 (dist 0..4000m in steps)
      - lap boundary detected → flush_shard() called BEFORE append()
        → _completed_lap_numbers is still {} → on_lap_flushed never fires here
      - boundary frame appended → append() sets _completed_lap_numbers = {1}
      - 4 more frames on lap 2
      - 30-second timer flush → on_lap_flushed fires with the LAP-2 shard, not lap-1 shard
    """
    notifications: list[tuple[Path, int]] = []

    def on_lap_flushed(shard_path: Path, lap_num: int) -> None:
        t = pq.read_table(shard_path)
        lap1_rows = sum(1 for ln in t.column("lap_number").to_pylist() if ln == lap_num)
        notifications.append((shard_path, lap_num))
        print(
            f"  on_lap_flushed: lap={lap_num}  shard={shard_path.name}"
            f"  rows_for_this_lap={lap1_rows}"
            f"  {'<-- WRONG: 0 rows for completed lap' if lap1_rows == 0 else '<-- OK'}"
        )

    writer = SessionWriter(out_dir, "lmu", "bahrain-outer-circuit", 50.0,
                           on_lap_flushed=on_lap_flushed)

    last_lap = -1

    def process_frame(frame: Frame) -> None:
        nonlocal last_lap
        if frame.lap_number != last_lap:
            if last_lap >= 0:
                # BUG: flush_shard() called before append(), so _completed_lap_numbers is empty
                writer.flush_shard()
                print(f"  [boundary flush] lap {last_lap} -> {frame.lap_number}"
                      f"  (completed_laps at flush time: {writer._completed_lap_numbers})")
            last_lap = frame.lap_number
        writer.append(frame)

    # 5 frames on lap 1
    for i in range(5):
        process_frame(_frame(1, float(i * 15), float(i * 700)))

    print("\n--- lap boundary fires ---")
    # First frame of lap 2 triggers boundary detection
    process_frame(_frame(2, 75.0, 0.0))

    # 4 more lap-2 frames
    for i in range(1, 5):
        process_frame(_frame(2, 75.0 + i * 15, float(i * 700)))

    print("\n--- timer-based flush (simulating 30s interval) ---")
    # This flush sees _completed_lap_numbers = {1} → fires on_lap_flushed
    # but the shard now contains lap-2 frames
    writer.flush_shard()

    writer.close()
    return notifications


# ---------------------------------------------------------------------------
# Simulate the record.py loop — FIXED behaviour
# ---------------------------------------------------------------------------

def simulate_record_loop_fixed(out_dir: Path) -> list[tuple[Path, int]]:
    """Simulates the fixed record.py loop.

    Fix: writer.lap_completed(last_lap) is called before flush_shard() so
    _completed_lap_numbers = {last_lap} at flush time → on_lap_flushed fires
    on the correct shard (the one that contains the completed lap's data).
    """
    notifications: list[tuple[Path, int]] = []

    def on_lap_flushed(shard_path: Path, lap_num: int) -> None:
        t = pq.read_table(shard_path)
        lap_rows = sum(1 for ln in t.column("lap_number").to_pylist() if ln == lap_num)
        notifications.append((shard_path, lap_num))
        print(
            f"  on_lap_flushed: lap={lap_num}  shard={shard_path.name}"
            f"  rows_for_this_lap={lap_rows}"
            f"  {'<-- OK' if lap_rows > 0 else '<-- WRONG'}"
        )

    writer = SessionWriter(out_dir, "lmu", "bahrain-outer-circuit", 50.0,
                           on_lap_flushed=on_lap_flushed)

    last_lap = -1

    def process_frame(frame: Frame) -> None:
        nonlocal last_lap
        if frame.lap_number != last_lap:
            if last_lap >= 0:
                # FIX: register completed lap BEFORE flushing
                writer.lap_completed(last_lap)
            writer.flush_shard()
            print(f"  [boundary flush] lap {last_lap} -> {frame.lap_number}"
                  f"  (completed_laps at flush time: {writer._completed_lap_numbers})")
            last_lap = frame.lap_number
        writer.append(frame)

    for i in range(5):
        process_frame(_frame(1, float(i * 15), float(i * 700)))

    print("\n--- lap boundary fires ---")
    process_frame(_frame(2, 75.0, 0.0))

    for i in range(1, 5):
        process_frame(_frame(2, 75.0 + i * 15, float(i * 700)))

    print("\n--- timer-based flush (simulating 30s interval) ---")
    writer.flush_shard()

    writer.close()
    return notifications


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("BROKEN behaviour (current record.py):")
    print("=" * 60)
    with tempfile.TemporaryDirectory() as d:
        broken = simulate_record_loop_broken(Path(d))

    print()
    print("Broken: on_lap_flushed called", len(broken), "time(s)")
    print("  (shard files deleted with temp dir — row counts shown inline above)")

    print()
    print("=" * 60)
    print("FIXED behaviour (after applying lap_completed() fix):")
    print("=" * 60)
    try:
        notifications_copy: list[tuple[int, int]] = []  # (lap_num, row_count)
        with tempfile.TemporaryDirectory() as d:
            fixed = simulate_record_loop_fixed(Path(d))
            for path, lap in fixed:
                t = pq.read_table(path)
                rows = sum(1 for ln in t.column("lap_number").to_pylist() if ln == lap)
                notifications_copy.append((lap, rows))
        print()
        print("Fixed: on_lap_flushed called", len(fixed), "time(s)")
        for lap, rows in notifications_copy:
            print(f"  lap={lap}  rows_for_lap={rows}  (expected > 0)")
        assert all(rows > 0 for _, rows in notifications_copy), \
            "FIXED path still has zero-row notifications!"
        print("\nAll fixed assertions passed.")
    except AttributeError as exc:
        print(f"\nFix not yet applied — writer.lap_completed() missing: {exc}")
