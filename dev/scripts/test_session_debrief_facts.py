#!/usr/bin/env python3
"""Per-lap debrief facts tests (slice 02 of the session debrief).

The session facts are the data every later slice reasons over, so these tests
pin the things that would silently poison it: lap identity, the reference
baseline, uncapped output, and the five-lap gate.

Protocol: prints [PASS]/[FAIL] lines and exits non-zero on any failure.
"""
from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "product" / "python"))
sys.path.insert(0, str(ROOT / "dev" / "scripts"))

from lap_telemetry.coach.facts import CornerLoss  # noqa: E402
from lap_telemetry.debrief import run as debrief_run  # noqa: E402
from lap_telemetry.session_facts import (  # noqa: E402
    build_session_facts,
    excluded_laps,
)
from lap_telemetry.session_inputs import (  # noqa: E402
    DebriefInputError,
    resolve_debrief_inputs,
)
from lap_telemetry.session_laps import MIN_ELIGIBLE_LAPS, classify_laps  # noqa: E402
from lap_telemetry.session_source import load_session  # noqa: E402

PRACTICE = (ROOT / "dev" / "sessions"
            / "session_20260524T141613Z_paul-ricard---3a_lmu.parquet")
SHORT_SESSION = (ROOT / "dev" / "sessions"
                 / "session_20260905T065812Z_lusail-international-circuit_lmu_practice.parquet")

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


def _fixture():
    session = load_session(PRACTICE)
    records = classify_laps(session.table, sample_rate_hz=session.sample_rate_hz)
    inputs = resolve_debrief_inputs(session)
    return session, records, inputs


def test_inputs_resolve_by_track_and_car() -> None:
    session = load_session(PRACTICE)
    inputs = resolve_debrief_inputs(session)

    check(inputs.track == "Paul Ricard - 3A", "track comes from the sidecar", inputs.track)
    check(inputs.vehicle_name == "DKR Engineering #4:ELMS25",
          "vehicle comes from the sidecar", inputs.vehicle_name)
    check(inputs.car_slug == "ginetta-lmp3",
          "the car resolves to its canonical model, not its livery", str(inputs.car_slug))
    check(inputs.reference_path.name.endswith("_time_01.17.166.parquet"),
          "the fastest reference lap for the combo is chosen", inputs.reference_path.name)
    check(abs(inputs.reference_lap_time_s - 77.166) < 0.01,
          "reference duration is authoritative", f"{inputs.reference_lap_time_s:.3f}")
    check(inputs.track_model.track_id == "paul-ricard---3a",
          "coaching model matches the track", inputs.track_model.track_id)

    try:
        resolve_debrief_inputs(
            session,
            reference=Path("/nonexistent/reference.parquet"),
        )
        check(False, "an unusable reference path is rejected")
    except DebriefInputError as exc:
        check("reference" in str(exc).lower(), "an unusable reference path is rejected", str(exc))


def test_lap_identity_is_the_segment() -> None:
    """Segments 1 and 4 both carry lap_number 1 but are different laps."""
    session, records, inputs = _fixture()
    facts = build_session_facts(session, records, inputs)
    by_segment = {lap.segment_index: lap for lap in facts.laps}

    check(len(facts.laps) == 18, "one entry per eligible lap", str(len(facts.laps)))
    check(by_segment[1].lap_number == 1 and by_segment[4].lap_number == 1,
          "both stints contribute a lap numbered 1")
    check(abs(by_segment[1].lap_time_s - 84.804) < 0.01,
          "stint 1 lap 1 keeps its own duration", f"{by_segment[1].lap_time_s:.3f}")
    check(abs(by_segment[4].lap_time_s - 82.491) < 0.01,
          "stint 2 lap 1 keeps a different duration", f"{by_segment[4].lap_time_s:.3f}")
    check(by_segment[1].lap_time_s != by_segment[4].lap_time_s,
          "lap_number alone would have merged them")

    durations = {r.segment_index: r.duration_s for r in records if r.eligible}
    check(all(abs(by_segment[i].lap_time_s - d) < 1e-6 for i, d in durations.items()),
          "every lap duration matches the inventory that classified it")


def test_facts_are_reference_relative_and_uncapped() -> None:
    session, records, inputs = _fixture()
    facts = build_session_facts(session, records, inputs)

    check(abs(facts.session.reference_lap_s - inputs.reference_lap_time_s) < 1e-9,
          "session summary carries the reference baseline")
    check(all(abs(lap.delta_s - (lap.lap_time_s - facts.session.reference_lap_s)) < 1e-6
              for lap in facts.laps),
          "every lap delta is lap time minus reference")
    check(abs(facts.session.reference_lap_s - 77.166) < 0.001,
          "the baseline is the reference file's certified time",
          f"{facts.session.reference_lap_s:.3f}")
    check(facts.session.eligible_laps == 18 and facts.session.clean_laps == 16,
          "eligible and clean counts come from the inventory",
          f"{facts.session.eligible_laps}/{facts.session.clean_laps}")

    phase_counts = [len(lap.phases) for lap in facts.laps]
    check(max(phase_counts) > 6,
          "phases are uncapped, beyond the live coach's 3 losses + 3 gains",
          f"max {max(phase_counts)} per lap")
    check(all(isinstance(p, CornerLoss) for lap in facts.laps for p in lap.phases),
          "phase facts reuse CornerLoss rather than a parallel type")
    check(all(len({(p.corner_id, p.phase) for p in lap.phases}) == len(lap.phases)
              for lap in facts.laps),
          "a corner phase appears at most once per lap")

    distances = [p.apex_distance_m for lap in facts.laps for p in lap.phases]
    check(all(d is not None for d in distances) and min(distances) >= 0,
          "every phase is anchored to a corner apex distance")


