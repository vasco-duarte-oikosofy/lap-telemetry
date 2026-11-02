"""Slice 24: distinct 1A race reference, official names and real flat bends."""
import json
import math
import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'product/python'))
from lap_telemetry.coach.track_model import load_track_coaching_model
from lap_telemetry.coach.reference_resolver import resolve_reference_lap
from lap_telemetry.coach.track_model_resolver import resolve_track_model
from lap_telemetry.parquet_utils import build_segments

TRACK = 'paul-ricard---1a'
CAR = 'dkr-engineering-4-elms25'
MODEL = ROOT / f'product/data/track-coaching/{TRACK}_{CAR}.json'
OUTLINE = ROOT / f'product/data/track-outlines/{TRACK}.json'
IDS = ['verrerie_1', 'verrerie_2', 'hotel_1', 'hotel_2', 'camp', 'sainte_baume',
       'mistral', 'signes', 'beausset_1', 'beausset_2', 'bendor', 'garlaban', 'lac', 'pont']
NAMES = ['S de la Verrerie 1', 'S de la Verrerie 2', "Virage de l'Hôtel 1",
         "Virage de l'Hôtel 2", 'Virage du Camp', 'Virage de la Sainte-Baume',
         'Ligne Droite du Mistral', 'Courbe de Signes', 'Double Droite du Beausset 1',
         'Double Droite du Beausset 2', 'Virage de Bendor', 'Courbe du Garlaban',
         'Virage du Lac', 'Virage du Pont']
SIDES = ['left', 'right', 'right', 'left', 'right', 'right', 'left', 'right',
         'right', 'right', 'left', 'right', 'left', 'right']
FLAT = {'verrerie_1': (560, 607, 710), 'verrerie_2': (785, 852, 970),
        'mistral': (1780, 1841, 1910), 'garlaban': (4810, 4846, 5070)}
passed = failed = 0


def ok(value, label):
    global passed, failed
    passed += bool(value)
    failed += not bool(value)
    print(f'[{"PASS" if value else "FAIL"}] {label}')


