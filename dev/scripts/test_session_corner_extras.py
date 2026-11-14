#!/usr/bin/env python3
"""Extended corner facts: gear, brakes, steering, slip, electronics, line.

These facts exist to answer "why" after slice 02 answered "where". They are
pure extraction from channels that already exist, so they are tested exactly on
a synthetic lap and plausibly on a real one: a hairpin must be in 2nd gear with
a full brake pedal, and Signes must not.

Protocol: prints [PASS]/[FAIL] lines and exits non-zero on any failure.
"""
from __future__ import annotations

import json
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "product" / "python"))
sys.path.insert(0, str(ROOT / "dev" / "scripts"))

import pyarrow as pa  # noqa: E402

from lap_telemetry.session_corner_extras import (  # noqa: E402
    _trail_depth,
    corner_channels,
    extract_all_corners,
    phase_windows,
    unmeasurable_channels,
)
from lap_telemetry.session_facts import build_session_facts  # noqa: E402
from lap_telemetry.session_inputs import resolve_debrief_inputs  # noqa: E402
from lap_telemetry.session_laps import classify_laps  # noqa: E402
from lap_telemetry.session_source import load_session  # noqa: E402

PRACTICE = (ROOT / "dev" / "sessions"
            / "session_20260524T141613Z_paul-ricard---3a_lmu.parquet")

_passed = 0
_failed = 0


def check(condition: bool, name: str, detail: str = "") -> None:
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  [PASS] {name}{' — ' + detail if detail else ''}")
    else:
        _failed += 1
        print(f"  [FAIL] {name}{' — ' + detail if detail else ''}")


# --------------------------------------------------------------------------
# A synthetic lap with hand-computed answers, 5 m between samples, 0..995 m.
# --------------------------------------------------------------------------
STEP_M = 5.0
NSAMPLES = 200


def _idx(distance_m: float) -> int:
    return int(round(distance_m / STEP_M))


def synthetic_table(*, drop: tuple[str, ...] = (), tc_fires: bool = True) -> pa.Table:
    distance = [i * STEP_M for i in range(NSAMPLES)]

    gear = [4] * NSAMPLES
    for i in range(NSAMPLES):
        if distance[i] >= 250:
            gear[i] = 5
        if distance[i] >= 400:
            gear[i] = 6

    # The hardest braking happens BEFORE the model's corner zone (which starts
    # at 100 m) — that is what the entry phase is for.
    brake = [0.0] * NSAMPLES
    for i in range(_idx(60), _idx(75) + 1):        # 60..75 m: initial bite
        brake[i] = 0.5
    brake[_idx(80)] = 1.0                           # 80 m: peak pressure
    for i in range(_idx(85), _idx(95) + 1):        # 85..95 m: still hard
        brake[i] = 0.8
    for i in range(_idx(100), _idx(175) + 1):      # 100..175 m: trail off
        brake[i] = 0.6
    for i in range(_idx(180), _idx(195) + 1):      # 180..195 m: squeeze
        brake[i] = 0.9
    brake[_idx(200)] = 0.5                          # apex: light pressure
    for i in range(_idx(205), _idx(215) + 1):      # 205..215 m: trailing off
        brake[i] = 0.3
    brake[_idx(235)] = 0.1                          # last sample still trailing
    # 240 m onward: fully released

    steering = [0.0] * NSAMPLES
    for i in range(_idx(100), _idx(145)):          # 100..140 m: turning in
        steering[i] = 0.4
    for i in range(_idx(145), _idx(175)):          # 145..170 m: more lock   (+)
        steering[i] = 0.6
    for i in range(_idx(175), _idx(225)):          # 175..220 m: unwinding   (-)
        steering[i] = 0.3
    for i in range(_idx(225), _idx(250)):          # 225..245 m: crossed zero (-)
        steering[i] = -0.2
    for i in range(_idx(250), _idx(300)):          # 250..295 m: winding back (+)
        steering[i] = -0.1

    slip_rl = [2.0 if d < 255 else 0.4 for d in distance]
    slip_rr = [1.0 if d < 225 else (4.0 if d < 255 else 0.5) for d in distance]

    tc = [tc_fires and 100 <= d < 150 for d in distance]
    abs_ = [145 <= d < 200 for d in distance]
    lateral = [0.1 * d for d in distance]
    reference_lateral = [0.05 * d for d in distance]

    rows: dict[str, list] = {
        "lap_number": [1] * NSAMPLES,
        "lap_distance_m": distance,
        "speed_kph": [120.0] * NSAMPLES,
        "lap_time_s": [i * 0.1 for i in range(NSAMPLES)],
        "session_time_s": [i * 0.1 for i in range(NSAMPLES)],
        "gear": gear,
        "brake_norm": brake,
        "throttle_norm": [1.0 - b for b in brake],
        "steering_norm": steering,
        "slip_angle_rl_deg": slip_rl,
        "slip_angle_rr_deg": slip_rr,
        "tc_active": tc,
        "abs_active": abs_,
        "path_lateral_m": lateral,
    }
    for name in drop:
        rows.pop(name, None)
    if "path_lateral_m" in rows:
        rows["reference_path_lateral_m"] = reference_lateral
    return pa.table(rows)


