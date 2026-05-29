"""Tests for bug 10c: extract_reference_lap uses authoritative lap duration.

Verifies that _authoritative_duration reads scoring_last_lap_time_s from
the next segment rather than max(lap_time_s) from the current segment.
"""
import sys
from pathlib import Path

import pyarrow as pa
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from extract_reference_lap import _authoritative_duration, _build_segments


def _make_table(
    lap_numbers: list[int],
    lap_times: list[float],
    last_lap_times: list[float | None],
) -> pa.Table:
    return pa.table({
        "lap_number": pa.array(lap_numbers, type=pa.int32()),
        "lap_time_s": pa.array(lap_times, type=pa.float32()),
        "scoring_last_lap_time_s": pa.array(last_lap_times, type=pa.float32()),
    })


def test_authoritative_duration_from_next_segment():
    # Lap 1 rows: lap_time_s max = 71.562; lap 2 rows carry scoring_last_lap_time_s = 71.679
    table = _make_table(
        lap_numbers=[1, 1, 1, 2, 2, 2],
        lap_times=[70.0, 71.0, 71.562, 1.0, 2.0, 3.0],
        last_lap_times=[None, None, None, 71.679, 71.679, 71.679],
    )
    segments = _build_segments(table.column("lap_number").to_pylist())
    result = _authoritative_duration(table, 0, segments)
    assert abs(result - 71.679) < 0.001


def test_fallback_when_column_absent():
    table = pa.table({
        "lap_number": pa.array([1, 1, 1, 2, 2], type=pa.int32()),
        "lap_time_s": pa.array([70.0, 71.0, 71.562, 1.0, 2.0], type=pa.float32()),
    })
    segments = _build_segments(table.column("lap_number").to_pylist())
    result = _authoritative_duration(table, 0, segments)
    assert abs(result - 71.562) < 0.001


def test_fallback_when_lap_invalid():
    # max(lap_time_s) for current lap = 78.883; candidate from next = 71.679 (>1 s diff → discard)
    table = _make_table(
        lap_numbers=[1, 1, 1, 2, 2, 2],
        lap_times=[77.0, 78.0, 78.883, 1.0, 2.0, 3.0],
        last_lap_times=[None, None, None, 71.679, 71.679, 71.679],
    )
    segments = _build_segments(table.column("lap_number").to_pylist())
    result = _authoritative_duration(table, 0, segments)
    assert abs(result - 78.883) < 0.001


def test_fallback_for_last_segment():
    table = _make_table(
        lap_numbers=[1, 1, 1],
        lap_times=[70.0, 71.0, 71.562],
        last_lap_times=[None, None, None],
    )
    segments = _build_segments(table.column("lap_number").to_pylist())
    result = _authoritative_duration(table, 0, segments)
    assert abs(result - 71.562) < 0.001


def test_fallback_when_next_segment_all_none():
    table = _make_table(
        lap_numbers=[1, 1, 2, 2],
        lap_times=[71.0, 71.562, 1.0, 2.0],
        last_lap_times=[None, None, None, None],
    )
    segments = _build_segments(table.column("lap_number").to_pylist())
    result = _authoritative_duration(table, 0, segments)
    assert abs(result - 71.562) < 0.001


@pytest.mark.skipif(
    not Path("sessions/session_20260529T092852Z_bahrain-outer-circuit_lmu.parquet").exists(),
    reason="live session file not present",
)
def test_integration_live_session():
    import pyarrow.parquet as pq
    path = Path("sessions/session_20260529T092852Z_bahrain-outer-circuit_lmu.parquet")
    t = pq.read_table(path)
    segments = _build_segments(t.column("lap_number").to_pylist())

    # Map lap_number -> seg_idx for laps 3, 5, 6
    lap_to_seg = {seg[0]: i for i, seg in enumerate(segments)}

    expected = {3: 71.679, 5: 72.029, 6: 71.900}
    for lap_num, expected_duration in expected.items():
        seg_idx = lap_to_seg[lap_num]
        result = _authoritative_duration(t, seg_idx, segments)
        assert abs(result - expected_duration) < 0.001, (
            f"lap {lap_num}: expected {expected_duration}, got {result}"
        )
