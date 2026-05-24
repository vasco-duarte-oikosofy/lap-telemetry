#!/usr/bin/env python3
"""Test fuel fact recorder channels (slice 08).

Run: python dev/scripts/test_fuel_facts.py
"""
from __future__ import annotations

import json
import math
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "product" / "python"))

import pyarrow as pa
import pyarrow.parquet as pq

from lap_telemetry.recorder.connect import Frame
from lap_telemetry.recorder.writer import _SCHEMA
from lap_telemetry.coach.fuel_facts import (
    FuelFacts,
    compute_fuel_facts,
    session_type_str,
    _classify_status,
)

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


def _make_frame(
    lap_number: int = 1,
    fuel_l: float | None = None,
    fuel_capacity_l: float | None = None,
    session_type: int | None = None,
    session_time_remaining_s: float | None = None,
    race_laps_total: int | None = None,
    track_name: str = "circuit-de-barcelona",
) -> Frame:
    return Frame(
        sim="lmu",
        session_time_s=100.0,
        lap_number=lap_number,
        lap_distance_m=500.0,
        lap_time_s=90.0,
        speed_kph=200.0,
        throttle_norm=0.5,
        brake_norm=0.0,
        steering_norm=0.0,
        gear=6,
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
        track_name=track_name,
        vehicle_name="DKR4",
        player_scor_index=0,
        fuel_l=fuel_l,
        fuel_capacity_l=fuel_capacity_l,
        session_type=session_type,
        session_time_remaining_s=session_time_remaining_s,
        race_laps_total=race_laps_total,
    )


def _write_frames_parquet(frames: list[Frame]) -> Path:
    """Write a list of frames to a temporary Parquet file."""
    from lap_telemetry.coach.frames_to_parquet import frames_to_parquet
    path = frames_to_parquet(frames, suffix=".parquet")
    return path


# ── Frame new fields ──────────────────────────────────────────────────────

print("-- Frame fuel fields --")

f0 = _make_frame(
    fuel_l=95.0,
    fuel_capacity_l=100.0,
    session_type=3,
    session_time_remaining_s=1800.0,
    race_laps_total=50,
)
ok(f0.fuel_l == 95.0, "T1a: Frame.fuel_l populated")
ok(f0.fuel_capacity_l == 100.0, "T1b: Frame.fuel_capacity_l populated")
ok(f0.session_type == 3, "T1c: Frame.session_type populated")
ok(f0.session_time_remaining_s == 1800.0, "T1d: Frame.session_time_remaining_s populated")
ok(f0.race_laps_total == 50, "T1e: Frame.race_laps_total populated")

f1 = _make_frame()
ok(f1.fuel_l is None, "T2a: Frame.fuel_l defaults to None")
ok(f1.fuel_capacity_l is None, "T2b: Frame.fuel_capacity_l defaults to None")
ok(f1.session_type is None, "T2c: Frame.session_type defaults to None")
ok(f1.session_time_remaining_s is None, "T2d: Frame.session_time_remaining_s defaults to None")
ok(f1.race_laps_total is None, "T2e: Frame.race_laps_total defaults to None")

# ── Session type mapping ────────────────────────────────────────────────

print("\n-- Session type mapping --")

ok(session_type_str(0) == "practice", "T3a: session_type 0 = practice")
ok(session_type_str(1) == "test", "T3b: session_type 1 = test")
ok(session_type_str(2) == "qualifying", "T3c: session_type 2 = qualifying")
ok(session_type_str(3) == "race", "T3d: session_type 3 = race")
ok(session_type_str(4) == "other", "T3e: session_type 4 = other")
ok(session_type_str(8) == "other", "T3f: session_type 8 = other")
ok(session_type_str(None) == "unknown", "T3g: session_type None = unknown")
ok(session_type_str(99) == "unknown", "T3h: session_type 99 = unknown")

# ── Fuel status classification ────────────────────────────────────────────

print("\n-- Fuel status classification --")

ok(_classify_status(None) == "UNKNOWN", "T4a: None → UNKNOWN")
ok(_classify_status(0.5) == "CRITICAL", "T4b: 0.5 laps → CRITICAL")
ok(_classify_status(1.9) == "CRITICAL", "T4c: 1.9 laps → CRITICAL")
ok(_classify_status(2.0) == "WARNING", "T4d: 2.0 laps → WARNING")
ok(_classify_status(3.5) == "WARNING", "T4e: 3.5 laps → WARNING")
ok(_classify_status(5.0) == "WARNING", "T4f: 5.0 laps → WARNING")
ok(_classify_status(5.1) == "OK", "T4g: 5.1 laps → OK")
ok(_classify_status(10.0) == "OK", "T4h: 10.0 laps → OK")

