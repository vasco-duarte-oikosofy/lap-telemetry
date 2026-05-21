#!/usr/bin/env python3
"""Test JS pipeline contract: delta_t, speed grids, and smoothDt match web UI."""
from __future__ import annotations

import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "product" / "python"))

from lap_telemetry.coach.js_pipeline import run_js_pipeline, delta_t_ms_to_seconds


pass_count = 0
fail_count = 0


def ok(condition: bool, label: str) -> None:
    global pass_count, fail_count
    if condition:
        pass_count += 1
        print(f"  [PASS] {label}")
    else:
        fail_count += 1
        print(f"  [FAIL] {label}")


def _load_fixture_tables():
    current_lap = ROOT / "dev" / "fixtures" / "coach" / "barcelona_lap15_current.parquet"
    reference_lap = ROOT / "product" / "data" / "reference-laps" / "circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.456.parquet"
    if not current_lap.exists():
        return None, None
    return pq.read_table(current_lap), pq.read_table(reference_lap)


def _run_default_pipeline():
    current_table, ref_table = _load_fixture_tables()
    if current_table is None:
        return None
    return run_js_pipeline(
        driver_lap_time_s=current_table.column("lap_time_s").to_pylist(),
        driver_lap_distance_m=current_table.column("lap_distance_m").to_pylist(),
        driver_speed_kph=current_table.column("speed_kph").to_pylist(),
        ref_lap_time_s=ref_table.column("lap_time_s").to_pylist(),
        ref_lap_distance_m=ref_table.column("lap_distance_m").to_pylist(),
        ref_speed_kph=ref_table.column("speed_kph").to_pylist(),
        track_length=4680,
    )


def test_js_pipeline_delta_t_matches_web_ui() -> None:
    """JS pipeline delta_t at key distances matches user-confirmed web UI values."""
    result = _run_default_pipeline()
    if result is None:
        print("  SKIP: JS pipeline contract (fixture not found)")
        return

    dt_ms = result["delta_t_ms"]
    ok(abs(dt_ms[2158] - 436) < 0.5,
       f"delta_t[2158] = {dt_ms[2158]:.1f} ms, expected ~436 ms (web UI confirmed)")
    ok(abs(dt_ms[2439] - 331) < 0.5,
       f"delta_t[2439] = {dt_ms[2439]:.1f} ms, expected ~331 ms (web UI confirmed)")
    ok(abs(dt_ms[-1] - 1155) < 1.0,
       f"delta_t[-1] = {dt_ms[-1]:.1f} ms, expected ~1155 ms (lap_time_delta = 1.155 s)")


def test_js_pipeline_speed_matches_web_ui() -> None:
    """JS pipeline resampled speed at key distances matches web UI."""
    result = _run_default_pipeline()
    if result is None:
        print("  SKIP: JS pipeline speed contract (fixture not found)")
        return

    driver_speed = result["driver_speed_kph"]
    ref_speed = result["ref_speed_kph"]
    ok(abs(driver_speed[2158] - 92.0) < 1.0,
       f"driver_speed[2158] = {driver_speed[2158]:.1f}, expected ~92 kph")
    ok(abs(ref_speed[2158] - 91.0) < 1.0,
       f"ref_speed[2158] = {ref_speed[2158]:.1f}, expected ~91 kph")

    tl = result["track_length"]
    ok(len(driver_speed) == tl + 1, f"driver_speed len = {len(driver_speed)}, expected {tl + 1}")
    ok(len(ref_speed) == tl + 1, f"ref_speed len = {len(ref_speed)}, expected {tl + 1}")
    ok(len(result["delta_t_ms"]) == tl + 1, f"delta_t len = {len(result['delta_t_ms'])}, expected {tl + 1}")


def test_js_pipeline_smooth_dt_reduces_jitter() -> None:
    """smoothDt attenuates plateau-alignment jitter by ~6x."""
    result = _run_default_pipeline()
    if result is None:
        print("  SKIP: smoothDt jitter test (fixture not found)")
        return

    dt_smoothed_ms = result["delta_t_ms"]
    zone_start, zone_end = 2050, 2250
    max_adjacent_jump = 0
    for i in range(zone_start + 1, min(zone_end, len(dt_smoothed_ms))):
        jump = abs(dt_smoothed_ms[i] - dt_smoothed_ms[i - 1])
        if jump > max_adjacent_jump:
            max_adjacent_jump = jump

    ok(max_adjacent_jump < 10.0,
       f"smoothed adjacent jump max = {max_adjacent_jump:.2f} ms, expected < 10 ms (smoothDt works)")


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    print("═══ JS Pipeline Contract Tests ═══\n")

    test_js_pipeline_delta_t_matches_web_ui()
    test_js_pipeline_speed_matches_web_ui()
    test_js_pipeline_smooth_dt_reduces_jitter()

    total = pass_count + fail_count
    print(f"\n  {pass_count}/{total} assertions passed")
    if fail_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())