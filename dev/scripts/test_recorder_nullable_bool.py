#!/usr/bin/env python3
"""Test that inactive ABS/TC frames are recorded as None, not False.

Root cause of the Lusail stack-overflow bug: long uniform False runs in
tc_active / abs_active overflow the JS call stack when hyparquet expands
them. The fix is to write None for inactive frames so pyarrow uses its
definition-level bitmap (no data run) instead of a long RLE False run.

Verifies:
  1. The expression logic: inactive SHM value -> None, active -> True.
  2. End-to-end encoding: None survives the SessionWriter -> parquet ->
     pyarrow read cycle as a null, not as False.

Run: python dev/scripts/test_recorder_nullable_bool.py
"""
from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "product" / "python"))

from lap_telemetry.recorder.connect import Frame
from lap_telemetry.recorder.writer import SessionWriter
import pyarrow.parquet as pq

pass_count = 0
fail_count = 0


def ok(condition: bool, label: str, detail: str = "") -> None:
    global pass_count, fail_count
    if condition:
        pass_count += 1
        print(f"  [PASS] {label}")
    else:
        fail_count += 1
        print(f"  [FAIL] {label}{' — ' + detail if detail else ''}")


def _make_frame(tc_active, abs_active) -> Frame:
    return Frame(
        sim="lmu",
        session_time_s=0.0,
        lap_number=1,
        lap_distance_m=0.0,
        lap_time_s=0.0,
        speed_kph=0.0,
        throttle_norm=0.0,
        brake_norm=0.0,
        steering_norm=0.0,
        gear=1,
        engine_rpm=0.0,
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
        abs_active=abs_active,
        tc_active=tc_active,
        in_realtime=True,
        paused=False,
        track_name="lusail-international-circuit",
        vehicle_name="DKR4",
        player_scor_index=0,
    )


print("-- T1: expression logic --")

mTCActive_inactive = 0
mTCActive_active   = 1

ok(
    (True if mTCActive_inactive else None) is None,
    "T1a: inactive SHM value (0) -> None",
    repr(True if mTCActive_inactive else None),
)
ok(
    (True if mTCActive_active else None) is True,
    "T1b: active SHM value (1) -> True",
    repr(True if mTCActive_active else None),
)
ok(
    (True if False else None) is None,
    "T1c: bool False -> None",
)
ok(
    (True if True else None) is True,
    "T1d: bool True -> True",
)

print("\n-- T2: parquet round-trip via SessionWriter --")

with tempfile.TemporaryDirectory() as tmpdir:
    out = Path(tmpdir)
    writer = SessionWriter(out, sim="lmu", track="lusail-international-circuit", rate_hz=50.0)

    frames = [
        _make_frame(tc_active=None,  abs_active=None),   # row 0: both inactive
        _make_frame(tc_active=True,  abs_active=True),   # row 1: both active
        _make_frame(tc_active=None,  abs_active=None),   # row 2: both inactive
    ]
    for f in frames:
        writer.append(f)

    parquet_path, _ = writer.close()

    table = pq.read_table(parquet_path)
    tc_col  = table.column("tc_active").to_pylist()
    abs_col = table.column("abs_active").to_pylist()

    ok(tc_col[0] is None,  "T2a: row 0 tc_active is null (not False)", repr(tc_col[0]))
    ok(tc_col[1] is True,  "T2b: row 1 tc_active is True",             repr(tc_col[1]))
    ok(tc_col[2] is None,  "T2c: row 2 tc_active is null (not False)", repr(tc_col[2]))
    ok(abs_col[0] is None, "T2d: row 0 abs_active is null",            repr(abs_col[0]))
    ok(abs_col[1] is True, "T2e: row 1 abs_active is True",            repr(abs_col[1]))

    false_count = sum(1 for v in tc_col if v is False)
    ok(false_count == 0, "T2f: no False values written for inactive frames",
       f"{false_count} False values found")

print(f"\n{'-' * 60}")
if fail_count:
    print(f"  FAIL: {fail_count} FAILURES")
    sys.exit(1)
else:
    print(f"  PASS: {pass_count} assertions passed")