# ── FuelFacts dataclass ──────────────────────────────────────────────────

print("\n-- FuelFacts construction --")

facts = FuelFacts(
    track_name="circuit-de-barcelona",
    session_type="race",
    race_laps_total=50,
    race_laps_remaining=42,
    fuel_at_start_l=95.0,
    fuel_at_end_l=12.3,
    fuel_used_l=82.7,
    laps_completed=8,
    fuel_per_lap_l=10.3,
    laps_of_fuel_remaining=1.2,
    fuel_status="CRITICAL",
)
ok(facts.track_name == "circuit-de-barcelona", "T5a: FuelFacts track_name")
ok(facts.fuel_status == "CRITICAL", "T5b: FuelFacts fuel_status")
ok(facts.fuel_per_lap_l == 10.3, "T5c: FuelFacts fuel_per_lap_l")
ok(facts.laps_of_fuel_remaining == 1.2, "T5d: FuelFacts laps_of_fuel_remaining")

# Default UNKNOWN dataclass
facts_missing = FuelFacts(
    track_name="unknown",
    session_type="unknown",
    race_laps_total=None,
    race_laps_remaining=None,
    fuel_at_start_l=None,
    fuel_at_end_l=None,
    fuel_used_l=None,
    laps_completed=0,
    fuel_per_lap_l=None,
    laps_of_fuel_remaining=None,
    fuel_status="UNKNOWN",
)
ok(facts_missing.fuel_at_start_l is None, "T5e: FuelFacts default None for fuel_at_start_l")
ok(facts_missing.fuel_status == "UNKNOWN", "T5f: FuelFacts default UNKNOWN status")

# ── compute_fuel_facts from Frame list ────────────────────────────────────

print("\n-- compute_fuel_facts from frames --")

# T6: 8 laps, fuel starts at 95.0 L, ends at ~12.3 L.
# Each lap uses ~(95.0-12.3)/8 = ~10.3 L
frames6 = []
for lap in range(1, 9):
    fuel = 95.0 - (95.0 - 12.3) * lap / 8  # linear decrease
    frames6.append(_make_frame(
        lap_number=lap,
        fuel_l=round(fuel, 1),
        fuel_capacity_l=100.0,
        session_type=3,
        race_laps_total=50,
        track_name="circuit-de-barcelona",
    ))

facts6 = compute_fuel_facts(frames6)
ok(facts6.session_type == "race", "T6a: session_type = race")
ok(facts6.race_laps_total == 50, "T6b: race_laps_total = 50")
ok(facts6.fuel_at_start_l is not None and facts6.fuel_at_start_l > 80,
   "T6c: fuel_at_start near start of session", f"got {facts6.fuel_at_start_l}")
ok(facts6.laps_completed == 8, "T6d: laps_completed = 8", f"got {facts6.laps_completed}")
ok(facts6.fuel_per_lap_l is not None and facts6.fuel_per_lap_l > 0, "T6e: fuel_per_lap computed")
ok(facts6.fuel_used_l is not None and facts6.fuel_used_l > 0, "T6f: fuel_used computed")
ok(facts6.laps_of_fuel_remaining is not None, "T6g: laps_of_fuel_remaining computed")
# race_laps_remaining = 50 - 8 = 42
ok(facts6.race_laps_remaining == 42, "T6h: race_laps_remaining = 42", f"got {facts6.race_laps_remaining}")

# T7: fuel status OK — low consumption, plenty remaining
# 3 laps, fuel from 80 to 74 (2 L/lap), 74/2 = 37 laps remaining → OK
frames7 = [
    _make_frame(lap_number=1, fuel_l=80.0, session_type=3, race_laps_total=10),
    _make_frame(lap_number=2, fuel_l=78.0, session_type=3, race_laps_total=10),
    _make_frame(lap_number=3, fuel_l=74.0, session_type=3, race_laps_total=10),
]
facts7 = compute_fuel_facts(frames7)
ok(facts7.fuel_status == "OK", f"T7: fuel_status OK", f"got {facts7.fuel_status}, laps_remaining={facts7.laps_of_fuel_remaining}")

# T8: fuel status CRITICAL — very low remaining
frames8 = [
    _make_frame(lap_number=1, fuel_l=5.0),
    _make_frame(lap_number=2, fuel_l=1.0),
]
facts8 = compute_fuel_facts(frames8)
ok(facts8.fuel_status == "CRITICAL", f"T8: fuel_status CRITICAL", f"got {facts8.fuel_status}")

