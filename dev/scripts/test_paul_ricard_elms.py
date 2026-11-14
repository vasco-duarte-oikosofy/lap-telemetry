"""Slice 50: Paul Ricard - ELMS / Ferrari 296 GT3 — new layout, official names.

The ELMS (5.8 km, 1C) configuration is NOT the 1A, 1A-V2-Short or 3A layout: it
uses the tight Verrerie `S` and the Chicane Nord pair in the middle of the
Mistral. This test pins the reference lap, the 16 curated coaching zones
(official names, real sides, the two genuinely flat bends) and the trajectory
outline whose turn anchors feed the map and the TinyPedal label export.
"""
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

TRACK = 'paul-ricard---elms'
CAR = 'vista-af-corse-2026-21-lm'
VEHICLE = 'Vista AF Corse 2026 #21:LM'
MODEL = ROOT / f'product/data/track-coaching/{TRACK}_{CAR}.json'
OUTLINE = ROOT / f'product/data/track-outlines/{TRACK}.json'
# id, official name, side, flat. 16 zones: 15 official turns with the Chicane
# Nord pair and the double Beausset each split into their two apices.
ZONES = [
    ('verrerie_1', 'S de la Verrerie 1', 'left', False),
    ('verrerie_2', 'S de la Verrerie 2', 'right', False),
    ('hotel_1', "Virage de l'Hôtel 1", 'right', False),
    ('hotel_2', "Virage de l'Hôtel 2", 'left', False),
    ('camp', 'Virage du Camp', 'right', False),
    ('sainte_baume', 'Virage de la Sainte-Baume', 'right', False),
    ('mistral', 'Ligne Droite du Mistral', 'left', True),
    ('chicane_nord_1', 'Chicane Nord 1', 'left', False),
    ('chicane_nord_2', 'Chicane Nord 2', 'right', False),
    ('signes', 'Courbe de Signes', 'right', False),
    ('beausset_1', 'Double Droite du Beausset 1', 'right', False),
    ('beausset_2', 'Double Droite du Beausset 2', 'right', False),
    ('bendor', 'Virage de Bendor', 'left', False),
    ('garlaban', 'Courbe du Garlaban', 'right', True),
    ('lac', 'Virage du Lac', 'left', False),
    ('pont', 'Virage du Pont', 'right', False),
]
FLAT = {'mistral': (1815.0, 1886.0, 1920.0), 'garlaban': (4900.0, 4949.0, 5170.0)}
passed = failed = 0


def ok(value, label):
    global passed, failed
    passed += bool(value)
    failed += not bool(value)
    print(f'[{"PASS" if value else "FAIL"}] {label}')


