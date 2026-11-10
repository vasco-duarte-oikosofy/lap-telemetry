#!/usr/bin/env python3
"""Session lap inventory tests (slice 01 of the session debrief).

The inventory answers one question: which contiguous segments of this
recording are real flying laps? Everything downstream (per-lap facts,
consistency, the coaching conversation) depends on that answer being right,
so these tests pin the classification rules and the shard merge.

Protocol: prints [PASS]/[FAIL] lines and exits non-zero on any failure.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "product" / "python"))
sys.path.insert(0, str(ROOT / "dev" / "scripts"))

from lap_inventory_audit import synth_session  # noqa: E402

from lap_telemetry.lap_inventory_view import format_inventory  # noqa: E402
from lap_telemetry.session_laps import (  # noqa: E402
    MIN_ELIGIBLE_LAPS,
    LapStatus,
    classify_laps,
)
from lap_telemetry.session_source import load_session  # noqa: E402

REAL_SESSION = (
    ROOT / "dev" / "sessions"
    / "session_20260524T141613Z_paul-ricard---3a_lmu.parquet"
)

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


def by_segment(records) -> dict[int, object]:
    return {r.segment_index: r for r in records}


def test_synthetic_classification() -> None:
    """Each rule produces the intended status on a controlled session."""
    table = synth_session([
        {"lap_number": 0, "duration_s": 150.0, "frames": 7500, "start_speed": 0.2},   # out-lap
        {"lap_number": 1, "duration_s": 80.0, "frames": 4000},                   # eligible + clean
        {"lap_number": 2, "duration_s": 81.0, "frames": 4050},                   # eligible + clean
        {"lap_number": 3, "duration_s": 30.0, "frames": 1500},                   # in-lap
        {"lap_number": 0, "duration_s": 140.0, "frames": 7000, "start_speed": 0.2},  # restart out-lap
        {"lap_number": 1, "duration_s": 100.0, "frames": 5000, "stop_s": 9.0},   # pit-lap (stop)
        {"lap_number": 2, "duration_s": 79.5, "frames": 3975},                   # eligible + clean
        {"lap_number": 3, "duration_s": 120.0, "frames": 100, "covered_m": 500.0},  # incomplete
    ])

    records = classify_laps(table)
    r = by_segment(records)

    check(len(records) == 8, "one record per contiguous segment", str(len(records)))
    check(r[0].status == LapStatus.OUT_LAP, "first segment of the session is an out-lap", r[0].status)
    check(r[4].status == LapStatus.OUT_LAP, "lap_number reset starts a new stint (out-lap)", r[4].status)
    check(r[1].status == LapStatus.ELIGIBLE, "full-speed full-coverage lap is eligible", r[1].status)
    check(r[3].status == LapStatus.IN_LAP, "short duration is an in-lap", r[3].status)
    check(r[5].status == LapStatus.PIT_LAP, "sustained standing still is a pit-lap", r[5].status)
    check(r[7].status == LapStatus.INCOMPLETE, "partial distance coverage is incomplete", r[7].status)
    check(r[7].reason != "", "non-eligible laps carry a reason")
    check(r[1].reason == "", "eligible laps carry no reason")
    check(
        sum(1 for x in records if x.status == LapStatus.ELIGIBLE) == 3,
        "exactly the three flying laps are eligible",
    )
    check(
        [x.segment_index for x in records] == list(range(8)),
        "records are in session order",
    )


def test_clean_flag_uses_fastest_eligible_lap() -> None:
    table = synth_session([
        {"lap_number": 0, "duration_s": 150.0, "frames": 7500},
        {"lap_number": 1, "duration_s": 79.0, "frames": 3950},   # best
        {"lap_number": 2, "duration_s": 80.0, "frames": 4000},   # +1.3% -> clean
        {"lap_number": 3, "duration_s": 85.0, "frames": 4250},   # +7.6% -> not clean
        {"lap_number": 4, "duration_s": 79.5, "frames": 3975},   # +0.6% -> clean
        {"lap_number": 5, "duration_s": 20.0, "frames": 1000, "covered_m": 700.0},
    ])
    r = by_segment(classify_laps(table))
    check(r[1].clean and r[2].clean and r[4].clean, "laps within 5% of the best are clean")
    check(not r[3].clean, "a lap 7.6% off the best is eligible but not clean")
    check(all(x.clean is False for x in r.values() if x.status != LapStatus.ELIGIBLE),
          "non-eligible laps are never clean")


def test_integrity_and_slow_rules() -> None:
    table = synth_session([
        {"lap_number": 0, "duration_s": 150.0, "frames": 7500},
        {"lap_number": 1, "duration_s": 80.0, "frames": 4000},
        {"lap_number": 2, "duration_s": 80.0, "frames": 50},      # frames/duration mismatch
        {"lap_number": 3, "duration_s": 105.0, "frames": 5250},   # 1.31x -> pit-lap
        {"lap_number": 4, "duration_s": 80.0, "frames": 4000},
    ])
    r = by_segment(classify_laps(table))
    check(r[2].status == LapStatus.SHORT, "frame count inconsistent with duration is flagged", r[2].status)
    check(r[3].status == LapStatus.PIT_LAP, "duration above the band is a pit-lap", r[3].status)


def test_stint_boundary_is_a_restart_not_a_gap() -> None:
    """A skipped lap number is not a new stint; a reset to 0 is.

    Real recordings contain stuck/dropped lap numbers (a paused sim leaves
    segment after segment on lap 9), so ``11`` can follow ``9``. Treating that
    as a pit exit discarded good laps; Lusail 2026-09-05 lost its fastest lap
    this way.
    """
    table = synth_session([
        {"lap_number": 9, "duration_s": 115.0, "frames": 1500, "covered_m": 2700.0},
        {"lap_number": 11, "duration_s": 112.6, "frames": 5630},   # gap, not a stint boundary
        {"lap_number": 9, "duration_s": 115.0, "frames": 1500, "covered_m": 2700.0},
        {"lap_number": 13, "duration_s": 111.0, "frames": 5550},  # fastest lap
        {"lap_number": 14, "duration_s": 113.0, "frames": 5650},
        {"lap_number": 15, "duration_s": 20.0, "frames": 1000, "covered_m": 800.0},
    ])
    r = by_segment(classify_laps(table))
    check(r[1].status == LapStatus.ELIGIBLE, "a skipped lap number is not a stint boundary", r[1].status)
    check(r[3].status == LapStatus.ELIGIBLE, "the lap after a gap is eligible", r[3].status)
    check(r[3].clean, "a lap after a gap can still be the reference lap")

    restart = synth_session([
        {"lap_number": 2, "duration_s": 80.0, "frames": 4000},
        {"lap_number": 0, "duration_s": 120.0, "frames": 6000, "start_speed": 0.2},
        {"lap_number": 1, "duration_s": 80.0, "frames": 4000},
    ])
    rr = by_segment(classify_laps(restart))
    check(rr[1].status == LapStatus.OUT_LAP, "a reset to lap 0 starts a new stint", rr[1].status)


def test_lap_valid_only_when_it_discriminates() -> None:
    specs = [
        {"lap_number": 0, "duration_s": 150.0, "frames": 7500},
        {"lap_number": 1, "duration_s": 80.0, "frames": 4000, "valid": False},
        {"lap_number": 2, "duration_s": 80.5, "frames": 4025},
        {"lap_number": 3, "duration_s": 81.0, "frames": 4050},
    ]
    r = by_segment(classify_laps(synth_session(specs)))
    check(r[1].status == LapStatus.INVALID, "an invalid frame inside the lap marks it invalid", r[1].status)

    # A constant column is treated as unreliable and ignored.
    all_true = [dict(s, valid=True) for s in specs]
    r_true = by_segment(classify_laps(synth_session(all_true)))
    check(r_true[1].status == LapStatus.ELIGIBLE,
          "a constant lap_valid column is ignored, not trusted", r_true[1].status)
    check(r_true[1].valid_flag is None, "unreliable validity is reported as unknown",
          str(r_true[1].valid_flag))


def test_shard_merge() -> None:
    """Shards are merged in numeric part order, in memory, with the sidecar."""
    base = "session_20260101T000000Z_test-track_lmu"
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        first = synth_session([
            {"lap_number": 0, "duration_s": 150.0, "frames": 7500},
            {"lap_number": 1, "duration_s": 80.0, "frames": 4000},
        ])
        second = synth_session([
            {"lap_number": 2, "duration_s": 80.5, "frames": 4025},
            {"lap_number": 3, "duration_s": 81.0, "frames": 4050},
        ])
        pq.write_table(first, tmp_path / f"{base}.part0.parquet")
        pq.write_table(second, tmp_path / f"{base}.part1.parquet")
        (tmp_path / f"{base}.json").write_text(
            json.dumps({"track": "Test Track", "vehicle_name": "Test Car",
                        "sample_rate_hz": 50.0, "started_utc": "2026-01-01T00:00:00Z"}),
            encoding="utf-8",
        )

        session = load_session(tmp_path / f"{base}.part1.parquet")

        check(len(session.shards) == 2, "both shards found from any part path", str(len(session.shards)))
        check(session.table.num_rows == 7500 + 4000 + 4025 + 4050,
              "merged row count is the sum of the shards", str(session.table.num_rows))
        check(session.track == "Test Track", "sidecar track is exposed", session.track)
        check(session.vehicle_name == "Test Car", "sidecar vehicle is exposed", session.vehicle_name)
        laps = classify_laps(session.table)
        check([x.segment_index for x in laps] == list(range(4)),
              "merged shards are classified as one continuous session")
        check(laps[-1].status == LapStatus.INCOMPLETE,
              "the last segment of the merged shard view is incomplete", laps[-1].status)


def test_real_session_inventory() -> None:
    """The Paul Ricard practice session is the canonical 25-segment fixture."""
    if not REAL_SESSION.exists():
        check(False, "Paul Ricard fixture present", str(REAL_SESSION))
        return

    session = load_session(REAL_SESSION)
    records = classify_laps(session.table)
    r = by_segment(records)

    check(len(records) == 25, "fixture has 25 contiguous segments", str(len(records)))
    check(records[0].status == LapStatus.OUT_LAP, "segment 0 is the out-lap", records[0].status)
    check(records[-1].status == LapStatus.INCOMPLETE, "the final segment is incomplete", records[-1].status)

    in_lap = [x for x in records if x.status == LapStatus.IN_LAP]
    check(len(in_lap) == 1 and abs(in_lap[0].duration_s - 21.917) < 0.01,
          "the 21.9 s segment is the only in-lap",
          str([(x.segment_index, round(x.duration_s, 3)) for x in in_lap]))

    pit_laps = [x for x in records if x.status == LapStatus.PIT_LAP]
    check(len(pit_laps) == 1 and abs(pit_laps[0].duration_s - 119.104) < 0.01,
          "the 119.1 s segment with a stop is the only pit-lap",
          str([(x.segment_index, round(x.duration_s, 3)) for x in pit_laps]))

    eligible = [x for x in records if x.status == LapStatus.ELIGIBLE]
    clean = [x for x in eligible if x.clean]
    check(len(eligible) == 18, "18 laps are eligible", str(len(eligible)))
    check(len(clean) == 16, "16 of them are clean", str(len(clean)))
    check(len(eligible) >= MIN_ELIGIBLE_LAPS, "the session clears the five-lap gate")
    check(all(x.reason for x in records if x.status != LapStatus.ELIGIBLE),
          "every excluded segment states a reason")
    check(all(79.0 < x.duration_s < 95.0 for x in eligible),
          "eligible lap durations are all flying-lap length")
    dup = [x for x in records if x.status == LapStatus.SHORT]
    check(len(dup) == 1 and dup[0].segment_index == 2,
          "a lap with duplicated rows is rejected as short",
          str([(x.segment_index, x.reason) for x in dup]))


def test_real_lusail_stuck_lap_number() -> None:
    """Regression: stuck lap numbers must not manufacture pit exits.

    This recording keeps emitting fragments of lap 9 after a pause, so the
    sequence runs 9, 11, 9, 13, 9, 15, 16, 9, 10. Treating every non-consecutive
    lap number as a stint boundary threw away segments 1 and 4, and segment 4
    (1:52.620) was the fastest lap of the session — faster than the lap the
    coach would have kept. Only a reset to lap 0 may start a stint.
    """
    session_path = (
        ROOT / "dev" / "sessions"
        / "session_20260905T065812Z_lusail-international-circuit_lmu_practice.parquet"
    )
    if not session_path.exists():
        check(False, "Lusail fixture present", str(session_path))
        return

    session = load_session(session_path)
    records = classify_laps(session.table, sample_rate_hz=session.sample_rate_hz)
    r = by_segment(records)

    check(len(records) == 11, "fixture has 11 contiguous segments", str(len(records)))
    check(r[1].status == LapStatus.ELIGIBLE,
          "11 after a stuck 9 is a continued stint, not an out-lap", r[1].status)
    check(r[4].status == LapStatus.ELIGIBLE,
          "13 after a stuck 9 is a continued stint, not an out-lap", r[4].status)

    eligible = [x for x in records if x.eligible]
    fastest = min(eligible, key=lambda x: x.duration_s)
    check(fastest.segment_index == 5 and abs(fastest.duration_s - 111.975) < 0.01,
          "the fastest lap of the session is the 1:51.975", 
          f"segment {fastest.segment_index} at {fastest.duration_s:.3f} s")
    check(r[4].duration_s - fastest.duration_s < 1.0,
          "the lap the old rule discarded (1:52.620) is within a second of the best",
          f"segment 4 at {r[4].duration_s:.3f} s")
    check(len(eligible) == 4, "four laps are eligible after the fix", str(len(eligible)))
    check(sum(1 for x in eligible if x.clean) == 3, "three of them are clean")

    check([x for x in records if x.status == LapStatus.OUT_LAP] == [],
          "a session with no lap-0 reset reports no out-laps")
    stuck = [x for x in records if x.lap_number == 9]
    check(len(stuck) == 4 and all(x.status == LapStatus.INCOMPLETE for x in stuck),
          "every stuck lap-9 fragment is incomplete",
          str([(x.segment_index, x.status) for x in stuck]))
    check(all(x.status != LapStatus.OUT_LAP or x.lap_number == 0 for x in records),
          "invariant: only a lap-0 reset can be an out-lap")


def test_out_lap_needs_a_pit_exit() -> None:
    """A stint boundary is only an out-lap if the car entered from the pits.

    Recording can start with the car already on a flying lap. That segment 0
    passes coverage and duration, so calling it an out-lap discards a real lap
    purely because of where the recording began.
    """
    slow_start = classify_laps(synth_session([
        {"lap_number": 0, "duration_s": 150.0, "frames": 7500, "start_speed": 0.2},
        {"lap_number": 1, "duration_s": 80.0, "frames": 4000},
        {"lap_number": 2, "duration_s": 20.0, "frames": 1000, "covered_m": 700.0},
    ]))
    check(by_segment(slow_start)[0].status == LapStatus.OUT_LAP,
          "segment 0 entered from the pits is an out-lap", slow_start[0].status)

    racing_start = classify_laps(synth_session([
        {"lap_number": 0, "duration_s": 80.5, "frames": 4025, "start_speed": 210.0},
        {"lap_number": 1, "duration_s": 80.0, "frames": 4000},
        {"lap_number": 2, "duration_s": 20.0, "frames": 1000, "covered_m": 700.0},
    ]))
    check(by_segment(racing_start)[0].status == LapStatus.ELIGIBLE,
          "segment 0 started on a flying lap is kept", racing_start[0].status)
    check(by_segment(racing_start)[0].clean,
          "the recovered lap participates in the clean set")

    reset_at_speed = classify_laps(synth_session([
        {"lap_number": 2, "duration_s": 80.0, "frames": 4000},
        {"lap_number": 0, "duration_s": 80.2, "frames": 4010, "start_speed": 205.0},
        {"lap_number": 1, "duration_s": 20.0, "frames": 1000, "covered_m": 700.0},
    ]))
    check(by_segment(reset_at_speed)[1].status == LapStatus.ELIGIBLE,
          "a lap-0 reset at racing speed is not a pit exit", reset_at_speed[1].status)

    # Without speed/session-time channels the rule falls back to the lap number.
    table = synth_session([
        {"lap_number": 0, "duration_s": 150.0, "frames": 7500},
        {"lap_number": 1, "duration_s": 80.0, "frames": 4000},
        {"lap_number": 2, "duration_s": 20.0, "frames": 1000, "covered_m": 700.0},
    ]).drop_columns(["speed_kph"])
    check(classify_laps(table)[0].status == LapStatus.OUT_LAP,
          "without speed data the lap-number fallback still applies")


def test_format_inventory() -> None:
    records = classify_laps(synth_session([
        {"lap_number": 0, "duration_s": 150.0, "frames": 7500, "start_speed": 0.2},
        {"lap_number": 1, "duration_s": 80.0, "frames": 4000},
        {"lap_number": 2, "duration_s": 120.0, "frames": 100, "covered_m": 500.0},
    ]))
    text = format_inventory(
        records,
        {"track": "Test Track", "vehicle_name": "Test Car", "sample_rate_hz": 50.0,
         "stem": "session_test"},
        shard_count=2,
    )
    check("Test Track" in text and "Test Car" in text, "inventory names the track and car")
    check("shards  : 2" in text, "inventory reports the shard count", text.splitlines()[3])
    check(LapStatus.OUT_LAP in text and LapStatus.ELIGIBLE in text,
          "every segment appears with its status")
    check("1 of 3 segments eligible" in text, "inventory summarises eligible vs total")
    check(f"at least {MIN_ELIGIBLE_LAPS}" in text, "inventory warns below the five-lap gate")

    healthy = classify_laps(synth_session(
        [{"lap_number": 0, "duration_s": 150.0, "frames": 7500}]
        + [{"lap_number": i + 1, "duration_s": 80.0, "frames": 4000} for i in range(6)]
    ))
    healthy_text = format_inventory(healthy, {"track": "T", "vehicle_name": "C"}, shard_count=1)
    check(f"at least {MIN_ELIGIBLE_LAPS}" not in healthy_text,
          "no gate warning when enough laps are eligible")


def main() -> int:
    print("═══ Session lap inventory tests ═══\n")
    test_synthetic_classification()
    test_clean_flag_uses_fastest_eligible_lap()
    test_integrity_and_slow_rules()
    test_stint_boundary_is_a_restart_not_a_gap()
    test_out_lap_needs_a_pit_exit()
    test_lap_valid_only_when_it_discriminates()
    test_shard_merge()
    test_real_session_inventory()
    test_real_lusail_stuck_lap_number()
    test_format_inventory()
    print(f"\n{_passed}/{_passed + _failed} assertions passed")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