# T9: fuel status WARNING — moderate remaining
# 4 laps, fuel from 50 to 38 (3 L/lap), 38/3 = 12.7 → OK, not WARNING
# Let me make it WARNING: 4 laps, fuel from 20 to 12 (2 L/lap), 12/2 = 6 → OK still
# 4 laps, fuel from 20 to 8 (3 L/lap), 8/3 = 2.67 → WARNING
frames9 = [
    _make_frame(lap_number=1, fuel_l=20.0),
    _make_frame(lap_number=2, fuel_l=17.0),
    _make_frame(lap_number=3, fuel_l=14.0),
    _make_frame(lap_number=4, fuel_l=8.0),
]
facts9 = compute_fuel_facts(frames9)
ok(facts9.fuel_status == "WARNING", f"T9: fuel_status WARNING", f"got {facts9.fuel_status}, laps_remaining={facts9.laps_of_fuel_remaining}")

# T10: no fuel data → UNKNOWN
frames10 = [_make_frame(lap_number=i) for i in range(1, 5)]
facts10 = compute_fuel_facts(frames10)
ok(facts10.fuel_status == "UNKNOWN", "T10a: fuel_status UNKNOWN with no fuel data")
ok(facts10.fuel_at_start_l is None, "T10b: fuel_at_start_l None")
ok(facts10.fuel_per_lap_l is None, "T10c: fuel_per_lap_l None")

# T11: empty frames list
facts11 = compute_fuel_facts([])
ok(facts11.fuel_status == "UNKNOWN", "T11a: empty frames → UNKNOWN")
ok(facts11.laps_completed == 0, "T11b: empty frames → 0 laps_completed")
ok(facts11.track_name == "unknown", "T11c: empty frames → unknown track")

# T12: practice session — no race_laps_remaining
frames12 = [_make_frame(lap_number=i, fuel_l=50.0, session_type=0) for i in range(1, 4)]
facts12 = compute_fuel_facts(frames12)
ok(facts12.session_type == "practice", "T12a: practice session")
ok(facts12.race_laps_remaining is None, "T12b: race_laps_remaining None for practice")

# ── compute_fuel_facts from Parquet file ──────────────────────────────────

print("\n-- compute_fuel_facts from Parquet --")

# T13: write frames to Parquet, then compute facts
# 5 laps, fuel from 100 to 60. 8 L/lap. fuel_remaining = 60/8 = 7.5 → OK
frames13 = []
for lap in range(1, 6):
    fuel = 100.0 - lap * 8.0
    frames13.append(_make_frame(
        lap_number=lap,
        fuel_l=round(fuel, 1),
        fuel_capacity_l=110.0,
        session_type=3,
        race_laps_total=20,
        track_name="spa-francorchamps",
    ))

parquet_path_13 = _write_frames_parquet(frames13)
facts13 = compute_fuel_facts(parquet_path_13)
# Note: track_name comes from JSON sidecar, which doesn't exist for temp files,
# so it will be "unknown"
ok(facts13.track_name == "unknown", "T13a: track from Parquet = unknown (no sidecar)")
ok(facts13.session_type == "race", "T13b: session_type race from Parquet")
ok(facts13.race_laps_total == 20, "T13c: race_laps_total from Parquet")
ok(facts13.fuel_at_start_l is not None and facts13.fuel_at_start_l == 92.0,
   "T13d: fuel_at_start from Parquet", f"got {facts13.fuel_at_start_l}")
ok(facts13.laps_completed == 5, "T13e: laps_completed from Parquet")
ok(facts13.fuel_per_lap_l is not None, "T13f: fuel_per_lap computed from Parquet")
ok(facts13.fuel_status == "OK", "T13g: fuel_status OK", f"got {facts13.fuel_status}")
parquet_path_13.unlink(missing_ok=True)

# ── Parquet round-trip ────────────────────────────────────────────────────

print("\n-- Parquet round-trip --")

# T14: write frames with fuel fields to Parquet, read back, verify columns exist
frames14 = [_make_frame(lap_number=1, fuel_l=50.0, fuel_capacity_l=110.0,
                         session_type=3, session_time_remaining_s=1200.0,
                         race_laps_total=30)]
