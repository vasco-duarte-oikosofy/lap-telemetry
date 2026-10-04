#!/usr/bin/env python3
"""Bug 28 surface tests: the telemetry lap-start clock across every product surface.

Covers the recorder output contract, the Python summary pipeline, the guarded
reference export, the coaching comparator, and the extracted reference file.
The web (`dist/compare.html`) surface is covered by
`dev/scripts/test_compare_reference_duration.js` (Playwright).

Protocol: prints [PASS]/[FAIL] lines and exits non-zero on any failure.
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "product" / "python"))
sys.path.insert(0, str(ROOT / "dev" / "scripts"))

from lap_telemetry.parquet_utils import authoritative_duration, build_segments  # noqa: E402
from lap_telemetry import summary  # noqa: E402
from lap_telemetry.coach.lap_comparator import compare_laps  # noqa: E402
from lap_telemetry.coach.track_model import load_track_coaching_model  # noqa: E402
from export_fastest_reference_laps import find_complete_laps, parse_lap_time_from_name  # noqa: E402
from extract_reference_lap import _with_authoritative_metadata  # noqa: E402

RACE = ROOT / "sessions" / "session_20261004T164430Z_michelin-raceway-road-atlanta_lmu_race.parquet"
PRACTICE_TRUNCATED = ROOT / "sessions" / "session_20261004T155735Z_michelin-raceway-road-atlanta_lmu_practice.parquet"
REF = ROOT / "product" / "data" / "reference-laps" / "michelin-raceway-road-atlanta_dkr-engineering-4-elms25_time_01.16.304.parquet"
MODEL = ROOT / "product" / "data" / "track-coaching" / "michelin-raceway-road-atlanta_dkr-engineering-4-elms25.json"

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


def test_recorder_output_contract() -> None:
    """The recorder stores session_time_s - lap_time_s == mLapStartET, which
    must be constant within a completed lap for the clock to be recoverable."""
    if not RACE.exists():
        check(False, "race session present", str(RACE))
        return
    t = pq.read_table(RACE, columns=["lap_number", "lap_time_s", "session_time_s"])
    lap = t.column("lap_number").to_pylist()
    lt = t.column("lap_time_s").to_pylist()
    st = t.column("session_time_s").to_pylist()
    worst, worst_lap = 0.0, None
    for lap_num, s, e in build_segments(lap):
        if lap_num is None or lap_num < 1:
            continue
        vals = [st[i] - lt[i] for i in range(s, e)
                if st[i] is not None and lt[i] is not None and lt[i] > 0]
        if len(vals) < 20:
            continue
        spread = max(vals) - min(vals)
        if spread > worst:
            worst, worst_lap = spread, lap_num
    check(worst < 0.01, "recorder lap-start ET constant within each completed lap",
          f"max spread {worst:.6f}s (lap {worst_lap})")


def test_summary_pipeline() -> None:
    if not RACE.exists():
        check(False, "race session present", str(RACE))
        return
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = summary.run(RACE)
    out = buf.getvalue()
    check(rc == 0, "summary.run exits 0")
    check("1:16.304" in out, "summary prints race lap 15 as 1:16.304")


def test_export_selection() -> None:
    if not RACE.exists():
        check(False, "race session present", str(RACE))
        return
    best = min(find_complete_laps(pq.read_table(RACE)), key=lambda c: c[1])
    check(best[0] == 15 and abs(best[1] - 76.304) < 0.001,
          "export selects race lap 15 @ 76.304", f"lap {best[0]} @ {best[1]:.3f}")

    if PRACTICE_TRUNCATED.exists():
        cands = find_complete_laps(pq.read_table(PRACTICE_TRUNCATED))
        closest = min((abs(c[1] - 75.994) for c in cands), default=999)
        check(closest > 0.01, "restart-truncated 1:15.994 lap is rejected by the guards",
              f"closest candidate is {closest:.3f}s away")


def test_coach_surface() -> None:
    if not (RACE.exists() and REF.exists() and MODEL.exists()):
        check(False, "coach inputs present")
        return
    model = load_track_coaching_model(MODEL)
    facts = compare_laps(RACE, REF, model, top_n=1, lap_number=21)
    # race lap 21 = 76.417s, reference lap 15 = 76.304s => +0.113s
    check(abs(facts.lap_time_delta_s - 0.113) < 0.02,
          "coach delta uses the telemetry clock (lap 21 vs ref = +0.113s)",
          f"{facts.lap_time_delta_s:+.3f}s")


def test_reference_file() -> None:
    if not REF.exists():
        check(False, "reference file present", str(REF))
        return
    t = pq.read_table(REF)
    check(abs(authoritative_duration(t, 0, t.num_rows) - 76.304) < 0.001,
          "reference metadata authoritative_lap_time_s = 76.304")
    check(parse_lap_time_from_name(REF) == 76.304, "reference filename encodes 01.16.304")


def test_manual_extract_stamps_metadata() -> None:
    t = pa.table({"lap_time_s": pa.array([10.0, 20.0, 76.722])})
    out = _with_authoritative_metadata(t, 76.304)
    meta = out.schema.metadata or {}
    check(b"authoritative_lap_time_s" in meta, "manual extract stamps authoritative metadata")
    check(abs(authoritative_duration(out, 0, out.num_rows) - 76.304) < 1e-9,
          "stamped metadata wins over max(lap_time_s) for single-segment files")


def main() -> int:
    print("═══ Bug 28 surface tests (telemetry lap clock) ═══\n")
    test_recorder_output_contract()
    test_summary_pipeline()
    test_export_selection()
    test_coach_surface()
    test_reference_file()
    test_manual_extract_stamps_metadata()
    print(f"\n{_passed}/{_passed + _failed} assertions passed")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
