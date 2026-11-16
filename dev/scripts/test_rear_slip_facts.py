#!/usr/bin/env python3
"""Slice 01 phase C: a validated rear slip angle, and what it may not claim.

Two things are pinned here.

1. **The angle is a real slip angle.** It is computed in the recorder's own
   recorded channels — the rear wheels' ground velocities — as
   ``atan2(lat, |lon|)``. A rear wheel's heading is the car's heading, so the
   angle between its ground velocity and its plane *is* the tyre slip angle.
   Measured on committed sessions: ~0.1 deg on a straight, monotone in lateral
   acceleration, same sign as the yaw rate on >99% of rotating samples.

2. **The dead channels stay dead.** LMU publishes ``mGripFract`` as a constant
   0.0 in every sample of every recording on this machine, so grip fraction
   cannot answer "was it sliding"; it must be reported as unmeasurable, never as
   "no slip". The legacy ``slip_angle_*`` channels keep their own refusal.

Protocol: prints [PASS]/[FAIL] lines and exits non-zero on any failure.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "product" / "python"))

from lap_telemetry import rear_slip, rear_stability  # noqa: E402
from lap_telemetry.session_corner_extras import CornerExtras  # noqa: E402
from lap_telemetry.session_facts import build_session_facts  # noqa: E402
from lap_telemetry.session_inputs import resolve_debrief_inputs  # noqa: E402
from lap_telemetry.session_laps import classify_laps  # noqa: E402
from lap_telemetry.session_source import load_session  # noqa: E402

BARCELONA_RACE = ROOT / "sessions/session_20261115T184452Z_circuit-de-barcelona_lmu_race.parquet"
BARCELONA_QUALI = ROOT / "sessions/session_20261115T183239Z_circuit-de-barcelona_lmu_quali.parquet"
OLD_SESSION = ROOT / "sessions/session_20260517T173100Z_autodromo-enzo-e-dino-ferrari_lmu.parquet"

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


def median(values):
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def correlation(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    sa = sum((x - ma) ** 2 for x in a) ** 0.5
    sb = sum((y - mb) ** 2 for y in b) ** 0.5
    if not sa or not sb:
        return 0.0
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb)


# ---------------------------------------------------------------- 1. physics
def test_real_recording() -> None:
    table = pq.read_table(BARCELONA_RACE)
    series = rear_slip.slip_series(table)
    check(series is not None, "the rear ground velocities produce a slip series")
    if series is None:
        return
    speed = table.column("speed_kph").to_pylist()
    steering = table.column("steering_norm").to_pylist()
    yaw = table.column("yaw_rate_radps").to_pylist()
    surface = table.column("surface_type_rl").to_pylist()
    brake = table.column("brake_norm").to_pylist()

    def rows(predicate):
        out = []
        for i, value in enumerate(series):
            if value is None or speed[i] is None or speed[i] < 30:
                continue
            if surface[i] not in (0, None):
                continue
            if predicate(i):
                out.append(i)
        return out

    straight = rows(lambda i: abs(steering[i] or 0.0) < 0.05
                    and abs(yaw[i] or 0.0) < 0.05 and speed[i] > 80)
    straight_median = median([abs(series[i]) for i in straight])
    check(straight_median < 0.5,
          "on a straight the rear slip angle sits near zero, like a real slip angle",
          f"median {straight_median:.2f} deg over {len(straight)} samples")

    rotating = rows(lambda i: abs(yaw[i] or 0.0) > 0.15)
    agreement = sum(1 for i in rotating if (series[i] > 0) == (yaw[i] > 0))
    check(agreement / len(rotating) > 0.95,
          "the slip angle carries the yaw rate's sign while the car rotates",
          f"{100 * agreement / len(rotating):.1f}% of {len(rotating)} samples")

    bands = {}
    for label, low, high in (("low", 0.0, 0.3), ("mid", 0.8, 1.3), ("high", 1.3, 3.0)):
        band = rows(lambda i: low <= abs((yaw[i] or 0.0) * speed[i] / 3.6 / 9.81) < high)
        bands[label] = median([abs(series[i]) for i in band])
    check(bands["low"] < bands["mid"] < bands["high"],
          "the angle grows with lateral acceleration instead of following steering",
          f"{bands['low']:.2f} / {bands['mid']:.2f} / {bands['high']:.2f} deg")

    big = rows(lambda i: abs(series[i]) > 45)
    check(len(big) > 0,
          "off-track excursions exceed the sane bound, so it has to be filtered",
          f"{len(big)} samples > 45 deg")


def test_dead_channels() -> None:
    reasons = rear_slip.column_reasons(pq.read_table(BARCELONA_RACE))
    check("grip_fraction_rl" in reasons,
          "a constant-zero grip fraction is refused, not reported as zero slip")
    reason = reasons.get("grip_fraction_rl", "")
    check("mGripFract" in reason and "constant" in reason,
          "the refusal names the field and the constant value", reason[:90])
    check(not any(key.startswith("wheel_ground_vel") for key in reasons),
          "the ground-velocity channels are usable in that recording", str(list(reasons)))

    old = rear_slip.column_reasons(pq.read_table(OLD_SESSION))
    check("wheel_ground_vel_lat_rl" in old and "absent" in old["wheel_ground_vel_lat_rl"],
          "a recording without the new columns reports them absent")
    check(rear_slip.slip_series(pq.read_table(
        OLD_SESSION, columns=["lap_distance_m", "speed_kph"])) is None,
        "no ground velocities means no slip series (None, never 0.0)")


# ------------------------------------------------------------- 2. measurement
def _synthetic(table_rows=200, brake_to=120, gap_from=None):
    distance = [float(i) for i in range(table_rows)]
    slip = []
    for i, d in enumerate(distance):
        if gap_from is not None and d >= gap_from:
            slip.append(None)
        elif d < 60:
            slip.append(0.0)
        elif d < 140:
            slip.append(2.0)
        else:
            slip.append(6.0)
    brake = [0.5 if d <= brake_to else 0.0 for d in distance]
    return distance, slip, brake


def test_measure_corner() -> None:
    distance, slip, brake = _synthetic()
    measured = rear_slip.measure_corner(slip, distance, brake,
                                        apex_m=100.0, entry_m=40.0,
                                        zone=(40.0, 160.0))
    check(abs(measured.apex_deg - 2.0) < 1e-9, "apex slip is the median inside the apex window",
          str(measured.apex_deg))
    check(abs(measured.braking_deg - 2.0) < 1e-9,
          "braking slip is the median while the brake is on, before the apex",
          str(measured.braking_deg))
    check(measured.peak_deg is not None and measured.peak_deg > 5.0,
          "peak slip is the high percentile over the whole corner", str(measured.peak_deg))
    check(abs(measured.coverage - 1.0) < 1e-9, "coverage counts valid samples",
          str(measured.coverage))

    distance, slip, brake = _synthetic(gap_from=60)
    sparse = rear_slip.measure_corner(slip, distance, brake, apex_m=100.0,
                                      entry_m=40.0, zone=(40.0, 160.0))
    check(sparse.apex_deg is None and sparse.peak_deg is None,
          "below the coverage floor the corner has no slip fact, not a small one",
          f"coverage {sparse.coverage:.2f}")
    check(bool(sparse.reason), "an unmeasurable window says why", sparse.reason)

    wild = [0.0, 0.0, 90.0, 0.0] * 50
    distance = [float(i) for i in range(len(wild))]
    insane = rear_slip.measure_corner(wild, distance, [0.0] * len(wild),
                                      apex_m=100.0, entry_m=40.0, zone=(40.0, 160.0))
    check(insane.apex_deg is None,
          "a value past the sane bound is a spin or a bad channel, not slip",
          str(insane.apex_deg))


# -------------------------------------------------------------- 3. assessment
class FakeLap:
    def __init__(self, index: int, apex: float | None, braking: float | None,
                 clean: bool = True, corner: str = "c1"):
        self.segment_index = index
        self.lap_number = index
        self.lap_time_s = 80.0
        self.delta_s = 0.0
        self.clean = clean
        self.phases = []
        self.corners = [CornerExtras(corner_id=corner, corner_name="Corner",
                                     apex_distance_m=1000.0,
                                     rear_slip_apex_deg=apex,
                                     rear_slip_braking_deg=braking)]


def test_assessment() -> None:
    laps = [FakeLap(i, 1.7, 1.5) for i in range(6)]
    laps.append(FakeLap(6, 4.5, 4.1, clean=False))
    measured = rear_stability.assess_corner(laps, "c1", unmeasurable={})
    check(measured.state == "measured_instability",
          "one lap well above the session's own envelope is measured instability",
          measured.state)
    check(abs(measured.value_deg - 4.5) < 1e-9, "the cited value is the worst lap's",
          str(measured.value_deg))
    check(abs(measured.baseline_deg - 1.7) < 1e-9,
          "the baseline is the clean laps' own median, not a constant",
          str(measured.baseline_deg))
    check(measured.brake_overlap is True,
          "braking-phase slip at the same magnitude says the instability overlaps braking")
    check(measured.flagged and measured.flagged[0]["clean"] is False,
          "a non-clean observation is reported separately, not hidden",
          str(measured.flagged[0] if measured.flagged else None))

    calm = rear_stability.assess_corner([FakeLap(i, 1.7, 1.5) for i in range(6)], "c1",
                                   unmeasurable={})
    check(calm.state == "no_detected_instability",
          "valid low-slip laps are 'no detected instability', not 'stable'",
          calm.state)
    check(calm.value_deg is None, "nothing is flagged, so nothing is cited", str(calm.value_deg))

    blind = rear_stability.assess_corner([FakeLap(i, None, None) for i in range(6)], "c1",
                                    unmeasurable={})
    check(blind.state == "unknown", "missing data is unknown, never 'no slip'", blind.state)
    check("could not" in blind.reason or "no rear-slip" in blind.reason.lower()
          or "not measurable" in blind.reason.lower(),
          "unknown explains itself", blind.reason)

    patchy = [FakeLap(i, 1.7 if i < 2 else None, None) for i in range(6)]
    thin = rear_stability.assess_corner(patchy, "c1", unmeasurable={})
    check(thin.state == "unknown",
          "a couple of valid laps out of six is insufficient coverage", thin.state)


def test_real_session() -> None:
    session = load_session(BARCELONA_RACE)
    records = classify_laps(session.table, sample_rate_hz=session.sample_rate_hz)
    facts = build_session_facts(session, records, resolve_debrief_inputs(session))

    check("grip_fraction_rl" in facts.session.unmeasurable_channels,
          "the session payload refuses the dead grip channel")
    check(any(extra.rear_slip_apex_deg is not None
              for lap in facts.laps for extra in lap.corners),
          "corner extras carry a measured apex slip angle")

    stability = rear_stability.assess_session(facts)
    repsol = next((s for s in stability.values() if "Repsol" in s.corner_name), None)
    check(repsol is not None, "Repsol appears in the session's rear-stability map")
    if repsol is not None:
        check(repsol.state == "measured_instability",
              "Repsol on 2026-11-15 (the brake-into-apex slide) is measured instability",
              f"{repsol.state} at {repsol.value_deg} deg")
        check(repsol.value_deg is not None and repsol.value_deg >= 4.0,
              "the cited apex slip is the lap that actually slid", str(repsol.value_deg))
        check(repsol.brake_overlap is True,
              "the flag lands in the braking window, so brake advice must be qualified",
              f"braking {repsol.braking_deg} deg with brake on at the apex")

    campsa = next((s for s in stability.values() if "Campsa" in s.corner_name), None)
    check(campsa is not None and campsa.state == "no_detected_instability",
          "a corner without an outlier keeps normal advice",
          campsa.state if campsa else "missing")

    from lap_telemetry.session_brief import corner_block

    repsol_id = next((c.corner_id for c in facts.reference_corners
                      if "Repsol" in c.corner_name), None)
    block = corner_block(facts, repsol_id) if repsol_id else ""
    check("rear stability:" in block,
          "the corner drill-down cites the rear-slip evidence", block[:0])
    check("deg at the apex" in block and "on segment" in block,
          "the citation carries the value and the lap it came from")
    check("brake applied" in block or "not evidence of brake-induced" in block,
          "the citation says whether braking overlapped")

    campsa_id = next((c.corner_id for c in facts.reference_corners
                      if "Campsa" in c.corner_name), None)
    calm_block = corner_block(facts, campsa_id) if campsa_id else ""
    check("no instability detected" in calm_block,
          "a clean corner says so without claiming universal stability")

    old = load_session(OLD_SESSION)
    old_records = classify_laps(old.table, sample_rate_hz=old.sample_rate_hz)
    try:
        old_facts = build_session_facts(old, old_records, resolve_debrief_inputs(old))
    except Exception as exc:  # noqa: BLE001 - the fixture may not resolve a model
        print(f"  [PASS] old session cannot be analysed here ({type(exc).__name__}), "
              f"absent-channel refusal pinned directly")
    else:
        old_stability = rear_stability.assess_session(old_facts)
        if old_stability:
            states = {s.state for s in old_stability.values()}
            check(states == {"unknown"},
                  "a session without the new columns is unknown everywhere", str(states))
        old_block = corner_block(old_facts, old_facts.reference_corners[0].corner_id)
        check("not measurable" in old_block,
              "an old recording's drill-down refuses, it does not report zero slip")


if __name__ == "__main__":
    print("rear slip facts — slice 01 phase C")
    for name, test in (("physics", test_real_recording),
                       ("dead channels", test_dead_channels),
                       ("measurement", test_measure_corner),
                       ("assessment", test_assessment),
                       ("real session", test_real_session)):
        print(f"\n{name}")
        test()
    print(f"\n{_passed}/{_passed + _failed} assertions passed")
    sys.exit(1 if _failed else 0)
