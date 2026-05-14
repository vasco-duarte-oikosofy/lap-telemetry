/**
 * Track outline/apex Phase 01 recorder channel tests.
 *
 * Run: node scripts/test_track_outline_recorder_channels.js
 */

'use strict';

const { spawnSync } = require('child_process');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
let passCount = 0;
let failCount = 0;

function assert(cond, name, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (cond) passCount++; else failCount++;
  console.log(`  [${status}] ${name}${detail ? ' — ' + detail : ''}`);
}

function runPythonRecorderCheck() {
  const code = `
import json, math, sys, tempfile
from pathlib import Path
sys.path.insert(0, r'''${ROOT}''')
from lap_telemetry.recorder.writer import SessionWriter, _SCHEMA
from lap_telemetry.recorder.connect import Frame

expected = [
    'raw_lap_distance_m', 'path_lateral_m', 'track_edge_m',
    'distance_to_track_edge_m', 'surface_type_fl', 'surface_type_fr',
    'surface_type_rl', 'surface_type_rr', 'terrain_name_fl',
    'terrain_name_fr', 'terrain_name_rl', 'terrain_name_rr',
]
schema_names = [f.name for f in _SCHEMA]
missing = [name for name in expected if name not in schema_names]
assert not missing, f'missing schema fields: {missing}'
for name in expected:
    assert _SCHEMA.field(name).nullable, f'{name} must be nullable for unavailable SHM fields'

base = dict(sim='lmu', session_time_s=0.0, lap_number=1, lap_distance_m=0.0,
            lap_time_s=0.0, speed_kph=100.0, throttle_norm=0.5, brake_norm=0.0,
            steering_norm=0.0, gear=3, engine_rpm=8000.0,
            lap_valid=True, pos_x_m=0.0, pos_y_m=0.0, pos_z_m=0.0,
            last_sector_1_s=math.nan, last_sector_2_s=math.nan,
            slip_angle_fl_deg=0.0, slip_angle_fr_deg=0.0,
            slip_angle_rl_deg=0.0, slip_angle_rr_deg=0.0,
            abs_active=True, tc_active=False,
            in_realtime=True, paused=False,
            track_name='Test Track', vehicle_name='Test Car', player_scor_index=0)

with tempfile.TemporaryDirectory() as td:
    out = Path(td)
    w = SessionWriter(out, 'lmu', 'Test Track', 50.0)
    w.append(Frame(**base,
                   raw_lap_distance_m=123.5, path_lateral_m=2.0, track_edge_m=7.5,
                   surface_type_fl=0, surface_type_fr=5, surface_type_rl=2, surface_type_rr=4,
                   terrain_name_fl='dry', terrain_name_fr='kerb',
                   terrain_name_rl='grass', terrain_name_rr='gravel'))
    w.append(Frame(**base,
                   raw_lap_distance_m=130.0, path_lateral_m=-1.25, track_edge_m=6.25,
                   surface_type_fl=1, surface_type_fr=1, surface_type_rl=1, surface_type_rr=1,
                   terrain_name_fl='wet', terrain_name_fr='wet',
                   terrain_name_rl='wet', terrain_name_rr='wet'))
    w.append(Frame(**base))
    pq_path, sidecar_path = w.close()

    import pyarrow.parquet as pq
    table = pq.read_table(pq_path)
    cols = {name: table.column(name).to_pylist() for name in expected}
    assert cols['raw_lap_distance_m'] == [123.5, 130.0, None], cols['raw_lap_distance_m']
    assert cols['path_lateral_m'] == [2.0, -1.25, None], cols['path_lateral_m']
    assert cols['track_edge_m'] == [7.5, 6.25, None], cols['track_edge_m']
    assert cols['distance_to_track_edge_m'] == [5.5, 5.0, None], cols['distance_to_track_edge_m']
    assert cols['surface_type_fl'] == [0, 1, None], cols['surface_type_fl']
    assert cols['surface_type_fr'] == [5, 1, None], cols['surface_type_fr']
    assert cols['surface_type_rl'] == [2, 1, None], cols['surface_type_rl']
    assert cols['surface_type_rr'] == [4, 1, None], cols['surface_type_rr']
    assert cols['terrain_name_fl'] == ['dry', 'wet', None], cols['terrain_name_fl']
    assert cols['terrain_name_fr'] == ['kerb', 'wet', None], cols['terrain_name_fr']
    assert cols['terrain_name_rl'] == ['grass', 'wet', None], cols['terrain_name_rl']
    assert cols['terrain_name_rr'] == ['gravel', 'wet', None], cols['terrain_name_rr']

    sidecar = json.loads(sidecar_path.read_text(encoding='utf-8'))
    assert sidecar['schema_version'] == '2', sidecar
print('OK')
`;
  return spawnSync('python3', ['-c', code], { encoding: 'utf8', timeout: 30000 });
}

function main() {
  console.log('═══ Track Outline Phase 01 Recorder Channel Tests ═══\n');
  const res = runPythonRecorderCheck();
  assert(!res.error, 'python recorder check spawned', res.error?.message || '');
  assert(res.status === 0, 'recorder writes outline/apex channels and schema v2', res.status === 0 ? res.stdout.trim() : res.stderr.trim());
  console.log(`\n${passCount}/${passCount + failCount} assertions passed`);
  if (failCount) process.exit(1);
}

main();
