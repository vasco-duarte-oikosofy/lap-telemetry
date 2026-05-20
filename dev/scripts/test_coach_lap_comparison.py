#!/usr/bin/env python3
"""Test the lap comparison coaching engine."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "product" / "python"))

from lap_telemetry.coach.track_model import load_track_coaching_model, TrackModelValidationError
from lap_telemetry.coach.lap_comparator import compare_laps, resample_column


def test_resample_column():
    """Test distance-based resampling."""
    distances = [0.0, 1.0, 2.0, 3.0, 4.0]
    values = [10.0, 20.0, 30.0, 40.0, 50.0]

    result = resample_column(distances, values, 5)

    assert len(result) == 5, f"Expected 5 values, got {len(result)}"
    assert result[0] == 10.0, f"Expected 10.0 at d=0, got {result[0]}"
    assert result[4] == 50.0, f"Expected 50.0 at d=4, got {result[4]}"
    print("  PASS: resample_column")


def test_track_model_validation():
    """Test track coaching model loading and validation."""
    model_path = ROOT / "product" / "data" / "track-coaching" / "circuit-de-barcelona.json"

    model = load_track_coaching_model(model_path)

    assert model.schema_version == "1"
    assert model.track_id == "circuit-de-barcelona"
    assert len(model.corners) == 16, f"Expected 16 corners, got {len(model.corners)}"
    assert len(model.straight_zones) == 4, f"Expected 4 straight zones, got {len(model.straight_zones)}"

    # Test corner lookup
    t4 = model.get_corner_at(1650.0)
    assert t4 is not None, "Should find corner at 1650m"
    assert t4.id == "t4", f"Expected t4, got {t4.id}"

    # Test straight zone lookup
    straight = model.get_straight_at(500.0)
    assert straight is not None, "Should find straight at 500m"
    assert straight.id == "start-finish"

    print("  PASS: track_model_validation")


def test_invalid_track_model():
    """Test that invalid track models are rejected."""
    import tempfile
    import json

    # Test missing required field
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({"schema_version": "1", "track_id": "test"}, f)
        temp_path = Path(f.name)

    try:
        load_track_coaching_model(temp_path)
        assert False, "Should have raised TrackModelValidationError"
    except TrackModelValidationError:
        pass
    finally:
        temp_path.unlink()

    # Test invalid apex_side
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({
            "schema_version": "1",
            "track_id": "test",
            "layout_id": "default",
            "lap_length_m": 1000.0,
            "corners": [{
                "id": "t1",
                "name": "turn 1",
                "s_start_m": 100.0,
                "apex_s_m": 150.0,
                "s_end_m": 200.0,
                "apex_side": "invalid"
            }]
        }, f)
        temp_path = Path(f.name)

    try:
        load_track_coaching_model(temp_path)
        assert False, "Should have raised TrackModelValidationError for invalid apex_side"
    except TrackModelValidationError:
        pass
    finally:
        temp_path.unlink()

    print("  PASS: invalid_track_model")


def test_lap_comparison():
    """Test lap comparison with fixture data."""
    current_lap = ROOT / "dev" / "fixtures" / "coach" / "barcelona_lap15_current.parquet"
    reference_lap = ROOT / "product" / "data" / "reference-laps" / "circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.456.parquet"
    track_model = ROOT / "product" / "data" / "track-coaching" / "circuit-de-barcelona.json"

    if not current_lap.exists():
        print(f"  SKIP: lap_comparison (fixture not found: {current_lap})")
        return

    model = load_track_coaching_model(track_model)
    facts = compare_laps(current_lap, reference_lap, model)

    assert facts.type == "lap_coaching_summary"
    assert facts.track_id == "circuit-de-barcelona"
    assert isinstance(facts.lap_time_delta_s, float)

    # Output should be serializable
    output = facts.to_dict()
    assert "top_losses" in output
    assert "top_gains" in output
    assert isinstance(output["top_losses"], list)

    print(f"  PASS: lap_comparison (lap delta: {facts.lap_time_delta_s:.3f}s, {len(facts.top_losses)} losses)")


def test_cli_command():
    """Test the compare-laps CLI command."""
    import subprocess

    current_lap = ROOT / "dev" / "fixtures" / "coach" / "barcelona_lap15_current.parquet"
    reference_lap = ROOT / "product" / "data" / "reference-laps" / "circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.456.parquet"
    track_model = ROOT / "product" / "data" / "track-coaching" / "circuit-de-barcelona.json"

    if not current_lap.exists():
        print(f"  SKIP: cli_command (fixture not found: {current_lap})")
        return

    result = subprocess.run(
        [
            sys.executable, "-m", "lap_telemetry",
            "compare-laps",
            "--current-lap", str(current_lap),
            "--reference-lap", str(reference_lap),
            "--track-model", str(track_model),
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT / "product" / "python"),
    )

    if result.returncode != 0:
        print(f"  FAIL: cli_command (exit code {result.returncode})")
        print(f"    stderr: {result.stderr}")
        return

    # Should output valid JSON
    output = json.loads(result.stdout)
    assert output["type"] == "lap_coaching_summary"
    assert output["track_id"] == "circuit-de-barcelona"

    print("  PASS: cli_command")


def main():
    print("═══ Coach Lap Comparison Tests ═══\n")

    test_resample_column()
    test_track_model_validation()
    test_invalid_track_model()
    test_lap_comparison()
    test_cli_command()

    print("\nAll tests passed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
