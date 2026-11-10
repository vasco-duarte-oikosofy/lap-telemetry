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

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "product" / "python"))

from lap_telemetry.session_laps import (  # noqa: E402
    LapStatus,
    MIN_ELIGIBLE_LAPS,
    classify_laps,
    format_inventory,
    load_session,
)

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


def synth_session(specs: list[dict]) -> pa.Table:
    """Build a session table from per-segment specs.

    Each spec: ``lap_number``, ``duration_s``, ``frames``, optionally
    ``speed_kph`` (float) or ``stop_s`` (stationary time at the end),
    ``covered_m`` (distance reached, default a full lap).

    ``session_time_s - lap_time_s`` is the telemetry lap-start ET, so setting
    one start ET per segment produces the intended ``authoritative_duration``
    (difference between consecutive start ETs).
    """
    lap_number: list[int] = []
    session_time: list[float] = []
    lap_time: list[float] = []
    distance: list[float] = []
    speed: list[float] = []
    valid: list[bool] = []

    start_et = 100.0
    for spec in specs:
        frames = spec["frames"]
        duration = spec["duration_s"]
        covered = spec.get("covered_m", 4000.0)
        stop_s = spec.get("stop_s", 0.0)
        step = duration / max(1, frames)
        for i in range(frames):
            t = i * step
            lap_number.append(spec["lap_number"])
            lap_time.append(t)
            session_time.append(start_et + t)
            distance.append(covered * i / max(1, frames - 1))
            # Stop at the very end of the segment, so the next segment's ET
            # still advances by ``duration``.
            remaining = duration - t
            speed.append(0.0 if remaining <= stop_s else 200.0)
            valid.append(spec.get("valid", True))
        start_et += duration

    return pa.table({
        "lap_number": lap_number,
        "lap_time_s": lap_time,
        "session_time_s": session_time,
        "lap_distance_m": distance,
        "speed_kph": speed,
        "lap_valid": valid,
    })


def by_segment(records) -> dict[int, object]:
    return {r.segment_index: r for r in records}


def test_synthetic_classification() -> None:
    """Each rule produces the intended status on a controlled session."""
    table = synth_session([
        {"lap_number": 0, "duration_s": 150.0, "frames": 7500},                   # out-lap
        {"lap_number": 1, "duration_s": 80.0, "frames": 4000},                   # eligible + clean
        {"lap_number": 2, "duration_s": 81.0, "frames": 4050},                   # eligible + clean
        {"lap_number": 3, "duration_s": 30.0, "frames": 1500},                   # in-lap
        {"lap_number": 0, "duration_s": 140.0, "frames": 7000},                  # restart out-lap
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
    check(len(eligible) == 19, "19 laps are eligible", str(len(eligible)))
    check(len(clean) == 17, "17 of them are clean", str(len(clean)))
    check(len(eligible) >= MIN_ELIGIBLE_LAPS, "the session clears the five-lap gate")
    check(all(x.reason for x in records if x.status != LapStatus.ELIGIBLE),
          "every excluded segment states a reason")
    check(all(79.0 < x.duration_s < 95.0 for x in eligible),
          "eligible lap durations are all flying-lap length")


def test_format_inventory() -> None:
    records = classify_laps(synth_session([
        {"lap_number": 0, "duration_s": 150.0, "frames": 7500},
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
    test_lap_valid_only_when_it_discriminates()
    test_shard_merge()
    test_real_session_inventory()
    test_format_inventory()
    print(f"\n{_passed}/{_passed + _failed} assertions passed")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