CORNER = {"id": "tX", "display_name": "Test Corner", "s_start_m": 100.0,
          "s_end_m": 300.0, "apex_s_m": 200.0}
WINDOWS = {"entry_m": 60.0, "apex_m": 200.0, "exit_m": 280.0,
           "straight_end_m": 400.0, "source": "phases"}


class FakeCorner:
    def __init__(self, data: dict):
        self.id = data["id"]
        self.display_name = data["display_name"]
        self.s_start_m = data["s_start_m"]
        self.s_end_m = data["s_end_m"]
        self.apex_s_m = data["apex_s_m"]


def test_synthetic_extraction() -> None:
    table = synthetic_table()
    reference = pa.table({"lap_distance_m": table.column("lap_distance_m").to_pylist(),
                          "path_lateral_m": table.column("reference_path_lateral_m").to_pylist()})
    channels = corner_channels(table)
    reference_channels = corner_channels(reference)
    extras = extract_all_corners(
        channels, [FakeCorner(CORNER)],
        {"tX": WINDOWS},
        reference=reference_channels,
    )[0]

    check(extras.gear_min == 4, "gear_min is the lowest gear in the corner", str(extras.gear_min))
    check(extras.gear_at_apex == 4, "gear_at_apex is the gear at the minimum-speed point",
          str(extras.gear_at_apex))
    check(extras.gear_at_exit == 5, "gear_at_exit is the gear where the exit was detected",
          str(extras.gear_at_exit))

    check(abs(extras.brake_peak - 1.0) < 1e-9,
          "brake_peak is taken from the entry, which starts before the corner",
          f"{extras.brake_peak}")

    # Trapezoid over the literal breakpoints from entry (60 m) to apex (200 m).
    # Each breakpoint is a sample; steps are steps, not ramps.
    breakpoints = [(60, 0.5), (75, 0.5), (80, 1.0), (85, 0.8), (95, 0.8),
                   (100, 0.6), (175, 0.6), (180, 0.9), (195, 0.9), (200, 0.5)]
    expected_area = sum(
        (v0 + v1) / 2 * (d1 - d0)
        for (d0, v0), (d1, v1) in zip(breakpoints, breakpoints[1:])
    )
    check(abs((extras.brake_area or 0) - expected_area) < 1e-6,
          "brake_area integrates pressure over distance", f"{extras.brake_area}")
    # Released at 220 m; the 0.1 pressure at 235 m is a later touch and must
    # not extend the trail.
    check(abs(extras.trail_brake_depth_m - 20.0) < 1e-6,
          "trail_brake_depth_m stops at the first release after the apex",
          f"{extras.trail_brake_depth_m}")

    check(extras.steering_reversals == 2,
          "steering_reversals counts sign changes, not samples",
          str(extras.steering_reversals))
    check(extras.steering_rate_std is not None and extras.steering_rate_std > 0,
          "steering_rate_std is a spread of the per-metre change")

    check(abs(extras.rear_slip_max_deg - 4.0) < 1e-9,
          "rear_slip_max_deg is the largest absolute rear slip", f"{extras.rear_slip_max_deg}")
    check(abs(extras.rear_slip_exit_deg - 0.5) < 1e-9,
          "rear_slip_exit_deg is the slip at the exit distance", f"{extras.rear_slip_exit_deg}")

    zone = [i for i in range(NSAMPLES) if 100 <= i * STEP_M <= 300]
    tc_on = sum(1 for i in zone if table.column("tc_active")[i].as_py())
    check(abs(extras.tc_duty - tc_on / len(zone)) < 1e-9,
          "tc_duty is the fraction of the corner with TC active",
          f"{extras.tc_duty:.3f}")
    abs_on = sum(1 for i in zone if table.column("abs_active")[i].as_py())
    check(abs(extras.abs_duty is not None and abs(extras.abs_duty - abs_on / len(zone)) < 1e-9),
          "abs_duty is the fraction of the corner with ABS active", f"{extras.abs_duty:.3f}")

    check(abs((extras.lateral_at_apex_m or 0) - 20.0) < 1e-6,
          "lateral_at_apex_m is the path offset at the driver's apex",
          f"{extras.lateral_at_apex_m}")
    check(abs((extras.lateral_offset_m or 0) - 10.0) < 1e-6,
          "lateral_offset_m is measured against the reference at the same distance",
          f"{extras.lateral_offset_m}")
    check(extras.window_source == "phases", "windows come from the detected phases",
          extras.window_source)


