#!/usr/bin/env python3
"""Test delta-time gains for minimum_speed, entry, and exit phases."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "product" / "python"))

from lap_telemetry.coach.entry_detection import find_entry_point
from lap_telemetry.coach.lap_comparator import (
    PhaseDetectionThresholds,
    compute_minimum_speed_per_corner,
    compute_delta_time_trace,
    find_straight_end_after_corner,
    compare_laps,
)
from lap_telemetry.coach.track_model import Corner


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


# ── Delta-time trace tests ─────────────────────────────────────────────────


def test_delta_time_trace_basic() -> None:
    """Delta-time: driver slower everywhere -> trace ends positive (behind)."""
    n = 100
    driver_lap_time = [0.0 + i * 0.036 for i in range(n)]
    ref_lap_time = [0.0 + i * 0.018 for i in range(n)]

    delta_t = compute_delta_time_trace(driver_lap_time, ref_lap_time, n)

    ok(len(delta_t) == n, f"delta_t length = {len(delta_t)}, expected {n}")
    ok(delta_t[-1] > 0, f"delta_t[-1] = {delta_t[-1]:.4f}, expected positive (driver slower)")
    ok(delta_t[50] > delta_t[0], f"delta_t[50] = {delta_t[50]:.4f} > delta_t[0] = {delta_t[0]:.4f}")


def test_delta_time_trace_faster_driver() -> None:
    """Delta-time: driver faster everywhere -> trace ends negative (ahead)."""
    n = 100
    driver_lap_time = [0.0 + i * 0.018 for i in range(n)]
    ref_lap_time = [0.0 + i * 0.036 for i in range(n)]

    delta_t = compute_delta_time_trace(driver_lap_time, ref_lap_time, n)

    ok(len(delta_t) == n, f"delta_t length = {len(delta_t)}, expected {n}")
    ok(delta_t[-1] < 0, f"delta_t[-1] = {delta_t[-1]:.4f}, expected negative (driver faster)")


def test_delta_time_trace_equal_times() -> None:
    """Delta-time: identical times -> all deltas zero."""
    n = 100
    lap_time = [0.0 + i * 0.018 for i in range(n)]

    delta_t = compute_delta_time_trace(lap_time, lap_time, n)

    ok(delta_t[-1] == 0.0, f"delta_t[-1] = {delta_t[-1]:.6f}, expected 0")


def test_delta_time_trace_matches_lap_time() -> None:
    """Delta-time trace final value equals the lap time delta."""
    n = 1000
    driver_lap_time = [i * 0.036 for i in range(n)]
    ref_lap_time = [i * 0.032727 for i in range(n)]

    delta_t = compute_delta_time_trace(driver_lap_time, ref_lap_time, n)

    expected_delta = driver_lap_time[-1] - ref_lap_time[-1]
    ok(abs(delta_t[-1] - expected_delta) < 0.001,
       f"delta_t[-1] = {delta_t[-1]:.4f}, expected {expected_delta:.4f}")


def test_find_straight_end_middle_corner() -> None:
    """Straight end after a middle corner is entry of next corner."""
    corners = [
        Corner(id="t1", name="turn 1", s_start_m=900, apex_s_m=1000, s_end_m=1100, apex_side="right"),
        Corner(id="t2", name="turn 2", s_start_m=1400, apex_s_m=1500, s_end_m=1600, apex_side="right"),
    ]
    n = 2000
    speed = [200.0] * n
    throttle = [1.0] * n
    throttle[1350] = 0.5

    end = find_straight_end_after_corner(0, corners, speed, throttle, None, PhaseDetectionThresholds(), n)
    ok(end == 1350, f"straight end after t1 = {end}, expected 1350 (entry of t2)")


def test_find_straight_end_last_corner() -> None:
    """Straight end after last corner = end of lap."""
    corners = [
        Corner(id="t1", name="turn 1", s_start_m=900, apex_s_m=1000, s_end_m=1100, apex_side="right"),
    ]
    n = 1500
    speed = [200.0] * n

    end = find_straight_end_after_corner(0, corners, speed, None, None, PhaseDetectionThresholds(), n)
    ok(end == n - 1, f"straight end after last corner = {end}, expected {n - 1}")


# ── Minimum speed gain/loss ─────────────────────────────────────────────────


def test_minimum_speed_gain_uses_delta_time() -> None:
    """Minimum speed gains use delta-time from apex to end of straight."""
    n = 5000
    driver_speed = [200.0] * n
    ref_speed = [200.0] * n

    for i in range(900, 1100):
        ref_speed[i] = 95.0 + (i - 900) * 0.05
    ref_speed[950] = 100.0
    for i in range(900, 1100):
        driver_speed[i] = 105.0 + (i - 900) * 0.05
    driver_speed[950] = 110.0

    driver_throttle = [1.0] * n
    for i in range(1350, 1500):
        driver_throttle[i] = 0.5
        driver_speed[i] = 180.0
    for i in range(1400, 1500):
        ref_speed[i] = 180.0

    corners = [
        Corner(id="t1", name="turn 1", s_start_m=900, apex_s_m=1000, s_end_m=1100, apex_side="right"),
        Corner(id="t2", name="turn 2", s_start_m=1400, apex_s_m=1500, s_end_m=1600, apex_side="right"),
    ]

    driver_lap_time = [0.0] * n
    ref_lap_time = [0.0] * n
    for i in range(1, n):
        driver_lap_time[i] = driver_lap_time[i - 1] + 1.0 / max(driver_speed[i] / 3.6, 0.28)
        ref_lap_time[i] = ref_lap_time[i - 1] + 1.0 / max(ref_speed[i] / 3.6, 0.28)

    delta_t = compute_delta_time_trace(driver_lap_time, ref_lap_time, n)

    ok(delta_t[950] < 0, f"delta_t at apex = {delta_t[950]:.6f}, expected negative (driver ahead)")

    driver_min, ref_min, speed_delta, driver_apex_m, ref_apex_m = compute_minimum_speed_per_corner(
        driver_speed, ref_speed, corners[0]
    )
    ok(speed_delta < 0, f"speed_delta = {speed_delta:.1f}, expected negative (driver faster)")
    ok(driver_min > ref_min, f"driver_min = {driver_min:.1f} > ref_min = {ref_min:.1f}")

    straight_end = find_straight_end_after_corner(
        0, corners, driver_speed, driver_throttle, None, PhaseDetectionThresholds(), n
    )
    ok(straight_end == 1350, f"straight end = {straight_end}, expected 1350")

    gain_s = delta_t[straight_end] - delta_t[int(driver_apex_m)]
    ok(gain_s < 0, f"gain_s = {gain_s:.6f}, expected negative (driver gained time)")


def test_minimum_speed_loss_unchanged() -> None:
    """Minimum speed losses still use the speed_delta / 100 heuristic."""
    n = 1200
    driver_speed = [200.0] * n
    ref_speed = [200.0] * n

    for i in range(900, 1100):
        driver_speed[i] = 90.0 + (i - 900) * 0.05
    driver_speed[950] = 95.0
    for i in range(900, 1100):
        ref_speed[i] = 100.0 + (i - 900) * 0.05
    ref_speed[950] = 105.0

    corner = Corner(id="t1", name="turn 1", s_start_m=900, apex_s_m=1000, s_end_m=1100, apex_side="right")

    driver_min, ref_min, speed_delta, driver_apex_m, ref_apex_m = compute_minimum_speed_per_corner(
        driver_speed, ref_speed, corner
    )
    ok(speed_delta > 0, f"speed_delta = {speed_delta:.1f}, expected positive (ref faster)")
    expected_loss_s = speed_delta / 100.0
    ok(expected_loss_s > 0, f"expected_loss_s = {expected_loss_s:.4f}, expected positive")


# ── Entry gain/loss ──────────────────────────────────────────────────────────


def test_entry_gain_uses_delta_time() -> None:
    """Entry gains use delta_t[apex] - delta_t[entry] instead of speed_delta/100."""
    n = 5000
    driver_speed = [200.0] * n
    ref_speed = [200.0] * n

    driver_throttle = [1.0] * 880 + [0.5] * (n - 880)

    for i in range(880, 1000):
        driver_speed[i] = 250.0 - (i - 880) * 0.5
    driver_speed[950] = 180.0
    for i in range(1000, 1100):
        driver_speed[i] = 180.0 + (i - 1000) * 0.2

    for i in range(850, 1000):
        ref_speed[i] = 240.0 - (i - 850) * 0.5
    ref_speed[950] = 175.0
    for i in range(1000, 1100):
        ref_speed[i] = 175.0 + (i - 1000) * 0.2

    corners = [
        Corner(id="t1", name="turn 1", s_start_m=900, apex_s_m=1000, s_end_m=1100, apex_side="right"),
    ]

    driver_lap_time = [0.0] * n
    ref_lap_time = [0.0] * n
    for i in range(1, n):
        driver_lap_time[i] = driver_lap_time[i - 1] + 1.0 / max(driver_speed[i] / 3.6, 0.28)
        ref_lap_time[i] = ref_lap_time[i - 1] + 1.0 / max(ref_speed[i] / 3.6, 0.28)

    delta_t = compute_delta_time_trace(driver_lap_time, ref_lap_time, n)

    entry_idx, method = find_entry_point(driver_speed, driver_throttle, None, corners[0], PhaseDetectionThresholds())
    ok(method == "throttle_lift", f"entry method = {method}, expected throttle_lift")
    ok(entry_idx == 880, f"entry at {entry_idx}, expected 880")

    entry_delta = ref_speed[entry_idx] - driver_speed[entry_idx]
    ok(entry_delta < 0, f"entry_delta = {entry_delta:.1f}, expected negative (driver faster at entry)")

    apex_idx = int(corners[0].apex_s_m)
    expected_gain = delta_t[apex_idx] - delta_t[entry_idx]
    heuristic_value = entry_delta / 100.0

    ok(expected_gain < heuristic_value,
       f"delta-time gain ({expected_gain:.6f}) should be more negative than heuristic ({heuristic_value:.6f})")
    ok(expected_gain < 0, f"expected_gain = {expected_gain:.6f}, expected negative (driver gained time)")
    ok(float(apex_idx) == float(corners[0].apex_s_m),
       f"apex_idx {apex_idx} should equal corner.apex_s_m {corners[0].apex_s_m}")


def test_entry_loss_unchanged() -> None:
    """Entry losses still use the speed_delta / 100 heuristic."""
    n = 1200
    driver_speed = [200.0] * n
    ref_speed = [200.0] * n

    driver_speed[880] = 190.0
    ref_speed[880] = 250.0

    corner = Corner(id="t1", name="turn 1", s_start_m=900, apex_s_m=1000, s_end_m=1100, apex_side="right")

    entry_delta = ref_speed[880] - driver_speed[880]
    ok(entry_delta > 0, f"entry_delta = {entry_delta:.1f}, expected positive (driver slower)")
    ok(entry_delta / 100.0 > 0, f"expected_loss_s = {entry_delta / 100.0:.4f}, expected positive")


# ── Fixture-based gain tests ─────────────────────────────────────────────────


def test_apex_offset_in_comparison() -> None:
    """Full comparison includes apex_offset_m on minimum_speed phases."""
    current_lap = ROOT / "dev" / "fixtures" / "coach" / "barcelona_lap15_current.parquet"
    reference_lap = ROOT / "product" / "data" / "reference-laps" / "circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.456.parquet"
    track_model = ROOT / "product" / "data" / "track-coaching" / "circuit-de-barcelona_dkr-engineering-4-elms25.json"

    if not current_lap.exists():
        print("  SKIP: apex offset comparison (fixture not found)")
        return

    from lap_telemetry.coach.track_model import load_track_coaching_model
    model = load_track_coaching_model(track_model)
    facts = compare_laps(current_lap, reference_lap, model)

    for loss in facts.top_losses + facts.top_gains:
        if loss.phase == "minimum_speed":
            ok(loss.apex_offset_m is not None,
               f"{loss.corner_id} minimum_speed has apex_offset_m = {loss.apex_offset_m}")
            expected_offset = loss.reference_apex_distance_m - loss.driver_apex_distance_m
            ok(abs(loss.apex_offset_m - expected_offset) < 0.5,
               f"{loss.corner_id} apex_offset_m = {loss.apex_offset_m:.1f}, expected {expected_offset:.1f}")

    output = facts.to_dict()
    for d in output["top_losses"] + output["top_gains"]:
        if d["phase"] == "minimum_speed":
            ok("apex_offset_m" in d, f"minimum_speed dict has apex_offset_m")


def test_minimum_speed_gain_negative_loss_s() -> None:
    """Minimum speed gains have negative loss_s (real integrated time)."""
    current_lap = ROOT / "dev" / "fixtures" / "coach" / "barcelona_lap15_current.parquet"
    reference_lap = ROOT / "product" / "data" / "reference-laps" / "circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.456.parquet"
    track_model = ROOT / "product" / "data" / "track-coaching" / "circuit-de-barcelona_dkr-engineering-4-elms25.json"

    if not current_lap.exists():
        print("  SKIP: gain negative loss_s (fixture not found)")
        return

    from lap_telemetry.coach.track_model import load_track_coaching_model
    model = load_track_coaching_model(track_model)
    facts = compare_laps(current_lap, reference_lap, model)

    for gain in facts.top_gains:
        ok(gain.loss_s < 0, f"gain {gain.corner_id} {gain.phase} loss_s = {gain.loss_s:.4f}, expected negative")
        if gain.phase == "minimum_speed":
            ok(abs(gain.loss_s) < 10.0,
               f"minimum_speed gain loss_s = {gain.loss_s:.4f} is plausible (< 10s)")


def test_entry_gain_swap_barcelona() -> None:
    """Entry gains on swapped Barcelona use delta_t entry->apex, not heuristic."""
    current_lap = ROOT / "dev" / "fixtures" / "coach" / "barcelona_lap15_current.parquet"
    reference_lap = ROOT / "product" / "data" / "reference-laps" / "circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.456.parquet"
    track_model = ROOT / "product" / "data" / "track-coaching" / "circuit-de-barcelona_dkr-engineering-4-elms25.json"

    if not current_lap.exists():
        print("  SKIP: entry gain swap (fixture not found)")
        return

    from lap_telemetry.coach.track_model import load_track_coaching_model
    model = load_track_coaching_model(track_model)
    facts = compare_laps(reference_lap, current_lap, model, top_n=20)

    entry_results = [c for c in facts.top_losses + facts.top_gains if c.phase == "entry"]
    entry_gains = [c for c in entry_results if c.loss_s < 0]

    if not entry_gains:
        print("  SKIP: no entry gains in swapped Barcelona")
        return

    for gain in entry_gains:
        speed_delta = gain.reference_value - gain.driver_value
        heuristic = speed_delta / 100.0
        ok(gain.loss_s < heuristic,
           f"{gain.corner_id} entry gain {gain.loss_s:.4f} < heuristic {heuristic:.4f} (delta-t is larger gain)")
        ok(gain.gain_end_distance_m is not None,
           f"{gain.corner_id} entry gain has gain_end_distance_m")
        ok(gain.gain_end_distance_m == gain.apex_distance_m,
           f"{gain.corner_id} entry gain_end={gain.gain_end_distance_m} == apex={gain.apex_distance_m}")

    t1_entry = [g for g in entry_gains if g.corner_id == "t1"]
    if t1_entry:
        t1_ms = t1_entry[0].loss_s * 1000
        ok(abs(t1_ms - (-156)) < 10,
           f"t1 entry gain approx -156 ms, got {t1_ms:.1f} ms")


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    print("═══ Delta-Time & Gains Tests ═══\n")

    test_delta_time_trace_basic()
    test_delta_time_trace_faster_driver()
    test_delta_time_trace_equal_times()
    test_delta_time_trace_matches_lap_time()
    test_find_straight_end_middle_corner()
    test_find_straight_end_last_corner()
    test_minimum_speed_gain_uses_delta_time()
    test_minimum_speed_loss_unchanged()
    test_entry_gain_uses_delta_time()
    test_entry_loss_unchanged()
    test_apex_offset_in_comparison()
    test_minimum_speed_gain_negative_loss_s()
    test_entry_gain_swap_barcelona()

    total = pass_count + fail_count
    print(f"\n  {pass_count}/{total} assertions passed")
    if fail_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())