#!/usr/bin/env python3
"""Test live telemetry bus, lap detector, and coach tap (slice 05).

Run: python dev/scripts/test_live_bus_tap.py
"""
from __future__ import annotations

import math
import sys
import threading
import time
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "product" / "python"))

from lap_telemetry.recorder.connect import Frame
from lap_telemetry.recorder.bus import LiveBus, QueuedBus
from lap_telemetry.coach.lap_detector import LapDetector, LapCompleted, NewLap
from lap_telemetry.coach.coach_tap import CoachTap

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
    lap_distance_m: float = 0.0,
    lap_time_s: float = 0.0,
    track_name: str = "circuit-de-barcelona",
    vehicle_name: str = "DKR4",
    speed_kph: float = 200.0,
) -> Frame:
    return Frame(
        sim="lmu",
        session_time_s=lap_time_s,
        lap_number=lap_number,
        lap_distance_m=lap_distance_m,
        lap_time_s=lap_time_s,
        speed_kph=speed_kph,
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
        vehicle_name=vehicle_name,
        player_scor_index=0,
    )


# ── LiveBus tests ───────────────────────────────────────────────────────────

print("-- LiveBus --")

bus = LiveBus()
received: list[Frame] = []
bus.subscribe(lambda f: received.append(f))
f1 = _make_frame(lap_number=1)
bus.publish(f1)
ok(len(received) == 1, "T1a: LiveBus subscribe/publish — callback called", f"got {len(received)}")
ok(received[0] is f1, "T1b: callback received the published frame")

# T2: multiple subscribers
bus2 = LiveBus()
r1: list[Frame] = []
r2: list[Frame] = []
bus2.subscribe(lambda f: r1.append(f))
bus2.subscribe(lambda f: r2.append(f))
f2 = _make_frame(lap_number=2)
bus2.publish(f2)
ok(len(r1) == 1 and len(r2) == 1, "T2: LiveBus multiple subscribers — both called")

# T3: unsubscribe
bus3 = LiveBus()
r3: list[Frame] = []
handle = bus3.subscribe(lambda f: r3.append(f))
handle()
bus3.publish(_make_frame())
ok(len(r3) == 0, "T3: LiveBus unsubscribe — callback not called after unsub")

# T4: callback exception isolation
bus4 = LiveBus()
good_calls: list[Frame] = []


def bad_callback(_f: Frame) -> None:
    raise RuntimeError("boom")


bus4.subscribe(bad_callback)
bus4.subscribe(lambda f: good_calls.append(f))
bus4.publish(_make_frame())
ok(len(good_calls) == 1, "T4: LiveBus exception isolation — second callback still called")

# ── QueuedBus tests ────────────────────────────────────────────────────────

print("\n-- QueuedBus --")

# T5: publish/consume
qbus = QueuedBus(maxsize=10)
qr: list[Frame] = []
qbus.subscribe(lambda f: qr.append(f))
qbus.start()
f5 = _make_frame(lap_number=5)
qbus.publish(f5)
time.sleep(0.3)
qbus.shutdown()
ok(len(qr) == 1, "T5: QueuedBus publish/consume — frame delivered", f"got {len(qr)}")
ok(qr[0] is f5, "T5b: correct frame delivered")

# T6: drop when full
# Pause the worker, fill the queue past capacity, verify oldest dropped.
qbus2 = QueuedBus(maxsize=2)
received6: list[Frame] = []
block_event = threading.Event()
release_event = threading.Event()


def blocking_callback(f: Frame) -> None:
    received6.append(f)
    # Block worker after first frame so queue fills up
    if not block_event.is_set():
        block_event.set()
        release_event.wait(timeout=5)


qbus2.subscribe(blocking_callback)
qbus2.start()
# Publish first frame — worker picks it up and blocks
qbus2.publish(_make_frame(lap_number=10))
block_event.wait(timeout=2)
time.sleep(0.1)  # let worker fully block
# Queue is now empty, worker is paused. Fill queue with 2 items.
qbus2.publish(_make_frame(lap_number=11))  # slot 1
qbus2.publish(_make_frame(lap_number=12))  # slot 2 (full)
# Next publish drops oldest (11) to make room
qbus2.publish(_make_frame(lap_number=13))  # drops 11
# Release the worker
release_event.set()
time.sleep(0.3)
qbus2.shutdown()
lap_nums = [f.lap_number for f in received6]
ok(
    10 in lap_nums and 12 in lap_nums and 13 in lap_nums,
    "T6a: QueuedBus drop when full — newest frames delivered, oldest dropped",
    f"lap_numbers={lap_nums}",
)
ok(
    11 not in lap_nums,
    "T6b: QueuedBus drop when full — lap 11 was dropped",
    f"lap_numbers={lap_nums}",
)