def wrapped_table(start_m: float = 460.0) -> pa.Table:
    """The synthetic lap with its rows rotated so row 0 sits at ``start_m``.

    A lap's ``lap_distance_m`` starts at the sim's own axis value and wraps to 0
    part-way through, so a real lap's first row can already sit past every
    corner in the lap (bug 36). Rotating keeps the driving order intact; only
    the row that happens to be first changes.
    """
    table = synthetic_table()
    distances = table.column("lap_distance_m").to_pylist()
    start = min(range(len(distances)), key=lambda i: abs(distances[i] - start_m))
    order = list(range(start, len(distances))) + list(range(0, start))
    return pa.table({name: table.column(name).take(pa.array(order)).to_pylist()
                     for name in table.column_names})


def test_wrapped_distance_axis() -> None:
    table = wrapped_table()
    first = table.column("lap_distance_m")[0].as_py()
    check(first > CORNER["s_end_m"],
          "the wrapped fixture starts past the corner, like a real lap",
          f"row 0 at {first} m")
    extras = extract_all_corners(
        corner_channels(table), [FakeCorner(CORNER)], {"tX": WINDOWS}
    )[0]
    check(extras.trail_brake_depth_m is not None
          and abs(extras.trail_brake_depth_m - 20.0) < 1e-6,
          "a wrapped axis still finds the first release by distance, not by row",
          f"{extras.trail_brake_depth_m}")


def test_never_released_is_unmeasurable() -> None:
    distances = [190.0, 200.0, 210.0, 220.0, 230.0]
    pedal_down = [0.9, 0.8, 0.7, 0.5, 0.3]
    check(_trail_depth(pedal_down, distances, 200.0, 300.0) is None,
          "a brake still on at the bound is unmeasurable, not the window length",
          str(_trail_depth(pedal_down, distances, 200.0, 300.0)))
    released = [0.9, 0.8, 0.02, 0.0, 0.0]
    check(abs((_trail_depth(released, distances, 200.0, 300.0) or 0) - 10.0) < 1e-6,
          "the depth is the distance to the first release")
    check(_trail_depth(released, [4652.0] + distances[1:], 200.0, 300.0) == 10.0,
          "a row past the bound does not end the search")


def test_missing_columns_degrade() -> None:
    table = synthetic_table(drop=("gear", "path_lateral_m", "slip_angle_rl_deg",
                                  "slip_angle_rr_deg", "tc_active", "abs_active"))
    extras = extract_all_corners(
        corner_channels(table), [FakeCorner(CORNER)], {"tX": WINDOWS}
    )[0]
    payload = extras.to_dict()
    for field in ("gear_min", "gear_at_apex", "gear_at_exit", "rear_slip_max_deg",
                  "rear_slip_exit_deg", "tc_duty", "abs_duty", "lateral_at_apex_m"):
        check(field not in payload, f"a missing column omits {field} instead of zero-filling")
    check(abs(extras.brake_peak - 1.0) < 1e-9, "the columns that do exist still work")
    check(payload.get("brake_peak") == 1.0, "present columns are serialized")


