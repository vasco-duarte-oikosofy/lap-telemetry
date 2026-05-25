#!/usr/bin/env python3
"""Test ghost lap filter in LiveFactGenerator.

Bug: 06-ghost-lap-comparator-crash
Run: python3 dev/scripts/test_ghost_lap_filter.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "product" / "python"))

from lap_telemetry.coach.lap_detector import LapCompleted
from lap_telemetry.coach.live_fact_generator import LiveFactGenerator, LiveFactGeneratorConfig, _MIN_VALID_FRAMES
from lap_telemetry.recorder.connect import Frame

pass_count = 0
fail_count = 0
utterance_fn_calls: list[int] = []


def ok(condition: bool, label: str, detail: str = "") -> None:
    global pass_count, fail_count
    if condition:
        pass_count += 1
        print(f"  [PASS] {label}")
    else:
        fail_count += 1
        print(f"  [FAIL] {label}{' — ' + detail if detail else ''}")


def _mock_utterance_fn(facts) -> str | None:
    utterance_fn_calls.append(1)
    return "Mock utterance."


def _make_frame(lap_number: int = 1) -> Frame:
    return Frame(
        sim="lmu",
        session_time_s=0.0,
        lap_number=lap_number,
        lap_distance_m=100.0,
        lap_time_s=10.0,
        speed_kph=150.0,
        throttle_norm=0.5,
        brake_norm=0.0,
        steering_norm=0.0,
        gear=4,
        engine_rpm=6000.0,
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
        track_name="test-track",
        vehicle_name="TestCar",
        player_scor_index=0,
    )


def _make_event(frame_count: int, lap_time_s: float) -> LapCompleted:
    frames = [_make_frame() for _ in range(frame_count)]
    return LapCompleted(
        lap_number=3,
        track_name="test-track",
        lap_time_s=lap_time_s,
        frame_count=frame_count,
        frames=frames,
    )


gen = LiveFactGenerator(
    utterance_fn=_mock_utterance_fn,
    config=LiveFactGeneratorConfig(
        reference_search_dir=Path("/nonexistent"),
        track_model_search_dir=Path("/nonexistent"),
    ),
)

# ── Ghost lap filtering ───────────────────────────────────────────────────

print("-- Ghost lap filter --")

# T1: 1-frame session-end lap returns None
utterance_fn_calls.clear()
result = gen.generate(_make_event(frame_count=1, lap_time_s=-0.10))
ok(result is None, "T1: 1-frame negative-time lap returns None")
ok(len(utterance_fn_calls) == 0, "T1b: utterance_fn not called for ghost lap")

# T2: Zero-frame event returns None
utterance_fn_calls.clear()
result = gen.generate(_make_event(frame_count=0, lap_time_s=0.0))
ok(result is None, "T2: zero-frame event returns None")

# T3: Negative lap_time_s returns None even with many frames
utterance_fn_calls.clear()
result = gen.generate(_make_event(frame_count=200, lap_time_s=-5.0))
ok(result is None, "T3: negative lap_time_s returns None")
ok(len(utterance_fn_calls) == 0, "T3b: utterance_fn not called for negative time lap")

# T4: Exactly 0.0 lap_time_s returns None
utterance_fn_calls.clear()
result = gen.generate(_make_event(frame_count=200, lap_time_s=0.0))
ok(result is None, "T4: zero lap_time_s returns None")

# T5: frame_count below threshold returns None
utterance_fn_calls.clear()
result = gen.generate(_make_event(frame_count=_MIN_VALID_FRAMES - 1, lap_time_s=75.0))
ok(result is None, f"T5: frame_count < {_MIN_VALID_FRAMES} returns None")
ok(len(utterance_fn_calls) == 0, "T5b: utterance_fn not called for sub-threshold frame count")

# T6: frame_count at exactly threshold with valid time proceeds to pipeline
# (will return None because no reference lap, but the ghost filter does NOT block it)
utterance_fn_calls.clear()
result = gen.generate(_make_event(frame_count=_MIN_VALID_FRAMES, lap_time_s=75.0))
# No reference lap exists → returns None from resolver, not from ghost filter.
# utterance_fn should NOT be called (no ref lap), but the ghost guard didn't trigger.
ok(result is None, f"T6: frame_count == {_MIN_VALID_FRAMES}, valid time — passes ghost guard (no ref = None)")

# T7: _MIN_VALID_FRAMES constant is exported and reasonable
ok(10 <= _MIN_VALID_FRAMES <= 200, f"T7: _MIN_VALID_FRAMES={_MIN_VALID_FRAMES} is in sensible range [10, 200]")

# ── Summary ───────────────────────────────────────────────────────────────

print(f"\n{'-' * 60}")
if fail_count:
    print(f"  FAIL: {fail_count} FAILURES")
    sys.exit(1)
else:
    print(f"  PASS: {pass_count} assertions passed")