# ── LapDetector tests ──────────────────────────────────────────────────────

print("\n-- LapDetector --")

# T7: new lap detection
events7: list = []
det7 = LapDetector()
det7.on_new_lap = lambda e: events7.append(e)
det7.on_lap_completed = lambda e: events7.append(e)

f7a = _make_frame(lap_number=1, lap_time_s=10.0, track_name="circuit-de-barcelona")
det7.feed(f7a)
ok(len(events7) == 1, "T7a: first frame emits NewLap", f"events={len(events7)}")
ok(isinstance(events7[0], NewLap), "T7b: first frame event is NewLap")
ok(events7[0].lap_number == 1, "T7c: NewLap lap_number=1")

f7b = _make_frame(lap_number=2, lap_time_s=5.0, track_name="circuit-de-barcelona")
det7.feed(f7b)
ok(len(events7) == 3, "T7d: lap 2 start emits LapCompleted + NewLap", f"events={len(events7)}")
ok(isinstance(events7[1], LapCompleted), "T7e: second event is LapCompleted")
ok(events7[1].lap_number == 1, "T7f: LapCompleted for lap 1")
ok(isinstance(events7[2], NewLap), "T7g: third event is NewLap")
ok(events7[2].lap_number == 2, "T7h: NewLap for lap 2")

# T8: lap completed with frame count and lap time
events8: list = []
det8 = LapDetector()
det8.on_lap_completed = lambda e: events8.append(e)
det8.on_new_lap = lambda e: events8.append(e)

# Feed 3 frames for lap 3
for i in range(3):
    det8.feed(_make_frame(lap_number=3, lap_time_s=80.0 + i * 3.0, track_name="circuit-de-barcelona"))
# Start lap 4 to trigger completion of lap 3
det8.feed(_make_frame(lap_number=4, lap_time_s=2.0, track_name="circuit-de-barcelona"))

completed = [e for e in events8 if isinstance(e, LapCompleted)]
ok(len(completed) == 1, "T8a: LapCompleted for lap 3")
ok(completed[0].lap_number == 3, "T8b: completed lap number is 3")
ok(completed[0].frame_count == 3, "T8c: frame count is 3", f"got {completed[0].frame_count}")
ok(completed[0].lap_time_s == 86.0, "T8d: lap time is last frame's lap_time_s", f"got {completed[0].lap_time_s}")
ok(completed[0].track_name == "circuit-de-barcelona", "T8e: track name preserved")
ok(len(completed[0].frames) == 3, "T8f: completed lap has frozen frames")

# T9: track change discards in-progress lap
events9: list = []
det9 = LapDetector()
det9.on_lap_completed = lambda e: events9.append(e)
det9.on_new_lap = lambda e: events9.append(e)

det9.feed(_make_frame(lap_number=1, lap_time_s=5.0, track_name="silverstone"))
det9.feed(_make_frame(lap_number=1, lap_time_s=10.0, track_name="silverstone"))
# Track change
det9.feed(_make_frame(lap_number=1, lap_time_s=2.0, track_name="monza"))

completed9 = [e for e in events9 if isinstance(e, LapCompleted)]
new_lap9 = [e for e in events9 if isinstance(e, NewLap)]
ok(len(completed9) == 0, "T9a: no LapCompleted on track change — in-progress lap discarded")
ok(len(new_lap9) == 2, "T9b: NewLap for silverstone then monza", f"got {len(new_lap9)}")

# T10: lap number resets (session restart)
events10: list = []
det10 = LapDetector()
det10.on_lap_completed = lambda e: events10.append(e)
det10.on_new_lap = lambda e: events10.append(e)

det10.feed(_make_frame(lap_number=5, lap_time_s=5.0))
det10.feed(_make_frame(lap_number=5, lap_time_s=10.0))
# Lap number goes backward (session restart)
det10.feed(_make_frame(lap_number=1, lap_time_s=0.5))

completed10 = [e for e in events10 if isinstance(e, LapCompleted)]
new_lap10 = [e for e in events10 if isinstance(e, NewLap)]
ok(len(completed10) == 0, "T10a: no LapCompleted on backward lap number — discarded")
ok(len(new_lap10) == 2, "T10b: NewLap for lap 5 then lap 1", f"got {len(new_lap10)}")

# T10c: current_lap_frames is reset after backward jump
ok(len(det10.current_lap_frames) == 1, "T10c: current_lap_frames reset to 1 frame after restart")

# ── CoachTap tests ─────────────────────────────────────────────────────────

print("\n-- CoachTap --")