def test_excluded_laps_are_reported() -> None:
    session, records, inputs = _fixture()
    excluded = excluded_laps(records)
    facts = build_session_facts(session, records, inputs)

    check(len(excluded) == 7, "the seven non-eligible segments are listed", str(len(excluded)))
    check(len(facts.excluded) == len(excluded), "and appear in the facts payload")
    check(all(x.reason for x in excluded), "each states why it was dropped")
    check({x.status for x in excluded} == {"out-lap", "in-lap", "pit-lap", "incomplete", "short"},
          "the status vocabulary matches the inventory",
          str(sorted({x.status for x in excluded})))


def test_reference_baseline_is_the_certified_time() -> None:
    """A single-segment reference cannot re-derive its duration reliably.

    The telemetry-clock method needs the next lap's start ET, which an extracted
    reference does not have, so ``authoritative_duration`` falls back to the
    scorer's ``mLastLapTime`` — stale by up to a second. For the 23 references
    without an ``authoritative_lap_time_s`` stamp the filename is the value the
    export certified.
    """
    import pyarrow.parquet as pq

    from lap_telemetry.coach.lap_table import duration_segment_for_lap, segment_duration
    from lap_telemetry.session_inputs import (
        reference_lap_time_from_name,
        reference_lap_time_s,
    )

    paul_ricard = (ROOT / "product" / "data" / "reference-laps"
                   / "paul-ricard---3a_dkr-engineering-4-elms25_time_01.17.166.parquet")
    table = pq.read_table(paul_ricard)
    certified = reference_lap_time_s(table, paul_ricard)
    rederived = segment_duration(
        table, duration_segment_for_lap(table, None), allow_same_segment_scoring=True
    )
    check(abs(certified - 77.166) < 0.001,
          "the filename time is the baseline, not the stale scorer", f"{certified:.3f}")
    check(rederived - certified > 0.4,
          "and it differs materially from a re-derivation",
          f"re-derived {rederived:.3f} vs certified {certified:.3f}")

    stamped = (ROOT / "product" / "data" / "reference-laps"
               / "algarve-international-circuit_dkr-engineering-4-elms25_time_01.40.706.parquet")
    stamped_table = pq.read_table(stamped)
    check(abs(reference_lap_time_s(stamped_table, stamped) - 100.706) < 0.001,
          "a metadata stamp is honoured as-is, filename or not")

    check(reference_lap_time_from_name("x_time_01.17.166.parquet") == 77.166,
          "the filename parser reads mm.ss.mmm")
    check(reference_lap_time_from_name("no-time-here.parquet") is None,
          "and returns None when there is nothing to read")


def test_json_payload_is_serializable_and_complete() -> None:
    session, records, inputs = _fixture()
    payload = build_session_facts(session, records, inputs).to_dict()

    text = json.dumps(payload)
    check(len(text) > 1000, "payload serializes to real JSON", f"{len(text)} chars")
    check(payload["type"] == "session_debrief", "type names the product")
    check(payload["schema_version"] == "1", "schema version is explicit")
    check(payload["session"]["car_slug"] == "ginetta-lmp3",
          "combo identity is in the payload (forward-compatible with a profile)")
    check({"laps", "excluded", "session"} <= set(payload),
          "payload has session, laps and excluded", str(sorted(payload)))

    first = payload["laps"][0]
    check({"segment_index", "lap_number", "lap_time_s", "delta_s", "clean", "phases"} <= set(first),
          "each lap states its identity, baseline delta and phases")
    phase = first["phases"][0]
    check({"corner_id", "corner_name", "phase", "loss_s", "driver_value",
           "reference_value", "unit"} <= set(phase),
          "each phase carries the shared CornerLoss serialization", str(sorted(phase)))


def test_short_session_is_refused() -> None:
    if not SHORT_SESSION.exists():
        check(False, "short-session fixture present", str(SHORT_SESSION))
        return

    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = debrief_run(SHORT_SESSION, json_only=True)

    check(code == 1, "a four-lap session exits non-zero", str(code))
    message = err.getvalue()
    check(str(MIN_ELIGIBLE_LAPS) in message, "the gate states its minimum", message.strip()[:90])
    check(out.getvalue() == "", "no JSON is printed when the gate refuses")
    check("incomplete" in message, "the rejected laps are listed with reasons", message.strip()[:90])


def test_cli_json_round_trip() -> None:
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = debrief_run(PRACTICE, json_only=True)

    check(code == 0, "the practice session exits zero", err.getvalue()[:100])
    payload = json.loads(out.getvalue())
    check(len(payload["laps"]) == 18, "CLI prints every eligible lap")
    check(payload["session"]["track"] == "Paul Ricard - 3A", "CLI carries the session header")


def main() -> int:
    print("═══ Session debrief facts tests ═══\n")
    test_inputs_resolve_by_track_and_car()
    test_lap_identity_is_the_segment()
    test_facts_are_reference_relative_and_uncapped()
    test_excluded_laps_are_reported()
    test_reference_baseline_is_the_certified_time()
    test_json_payload_is_serializable_and_complete()
    test_short_session_is_refused()
    test_cli_json_round_trip()
    print(f"\n{_passed}/{_passed + _failed} assertions passed")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