def main():
    refs = list((ROOT / 'product/data/reference-laps').glob(f'{TRACK}_{CAR}_time_*.parquet'))
    ok(len(refs) == 1, 'exactly one NEW 1A/P3 reference exists')
    ok(MODEL.exists(), 'new 1A/P3 coaching model exists')
    ok(OUTLINE.exists(), 'new distinct 1A layout outline exists')
    if not refs or not MODEL.exists() or not OUTLINE.exists():
        return
    raw = json.loads(MODEL.read_text(encoding='utf-8'))
    ref = ROOT / raw['reference_lap']['path']
    t = pq.read_table(ref)
    duration = float(t.schema.metadata[b'authoritative_lap_time_s'])
    ok(len(build_segments(t['lap_number'].to_pylist())) == 1, 'reference is a contiguous segment')
    ok(set(t['lap_number'].to_pylist()) == {10}, 'fastest complete valid race lap 10 selected')
    ok(all(t['lap_valid'].to_pylist()), 'reference is valid in every frame')
    ok(t.num_rows == 5323, 'reference contains exactly the selected 5323 source rows')
    ok(abs(duration - 106.8338623046875) < 0.001, 'authoritative race time 1:46.834, not sampled maximum')
    ok(abs(raw['reference_lap']['lap_time_s'] - duration) < 0.001, 'model/ref authoritative times agree')
    ok('\\' not in raw['reference_lap']['path'], 'committed reference path is portable')
    m = load_track_coaching_model(MODEL)
    ok(m.track_id == TRACK and m.layout_id == '1a', 'model is exact 1A, not 3A or V2-Short')
    ok(5690 < m.lap_length_m < 5710, 'model uses the full 1A simulator distance axis')
    ok([c.id for c in m.corners] == IDS, '14 reviewed zones include both Beausset apices')
    ok([c.name for c in m.corners] == NAMES, 'official names retained, including Lac and Garlaban')
    ok([c.apex_side for c in m.corners] == SIDES, 'sides agree with official map and calibrated steering')
    ok({c.id for c in m.corners if c.target_throttle_pct == 100} == set(FLAT),
       'all four genuinely flat bends have 100-percent targets')
    d = t['lap_distance_m'].to_pylist()
    for c in m.corners:
        ok(0 <= c.s_start_m < c.apex_s_m < c.s_end_m <= m.lap_length_m,
           f'{c.id}: full non-degenerate entry/apex/exit zone')
        indices = [i for i, s in enumerate(d) if abs(s - c.apex_s_m) < 8]
        mean = sum(t['steering_norm'][i].as_py() for i in indices) / len(indices)
        ok((mean > 0) == (c.apex_side == 'right'), f'{c.id}: apex is on the physical named bend')
        if c.id in FLAT:
            ok((c.s_start_m, c.apex_s_m, c.s_end_m) == FLAT[c.id], f'{c.id}: reviewed flat geometry pinned')
            rows = [i for i, s in enumerate(d) if c.s_start_m <= s <= c.s_end_m]
            ok(min(t['throttle_norm'][i].as_py() for i in rows) >= 0.99 and
               max(t['brake_norm'][i].as_py() for i in rows) < 0.01,
               f'{c.id}: actual reference confirms full throttle and zero braking across the zone')
    ok(all(a.s_end_m < b.s_start_m for a, b in zip(m.corners, m.corners[1:])),
       'chained Hotel/Camp, Beausset and Lac/Pont remain separate non-overlapping zones')
    ok(not any(2000 < c.apex_s_m < 3600 for c in m.corners), 'no invented Mistral chicane on 1A')
    o = json.loads(OUTLINE.read_text(encoding='utf-8'))
    ok(o['layout_name'] == '1a' and o['sim_track_name'] == 'Paul Ricard - 1A', 'outline exact layout identity')
    ok(o['lap_length_m'] == m.lap_length_m, 'map fractions use simulator axis, not geometric trace length')
    ok(o['alignment']['reference_lap'] == raw['reference_lap']['path'], 'outline provenance uses this race reference')
    ok([x['id'] for x in o['turns']] == IDS and [x['name'] for x in o['turns']] == NAMES,
       'all official/subdivided names reach the map, including four flat bends')
    for side in ('centerline', 'left_boundary', 'right_boundary'):
        ok(len(o[side]) == 500, f'{side}: 500 finite trajectory points')
    for side in ('left_boundary', 'right_boundary'):
        ok(all(abs(math.hypot(a['x']-b['x'], a['y']-b['y']) - 5) < 0.01
               for a, b in zip(o['centerline'], o[side])), f'{side}: explicitly synthetic 5m shell')
    for turn, c in zip(o['turns'], m.corners):
        i = min(range(len(d)), key=lambda i: abs(d[i] - c.apex_s_m))
        ok(math.hypot(turn['x']-t['pos_x_m'][i].as_py(), turn['y']-t['pos_z_m'][i].as_py()) < 3,
           f'{c.id}: map anchor matches the reference position')
    vehicle = 'DKR Engineering #4:ELMS25'
    ok(resolve_reference_lap('Paul Ricard - 1A', vehicle_name=vehicle) == ref, 'live coach resolves exact 1A/P3 reference')
    ok(resolve_track_model('Paul Ricard - 1A', vehicle_name=vehicle) == MODEL, 'live coach resolves exact 1A/P3 model')
    ok(resolve_reference_lap('Paul Ricard - 3A', vehicle_name=vehicle) != ref, '3A is not aliased to 1A')


def test_writer():
    import tempfile
    sys.path.insert(0, str(ROOT / 'dev/scripts'))
    try:
        from create_paul_ricard_1a_assets import write_new
    except ImportError:
        ok(False, 'guarded new-layout writer exists')
        return
    with tempfile.TemporaryDirectory() as directory:
        p = Path(directory) / 'curated.json'
        data = {'corners': [{'id': 'flat', 'name': 'S de la Verrerie 1', 'target_throttle_pct': 100}]}
        write_new(p, data, json.dumps(data))
        before = p.read_bytes()
        write_new(p, data, json.dumps(data))
        ok(p.read_bytes() == before, 'creator rerun is byte-idempotent')
        refused = False
        try:
            write_new(p, {'corners': []}, '{"corners": []}')
        except ValueError:
            refused = True
        ok(refused and p.read_bytes() == before, 'creator refuses overwriting curated flat/name data')


if __name__ == '__main__':
    main()
    test_writer()
    print(f'{passed}/{passed + failed} assertions passed')
    sys.exit(bool(failed))
