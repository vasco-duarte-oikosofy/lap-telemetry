/**
 * Track coaching model generator tests.
 *
 * Run: node dev/scripts/test_generate_track_coaching_model_from_reference.js
 */
// @parallel false

'use strict';

const { spawnSync } = require('child_process');
const path = require('path');

const ROOT = path.resolve(__dirname, '..', '..');

const PYTHON_TEST = String.raw`
import json
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
sys.path.insert(0, str(ROOT / 'dev' / 'scripts'))
sys.path.insert(0, str(ROOT / 'product' / 'python'))

import generate_track_coaching_model_from_reference as gen
from lap_telemetry.coach.lap_comparator import resample_column

pass_count = 0
fail_count = 0

class FakeColumn:
    def __init__(self, values):
        self.values = values
    def to_pylist(self):
        return list(self.values)

class FakeTable:
    def __init__(self, columns):
        self.columns = columns
        self.column_names = list(columns.keys())
    def column(self, name):
        return FakeColumn(self.columns[name])

def check(condition, name, detail=''):
    global pass_count, fail_count
    status = 'PASS' if condition else 'FAIL'
    if condition:
        pass_count += 1
    else:
        fail_count += 1
    suffix = f' — {detail}' if detail else ''
    print(f'  [{status}] {name}{suffix}')


def synthetic_speed(rows, dips):
    speed = []
    for i in range(rows):
        value = 220.0
        for center, depth, width in dips:
            effect = max(0.0, 1.0 - abs(i - center) / width)
            value -= depth * effect
        speed.append(value)
    return speed


def table_with_car(include_car):
    columns = {
        'lap_distance_m': [float(i) for i in range(10)],
        'speed_kph': [200.0 for _ in range(10)],
        'lap_time_s': [i / 10.0 for i in range(10)],
        'lap_number': [1 for _ in range(10)],
    }
    if include_car:
        columns['vehicle_id'] = ['synthetic-car' for _ in range(10)]
    return FakeTable(columns)


def run_unit_tests():
    candidates, _ = gen.detect_apex_candidates(synthetic_speed(1200, [(300, 80, 70)]))
    check(len(candidates) == 1, 'single V-shaped trace produces one corner', str(len(candidates)))
    check(abs(candidates[0].apex_m - 300) <= 2, 'single V-shaped trace apex is near expected distance', str(candidates[0].apex_m))

    model = gen.build_model(Path('synthetic.parquet'), 'synthetic', 'test', 'synthetic-car', 24.0, 1199.0, candidates, 'right')
    check(model['reference_lap']['car_id'] == 'synthetic-car', 'generated JSON includes reference car_id', model['reference_lap']['car_id'])

    candidates, _ = gen.detect_apex_candidates(synthetic_speed(1200, [(250, 75, 60), (700, 65, 60)]))
    check(len(candidates) == 2, 'two separated V-shaped traces produce two corners', str(len(candidates)))
    check(candidates[0].apex_m < candidates[1].apex_m, 'generated corners are sorted by distance')

    candidates, _ = gen.detect_apex_candidates(
        synthetic_speed(1200, [(300, 35, 25), (325, 80, 25)]),
        min_separation_m=60,
    )
    check(len(candidates) == 1, 'min-distance merging avoids duplicate apexes', str(len(candidates)))
    check(abs(candidates[0].apex_m - 325) <= 3, 'min-distance merging keeps strongest nearby candidate', str(candidates[0].apex_m))

    car_id = gen.resolve_car_id(table_with_car(True), Path('synthetic.parquet'), 'synthetic', None)
    check(car_id == 'synthetic-car', 'car id is read from vehicle_id column', car_id)

    try:
        gen.resolve_car_id(table_with_car(False), Path('lap.parquet'), 'synthetic', None)
        missing_failed = False
    except ValueError as exc:
        missing_failed = 'car identity' in str(exc)
    check(missing_failed, 'missing car identity fails without --car-id')

    manual_car = gen.resolve_car_id(table_with_car(False), Path('lap.parquet'), 'synthetic', 'manual-car')
    check(manual_car == 'manual-car', 'missing car identity succeeds with --car-id', manual_car)


def run_barcelona_generation_test():
    import pyarrow.parquet as pq

    reference_lap = ROOT / 'product' / 'data' / 'reference-laps' / 'circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.456.parquet'
    table = pq.read_table(reference_lap)
    distances, speeds = gen.finite_pairs(table.column('lap_distance_m').to_pylist(), table.column('speed_kph').to_pylist())
    resampled_speed = resample_column(distances, speeds, int(max(distances)))
    candidates, _ = gen.detect_apex_candidates(resampled_speed)
    model = gen.build_model(
        reference_lap,
        'circuit-de-barcelona',
        'lmu-default',
        'dkr-engineering-4-elms25',
        gen.lap_time_s(table),
        float(max(distances)),
        candidates,
        'right',
    )
    diagnostics = gen.diagnostics_text(candidates)

    check(model['reference_lap']['car_id'] == 'dkr-engineering-4-elms25', 'Barcelona output records reference car id', model['reference_lap']['car_id'])
    sorted_zones = all(previous['s_end_m'] <= current['s_start_m'] for previous, current in zip(model['corners'], model['corners'][1:]))
    check(sorted_zones, 'Barcelona corner zones are sorted and non-overlapping')
    apexes = [corner['apex_s_m'] for corner in model['corners']]
    for expected in [829, 941, 1162, 1730]:
        nearest = min(apexes, key=lambda value: abs(value - expected))
        check(abs(nearest - expected) <= 20, f'Barcelona candidate near {expected}m', f'nearest={nearest}')
    check('accepted' in diagnostics, 'Barcelona diagnostics include accepted candidates')


print('═══ Track Model From Reference Lap Tests ═══\n')
run_unit_tests()
run_barcelona_generation_test()
print(f'\n{pass_count}/{pass_count + fail_count} assertions passed')
if fail_count:
    sys.exit(1)
`;

const res = spawnSync('python3', ['-c', PYTHON_TEST, ROOT], {
  cwd: ROOT,
  encoding: 'utf8',
  timeout: 30000,
  env: { ...process.env, PYTHONPATH: path.join(ROOT, 'product', 'python') },
});

process.stdout.write(res.stdout || '');
process.stderr.write(res.stderr || '');
if (res.error) {
  console.log(`  [FAIL] python generator tests spawned — ${res.error.message}`);
  process.exit(1);
}
process.exit(res.status || 0);