parquet_path_14 = _write_frames_parquet(frames14)
table14 = pq.read_table(str(parquet_path_14))
col_names = set(table14.schema.names)
ok("fuel_l" in col_names, "T14a: Parquet has fuel_l column")
ok("fuel_capacity_l" in col_names, "T14b: Parquet has fuel_capacity_l column")
ok("session_type" in col_names, "T14c: Parquet has session_type column")
ok("session_time_remaining_s" in col_names, "T14d: Parquet has session_time_remaining_s column")
ok("race_laps_total" in col_names, "T14e: Parquet has race_laps_total column")
parquet_path_14.unlink(missing_ok=True)

# ── Backward compatibility ────────────────────────────────────────────────

print("\n-- Backward compatibility --")

# T15: old Parquet without fuel columns should load fine (PyArrow fills null)
# Create a Parquet with only original columns (no fuel columns)
from lap_telemetry.coach.frames_to_parquet import frames_to_parquet
old_frames15 = [_make_frame()]  # No fuel data set
# Write to parquet normally then verify fuel columns exist as nulls
parquet_path_15 = _write_frames_parquet(old_frames15)
table15 = pq.read_table(str(parquet_path_15))
# Verify fuel columns exist (they will, since we added them to schema)
ok("fuel_l" in set(table15.schema.names), "T15a: New Parquet has fuel_l column")
fuel_vals = table15.column("fuel_l").to_pylist()
ok(all(v is None for v in fuel_vals), "T15b: fuel_l column is all null for frames without fuel data")
parquet_path_15.unlink(missing_ok=True)

# ── CLI invocation ─────────────────────────────────────────────────────────

print("\n-- CLI invocation --")

# T16: create a Parquet file, then compute facts and check human-readable format
from lap_telemetry.coach.fuel_facts import _format_facts
# Use the same frames as T6 for consistent testing
facts16 = compute_fuel_facts(frames6)
formatted = _format_facts(facts16)
ok("Track:" in formatted, "T16a: format includes Track")
ok("Session type: race" in formatted, "T16b: format includes session type")
ok("Fuel at start:" in formatted, "T16c: format includes fuel at start")
ok("Fuel per lap:" in formatted, "T16d: format includes fuel per lap")
ok("Fuel status:" in formatted, "T16e: format includes fuel status")

# T17: JSON output
json_out = json.dumps(asdict(facts16))
parsed = json.loads(json_out)
ok(parsed["session_type"] == "race", "T17a: JSON has session_type race")
ok(parsed["fuel_status"] in ("OK", "WARNING", "CRITICAL", "UNKNOWN"), "T17b: JSON has valid fuel_status")
ok(parsed["race_laps_remaining"] == 42, "T17c: JSON has race_laps_remaining")

# T18: CLI subprocess
import subprocess

parquet_path_18 = _write_frames_parquet(frames6)

# Human-readable
res = subprocess.run(
    [sys.executable, "-m", "lap_telemetry.coach.fuel_facts", str(parquet_path_18)],
    capture_output=True, text=True, timeout=30,
    env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT / "product" / "python")},
)
ok(res.returncode == 0, "T18a: CLI exits 0", f"stderr: {res.stderr[:200] if res.stderr else ''}")
ok("Fuel at start:" in res.stdout or "fuel_at_start" in res.stdout.lower(),
   "T18b: CLI output contains fuel info")

# JSON output
res_json = subprocess.run(
    [sys.executable, "-m", "lap_telemetry.coach.fuel_facts", "--json", str(parquet_path_18)],
    capture_output=True, text=True, timeout=30,
    env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT / "product" / "python")},
)
ok(res_json.returncode == 0, "T18c: CLI --json exits 0")
json_parsed = json.loads(res_json.stdout)
ok(isinstance(json_parsed, dict), "T18d: --json outputs valid JSON dict")
ok(json_parsed.get("fuel_status") in ("OK", "WARNING", "CRITICAL", "UNKNOWN"),
   "T18e: JSON fuel_status valid")
parquet_path_18.unlink(missing_ok=True)

# T19: CLI with nonexistent file
res_bad = subprocess.run(
    [sys.executable, "-m", "lap_telemetry.coach.fuel_facts", "/tmp/nonexistent_12345.parquet"],
    capture_output=True, text=True, timeout=30,
    env={**dict(__import__("os").environ), "PYTHONPATH": str(ROOT / "product" / "python")},
)
ok(res_bad.returncode != 0, "T19: CLI exits non-zero for nonexistent file")

# ── Summary ───────────────────────────────────────────────────────────────

print(f"\n{'-' * 60}")
if fail_count:
    print(f"  FAIL: {fail_count} FAILURES")
    sys.exit(1)
else:
    print(f"  PASS: {pass_count} assertions passed")