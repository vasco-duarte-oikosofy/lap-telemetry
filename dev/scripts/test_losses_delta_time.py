#!/usr/bin/env python3
"""Test that losses use real delta-time (not speed_delta/100 heuristic).

Validates the 01c.4 decision: all phases use the same delta-time formula
for both losses and gains, and gain_end_distance_m is always populated.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "product" / "python"))

from lap_telemetry.coach.lap_comparator import compare_laps

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


def _load_fixture():
    """Load Barcelona fixture; return facts or None if files missing."""
    current_lap = ROOT / "dev" / "fixtures" / "coach" / "barcelona_lap15_current.parquet"
    reference_lap = (
        ROOT / "product" / "data" / "reference-laps"
        / "circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.456.parquet"
    )
    track_model = (
        ROOT / "product" / "data" / "track-coaching"
        / "circuit-de-barcelona_dkr-engineering-4-elms25.json"
    )
    if not current_lap.exists():
        return None
    from lap_telemetry.coach.track_model import load_track_coaching_model
    model = load_track_coaching_model(track_model)
    return compare_laps(current_lap, reference_lap, model)


def test_losses_use_delta_time() -> None:
    """Losses use real delta-time, not the speed_delta/100 heuristic."""
    facts = _load_fixture()
    if facts is None:
        print("  SKIP: losses delta-time (fixture not found)")
        return

    for loss in facts.top_losses:
        speed_delta = loss.reference_value - loss.driver_value
        heuristic = speed_delta / 100.0
        if loss.loss_s > 0 and abs(heuristic) > 0.001:
            ok(abs(loss.loss_s - heuristic) > 0.005,
               f"{loss.corner_id}/{loss.phase} loss_s={loss.loss_s:.3f}"
               f" ≠ heuristic={heuristic:.3f}")


def test_gain_end_distance_always_populated() -> None:
    """gain_end_distance_m is present for both losses and gains."""
    facts = _load_fixture()
    if facts is None:
        print("  SKIP: gain_end_distance (fixture not found)")
        return

    for c in facts.top_losses + facts.top_gains:
        ok(c.gain_end_distance_m is not None,
           f"{c.corner_id}/{c.phase} has gain_end_distance_m={c.gain_end_distance_m}")
        ok(c.gain_end_distance_m > 0,
           f"{c.corner_id}/{c.phase} gain_end_distance_m={c.gain_end_distance_m} > 0")


def test_losses_positive_gains_negative() -> None:
    """Sign convention: losses > 0, gains < 0."""
    facts = _load_fixture()
    if facts is None:
        print("  SKIP: sign convention (fixture not found)")
        return

    for loss in facts.top_losses:
        ok(loss.loss_s > 0,
           f"{loss.corner_id}/{loss.phase} loss_s={loss.loss_s:.3f} > 0")
    for gain in facts.top_gains:
        ok(gain.loss_s < 0,
           f"{gain.corner_id}/{gain.phase} loss_s={gain.loss_s:.3f} < 0")


def test_gain_end_distance_in_dict() -> None:
    """gain_end_distance_m appears in serialized output for all entries."""
    facts = _load_fixture()
    if facts is None:
        print("  SKIP: dict serialization (fixture not found)")
        return

    output = facts.to_dict()
    for entry in output["top_losses"] + output["top_gains"]:
        ok("gain_end_distance_m" in entry,
           f"{entry['corner_id']}/{entry['phase']} dict has gain_end_distance_m")


def main() -> int:
    print("═══ Losses Delta-Time Tests ═══\n")

    test_losses_use_delta_time()
    test_gain_end_distance_always_populated()
    test_losses_positive_gains_negative()
    test_gain_end_distance_in_dict()

    total = pass_count + fail_count
    print(f"\n  {pass_count}/{total} assertions passed")
    if fail_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())