#!/usr/bin/env python3
"""Improvement priorities: one deduplicated, ranked, explainable list.

Slice 03 produced two rankings and slice 04 produced the channel facts. This
slice is the only place that decides what the driver should actually change, and
it must do so without a model: every suggestion is computed from a measured
delta, and when no delta explains a loss the priority says so.

Protocol: prints [PASS]/[FAIL] lines and exits non-zero on any failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "product" / "python"))
sys.path.insert(0, str(ROOT / "dev" / "scripts"))

from lap_telemetry.coach.facts import CornerLoss  # noqa: E402
from lap_telemetry.session_corner_extras import CornerExtras  # noqa: E402
from lap_telemetry.session_facts import build_session_facts  # noqa: E402
from lap_telemetry.session_inputs import resolve_debrief_inputs  # noqa: E402
from lap_telemetry.session_laps import classify_laps  # noqa: E402
from lap_telemetry.session_priorities import build_priorities, suggest_change  # noqa: E402
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
    def __init__(self, index: int, delta: float, phases: list[CornerLoss],
                 corners: list[CornerExtras], clean: bool = True):
        self.segment_index = index
        self.lap_number = index
        self.lap_time_s = 80.0 + delta
        self.delta_s = delta
        self.clean = clean
        self.phases = phases
        self.corners = corners


def phase(corner: str, name: str, kind: str, loss: float, driver: float,
          reference: float, *, apex: float = 1000.0, entry_delta: float | None = None,
          exit_delta: float | None = None, point: float | None = None) -> CornerLoss:
    return CornerLoss(
        corner_id=corner, corner_name=name, apex_distance_m=apex, phase=kind,
        loss_s=loss, driver_value=driver, reference_value=reference, unit="km/h",
        confidence="high", phase_distance_m=point,
        entry_distance_delta_m=entry_delta, exit_distance_delta_m=exit_delta,
    )


def extra(corner: str, name: str, *, gear: int | None = None, trail: float | None = None,
          apex: float = 1000.0) -> CornerExtras:
    return CornerExtras(corner_id=corner, corner_name=name, apex_distance_m=apex,
                        gear_at_apex=gear, trail_brake_depth_m=trail)


def scenario() -> tuple[list[FakeLap], list[CornerExtras]]:
    """A session with one slow-every-lap corner, one erratic corner, one fine."""
    laps: list[FakeLap] = []
    for index in range(6):
        phases = [
            # "slow": 0.6 s every lap, 4 km/h down, 12 m early on the brakes.
            phase("slow", "Slow Corner", "minimum_speed", 0.60 + 0.02 * index, 78.0, 82.0,
                  apex=1000.0),
            phase("slow", "Slow Corner", "entry", 0.2, 200.0, 202.0, apex=1000.0,
                  entry_delta=12.0, point=900.0),
            # "erratic": mean ~0, but swings by 1.2 s.
            phase("erratic", "Erratic Corner", "minimum_speed",
                  -0.55 if index % 2 else 0.65, 80.0, 80.0, apex=2000.0),
            # "fine": nothing to see.
            phase("fine", "Fine Corner", "minimum_speed", 0.01, 120.0, 120.1, apex=3000.0),
        ]
        corners = [
            extra("slow", "Slow Corner", gear=4, trail=0.0),
            extra("erratic", "Erratic Corner", gear=3),
            extra("fine", "Fine Corner", gear=5),
        ]
        laps.append(FakeLap(index, 1.5, phases, corners))
    reference = [extra("slow", "Slow Corner", gear=3, trail=8.0),
                 extra("erratic", "Erratic Corner", gear=3),
                 extra("fine", "Fine Corner", gear=5)]
    return laps, reference


def test_ranking_and_dedup() -> None:
    laps, reference = scenario()
    priorities = build_priorities(laps, reference, total_gap_s=1.5)
    ids = [p.corner_id for p in priorities]

    check(ids[0] == "slow", "the corner lost every lap outranks the erratic one", str(ids))
    check("fine" not in ids, "a corner with nothing measurable is dropped", str(ids))
    check(ids.count("slow") == 1 and ids.count("erratic") == 1,
          "each corner appears exactly once, not once per phase", str(ids))
    check([p.rank for p in priorities] == list(range(1, len(priorities) + 1)),
          "ranks are dense and ordered", str([p.rank for p in priorities]))

    slow = priorities[ids.index("slow")]
    check(slow.kind == "recurring", "a loss on every lap is recurring", slow.kind)
    check(abs(slow.recurring_loss_s - 0.65) < 0.05,
          "the headline loss is the corner's most expensive phase",
          f"{slow.recurring_loss_s}")
    check(slow.laps_affected == 6 and slow.laps == 6,
          "every lap was affected", f"{slow.laps_affected}/{slow.laps}")

    erratic = priorities[ids.index("erratic")]
    check(erratic.kind == "inconsistent", "a swing with no mean is inconsistent", erratic.kind)
    check(abs(erratic.spread_s - 1.2) < 0.01, "its spread is measured in seconds",
          f"{erratic.spread_s}")


def test_share_of_gap() -> None:
    laps, reference = scenario()
    priorities = build_priorities(laps, reference, total_gap_s=1.5)
    slow = next(p for p in priorities if p.corner_id == "slow")
    check(abs(slow.share_of_gap - slow.recurring_loss_s / 1.5) < 0.01,
          "share_of_gap is the corner's loss over the mean lap gap",
          f"{slow.share_of_gap:.2f}")
    check(all(0.0 <= p.share_of_gap <= 1.0 for p in priorities),
          "shares stay inside 0..1", str([round(p.share_of_gap, 2) for p in priorities]))


def test_suggestions() -> None:
    laps, reference = scenario()
    priorities = build_priorities(laps, reference, total_gap_s=1.5)
    slow = next(p for p in priorities if p.corner_id == "slow")
    check("one gear lower at the apex (3rd, not 4th)" in slow.suggestion,
          "a gear difference becomes a gear clause", slow.suggestion)
    check("carry 4 km/h more minimum speed" in slow.suggestion,
          "a speed deficit becomes a speed clause", slow.suggestion)
    check("brake 12 m later" not in slow.suggestion,
          "only the two strongest clauses are joined", slow.suggestion)

    entry_only = suggest_change(
        phases=[phase("x", "X", "entry", 0.3, 200.0, 202.0, entry_delta=12.0, point=900.0)],
        driver_extra=extra("x", "X"), reference_extra=extra("x", "X"),
    )
    check(entry_only == "brake 12 m later", "an early entry becomes 'brake N m later'",
          entry_only)

    throttle = suggest_change(
        phases=[phase("x", "X", "exit_throttle", 0.3, 150.0, 152.0, exit_delta=9.0,
                      point=1100.0)],
        driver_extra=extra("x", "X"), reference_extra=extra("x", "X"),
    )
    check(throttle.startswith("back on the throttle 9 m earlier"),
          "an early throttle exit becomes 'back on the throttle earlier'", throttle)

    brake_exit = suggest_change(
        phases=[phase("x", "X", "exit_brake", 0.3, 150.0, 152.0, exit_delta=6.0,
                      point=1100.0)],
        driver_extra=extra("x", "X"), reference_extra=extra("x", "X"),
    )
    check(brake_exit.startswith("hold the brake 6 m longer"),
          "an early brake release becomes 'hold the brake longer'", brake_exit)

    trail = suggest_change(
        phases=[phase("x", "X", "minimum_speed", 0.3, 80.0, 80.2)],
        driver_extra=extra("x", "X", gear=3, trail=2.0),
        reference_extra=extra("x", "X", gear=3, trail=14.0),
    )
    check("hold the brake 12 m past the apex" in trail,
          "a reference that trails deeper becomes a trail clause", trail)

    exit_speed = suggest_change(
        phases=[phase("x", "X", "exit_brake", 0.4, 60.0, 69.0, exit_delta=-11.5,
                      point=1100.0)],
        driver_extra=extra("x", "X"), reference_extra=extra("x", "X"),
        headline_phase="exit_brake",
    )
    check(exit_speed == "carry 9 km/h more speed onto the straight",
          "an exit-speed deficit becomes a speed-on-the-straight clause", exit_speed)

    late_exit = suggest_change(
        phases=[phase("x", "X", "exit_throttle", 0.4, 60.0, 61.0, exit_delta=-11.5,
                      point=1100.0)],
        driver_extra=extra("x", "X"), reference_extra=extra("x", "X"),
        headline_phase="exit_throttle",
    )
    check("earlier" not in late_exit,
          "a driver who exits later is not told to exit earlier", late_exit)

    implausible = suggest_change(
        phases=[phase("x", "X", "entry", 0.3, 200.0, 202.0, entry_delta=178.0,
                      point=900.0)],
        driver_extra=extra("x", "X"), reference_extra=extra("x", "X"),
        headline_phase="entry",
    )
    check("178" not in implausible,
          "an implausible entry delta is not turned into advice", implausible)

    once = suggest_change(
        phases=[phase("x", "X", "minimum_speed", 0.4, 80.0, 96.0),
                phase("x", "X", "exit", 0.3, 100.0, 116.0, exit_delta=-2.0, point=1100.0)],
        driver_extra=extra("x", "X"), reference_extra=extra("x", "X"),
        headline_phase="minimum_speed",
    )
    check(once.count("carry") == 1,
          "the same speed deficit is stated once, not twice", once)

    two_brakes = suggest_change(
        phases=[phase("x", "X", "exit_brake", 0.5, 60.0, 69.0, exit_delta=7.0,
                      point=1100.0)],
        driver_extra=extra("x", "X", gear=3, trail=2.0),
        reference_extra=extra("x", "X", gear=3, trail=11.0),
        headline_phase="exit_brake",
    )
    check(two_brakes.count("hold the brake") == 1,
          "two brake instructions are collapsed into one", two_brakes)

    nothing = suggest_change(
        phases=[phase("x", "X", "minimum_speed", 0.4, 80.0, 80.2)],
        driver_extra=extra("x", "X", gear=3, trail=None),
        reference_extra=extra("x", "X", gear=3, trail=None),
    )
    check(nothing.startswith("losing 0.4 s here with no single measurable cause"),
          "no measurable cause is stated, not invented", nothing)


def test_clean_laps_only() -> None:
    laps, reference = scenario()
    laps.append(FakeLap(99, 12.0, [
        phase("slow", "Slow Corner", "minimum_speed", 9.0, 40.0, 82.0),
    ], [], clean=False))
    priorities = build_priorities(laps, reference, total_gap_s=1.5)
    slow = next(p for p in priorities if p.corner_id == "slow")
    check(slow.laps == 6 and slow.recurring_loss_s < 1.0,
          "a traffic lap does not become the headline loss",
          f"{slow.laps} laps, {slow.recurring_loss_s} s")


def _practice():
    session = load_session(PRACTICE)
    records = classify_laps(session.table, sample_rate_hz=session.sample_rate_hz)
    inputs = resolve_debrief_inputs(session)
    return build_session_facts(session, records, inputs)


def test_real_session() -> None:
    facts = _practice()
    priorities = facts.priorities
    check(len(priorities) == 9, "every corner that costs time is listed once",
          str(len(priorities)))
    check(len({p.corner_id for p in priorities}) == len(priorities),
          "no corner is listed twice")
    check(priorities[0].rank == 1 and priorities[-1].rank == len(priorities),
          "the list is ranked")

    top = priorities[0]
    check(top.kind in ("recurring", "inconsistent", "both"),
          "the top priority names its kind", top.kind)
    check(top.suggestion and any(ch.isdigit() for ch in top.suggestion),
          "the suggestion carries a number", top.suggestion)
    check(all(p.suggestion for p in priorities),
          "every priority carries a suggestion")
    check(all(p.laps >= 5 for p in priorities),
          "priorities are backed by the clean laps", str(sorted({p.laps for p in priorities})))

    check(priorities[0].recurring_loss_s >= priorities[-1].recurring_loss_s - 1e-9,
          "scores are ordered",
          f"{priorities[0].score:.2f} .. {priorities[-1].score:.2f}")


def test_payload() -> None:
    facts = _practice()
    payload = facts.to_dict()
    check("priorities" in payload, "the payload carries the priorities")
    first = payload["priorities"][0]
    check({"rank", "corner_id", "corner_name", "phase", "kind", "suggestion",
           "recurring_loss_s", "spread_s", "share_of_gap"} <= set(first),
          "a priority serializes its evidence", str(sorted(first)))
    check(json.dumps(payload) and True, "the payload serializes to JSON")


def main() -> int:
    print("Improvement priorities")
    test_ranking_and_dedup()
    test_share_of_gap()
    test_suggestions()
    test_clean_laps_only()
    test_real_session()
    test_payload()
    total = _passed + _failed
    print(f"\n  {_passed}/{total} assertions passed")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
