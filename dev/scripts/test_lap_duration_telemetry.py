#!/usr/bin/env python3
"""Regression tests for authoritative lap duration via the telemetry clock.

TinyPedal derives a lap's duration from consecutive telemetry lap-start ETs
(``lmuTeleVeh.mLapStartET``), not from the scorer's ``mLastLapTime``. Our
recorder stores ``session_time_s - lap_time_s == telemetry mLapStartET``, so
the same value is recoverable from our parquet.

These tests cover:
  * synthetic two-segment table where the scorer value is stale/wrong;
  * the real Road Atlanta session (lap 15 must be 1:16.809, not 1:17.345);
  * the real Paul Ricard quali session (lap 4 must be 1:36.804);
  * an explicit ``authoritative_lap_time_s`` parquet metadata override.

Protocol: prints [PASS]/[FAIL] lines and exits non-zero on any failure.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "product" / "python"))

from lap_telemetry.parquet_utils import authoritative_duration, build_segments  # noqa: E402

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


def synth_table(rows: list[dict]) -> pa.Table:
    return pa.table({k: pa.array([r.get(k) for r in rows]) for k in rows[0].keys()})


def test_synthetic_telemetry_preferred_over_scorer() -> None:
    # lap 5: telemetry lap start = 100.0 (session - lap_time = 100 everywhere).
    # lap 6: telemetry lap start = 120.5 -> true lap 5 duration = 20.5.
    # scoring_last_lap_time_s in lap 6 is a stale 21.0 (previous lap) to prove
    # the telemetry clock wins.
    rows = []
    for sess, lap_t, last in [(100.0, 0.0, 0.0), (110.0, 10.0, 0.0), (120.0, 20.0, 0.0)]:
        rows.append(dict(lap_number=5, lap_time_s=lap_t, session_time_s=sess,
                         scoring_last_lap_time_s=last, lap_distance_m=lap_t * 50))
    for sess, lap_t, last in [(120.5, 0.0, 21.0), (130.5, 10.0, 21.0)]:
        rows.append(dict(lap_number=6, lap_time_s=lap_t, session_time_s=sess,
                         scoring_last_lap_time_s=last, lap_distance_m=lap_t * 50))
    t = synth_table(rows)
    segs = build_segments(t.column("lap_number").to_pylist())
    dur = authoritative_duration(t, segs[0][1], segs[0][2], segs[1][1], segs[1][2])
    check(abs(dur - 20.5) < 1e-9, "telemetry lap-start diff wins over stale scorer", f"{dur}")


def test_real_road_atlanta_lap15() -> None:
    session = ROOT / "sessions" / "session_20261004T133118Z_michelin-raceway-road-atlanta_lmu_practice.parquet"
    if not session.exists():
        check(False, "Road Atlanta session present", str(session))
        return
    t = pq.read_table(session, columns=["lap_number", "lap_time_s", "session_time_s", "scoring_last_lap_time_s"])
    segs = build_segments(t.column("lap_number").to_pylist())
    target = next((s for s in segs if s[0] == 15), None)
    nxt = next((s for s in segs if s[0] == 16), None)
    check(target is not None and nxt is not None, "Road Atlanta has lap 15 + 16 segments")
    dur = authoritative_duration(t, target[1], target[2], nxt[1], nxt[2])
    check(abs(dur - 76.809) < 0.01, "Road Atlanta lap 15 = 1:16.809 (TinyPedal value)", f"{dur:.3f}")


def test_real_paul_ricard_quali_lap4() -> None:
    session = ROOT / "sessions" / "session_20260920T055844Z_paul-ricard---1a-v2-short_lmu_quali.parquet"
    if not session.exists():
        check(False, "Paul Ricard quali session present", str(session))
        return
    t = pq.read_table(session, columns=["lap_number", "lap_time_s", "session_time_s", "scoring_last_lap_time_s"])
    segs = build_segments(t.column("lap_number").to_pylist())
    target = next((s for s in segs if s[0] == 4), None)
    nxt = next((s for s in segs if s[0] == 5), None)
    check(target is not None and nxt is not None, "Paul Ricard has lap 4 + 5 segments")
    dur = authoritative_duration(t, target[1], target[2], nxt[1], nxt[2])
    check(abs(dur - 96.804) < 0.01, "Paul Ricard lap 4 = 1:36.804", f"{dur:.3f}")


def test_metadata_override() -> None:
    t = synth_table([dict(lap_number=1, lap_time_s=10.0, session_time_s=110.0, lap_distance_m=500.0)])
    meta = dict(t.schema.metadata or {})
    meta[b"authoritative_lap_time_s"] = b"76.809"
    t = t.replace_schema_metadata(meta)
    dur = authoritative_duration(t, 0, t.num_rows)
    check(abs(dur - 76.809) < 1e-9, "explicit metadata override used for single-segment refs", f"{dur}")


def main() -> int:
    print("═══ Lap duration (telemetry clock) tests ═══\n")
    test_synthetic_telemetry_preferred_over_scorer()
    test_real_road_atlanta_lap15()
    test_real_paul_ricard_quali_lap4()
    test_metadata_override()
    print(f"\n{_passed}/{_passed + _failed} assertions passed")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
