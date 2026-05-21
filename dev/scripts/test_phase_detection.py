#!/usr/bin/env python3
"""Test the entry/exit phase detection algorithm for lap comparison coaching.

All tests use synthetic telemetry traces so that phase detection
can be validated against known distances.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "product" / "python"))

from lap_telemetry.coach.track_model import Corner
from lap_telemetry.coach.lap_comparator import (
    PhaseDetectionThresholds,
    compute_minimum_speed_per_corner,
    find_entry_point,
    find_brake_point,
    find_exit_points,
    resample_column,
    compare_laps,
)


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


def make_corner(
    s_start: float = 900.0,
    apex: float = 1000.0,
    s_end: float = 1100.0,
    corner_id: str = "t1",
    name: str = "turn 1",
) -> Corner:
    return Corner(
        id=corner_id, name=name,
        s_start_m=s_start, apex_s_m=apex, s_end_m=s_end,
        apex_side="right",
    )


def make_speed_trace(n: int, peak_at: int, peak_val: float, min_at: int, min_val: float) -> list[float]:
    """Build a speed trace that rises to peak_at then falls to min_at then rises again."""
    trace = [0.0] * n
    for i in range(n):
        if i <= peak_at:
            trace[i] = min_val + (peak_val - min_val) * (i / max(peak_at, 1))
        elif i <= min_at:
            frac = (i - peak_at) / max(min_at - peak_at, 1)
            trace[i] = peak_val - (peak_val - min_val) * frac
        else:
            remaining = n - min_at - 1
            if remaining > 0:
                frac = (i - min_at) / max(remaining, 1)
                trace[i] = min_val + (peak_val - min_val) * min(frac, 1.0)
            else:
                trace[i] = min_val
    return trace


# ── Tests ────────────────────────────────────────────────────────────────────


def test_throttle_lift_entry() -> None:
    """Throttle drops at a known distance; entry should be reported at s_lift, not apex-30."""
    corner = make_corner(s_start=900, apex=1000, s_end=1100)
    speed = [200.0] * 1200  # flat speed (simplified)
    throttle = [1.0] * 1200
    for i in range(950, 1001):
        throttle[i] = 0.5  # driver lifts at 950 m

    entry_idx, method = find_entry_point(speed, throttle, None, corner)
    ok(method == "throttle_lift", f"method = {method}, expected throttle_lift")
    ok(entry_idx == 950, f"entry at {entry_idx}, expected 950 (not apex-30={int(corner.apex_s_m - 30)})")


def test_throttle_lift_before_zone() -> None:
    """Throttle lift occurs before s_start_m; look-back should still find it."""
    # Zone starts at 500, but driver lifts throttle at 420 (80m before zone).
    # Without look-back, the algorithm would miss the lift and fall back
    # to speed_peak at the zone boundary.
    corner = make_corner(s_start=500, apex=600, s_end=700)
    speed = [200.0] * 1200
    throttle = [1.0] * 1200
    for i in range(420, 600):
        throttle[i] = 0.5  # lift starts at 420, well before zone

    entry_idx, method = find_entry_point(speed, throttle, None, corner)
    ok(method == "throttle_lift", f"method = {method}, expected throttle_lift")
    ok(entry_idx == 420, f"entry at {entry_idx}, expected 420 (lift before zone)")


def test_brake_point_before_zone() -> None:
    """Brake application occurs before s_start_m; look-back should find it."""
    corner = make_corner(s_start=500, apex=600, s_end=700)
    brake = [0.0] * 1200
    for i in range(430, 580):
        brake[i] = 0.5  # braking from 430, before zone at 500

    bp = find_brake_point(brake, corner)
    ok(bp == 430, f"brake point = {bp}, expected 430 (before zone start)")


def test_brake_off_exit() -> None:
    """Brake returns to 0 at known distance after apex; exit should be reported there."""
    corner = make_corner(s_start=900, apex=1000, s_end=1100)
    brake = [0.0] * 1200
    for i in range(980, 1020):
        brake[i] = 0.8  # braking zone
    # Brake off at 1020
    throttle = [0.0] * 1200  # never reaches full throttle

    exits = find_exit_points(brake, throttle, corner)
    ok(len(exits) >= 1, f"exit count {len(exits)}, expected >= 1")
    phase_name, dist = exits[0]
    ok(phase_name == "exit", f"phase = {phase_name}, expected exit (brake-only)")
    ok(dist == 1020, f"brake-off distance = {dist}, expected 1020")


def test_full_throttle_exit() -> None:
    """Throttle reaches 100% at known distance after apex; exit should be reported there."""
    corner = make_corner(s_start=900, apex=1000, s_end=1100)
    brake = None  # no brake data
    throttle = [0.0] * 1200
    for i in range(0, 950):
        throttle[i] = 1.0  # full throttle on straight
    # throttle = 0 in braking zone
    throttle[1050] = 0.96  # first full-throttle after apex

    exits = find_exit_points(brake, throttle, corner)
    ok(len(exits) == 1, f"exit count {len(exits)}, expected 1")
    phase_name, dist = exits[0]
    ok(phase_name == "exit", f"phase = {phase_name}, expected exit (throttle-only)")
    ok(dist == 1050, f"full-throttle distance = {dist}, expected 1050")


def test_separate_exit_phases() -> None:
    """Brake releases before full throttle; both exit_brake and exit_throttle reported."""
    corner = make_corner(s_start=900, apex=1000, s_end=1100)
    brake = [0.0] * 1200
    for i in range(980, 1020):
        brake[i] = 0.8
    # Brake off at 1020

    throttle = [0.0] * 1200
    for i in range(0, 950):
        throttle[i] = 1.0
    throttle[1040] = 0.96  # Full throttle at 1040 (>3m from brake-off)

    exits = find_exit_points(brake, throttle, corner)
    ok(len(exits) == 2, f"exit count {len(exits)}, expected 2 (separate phases)")
    ok(exits[0][0] == "exit_brake", f"first phase = {exits[0][0]}, expected exit_brake")
    ok(exits[0][1] == 1020, f"exit_brake dist = {exits[0][1]}, expected 1020")
    ok(exits[1][0] == "exit_throttle", f"second phase = {exits[1][0]}, expected exit_throttle")
    ok(exits[1][1] == 1040, f"exit_throttle dist = {exits[1][1]}, expected 1040")


def test_merged_exit() -> None:
    """Brake-off and full-throttle within 3m → single merged 'exit' phase."""
    corner = make_corner(s_start=900, apex=1000, s_end=1100)
    brake = [0.0] * 1200
    for i in range(980, 1020):
        brake[i] = 0.8
    # Brake off at 1020

    throttle = [0.0] * 1200
    for i in range(0, 950):
        throttle[i] = 1.0
    throttle[1022] = 0.96  # Full throttle 2m after brake-off (within 3m)

    exits = find_exit_points(brake, throttle, corner)
    ok(len(exits) == 1, f"exit count {len(exits)}, expected 1 (merged)")
    ok(exits[0][0] == "exit", f"phase = {exits[0][0]}, expected exit (merged)")
    ok(exits[0][1] == 1021, f"merged midpoint = {exits[0][1]}, expected 1021 (round((1020+1022)/2))")


def test_speed_fallback_entry() -> None:
    """No throttle data; entry should be at the speed local maximum (speed_peak)."""
    corner = make_corner(s_start=900, apex=1000, s_end=1100)
    speed = make_speed_trace(1200, peak_at=940, peak_val=250.0, min_at=1000, min_val=80.0)
    # no throttle, no brake
    entry_idx, method = find_entry_point(speed, None, None, corner)
    ok(method == "speed_peak", f"method = {method}, expected speed_peak")
    ok(entry_idx == 940, f"entry at {entry_idx}, expected 940 (speed peak)")


def test_speed_only_exit_fallback() -> None:
    """No brake or throttle data; exit should fall back to s_end_m."""
    corner = make_corner(s_start=900, apex=1000, s_end=1100)
    exits = find_exit_points(None, None, corner)
    ok(len(exits) == 1, f"exit count {len(exits)}, expected 1")
    ok(exits[0][0] == "exit", f"phase = {exits[0][0]}, expected exit")
    ok(exits[0][1] == 1100, f"exit dist = {exits[0][1]}, expected 1100 (s_end_m)")


def test_missing_channels_graceful() -> None:
    """Missing brake/throttle columns → algorithm still works with speed-only fallback."""
    corner = make_corner(s_start=900, apex=1000, s_end=1100)
    speed = make_speed_trace(1200, peak_at=940, peak_val=250.0, min_at=1000, min_val=80.0)

    # Entry: speed-only
    entry_idx, method = find_entry_point(speed, None, None, corner)
    ok(method == "speed_peak", f"speed-only entry method = {method}")
    ok(entry_idx == 940, f"speed-only entry at {entry_idx}")

    # Exit: zone boundary fallback
    exits = find_exit_points(None, None, corner)
    ok(len(exits) == 1, f"speed-only exit count = {len(exits)}")
    ok(exits[0][1] == 1100, f"speed-only exit at {exits[0][1]}, expected 1100")


def test_brake_point_secondary() -> None:
    """Brake application point is detected as a secondary entry fact."""
    corner = make_corner(s_start=900, apex=1000, s_end=1100)
    brake = [0.0] * 1200
    for i in range(960, 990):
        brake[i] = 0.5  # braking from 960

    bp = find_brake_point(brake, corner)
    ok(bp == 960, f"brake point = {bp}, expected 960")


def test_thresholds_configurable() -> None:
    """Custom thresholds change detection behavior."""
    corner = make_corner(s_start=900, apex=1000, s_end=1100)

    # Default threshold (0.9): throttle 0.85 lifts → detected
    throttle = [1.0] * 1200
    throttle[950] = 0.85
    entry_idx, method = find_entry_point([200.0] * 1200, throttle, None, corner)
    ok(method == "throttle_lift", f"default threshold: method = {method}")
    ok(entry_idx == 950, f"default: entry at {entry_idx}")

    # Custom threshold 0.7: throttle 0.85 NOT below → falls back to speed peak
    speed = make_speed_trace(1200, peak_at=940, peak_val=250.0, min_at=1000, min_val=80.0)
    custom_thresh = PhaseDetectionThresholds(throttle_lift=0.7)
    entry_idx2, method2 = find_entry_point(speed, throttle, None, corner, custom_thresh)
    ok(method2 == "speed_peak", f"custom threshold: method = {method2} (throttle 0.85 > 0.7)")


def test_apex_offset_same_position() -> None:
    """When driver and reference hit min speed at the same distance, both distances match."""
    corner = make_corner(s_start=900, apex=1000, s_end=1100)
    # Both traces min at 1000 m (index 1000)
    n = 1200
    driver_speed = [200.0] * n
    ref_speed = [200.0] * n
    driver_speed[1000] = 100.0  # driver min at 1000
    ref_speed[1000] = 105.0     # ref min at 1000

    driver_min, ref_min, delta, driver_apex, ref_apex = compute_minimum_speed_per_corner(
        driver_speed, ref_speed, corner
    )
    ok(driver_min == 100.0, f"driver min = {driver_min}, expected 100.0")
    ok(ref_min == 105.0, f"ref min = {ref_min}, expected 105.0")
    ok(driver_apex == 1000.0, f"driver apex distance = {driver_apex}, expected 1000")
    ok(ref_apex == 1000.0, f"ref apex distance = {ref_apex}, expected 1000")
    ok(driver_apex == ref_apex, "driver and reference apex at same position")


def test_apex_offset_driver_late() -> None:
    """When driver apexes 9 m later than reference, the distances reflect that."""
    corner = make_corner(s_start=900, apex=1000, s_end=1100)
    n = 1200
    driver_speed = [200.0] * n
    ref_speed = [200.0] * n
    # Reference apex at 995 m
    for i in range(990, 1001):
        ref_speed[i] = 110.0 + (1001 - i) * 2  # descending to minimum
    ref_speed[995] = 100.0  # ref min at 995
    # Driver apex at 1004 m (9 m late)
    for i in range(999, 1010):
        driver_speed[i] = 115.0 + (1010 - i) * 2
    driver_speed[1004] = 95.0  # driver min at 1004

    driver_min, ref_min, delta, driver_apex, ref_apex = compute_minimum_speed_per_corner(
        driver_speed, ref_speed, corner
    )
    ok(driver_apex == 1004.0, f"driver apex = {driver_apex}, expected 1004")
    ok(ref_apex == 995.0, f"ref apex = {ref_apex}, expected 995")
    offset = driver_apex - ref_apex
    ok(offset == 9.0, f"apex offset = {offset}, expected 9.0 (driver late)")


def test_apex_offset_fixture() -> None:
    """Barcelona fixture comparison includes driver_apex_distance_m and reference_apex_distance_m on minimum_speed phases."""
    current_lap = ROOT / "dev" / "fixtures" / "coach" / "barcelona_lap15_current.parquet"
    reference_lap = ROOT / "product" / "data" / "reference-laps" / "circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.456.parquet"
    track_model = ROOT / "product" / "data" / "track-coaching" / "circuit-de-barcelona_dkr-engineering-4-elms25.json"

    if not current_lap.exists():
        print("  SKIP: apex offset fixture (fixture not found)")
        return

    from lap_telemetry.coach.track_model import load_track_coaching_model
    model = load_track_coaching_model(track_model)
    facts = compare_laps(current_lap, reference_lap, model)

    min_speed_losses = [c for c in facts.top_losses if c.phase == "minimum_speed"]
    if not min_speed_losses:
        print("  SKIP: apex offset fixture (no minimum_speed losses)")
        return

    for loss in min_speed_losses:
        ok(
            loss.driver_apex_distance_m is not None,
            f"{loss.corner_id} minimum_speed has driver_apex_distance_m = {loss.driver_apex_distance_m}",
        )
        ok(
            loss.reference_apex_distance_m is not None,
            f"{loss.corner_id} minimum_speed has reference_apex_distance_m = {loss.reference_apex_distance_m}",
        )
        # The model apex_distance_m is the track model's defined apex
        ok(
            loss.apex_distance_m != loss.driver_apex_distance_m or loss.apex_distance_m != loss.reference_apex_distance_m,
            f"{loss.corner_id} apex positions are not both identical to track model apex (driver={loss.driver_apex_distance_m}, ref={loss.reference_apex_distance_m}, model={loss.apex_distance_m})",
        )

    # Also verify the JSON output contains the new fields
    output = facts.to_dict()
    min_speed_dicts = [d for d in output["top_losses"] if d["phase"] == "minimum_speed"]
    for d in min_speed_dicts:
        ok("driver_apex_distance_m" in d, f"minimum_speed dict has driver_apex_distance_m")
        ok("reference_apex_distance_m" in d, f"minimum_speed dict has reference_apex_distance_m")


def test_comparison_with_fixture() -> None:
    """Full comparison with Barcelona fixture produces valid output."""
    current_lap = ROOT / "dev" / "fixtures" / "coach" / "barcelona_lap15_current.parquet"
    reference_lap = ROOT / "product" / "data" / "reference-laps" / "circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.456.parquet"
    track_model = ROOT / "product" / "data" / "track-coaching" / "circuit-de-barcelona_dkr-engineering-4-elms25.json"

    if not current_lap.exists():
        print("  SKIP: fixture comparison (fixture not found)")
        return

    from lap_telemetry.coach.track_model import load_track_coaching_model
    model = load_track_coaching_model(track_model)
    facts = compare_laps(current_lap, reference_lap, model)

    ok(facts.type == "lap_coaching_summary", f"type = {facts.type}")
    ok(isinstance(facts.lap_time_delta_s, float), "lap_time_delta_s is float")

    output = facts.to_dict()
    ok("top_losses" in output, "top_losses in output")
    ok("top_gains" in output, "top_gains in output")

    # Verify entry distances are NOT fixed apex-30
    for loss in facts.top_losses + facts.top_gains:
        if loss.phase == "entry":
            ok(
                loss.phase_distance_m is not None,
                f"entry phase has phase_distance_m = {loss.phase_distance_m}",
            )
            # Entry should NOT be exactly apex - 30
            is_fixed_offset = abs(loss.phase_distance_m - (loss.apex_distance_m - 30)) < 0.5
            ok(
                not is_fixed_offset,
                f"entry at {loss.phase_distance_m} is NOT fixed apex-30={loss.apex_distance_m - 30}",
            )

    # Verify exit phases: no fixed apex+30
    for loss in facts.top_losses + facts.top_gains:
        if loss.phase in ("exit", "exit_brake", "exit_throttle"):
            ok(
                loss.phase_distance_m is not None,
                f"{loss.phase} phase has phase_distance_m = {loss.phase_distance_m}",
            )
            is_fixed_offset = abs(loss.phase_distance_m - (loss.apex_distance_m + 30)) < 0.5
            ok(
                not is_fixed_offset,
                f"{loss.phase} at {loss.phase_distance_m} is NOT fixed apex+30={loss.apex_distance_m + 30}",
            )


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    print("═══ Entry/Exit Phase Detection Tests ═══\n")

    test_throttle_lift_entry()
    test_throttle_lift_before_zone()
    test_brake_off_exit()
    test_brake_point_before_zone()
    test_full_throttle_exit()
    test_separate_exit_phases()
    test_merged_exit()
    test_speed_fallback_entry()
    test_speed_only_exit_fallback()
    test_missing_channels_graceful()
    test_brake_point_secondary()
    test_thresholds_configurable()
    test_apex_offset_same_position()
    test_apex_offset_driver_late()
    test_apex_offset_fixture()
    test_comparison_with_fixture()

    total = pass_count + fail_count
    print(f"\n  {pass_count}/{total} assertions passed")
    if fail_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())