def main():
    refs = list((ROOT / 'product/data/reference-laps').glob(f'{TRACK}_{CAR}_time_*.parquet'))
    ok(len(refs) == 1, 'exactly one Paul Ricard ELMS / F296 reference exists')
    ok(MODEL.exists(), 'new ELMS/F296 coaching model exists')
    ok(OUTLINE.exists(), 'new ELMS layout outline exists')
    if not refs or not MODEL.exists() or not OUTLINE.exists():
        return
    raw = json.loads(MODEL.read_text(encoding='utf-8'))
    ref = ROOT / raw['reference_lap']['path']
    t = pq.read_table(ref)
    duration = float(t.schema.metadata[b'authoritative_lap_time_s'])
    ok(len(build_segments(t['lap_number'].to_pylist())) == 1, 'reference is a contiguous segment')
    ok(set(t['lap_number'].to_pylist()) == {10}, 'fastest complete valid lap 10 of the 2026-11-14 race')
    ok(all(t['lap_valid'].to_pylist()), 'reference is valid in every frame')
    ok(t.num_rows == 6297, 'reference contains exactly the selected 6297 source rows')
    ok(abs(duration - 126.440) < 0.001, 'authoritative race time 2:06.440, not the sampled maximum')
    ok(abs(raw['reference_lap']['lap_time_s'] - duration) < 0.001, 'model/ref authoritative times agree')
    ok('\\' not in raw['reference_lap']['path'], 'committed reference path is portable')
    m = load_track_coaching_model(MODEL)
    ok(m.track_id == TRACK and m.layout_id == 'elms', 'model is the ELMS layout itself')
    ok(5800 < m.lap_length_m < 5810, 'model uses the 5.8 km simulator distance axis')
    ok([c.id for c in m.corners] == [z[0] for z in ZONES], '16 reviewed zones in lap order')
    ok([c.name for c in m.corners] == [z[1] for z in ZONES],
       'official names, including Chicane Nord and the double Beausset apices')
    ok([c.apex_side for c in m.corners] == [z[2] for z in ZONES],
       'sides agree with the official plan and the calibrated steering signal')
    ok({c.id for c in m.corners if c.target_throttle_pct == 100} == set(FLAT),
       'only the two genuinely flat bends carry 100-percent targets')
    d = t['lap_distance_m'].to_pylist()
    for c in m.corners:
        ok(0 <= c.s_start_m < c.apex_s_m < c.s_end_m <= m.lap_length_m,
           f'{c.id}: full non-degenerate entry/apex/exit zone')
        indices = [i for i, s in enumerate(d) if abs(s - c.apex_s_m) < 8]
        mean = sum(t['steering_norm'][i].as_py() for i in indices) / len(indices)
        ok((mean > 0) == (c.apex_side == 'right'), f'{c.id}: apex is on the physical named bend')
    for cid, (start, apex, end) in FLAT.items():
        corner = next(c for c in m.corners if c.id == cid)
        ok((corner.s_start_m, corner.apex_s_m, corner.s_end_m) == (start, apex, end),
           f'{cid}: reviewed flat geometry pinned')
        rows = [i for i, s in enumerate(d) if start <= s <= end]
        ok(min(t['throttle_norm'][i].as_py() for i in rows) >= 0.99 and
           max(t['brake_norm'][i].as_py() for i in rows) < 0.01,
           f'{cid}: actual reference confirms full throttle and zero braking across the zone')
    ok(all(a.s_end_m <= b.s_start_m for a, b in zip(m.corners, m.corners[1:])),
       'chained Hotel/Camp, Chicane Nord, Beausset and Lac/Pont stay non-overlapping')
    ok(len([c for c in m.corners if 2700 < c.apex_s_m < 3200]) == 2,
       'the Mistral chicane is modelled as its real left/right pair')
    ok(not any(3400 < c.apex_s_m < 3800 for c in m.corners),
       'no invented corner on the second half of the Mistral straight')
    o = json.loads(OUTLINE.read_text(encoding='utf-8'))
    ok(o['layout_name'] == 'elms' and o['sim_track_name'] == 'Paul Ricard - ELMS',
       'outline exact layout identity')
    ok(o['lap_length_m'] == m.lap_length_m, 'map fractions use simulator axis, not geometric trace length')
    ok(o['alignment']['reference_lap'] == raw['reference_lap']['path'], 'outline provenance uses this reference')
    ok([x['id'] for x in o['turns']] == [z[0] for z in ZONES] and
       [x['name'] for x in o['turns']] == [z[1] for z in ZONES],
       'all 16 official names reach the map, including both flat bends')
    for side in ('centerline', 'left_boundary', 'right_boundary'):
        ok(len(o[side]) == 500, f'{side}: 500 finite trajectory points')
    for side in ('left_boundary', 'right_boundary'):
        ok(all(abs(math.hypot(a['x']-b['x'], a['y']-b['y']) - 5) < 0.01
               for a, b in zip(o['centerline'], o[side])), f'{side}: explicitly synthetic 5m shell')
    for turn, c in zip(o['turns'], m.corners):
        i = min(range(len(d)), key=lambda i: abs(d[i] - c.apex_s_m))
        ok(math.hypot(turn['x']-t['pos_x_m'][i].as_py(), turn['y']-t['pos_z_m'][i].as_py()) < 3,
           f'{c.id}: map anchor matches the reference position')
    ok(resolve_reference_lap('Paul Ricard - ELMS', vehicle_name=VEHICLE) == ref,
       'live coach resolves the ELMS/F296 reference')
    ok(resolve_track_model('Paul Ricard - ELMS', vehicle_name=VEHICLE) == MODEL,
       'live coach resolves the ELMS/F296 model')
    ok(resolve_reference_lap('Paul Ricard - 1A', vehicle_name=VEHICLE) != ref,
       'ELMS is not aliased to the 1A reference')
    ok(resolve_track_model('Paul Ricard - 1A', vehicle_name=VEHICLE) != MODEL,
       'ELMS is not aliased to the 1A model')


def test_writer():
    sys.path.insert(0, str(ROOT / 'dev/scripts'))
    try:
        from create_paul_ricard_elms_assets import write_new
    except ImportError:
        ok(False, 'guarded new-layout writer exists')
        return
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        p = Path(directory) / 'curated.json'
        data = {'corners': [{'id': 'mistral', 'name': 'Ligne Droite du Mistral',
                             'target_throttle_pct': 100}]}
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
