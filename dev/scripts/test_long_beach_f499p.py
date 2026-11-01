"""Slice 38: Long Beach 499P reference, official turns and real flat geometry."""
import json
import math
import sys
import tempfile
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'product/python'))
sys.path.insert(0, str(ROOT / 'dev/scripts'))
from create_long_beach_f499p_assets import write_new
from lap_telemetry.coach.track_model import load_track_coaching_model
from lap_telemetry.coach.reference_resolver import resolve_reference_lap
from lap_telemetry.coach.track_model_resolver import resolve_track_model
from lap_telemetry.parquet_utils import build_segments

TRACK = 'grand-prix-of-long-beach'
CAR = 'ferrari-af-corse-2026-50-lm'
REF = ROOT / f'product/data/reference-laps/{TRACK}_{CAR}_time_01.15.889.parquet'
MODEL = ROOT / f'product/data/track-coaching/{TRACK}_{CAR}.json'
OUTLINE = ROOT / f'product/data/track-outlines/{TRACK}.json'
passed = failed = 0


def ok(condition, label):
    global passed, failed
    if condition:
        passed += 1
        print(f'[PASS] {label}')
    else:
        failed += 1
        print(f'[FAIL] {label}')


def main():
    for path in (REF, MODEL, OUTLINE):
        ok(path.exists(), f'combo asset exists: {path.name}')
    if not all(p.exists() for p in (REF, MODEL, OUTLINE)):
        return
    ref = pq.read_table(REF)
    ok(len(build_segments(ref['lap_number'].to_pylist())) == 1,
       'reference contains exactly one contiguous lap')
    ok(set(ref['lap_number'].to_pylist()) == {10}, 'guard-approved lap 10, not abandoned lap 4')
    duration = float(ref.schema.metadata[b'authoritative_lap_time_s'])
    ok(abs(duration - 75.888671875) < 0.001, f'authoritative telemetry timing: {duration:.6f}s')
    ok(all(ref['lap_valid'].to_pylist()), 'reference is valid throughout')
    ok(3700 < ref.num_rows < 3900, 'reference frame count agrees with 50 Hz duration')
    model = load_track_coaching_model(MODEL)
    ok([c.id for c in model.corners] == [f't{i}' for i in range(1, 12)],
       'all 11 official turns remain ordered, including flat turns')
    ok([c.name for c in model.corners] == [f'Turn {i}' for i in range(1, 12)],
       'official circuit map numbering retained, no invented corner names')
    ok([c.display_name for c in model.corners][-2:] == ['Ten', 'Eleven'],
       '10+ spoken aliases are words, not digit-by-digit numbers')
    flat = [c for c in model.corners if c.target_throttle_pct == 100]
    ok([c.id for c in flat] == ['t3', 't7'], 'both detector-missed flat turns retained')
    ok([c.apex_side for c in model.corners] ==
       ['left', 'right', 'left', 'right', 'right', 'left', 'left', 'right', 'right', 'left', 'right'],
       'apex sides match official layout and steering calibrated at Turn 1')
    for c in model.corners:
        ok(0 <= c.s_start_m < c.apex_s_m < c.s_end_m <= model.lap_length_m,
           f'{c.id}: real entry/apex/exit zone, not a degenerate marker')
    expected_flat = {'t3': (940, 950, 990), 't7': (1680, 1725, 1760)}
    distances = ref['lap_distance_m'].to_pylist()
    throttle = ref['throttle_norm'].to_pylist()
    brake = ref['brake_norm'].to_pylist()
    steering = ref['steering_norm'].to_pylist()
    for c in flat:
        ok((c.s_start_m, c.apex_s_m, c.s_end_m) == expected_flat[c.id],
           f'{c.id}: reviewed geometry pinned, never moved onto a neighbour')
        indices = [i for i, s in enumerate(distances) if c.s_start_m <= s <= c.s_end_m]
        ok(indices and min(throttle[i] for i in indices) >= 0.99
           and max(brake[i] for i in indices) < 0.01,
           f'{c.id}: real reference confirms full throttle/no braking throughout zone')
        ok(sum(steering[i] for i in indices) / len(indices) < -0.03,
           f'{c.id}: physical left-hand bend, not a straight-line marker')
    ok(model.corners[9].s_end_m < model.corners[10].s_start_m,
       'Turn 10 left bend and Turn 11 right hairpin are separate zones')
    outline = json.loads(OUTLINE.read_text(encoding='utf-8'))
    ok(outline['coordinate_system'] == 'sim_xy', 'outline uses simulator coordinates')
    ok('trajectory' in outline['source'].lower(), 'synthetic trajectory source is explicit')
    ok(len(outline['centerline']) == 500, 'outline retains 500 racing-line points')
    ok(all(len(outline[k]) == 500 for k in ('left_boundary', 'right_boundary')),
       'both boundary shells present')
    for side in ('left_boundary', 'right_boundary'):
        offsets = [math.hypot(a['x'] - b['x'], a['y'] - b['y'])
                   for a, b in zip(outline['centerline'], outline[side])]
        ok(all(abs(d - 5) < 0.01 for d in offsets), f'{side}: declared synthetic 5 m width')
    ok(len(outline.get('turns', [])) == 11, 'all official map turn anchors are present')
    ok([t['number'] for t in outline['turns']] == list(range(1, 12)),
       'map numbering agrees with official turns, not eight braking events')
    xs, zs = ref['pos_x_m'].to_pylist(), ref['pos_z_m'].to_pylist()
    for turn, c in zip(outline['turns'], model.corners):
        nearest = min(range(len(distances)), key=lambda i: abs(distances[i] - c.apex_s_m))
        ok(math.hypot(turn['x'] - xs[nearest], turn['y'] - zs[nearest]) < 3,
           f'{c.id}: turn anchor matches its real reference position')
    vehicle = 'Ferrari AF Corse 2026 #50:LM'
    ok(resolve_reference_lap('Grand Prix of Long Beach', vehicle_name=vehicle) == REF,
       'live coach resolves this reference for Ferrari 499P')
    ok(resolve_track_model('Grand Prix of Long Beach', vehicle_name=vehicle) == MODEL,
       'live coach resolves this model for Ferrari 499P')


def test_guarded_writer():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'curated.json'
        data = {'corners': [{'name': 'Turn 3', 's_start_m': 940, 'apex_s_m': 950, 's_end_m': 990}]}
        write_new(path, data, json.dumps(data))
        before = path.read_bytes()
        write_new(path, data, json.dumps(data))
        ok(path.read_bytes() == before, 'asset writer is byte-idempotent')
        refused = False
        try:
            write_new(path, {'corners': []}, '{"corners": []}')
        except ValueError:
            refused = True
        ok(refused and path.read_bytes() == before,
           'asset writer refuses any overwrite of curated names/flat geometry')


if __name__ == '__main__':
    main()
    test_guarded_writer()
    print(f'{passed}/{passed + failed} assertions passed')
    sys.exit(bool(failed))
