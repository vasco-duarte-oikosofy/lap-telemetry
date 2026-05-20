/**
 * Coach lap comparison tests.
 *
 * Run: node dev/scripts/test_coach_lap_comparison.js
 */
// @parallel true

'use strict';

const { spawnSync } = require('child_process');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');
let passCount = 0;
let failCount = 0;

function assert(cond, name, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (cond) passCount++; else failCount++;
  console.log(`  [${status}] ${name}${detail ? ' — ' + detail : ''}`);
}

function runPythonCoachTests() {
  const code = `
import json, sys
from pathlib import Path
sys.path.insert(0, r'''${path.join(ROOT, 'product', 'python')}''')

from lap_telemetry.coach.track_model import load_track_coaching_model, TrackModelValidationError
from lap_telemetry.coach.lap_comparator import compare_laps, resample_column

def test_resample_column():
    distances = [0.0, 1.0, 2.0, 3.0, 4.0]
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    result = resample_column(distances, values, 5)
    assert len(result) == 5, f"Expected 5 values, got {len(result)}"
    assert result[0] == 10.0, f"Expected 10.0 at d=0, got {result[0]}"
    assert result[4] == 50.0, f"Expected 50.0 at d=4, got {result[4]}"
    print('  resample_column: OK')

def test_track_model_validation():
    model_path = r'${path.join(ROOT, 'product', 'data', 'track-coaching', 'circuit-de-barcelona.json')}'
    model = load_track_coaching_model(model_path)
    assert model.schema_version == "1"
    assert model.track_id == "circuit-de-barcelona"
    assert len(model.corners) == 16, f"Expected 16 corners, got {len(model.corners)}"
    assert len(model.straight_zones) == 4, f"Expected 4 straight zones, got {len(model.straight_zones)}"
    t4 = model.get_corner_at(1650.0)
    assert t4 is not None, "Should find corner at 1650m"
    assert t4.id == "t4", f"Expected t4, got {t4.id}"
    straight = model.get_straight_at(500.0)
    assert straight is not None, "Should find straight at 500m"
    assert straight.id == "start-finish"
    print('  track_model_validation: OK')

def test_invalid_track_model():
    import tempfile
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
    print('  invalid_track_model: OK')

def test_lap_comparison():
    current_lap = r'${path.join(ROOT, 'dev', 'fixtures', 'coach', 'barcelona_lap15_current.parquet')}'
    reference_lap = r'${path.join(ROOT, 'product', 'data', 'reference-laps', 'circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.456.parquet')}'
    track_model = r'${path.join(ROOT, 'product', 'data', 'track-coaching', 'circuit-de-barcelona.json')}'
    if not Path(current_lap).exists():
        print(f'  lap_comparison: SKIP (fixture not found)')
        return
    model = load_track_coaching_model(track_model)
    facts = compare_laps(current_lap, reference_lap, model)
    assert facts.type == "lap_coaching_summary"
    assert facts.track_id == "circuit-de-barcelona"
    assert isinstance(facts.lap_time_delta_s, float)
    output = facts.to_dict()
    assert "top_losses" in output
    assert "top_gains" in output
    if output["top_losses"]:
        first_loss = output["top_losses"][0]
        corner = next(c for c in model.corners if c.id == first_loss["corner_id"])
        assert first_loss["apex_distance_m"] == corner.apex_s_m
        assert list(first_loss.keys())[2] == "apex_distance_m"
    print(f'  lap_comparison: OK (lap delta: {facts.lap_time_delta_s:.3f}s)')

def test_cli_command():
    import subprocess
    current_lap = r'${path.join(ROOT, 'dev', 'fixtures', 'coach', 'barcelona_lap15_current.parquet')}'
    reference_lap = r'${path.join(ROOT, 'product', 'data', 'reference-laps', 'circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.456.parquet')}'
    track_model = r'${path.join(ROOT, 'product', 'data', 'track-coaching', 'circuit-de-barcelona.json')}'
    if not Path(current_lap).exists():
        print(f'  cli_command: SKIP (fixture not found)')
        return
    result = subprocess.run(
        [
            sys.executable, "-m", "lap_telemetry",
            "compare-laps",
            "--current-lap", current_lap,
            "--reference-lap", reference_lap,
            "--track-model", track_model,
        ],
        capture_output=True,
        text=True,
        cwd=r'${path.join(ROOT, 'product', 'python')}',
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    output = json.loads(result.stdout)
    assert output["type"] == "lap_coaching_summary"
    assert output["track_id"] == "circuit-de-barcelona"
    if output["top_losses"]:
        assert "apex_distance_m" in output["top_losses"][0]
    print('  cli_command: OK')

test_resample_column()
test_track_model_validation()
test_invalid_track_model()
test_lap_comparison()
test_cli_command()
print('ALL OK')
`;
  return spawnSync('python3', ['-c', code], { encoding: 'utf8', timeout: 30000 });
}

function main() {
  console.log('═══ Coach Lap Comparison Tests ═══\n');
  const res = runPythonCoachTests();
  assert(!res.error, 'python coach tests spawned', res.error?.message || '');
  assert(res.status === 0, 'coach lap comparison tests', res.status === 0 ? res.stdout.trim() : res.stderr.trim());
  console.log(`\n${passCount}/${passCount + failCount} assertions passed`);
  if (failCount) process.exit(1);
}

main();