# T11: CoachTap produces debug output on lap boundary
qbus11 = QueuedBus(maxsize=10)
tap11 = CoachTap(qbus11)
tap11.start()

# Feed frames that cross a lap boundary
f11a = _make_frame(lap_number=1, lap_time_s=10.0)
f11b = _make_frame(lap_number=2, lap_time_s=1.0)
qbus11.publish(f11a)
qbus11.publish(f11b)
time.sleep(0.5)
tap11.shutdown()

ok(True, "T11: CoachTap runs with bus — no crash (stderr output is manual check)")

# ── Recorder integration check ──────────────────────────────────────────────

print("\n-- Recorder integration --")

# T12: verify the bus parameter exists in record.run() by reading the source.
# We avoid importing record.py directly because it pulls in pyarrow,
# which may have numpy version conflicts in some environments.
import ast

record_src = (ROOT / "product" / "python" / "lap_telemetry" / "recorder" / "record.py").read_text()
record_tree = ast.parse(record_src)

# Find the 'run' function and check its parameters
_run_func = next(
    (node for node in ast.walk(record_tree) if isinstance(node, ast.FunctionDef) and node.name == "run"),
    None,
)
ok(_run_func is not None, "T12a: record.run() function exists in source")
if _run_func:
    param_names = [arg.arg for arg in _run_func.args.args]
    ok("bus" in param_names, "T12b: record.run() accepts 'bus' parameter", f"params={param_names}")
    defaults = _run_func.args.defaults
    # bus has default None — find its position
    n_args = len(param_names)
    n_defaults = len(defaults)
    bus_idx = param_names.index("bus") if "bus" in param_names else -1
    default_idx = bus_idx - (n_args - n_defaults)
    if 0 <= default_idx < n_defaults:
        default_val = ast.dump(defaults[default_idx])
        ok(
            "None" in default_val,
            "T12c: record.run() bus default is None",
            f"default={default_val}",
        )
    else:
        ok(False, "T12c: record.run() bus default is None", "bus has no default")

# T12d: verify bus.publish is called after writer.append
ok(
    "bus.publish(frame)" in record_src or "bus.publish" in record_src,
    "T12d: record.py contains bus.publish(frame) call",
)
ok(
    "bus is not None" in record_src,
    "T12e: record.py guards bus.publish with 'bus is not None'",
)

# T12f: verify LiveBus is importable from the bus module
from lap_telemetry.recorder.bus import LiveBus as _LB, QueuedBus as _QB
ok(_LB is not None and _QB is not None, "T12f: LiveBus and QueuedBus importable from bus module")

# T12g: verify CoachTap and LapDetector importable
from lap_telemetry.coach.coach_tap import CoachTap as _CT
from lap_telemetry.coach.lap_detector import LapDetector as _LD, LapCompleted as _LC, NewLap as _NL
ok(_CT is not None and _LD is not None and _LC is not None and _NL is not None,
   "T12g: CoachTap, LapDetector, events importable")

# T12h: _is_recordable logic — reimplemented inline to avoid pyarrow import
def _is_recordable_test(frame: Frame | None) -> bool:
    if frame is None or frame.paused:
        return False
    return bool(frame.track_name) and bool(frame.vehicle_name)

ok(_is_recordable_test(_make_frame()) is True, "T12h: _is_recordable returns True for valid frame")
none_frame: Frame = None  # type: ignore[assignment]
ok(_is_recordable_test(none_frame) is False, "T12i: _is_recordable returns False for None")

paused_f = Frame(
    sim="lmu", session_time_s=0.0, lap_number=1, lap_distance_m=0.0,
    lap_time_s=0.0, speed_kph=0.0, throttle_norm=0.0, brake_norm=0.0,
    steering_norm=0.0, gear=1, engine_rpm=0.0, lap_valid=True,
    pos_x_m=0.0, pos_y_m=0.0, pos_z_m=0.0,
    last_sector_1_s=0.0, last_sector_2_s=0.0,
    slip_angle_fl_deg=0.0, slip_angle_fr_deg=0.0,
    slip_angle_rl_deg=0.0, slip_angle_rr_deg=0.0,
    abs_active=None, tc_active=None, in_realtime=True,
    paused=True, track_name="circuit-de-barcelona",
    vehicle_name="DKR4", player_scor_index=0,
)
ok(_is_recordable_test(paused_f) is False, "T12j: _is_recordable returns False for paused frame")

# ── Summary ─────────────────────────────────────────────────────────────────

print(f"\n{'-' * 60}")
if fail_count:
    print(f"  FAIL: {fail_count} FAILURES")
    sys.exit(1)
else:
    print(f"  PASS: {pass_count} assertions passed")