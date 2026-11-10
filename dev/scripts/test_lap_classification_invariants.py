#!/usr/bin/env python3
"""Invariant tests for lap classification — the *class* of bug, not one case.

Two real bugs had the same shape: a rule discarded a lap on evidence that did
not imply the conclusion.

1. Lusail practice: a forward gap in ``lap_number`` (the recorder stayed stuck
   on lap 9 after a pause) was read as a pit exit, dropping the session's
   fastest lap.
2. Seven sessions: ``segment_index == 0`` was read as a pit exit even when the
   recording started with the car at 210 km/h, dropping a real lap.

A fixture assertion for each would only pin those two recordings. Instead this
suite asserts two things:

* **Justification**: every exclusion is supported by the record it came from
  (``lap_inventory_audit.audit_classification``), over 60 seeded random
  sessions and the committed fixtures.
* **Detection**: the auditor actually reports a violation when a classification
  is unjustified — otherwise a green suite would mean nothing.

Protocol: prints [PASS]/[FAIL] lines and exits non-zero on any failure.
"""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "product" / "python"))
sys.path.insert(0, str(ROOT / "dev" / "scripts"))

from lap_inventory_audit import (  # noqa: E402
    audit_classification,
    random_sessions,
    synth_session,
)
from lap_telemetry.session_laps import (  # noqa: E402
    LapStatus,
    classify_laps,
    load_session,
)

FIXTURES = {
    "paul-ricard (25 segments, sim restart)":
        ROOT / "dev" / "sessions" / "session_20260524T141613Z_paul-ricard---3a_lmu.parquet",
    "lusail (stuck lap 9)":
        ROOT / "dev" / "sessions"
        / "session_20260905T065812Z_lusail-international-circuit_lmu_practice.parquet",
    "barcelona (recording starts in the pits)":
        ROOT / "dev" / "sessions" / "session_20260514T112603Z_circuit-de-barcelona_lmu.parquet",
    "silverstone (recording starts on a flying lap)":
        ROOT / "dev" / "sessions"
        / "session_20261031T051245Z_silverstone-international-circuit_lmu_quali_2laps.parquet",
}

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


def _classify(path: Path):
    session = load_session(path)
    records = classify_laps(session.table, sample_rate_hz=session.sample_rate_hz)
    return session.table, records


def test_random_sessions_are_justified() -> None:
    """No classification may claim a reason the record does not support."""
    violations: list[str] = []
    total_laps = 0
    for index, (table, _ctx) in enumerate(random_sessions(60)):
        records = classify_laps(table)
        total_laps += len(records)
        problems = audit_classification(table, records)
        if problems:
            violations.append(f"random session {index}: {problems[:3]}")
    check(not violations,
          "60 seeded random sessions classify with justified reasons",
          f"{total_laps} segments" + (f"; first violation: {violations[0]}" if violations else ""))


def test_committed_sessions_are_justified() -> None:
    for label, path in FIXTURES.items():
        if not path.exists():
            check(False, f"fixture present: {label}", str(path))
            continue
        table, records = _classify(path)
        problems = audit_classification(table, records)
        check(not problems, f"every exclusion is justified — {label}",
              "; ".join(problems[:3]))


def test_recording_that_starts_on_a_flying_lap_keeps_it() -> None:
    """Regression for the second bug: segment 0 is not automatically an out-lap."""
    path = FIXTURES["silverstone (recording starts on a flying lap)"]
    if not path.exists():
        check(False, "silverstone fixture present", str(path))
        return
    _table, records = _classify(path)
    first = records[0]
    check(first.status == LapStatus.ELIGIBLE,
          "segment 0 entered at racing speed is a real lap", first.status)
    check(first.reason == "", "a kept lap carries no exclusion reason")
    check(records[-1].status == LapStatus.INCOMPLETE,
          "the final segment stays incomplete", records[-1].status)


def test_recording_that_starts_in_the_pits_drops_it() -> None:
    path = FIXTURES["barcelona (recording starts in the pits)"]
    if not path.exists():
        check(False, "barcelona fixture present", str(path))
        return
    _table, records = _classify(path)
    first = records[0]
    check(first.status == LapStatus.OUT_LAP,
          "segment 0 entered from the pit box is an out-lap", first.status)
    check("stint" in first.reason, "and says why", first.reason)


def test_auditor_detects_the_bug_that_happened() -> None:
    """A green audit must mean something: prove it fails on the old mistake."""
    table = synth_session([
        {"lap_number": 9, "duration_s": 115.0, "frames": 5750, "covered_m": 2700.0},
        {"lap_number": 11, "duration_s": 112.6, "frames": 5630},   # racing start
        {"lap_number": 12, "duration_s": 113.0, "frames": 5650},
        {"lap_number": 13, "duration_s": 113.5, "frames": 5675},
        {"lap_number": 14, "duration_s": 20.0, "frames": 1000, "covered_m": 700.0},
    ])
    records = classify_laps(table)

    # The historical bug: a forward gap in lap_number treated as a pit exit.
    bug = [replace(r, status=LapStatus.OUT_LAP, reason="first segment of a stint")
           if r.segment_index == 1 else r for r in records]
    problems = audit_classification(table, bug)
    check(any("no stint boundary" in p for p in problems),
          "audit rejects an out-lap with no stint boundary", "; ".join(problems[:2]))

    # A pit exit claimed on a lap the car entered at racing speed.
    slow = synth_session([
        {"lap_number": 0, "duration_s": 80.0, "frames": 4000, "start_speed": 210.0},
        {"lap_number": 1, "duration_s": 80.0, "frames": 4000},
        {"lap_number": 2, "duration_s": 20.0, "frames": 1000, "covered_m": 700.0},
    ])
    slow_records = classify_laps(slow)
    claimed = [replace(r, status=LapStatus.OUT_LAP, reason="first segment of a stint")
               if r.segment_index == 0 else r for r in slow_records]
    problems = audit_classification(slow, claimed)
    check(any("not a pit exit" in p for p in problems),
          "audit rejects a pit exit on a 210 km/h entry", "; ".join(problems[:2]))

    # Silently dropping a segment, and an exclusion without a reason.
    truncated = [replace(r, reason="") if r.status != LapStatus.ELIGIBLE else r
                 for r in records]
    check(any("excluded without a reason" in p
              for p in audit_classification(table, truncated)),
          "audit rejects an exclusion with no reason")
    check(any("records for" in p
              for p in audit_classification(table, records[:-1])),
          "audit rejects a missing segment")


def main() -> int:
    print("═══ Lap classification invariant tests ═══\n")
    test_random_sessions_are_justified()
    test_committed_sessions_are_justified()
    test_recording_that_starts_on_a_flying_lap_keeps_it()
    test_recording_that_starts_in_the_pits_drops_it()
    test_auditor_detects_the_bug_that_happened()
    print(f"\n{_passed}/{_passed + _failed} assertions passed")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