def test_unmeasurable_flag_channel() -> None:
    table = synthetic_table(tc_fires=False)
    dead = unmeasurable_channels(table)
    check(set(dead) == {"tc_active"}, "a flag that never fires is reported as unmeasurable",
          str(sorted(dead)))
    extras = extract_all_corners(
        corner_channels(table, unmeasurable=dead), [FakeCorner(CORNER)], {"tX": WINDOWS}
    )[0]
    check(extras.tc_duty is None,
          "the unmeasurable duty is not computed", str(extras.tc_duty))
    check("tc_duty" not in extras.to_dict(), "and is omitted from JSON")


def test_window_fallback() -> None:
    table = synthetic_table()
    extras = extract_all_corners(corner_channels(table), [FakeCorner(CORNER)], {})[0]
    check(extras.window_source == "corner_model",
          "without detected phases the window falls back to the corner model",
          extras.window_source)
    check(extras.gear_min == 4 and extras.gear_at_apex == 4,
          "the fallback still measures the corner", f"{extras.gear_min}/{extras.gear_at_apex}")
    check(extras.trail_brake_depth_m is not None,
          "trail-braking is still measured without an exit phase")


def test_phase_windows_from_facts() -> None:
    from lap_telemetry.coach.facts import CornerLoss

    entry = CornerLoss(corner_id="tX", corner_name="Test", apex_distance_m=200.0,
                       phase="entry", loss_s=0.1, driver_value=100.0,
                       reference_value=101.0, unit="km/h", confidence="medium",
                       phase_distance_m=120.0, gain_end_distance_m=200.0)
    apex = CornerLoss(corner_id="tX", corner_name="Test", apex_distance_m=200.0,
                      phase="minimum_speed", loss_s=0.2, driver_value=80.0,
                      reference_value=82.0, unit="km/h", confidence="high",
                      driver_apex_distance_m=205.0, gain_end_distance_m=400.0)
    exit_ = CornerLoss(corner_id="tX", corner_name="Test", apex_distance_m=200.0,
                       phase="exit", loss_s=0.1, driver_value=110.0,
                       reference_value=111.0, unit="km/h", confidence="medium",
                       phase_distance_m=280.0, gain_end_distance_m=400.0)
    windows = phase_windows([FakeCorner(CORNER)], [entry, apex, exit_])
    window = windows["tX"]
    check(window["entry_m"] == 120.0 and window["exit_m"] == 280.0,
          "entry and exit distances come from the phase facts", str(window))
    check(window["apex_m"] == 205.0, "the apex is the driver's own minimum-speed point",
          str(window["apex_m"]))
    check(window["straight_end_m"] == 400.0, "the trail-brake window ends at the straight end",
          str(window["straight_end_m"]))


def _practice_facts():
    session = load_session(PRACTICE)
    records = classify_laps(session.table, sample_rate_hz=session.sample_rate_hz)
    inputs = resolve_debrief_inputs(session)
    return build_session_facts(session, records, inputs), session


