#!/usr/bin/env python3
"""Test fuel engineer call (slice 09).

Tests: build_fuel_messages(), LiveFuelFactGenerator filtering logic,
CoachRunConfig fuel_calls flag.

Run: python3 dev/scripts/test_fuel_engineer_call.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "product" / "python"))

from lap_telemetry.coach.coach_config import CoachRunConfig
from lap_telemetry.coach.fuel_facts import FuelFacts
from lap_telemetry.coach.fuel_prompt import build_fuel_messages
from lap_telemetry.coach.live_fuel_fact_generator import LiveFuelFactGenerator
from lap_telemetry.recorder.connect import Frame

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
    session_type: int | None = 3,  # race
    fuel_l: float | None = 20.0,
    fuel_capacity_l: float | None = 60.0,
    race_laps_total: int | None = 10,
    lap_distance_m: float = 0.0,
    lap_time_s: float = 0.0,
    track_name: str = "test-track",
) -> Frame:
    return Frame(
        sim="lmu",
        session_time_s=0.0,
        lap_number=lap_number,
        lap_distance_m=lap_distance_m,
        lap_time_s=lap_time_s,
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
        vehicle_name="TestCar",
        player_scor_index=0,
        session_type=session_type,
        fuel_l=fuel_l,
        fuel_capacity_l=fuel_capacity_l,
        race_laps_total=race_laps_total,
        session_time_remaining_s=None,
    )


def _make_warning_facts() -> FuelFacts:
    return FuelFacts(
        track_name="test-track",
        session_type="race",
        race_laps_total=10,
        race_laps_remaining=5,
        fuel_at_start_l=25.0,
        fuel_at_end_l=20.0,
        fuel_used_l=5.0,
        laps_completed=1,
        fuel_per_lap_l=5.0,
        laps_of_fuel_remaining=4.0,
        fuel_status="WARNING",
    )


def _make_critical_facts() -> FuelFacts:
    return FuelFacts(
        track_name="test-track",
        session_type="race",
        race_laps_total=10,
        race_laps_remaining=3,
        fuel_at_start_l=10.0,
        fuel_at_end_l=1.5,
        fuel_used_l=8.5,
        laps_completed=1,
        fuel_per_lap_l=8.5,
        laps_of_fuel_remaining=0.2,
        fuel_status="CRITICAL",
    )


def _make_ok_facts() -> FuelFacts:
    return FuelFacts(
        track_name="test-track",
        session_type="race",
        race_laps_total=20,
        race_laps_remaining=15,
        fuel_at_start_l=50.0,
        fuel_at_end_l=45.0,
        fuel_used_l=5.0,
        laps_completed=1,
        fuel_per_lap_l=5.0,
        laps_of_fuel_remaining=9.0,
        fuel_status="OK",
    )


# ══════════════════════════════════════════════════════════════════════════
# build_fuel_messages() tests
# ══════════════════════════════════════════════════════════════════════════

print("-- build_fuel_messages() --")

facts_w = _make_warning_facts()
msgs = build_fuel_messages(facts_w)

# T1: Returns two messages
ok(len(msgs) == 2, "T1: build_fuel_messages returns 2 messages", f"got {len(msgs)}")

# T2: System message contains 'race engineer'
ok(msgs[0]["role"] == "system", "T2a: first message has role=system")
ok("race engineer" in msgs[0]["content"].lower(), "T2b: system message contains 'race engineer'")

# T3: User message contains laps_of_fuel_remaining value
ok(msgs[1]["role"] == "user", "T3a: second message has role=user")
ok(str(facts_w.laps_of_fuel_remaining) in msgs[1]["content"], "T3b: user message contains laps_of_fuel_remaining value")

# ══════════════════════════════════════════════════════════════════════════
# LiveFuelFactGenerator — session type filtering
# ══════════════════════════════════════════════════════════════════════════

print("\n-- Session type filtering --")

mock_called: list[FuelFacts] = []


def mock_utterance_fn(facts: FuelFacts) -> str | None:
    mock_called.append(facts)
    return "test utterance"


gen = LiveFuelFactGenerator(utterance_fn=mock_utterance_fn)

# T4: Returns None for session_type 'practice'
frames_practice = [
    _make_frame(lap_number=1, session_type=0, lap_distance_m=float(i * 10))
    for i in range(5)
]
# Fuel data that would normally trigger WARNING
for f in frames_practice:
    object.__setattr__(f, "fuel_l", 20.0) if hasattr(f, "__dataclass_fields__") else None
result_practice = gen.generate(frames_practice)
ok(result_practice is None, "T4: returns None for session_type practice")

# T5: Returns None for session_type 'qualifying'
frames_qual = [
    _make_frame(lap_number=1, session_type=2, lap_distance_m=float(i * 10))
    for i in range(5)
]
result_qual = gen.generate(frames_qual)
ok(result_qual is None, "T5: returns None for session_type qualifying")

# ══════════════════════════════════════════════════════════════════════════
# LiveFuelFactGenerator — condition checks
# ══════════════════════════════════════════════════════════════════════════

print("\n-- Condition checks --")

# Build frames that produce a known FuelFacts — we mock utterance_fn and test
# the generator's _should_speak logic directly.

# T6: Returns None when fuel_status OK and no close margin
mock_called.clear()

class _FakeFuelFactGenerator(LiveFuelFactGenerator):
    """Override compute_fuel_facts to inject canned facts."""
    def __init__(self, facts: FuelFacts, utterance_fn):
        super().__init__(utterance_fn=utterance_fn)
        self._injected = facts

    def generate(self, frames):
        if not frames:
            return None
        if self._injected.session_type != "race":
            return None
        if not self._should_speak(self._injected):
            return None
        return self._utterance_fn(self._injected)


gen_ok = _FakeFuelFactGenerator(_make_ok_facts(), mock_utterance_fn)
mock_called.clear()
result_ok = gen_ok.generate([_make_frame()])
ok(result_ok is None, "T6: returns None for fuel_status OK and margin > 3 laps")
ok(len(mock_called) == 0, "T14a: utterance_fn not called when condition check returns False")

# T7: Returns string when fuel_status WARNING
mock_called.clear()
gen_warn = _FakeFuelFactGenerator(_make_warning_facts(), mock_utterance_fn)
result_warn = gen_warn.generate([_make_frame()])
ok(result_warn == "test utterance", "T7: returns utterance string for WARNING", f"got {result_warn!r}")

# T8: Returns string when fuel_status CRITICAL
mock_called.clear()
gen_crit = _FakeFuelFactGenerator(_make_critical_facts(), mock_utterance_fn)
result_crit = gen_crit.generate([_make_frame()])
ok(result_crit == "test utterance", "T8: returns utterance string for CRITICAL", f"got {result_crit!r}")

# T9: Returns string when laps_of_fuel_remaining and race_laps_remaining differ by <= 3
close_facts = FuelFacts(
    track_name="test-track",
    session_type="race",
    race_laps_total=10,
    race_laps_remaining=5,
    fuel_at_start_l=30.0,
    fuel_at_end_l=25.0,
    fuel_used_l=5.0,
    laps_completed=1,
    fuel_per_lap_l=5.0,
    laps_of_fuel_remaining=3.0,  # 5 - 3 = 2 laps margin -> close
    fuel_status="OK",
)
mock_called.clear()
gen_close = _FakeFuelFactGenerator(close_facts, mock_utterance_fn)
result_close = gen_close.generate([_make_frame()])
ok(result_close == "test utterance", "T9: returns utterance for close margin (<=3 laps)", f"got {result_close!r}")

# T10: Returns None when utterance_fn returns None (LLM error path)
mock_called.clear()

def failing_utterance_fn(facts: FuelFacts) -> str | None:
    return None

gen_fail = _FakeFuelFactGenerator(_make_warning_facts(), failing_utterance_fn)
result_fail = gen_fail.generate([_make_frame()])
ok(result_fail is None, "T10: returns None when utterance_fn returns None")

# T11: Returns None when frames list is empty
mock_called.clear()
result_empty = gen.generate([])
ok(result_empty is None, "T11: returns None for empty frames list")

# T12: Returns None when all fuel data is None (UNKNOWN status)
unknown_facts = FuelFacts(
    track_name="unknown",
    session_type="race",
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
mock_called.clear()
gen_unknown = _FakeFuelFactGenerator(unknown_facts, mock_utterance_fn)
result_unknown = gen_unknown.generate([_make_frame()])
ok(result_unknown is None, "T12: returns None for UNKNOWN fuel status")

# T13: Mock utterance_fn is called with a FuelFacts object
mock_called.clear()
received_type: list[type] = []


def typed_mock_fn(facts: FuelFacts) -> str | None:
    received_type.append(type(facts))
    return "typed utterance"


gen_typed = _FakeFuelFactGenerator(_make_warning_facts(), typed_mock_fn)
gen_typed.generate([_make_frame()])
ok(len(received_type) == 1 and received_type[0] is FuelFacts, "T13: utterance_fn called with FuelFacts object")

# T14b: utterance_fn called exactly once when condition met
call_count: list[int] = [0]


def counting_mock_fn(facts: FuelFacts) -> str | None:
    call_count[0] += 1
    return "counted utterance"


gen_count = _FakeFuelFactGenerator(_make_warning_facts(), counting_mock_fn)
gen_count.generate([_make_frame()])
ok(call_count[0] == 1, "T14b: utterance_fn called exactly once when condition met", f"got {call_count[0]} calls")

# ══════════════════════════════════════════════════════════════════════════
# CoachRunConfig fuel_calls flag
# ══════════════════════════════════════════════════════════════════════════

print("\n-- CoachRunConfig fuel_calls --")

cfg_default = CoachRunConfig()
ok(cfg_default.fuel_calls is False, "T15a: fuel_calls defaults to False")

cfg_enabled = CoachRunConfig(fuel_calls=True)
ok(cfg_enabled.fuel_calls is True, "T15b: fuel_calls can be set to True")

# ══════════════════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════════════════

print(f"\n{'-' * 60}")
if fail_count:
    print(f"  FAIL: {fail_count} FAILURES")
    sys.exit(1)
else:
    print(f"  PASS: {pass_count} assertions passed")
