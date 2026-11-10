#!/usr/bin/env python3
"""Consistency metric tests (slice 03 of the session debrief).

Consistency answers a different question than the reference comparison: is the
driver slow here *every lap*, or erratic? The two must never be merged, and the
ranking unit must be seconds — a big km/h spread through a slow hairpin is not
worth more than a smaller one at 250 km/h.

Protocol: prints [PASS]/[FAIL] lines and exits non-zero on any failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "product" / "python"))
sys.path.insert(0, str(ROOT / "dev" / "scripts"))

import pyarrow as pa  # noqa: E402

from lap_telemetry.coach.facts import CornerLoss  # noqa: E402
from lap_telemetry.lap_signals import sector_times  # noqa: E402
from lap_telemetry.session_consistency import (  # noqa: E402
    build_consistency,
    lap_pace,
    speed_envelope_optimal,
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


class FakeLap:
    """Minimal stand-in for LapFacts in the pure-aggregation tests."""

    def __init__(self, segment_index: int, duration: float, phases: list[CornerLoss],
                 clean: bool = True):
        self.segment_index = segment_index
        self.lap_number = segment_index
        self.lap_time_s = duration
        self.delta_s = 0.0
        self.clean = clean
        self.phases = phases


def phase(corner: str, name: str, kind: str, loss: float, value: float,
          apex: float = 1000.0, point: float | None = None) -> CornerLoss:
    return CornerLoss(
        corner_id=corner, corner_name=name, apex_distance_m=apex, phase=kind,
        loss_s=loss, driver_value=value, reference_value=value, unit="km/h",
        confidence="medium", phase_distance_m=point,
    )


def synth_lap_table(laps: list[tuple[list[float], list[float]]], lap_length: float) -> pa.Table:
    """Build a session table from per-lap (speed_kph, lap_time_s) samples."""
    rows: dict[str, list] = {
        "lap_number": [], "lap_distance_m": [], "speed_kph": [],
        "lap_time_s": [], "session_time_s": [],
    }
    start = 100.0
    for index, (speeds, times) in enumerate(laps, start=1):
        step = lap_length / (len(speeds) - 1)
        for i, (v, t) in enumerate(zip(speeds, times)):
            rows["lap_number"].append(index)
            rows["lap_distance_m"].append(i * step)
            rows["speed_kph"].append(v)
            rows["lap_time_s"].append(t)
            rows["session_time_s"].append(start + t)
        start += times[-1]
    return pa.table(rows)


class Record:
    def __init__(self, index: int, start: int, end: int, duration: float, clean: bool = True):
        self.segment_index = index
        self.start_row = start
        self.end_row = end
        self.duration_s = duration
        self.clean = clean


def test_envelope_is_the_harmonic_sum_of_best_speeds() -> None:
    """Two laps, each faster in one half: the envelope must beat both."""
    # 201 samples, 5 m apart over 1000 m. The envelope needs a dense trace.
    speed_a = [200.0 if i <= 100 else 100.0 for i in range(201)]
    speed_b = [100.0 if i <= 100 else 200.0 for i in range(201)]

    def times_for(speeds: list[float]) -> list[float]:
        out = [0.0]
        for v in speeds[1:]:
            out.append(out[-1] + (5.0 / (v / 3.6)))
        return out

    time_a, time_b = times_for(speed_a), times_for(speed_b)
    table = synth_lap_table([(speed_a, time_a), (speed_b, time_b)], 1000.0)

    envelope, gaps, used = speed_envelope_optimal(
        table,
        [Record(1, 0, len(speed_a), time_a[-1]),
         Record(2, len(speed_a), 2 * len(speed_a), time_b[-1])],
        lap_length_m=1000.0,
    )

    # Each lap is fast in one half; the envelope takes the fast half of each,
    # so 1000 m at 200 km/h — strictly better than either lap.
    expected = 1000.0 / (200.0 / 3.6)
    check(used == 2, "both laps contribute to the envelope", str(used))
    check(gaps == 0, "no distance bin is left uncovered", str(gaps))
    check(abs(envelope - expected) < 0.5,
          "envelope takes the best half of each lap",
          f"{envelope:.3f} vs {expected:.3f}")


def test_lap_pace_spread_and_available_time() -> None:
    laps = [FakeLap(i, d, []) for i, d in enumerate([80.0, 81.0, 82.0, 79.0, 83.0], start=1)]
    pace = lap_pace(laps, envelope_lap_s=78.0)

    check(pace.clean_laps == 5, "counts the clean laps", str(pace.clean_laps))
    check(abs(pace.best_lap_s - 79.0) < 1e-6, "best lap is the fastest clean one")
    check(abs(pace.median_lap_s - 81.0) < 1e-6, "median lap is the middle one")
    check(abs(pace.worst_clean_lap_s - 83.0) < 1e-6, "worst is the slowest clean one")
    check(abs(pace.spread_s - 4.0) < 1e-6, "spread is worst minus best", str(pace.spread_s))
    check(abs(pace.std_dev_s - 1.4142) < 0.001,
          "std dev is the population deviation of the clean laps", f"{pace.std_dev_s:.4f}")
    check(abs(pace.time_available_s - 1.0) < 1e-6,
          "time available is best minus envelope", str(pace.time_available_s))
    check(pace.basis == "speed_envelope", "the basis is stated", pace.basis)


def test_recurring_and_inconsistent_are_separate_rankings() -> None:
    """A steady loss and an erratic loss must not be conflated."""
    laps = []
    for index in range(5):
        steady = 0.30                       # always loses the same
        erratic = [0.02, 0.02, 0.60, 0.02, 0.02][index]
        laps.append(FakeLap(index + 1, 80.0 + index * 0.1, [
            phase("t_steady", "Steady", "minimum_speed", steady, 100.0, apex=1000.0),
            phase("t_erratic", "Erratic", "minimum_speed", erratic, 150.0, apex=2000.0),
        ]))

    consistency = build_consistency(laps, envelope_lap_s=79.5)

    recurring = {r.corner_id: r for r in consistency.recurring_losses}
    check(recurring["t_steady"].mean_loss_s > recurring["t_erratic"].mean_loss_s,
          "the steady corner leads the recurring ranking",
          f"{recurring['t_steady'].mean_loss_s:.2f} vs {recurring['t_erratic'].mean_loss_s:.2f}")
    check(recurring["t_steady"].laps_affected == 5,
          "and is reported as hurting on every lap", str(recurring["t_steady"].laps_affected))

    inconsistent = {c.corner_id: c for c in consistency.inconsistent_corners}
    check(inconsistent["t_erratic"].spread_s > inconsistent["t_steady"].spread_s,
          "the erratic corner leads the inconsistency ranking",
          f"{inconsistent['t_erratic'].spread_s:.2f} vs {inconsistent['t_steady'].spread_s:.2f}")
    check(len(consistency.inconsistent_corners) == 1
          or consistency.inconsistent_corners[0].corner_id == "t_erratic",
          "and it is ranked first", consistency.inconsistent_corners[0].corner_id)


def test_inconsistency_is_ranked_in_seconds_not_kmh() -> None:
    """A huge km/h spread at low speed must not outrank a real time spread."""
    laps = []
    for index in range(4):
        # Hairpin: 40 km/h spread, but the corner is slow, so it costs little time.
        hairpin_speed = 60.0 + index * 13.0
        hairpin_loss = 0.01 + index * 0.01
        # Fast sweeper: smaller speed spread, bigger time spread.
        sweeper_speed = 240.0 + index * 2.0
        sweeper_loss = [0.00, 0.35, 0.02, 0.30][index]
        laps.append(FakeLap(index + 1, 80.0, [
            phase("t_hairpin", "Hairpin", "minimum_speed", hairpin_loss, hairpin_speed, apex=500.0),
            phase("t_sweeper", "Sweeper", "minimum_speed", sweeper_loss, sweeper_speed, apex=1500.0),
        ]))

    consistency = build_consistency(laps, envelope_lap_s=79.0)
    check(consistency.inconsistent_corners[0].corner_id == "t_sweeper",
          "the corner with the larger time spread ranks first",
          consistency.inconsistent_corners[0].corner_id)

    spread = {s.corner_id: s for s in consistency.phase_spread if s.phase == "minimum_speed"}
    check(spread["t_hairpin"].spread > spread["t_sweeper"].spread,
          "even though the hairpin has the larger km/h spread",
          f"{spread['t_hairpin'].spread:.1f} vs {spread['t_sweeper'].spread:.1f} km/h")
    check(spread["t_hairpin"].unit == "km/h" and spread["t_hairpin"].samples == 4,
          "phase spread reports its unit and sample count")


def test_clean_laps_only() -> None:
    laps = [
        FakeLap(1, 80.0, [], clean=True),
        FakeLap(2, 80.2, [], clean=True),
        FakeLap(3, 95.0, [], clean=False),   # traffic
    ]
    pace = lap_pace(laps, envelope_lap_s=79.0)
    check(pace.clean_laps == 2, "a traffic lap is not part of the consistency set", str(pace.clean_laps))
    check(abs(pace.best_lap_s - 80.0) < 1e-6, "and cannot become the best lap")
    check(abs(pace.spread_s - 0.2) < 1e-6, "nor inflate the spread", str(pace.spread_s))

    # The rankings must ignore it too: give the traffic lap a corner loss big
    # enough to top both rankings if it were allowed in.
    traffic = FakeLap(3, 95.0, [
        phase("t1", "Turn 1", "minimum_speed", 9.0, 40.0),
    ], clean=False)
    clean_laps = [
        FakeLap(1, 80.0, [phase("t1", "Turn 1", "minimum_speed", 0.10, 100.0)]),
        FakeLap(2, 80.2, [phase("t1", "Turn 1", "minimum_speed", 0.20, 101.0)]),
        traffic,
    ]
    consistency = build_consistency(clean_laps, envelope_lap_s=79.0)
    check(all(abs(r.mean_loss_s) < 1.0 for r in consistency.recurring_losses),
          "a traffic lap cannot create a recurring loss",
          str([round(r.mean_loss_s, 3) for r in consistency.recurring_losses]))
    check(all(c.worst_loss_s < 1.0 for c in consistency.inconsistent_corners),
          "nor inflate a corner's inconsistency",
          str([round(c.worst_loss_s, 3) for c in consistency.inconsistent_corners]))


def test_real_session_consistency() -> None:
    if not PRACTICE.exists():
        check(False, "Paul Ricard fixture present", str(PRACTICE))
        return

    session = load_session(PRACTICE)
    records = classify_laps(session.table, sample_rate_hz=session.sample_rate_hz)
    inputs = resolve_debrief_inputs(session)
    facts = build_session_facts(session, records, inputs)
    consistency = facts.consistency

    check(consistency.pace.clean_laps == 16, "16 clean laps drive the metrics",
          str(consistency.pace.clean_laps))
    check(abs(consistency.pace.best_lap_s - 79.135) < 0.01,
          "best clean lap matches the inventory", f"{consistency.pace.best_lap_s:.3f}")
    check(consistency.pace.envelope_lap_s < consistency.pace.best_lap_s,
          "the envelope beats the best single lap",
          f"{consistency.pace.envelope_lap_s:.3f} vs {consistency.pace.best_lap_s:.3f}")
    check(0 < consistency.pace.time_available_s < 10,
          "the repeatability prize is plausible", f"{consistency.pace.time_available_s:.3f} s")
    check(len(consistency.recurring_losses) > 0 and len(consistency.inconsistent_corners) > 0,
          "both rankings are populated")
    check(consistency.recurring_losses == sorted(consistency.recurring_losses,
                                                 key=lambda r: r.mean_loss_s, reverse=True),
          "recurring losses are ranked by mean loss")
    check(all(a.spread_s >= b.spread_s for a, b in
              zip(consistency.inconsistent_corners, consistency.inconsistent_corners[1:])),
          "inconsistent corners are ranked by time spread")
    check(consistency.phase_spread == sorted(consistency.phase_spread,
                                             key=lambda s: s.spread, reverse=True),
          "phase spreads are ranked by their own-unit spread")


def test_consistency_is_in_the_payload() -> None:
    session = load_session(PRACTICE)
    records = classify_laps(session.table, sample_rate_hz=session.sample_rate_hz)
    payload = build_session_facts(session, records, resolve_debrief_inputs(session)).to_dict()

    check("consistency" in payload, "the payload carries the consistency section")
    consistency = payload["consistency"]
    check({"pace", "recurring_losses", "inconsistent_corners", "phase_spread"} <= set(consistency),
          "all four parts are present", str(sorted(consistency)))
    check(consistency["pace"]["basis"] == "speed_envelope",
          "the optimal-lap basis is explicit")
    json.dumps(payload)
    check(True, "the whole payload stays JSON-serializable")


def test_sector_times_extraction_still_available() -> None:
    """The reusable sector reader exists even though the metrics do not use it."""
    table = pa.table({
        "last_sector_1_s": [None, 18.0, 18.0],
        "last_sector_2_s": [None, 48.0, 48.0],
    })
    segments = [(1, 0, 1), (2, 1, 3)]
    check(sector_times(table, segments, 0, 80.0) == (18.0, 30.0, 32.0),
          "sectors walk past unsettled frames and derive S3 from the lap duration")
    check(sector_times(table, segments, 1, 80.0) == (None, None, None),
          "the final segment has no sector data")


def main() -> int:
    print("═══ Session consistency tests ═══\n")
    test_envelope_is_the_harmonic_sum_of_best_speeds()
    test_lap_pace_spread_and_available_time()
    test_recurring_and_inconsistent_are_separate_rankings()
    test_inconsistency_is_ranked_in_seconds_not_kmh()
    test_clean_laps_only()
    test_real_session_consistency()
    test_consistency_is_in_the_payload()
    test_sector_times_extraction_still_available()
    print(f"\n{_passed}/{_passed + _failed} assertions passed")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