def test_real_session() -> None:
    facts, session = _practice_facts()
    reference = {c.corner_id: c for c in facts.reference_corners}
    check(len(facts.reference_corners) == 9,
          "the reference is measured once for every corner",
          str(len(facts.reference_corners)))

    hairpin = reference["t5"]
    check(hairpin.gear_at_apex == 2,
          "the hairpin's reference apex is second gear", f"gear {hairpin.gear_at_apex}")

    first = reference["t1"]
    check(first.brake_peak is not None and first.brake_peak > 0.9,
          "the reference brakes near-full for the first corner", f"{first.brake_peak}")
    check(first.gear_at_apex == 1,
          "the first corner is first gear", f"gear {first.gear_at_apex}")

    signes = reference["t3"]
    check(signes.gear_min is not None and signes.gear_min >= 5,
          "Signes is taken in a high gear", f"gear {signes.gear_min}")
    check(signes.brake_peak is not None and signes.brake_peak < 0.3,
          "Signes needs almost no brake", f"{signes.brake_peak}")

    tour = reference["t8"]
    check(tour.trail_brake_depth_m is not None and tour.trail_brake_depth_m < 2,
          "the reference is off the brake by la Tour's apex",
          f"{tour.trail_brake_depth_m} m past the apex")

    village = reference["t7"]
    check(village.trail_brake_depth_m is None,
          "a corner taken without braking has no trail-brake depth",
          str(village.trail_brake_depth_m))

    gears_at_signes = {c.gear_at_apex for lap in facts.laps
                       for c in lap.corners if c.corner_id == "t3"}
    check(gears_at_signes == {5, 6},
          "the driver does not use one gear at Signes across the session",
          str(sorted(gears_at_signes)))

    lap = facts.laps[0]
    check(len(lap.corners) == 9, "every analysed lap carries every corner",
          str(len(lap.corners)))
    check(all(c.lateral_offset_m is not None for c in lap.corners),
          "line offsets are computed against the reference")
    offsets = [c.lateral_offset_m for c in lap.corners]
    check(any(abs(o) > 0.2 for o in offsets),
          "the driver's line differs from the reference somewhere",
          f"max {max(abs(o) for o in offsets):.2f} m")

    gears = [c.gear_at_apex for lap2 in facts.laps for c in lap2.corners if c.gear_at_apex]
    check(len(gears) == len(facts.laps) * 9, "no lap is missing gear data", str(len(gears)))
    check(min(gears) <= 3 and max(gears) >= 6,
          "gears span the range the corners require", f"{min(gears)}..{max(gears)}")
    check(facts.session.unmeasurable_channels.keys() >= {"slip_angle_rl_deg",
                                                         "slip_angle_rr_deg"},
          "the slip channels are refused, with a reason",
          str(sorted(facts.session.unmeasurable_channels)))
    reasons = " ".join(facts.session.unmeasurable_channels.values())
    check("wrap" in reasons, "the refusal names the reason, not just the channel", reasons[:60])


def test_payload() -> None:
    facts, _session = _practice_facts()
    payload = facts.to_dict()
    check("reference_corners" in payload, "the payload carries the reference's own channels")
    check(len(payload["reference_corners"]) == 9, "all nine corners are serialized",
          str(len(payload["reference_corners"])))
    refused = {name for name in payload["session"]["unmeasurable_channels"]}
    leaked = {key for lap in payload["laps"] for corner in lap["corners"]
              for key in corner
              if (key == "rear_slip_max_deg" and "slip_angle_rl_deg" in refused)
              or (key == "abs_duty" and "abs_active" in refused)
              or (key == "tc_duty" and "tc_active" in refused)}
    check(not leaked, "unmeasurable channels are refused on every lap, not just the reference",
          str(sorted(leaked)))

    first = payload["laps"][0]["corners"][0]
    check({"corner_id", "corner_name", "apex_distance_m"} <= set(first),
          "each lap corner is keyed by corner", str(sorted(first)[:4]))
    check(json.dumps(payload) and True, "the payload serializes to JSON")


def test_cli() -> None:
    import os
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "product" / "python")
    proc = subprocess.run(
        [sys.executable, "-m", "lap_telemetry", "debrief", str(PRACTICE), "--json"],
        cwd=str(ROOT), capture_output=True, text=True, env=env,
    )
    if proc.returncode != 0:
        check(False, "debrief --json exits 0", proc.stderr[-400:])
        return
    payload = json.loads(proc.stdout)
    check(len(payload["laps"][0]["corners"]) == 9,
          "the CLI payload carries the extended corners")


def main() -> int:
    print("Session corner extras")
    test_synthetic_extraction()
    test_wrapped_distance_axis()
    test_never_released_is_unmeasurable()
    test_missing_columns_degrade()
    test_unmeasurable_flag_channel()
    test_window_fallback()
    test_phase_windows_from_facts()
    test_real_session()
    test_payload()
    test_cli()
    total = _passed + _failed
    print(f"\n  {_passed}/{total} assertions passed")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
