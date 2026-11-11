"""Slice 51: Silverstone National Circuit / Ginetta LMP3 — new combo.

The National layout (2.64 km, 6 corners) is NOT the International or GP-ELMS
configuration: it never touches the Arena complex (Abbey / Farm Curve / Village
/ The Link) and instead runs the National pits straight into Copse, Maggotts,
the Wellington Straight, Brooklands, Luffield and Woodcote. This test pins the
reference lap, the curated coaching zones (official names, real sides, flat
bends) and the trajectory outline whose turn anchors feed the map and the
TinyPedal label export.

It also pins the guarded-exporter floor: a National lap is ~51 s, below the
historical 60 s `MIN_LAP_TIME_S`, so the exporter must accept an explicit
override instead of silently refusing every lap of a short circuit.
"""
import json
import math
import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'product/python'))
sys.path.insert(0, str(ROOT / 'dev/scripts'))
from lap_telemetry.coach.track_model import load_track_coaching_model
from lap_telemetry.coach.reference_resolver import resolve_reference_lap
from lap_telemetry.coach.track_model_resolver import resolve_track_model
from lap_telemetry.parquet_utils import build_segments

TRACK = 'silverstone-national-circuit'
CAR = 'dkr-engineering-4-elms25'
VEHICLE = 'DKR Engineering #4:ELMS25'
TRACK_NAME = 'Silverstone National Circuit'
SESSION = ROOT / 'sessions/session_20261111T172218Z_silverstone-national-circuit_lmu_practice.parquet'
MODEL = ROOT / f'product/data/track-coaching/{TRACK}_{CAR}.json'
OUTLINE = ROOT / f'product/data/track-outlines/{TRACK}.json'
REF_NAME = f'{TRACK}_{CAR}_time_00.50.446.parquet'
# id, official name, side, flat.  Silverstone's National corner list is Copse,
# Maggots, Becketts, Brooklands, Luffield, Woodcote. Maggots is the flat left
# flick into the complex and Becketts the braked right that peels onto the
# Wellington Straight; Woodcote is the flat right onto the National pits straight.
ZONES = [
    ('copse', 'Copse', 'right', False),
    ('maggots', 'Maggots', 'left', True),
    ('becketts', 'Becketts', 'right', False),
    ('brooklands', 'Brooklands', 'left', False),
    ('luffield', 'Luffield', 'right', False),
    ('woodcote', 'Woodcote', 'right', True),
]
FLAT = {'maggots', 'woodcote'}
passed = failed = 0


def ok(value, label):
    global passed, failed
    passed += bool(value)
    failed += not bool(value)
    print(f'[{"PASS" if value else "FAIL"}] {label}')


def test_exporter_floor():
    """A 51 s National lap is below the 60 s default floor; the override must work."""
    import export_fastest_reference_laps as exporter
    table = pq.read_table(SESSION)
    ok(exporter.find_complete_laps(table) == [],
       'default 60s floor rejects every short National lap (documented guard)')
    laps = exporter.find_complete_laps(table, min_lap_time_s=30.0)
    ok(len(laps) == 10, f'explicit 30s floor accepts the ten complete National laps: {len(laps)}')
    if laps:
        fastest = min(laps, key=lambda lap: lap[1])
        ok(fastest[0] == 7 and abs(fastest[1] - 50.859) < 0.001,
           'fastest complete lap is lap 7 at 50.859s by authoritative timing')
        ok(fastest[3] - fastest[2] == 2535, 'lap 7 segment is 2535 rows, not a lap_number filter')
    args = exporter.parse_args(['--min-lap-time-s', '30', 'sessions/x.parquet'])
    ok(args.min_lap_time_s == 30.0, 'exporter accepts --min-lap-time-s')
    ok(exporter.parse_args(['sessions/x.parquet']).min_lap_time_s == 60.0,
       'exporter floor still defaults to 60s for every other track')


def main():
    test_exporter_floor()
    refs = list((ROOT / 'product/data/reference-laps').glob(f'{TRACK}_{CAR}_time_*.parquet'))
    ok(len(refs) == 1, 'exactly one Silverstone National / LMP3 reference exists')
    ok(refs and refs[0].name == REF_NAME, f'reference is the guarded fastest lap file')
    ok(MODEL.exists(), 'new National/LMP3 coaching model exists')
    ok(OUTLINE.exists(), 'new National layout outline exists')
    if not refs or not MODEL.exists() or not OUTLINE.exists():
        return
    raw = json.loads(MODEL.read_text(encoding='utf-8'))
    ref = ROOT / raw['reference_lap']['path']
    t = pq.read_table(ref)
    duration = float(t.schema.metadata[b'authoritative_lap_time_s'])
    ok(len(build_segments(t['lap_number'].to_pylist())) == 1, 'reference is a contiguous segment')
    ok(set(t['lap_number'].to_pylist()) == {20}, 'fastest complete valid lap 20 selected')
    ok(all(t['lap_valid'].to_pylist()), 'reference is valid in every frame')
    ok(t.num_rows == 2512, 'reference contains exactly the selected 2512 source rows')
    ok(abs(duration - 50.446) < 0.001, 'authoritative practice time 0:50.446')
    ok(abs(raw['reference_lap']['lap_time_s'] - duration) < 0.001, 'model/ref authoritative times agree')
    ok('\\' not in raw['reference_lap']['path'], 'committed reference path is portable')
    m = load_track_coaching_model(MODEL)
    ok(m.track_id == TRACK and m.layout_id == 'national', 'model is the National layout itself')
    ok(2600 < m.lap_length_m < 2660, f'model uses the 2.64 km simulator distance axis ({m.lap_length_m})')
    ok([c.id for c in m.corners] == [z[0] for z in ZONES], 'six reviewed zones in lap order')
    ok([c.name for c in m.corners] == [z[1] for z in ZONES],
       'official Silverstone National names, Maggots left + Becketts right')
    ok([c.apex_side for c in m.corners] == [z[2] for z in ZONES],
       'sides agree with the official plan and the calibrated steering signal')
    ok({c.id for c in m.corners if c.target_throttle_pct == 100} == FLAT,
       'only the two genuinely flat bends carry 100-percent targets')
    d = t['lap_distance_m'].to_pylist()
    for c in m.corners:
        ok(0 <= c.s_start_m < c.apex_s_m < c.s_end_m <= m.lap_length_m,
           f'{c.id}: full non-degenerate entry/apex/exit zone')
        indices = [i for i, s in enumerate(d) if abs(s - c.apex_s_m) < 8]
        mean = sum(t['steering_norm'][i].as_py() for i in indices) / len(indices)
        ok((mean > 0) == (c.apex_side == 'right'), f'{c.id}: apex is on the physical named bend')
    for cid in FLAT:
        corner = next(c for c in m.corners if c.id == cid)
        rows = [i for i, s in enumerate(d) if corner.s_start_m <= s <= corner.s_end_m]
        ok(min(t['throttle_norm'][i].as_py() for i in rows) >= 0.98 and
           max(t['brake_norm'][i].as_py() for i in rows) < 0.01,
           f'{cid}: actual reference confirms full throttle and zero braking across the zone')
    ok(all(a.s_end_m <= b.s_start_m for a, b in zip(m.corners, m.corners[1:])),
       'Maggots/Becketts and the Brooklands/Luffield/Woodcote chain stay non-overlapping')
    ok(len([c for c in m.corners if 1110 < c.apex_s_m < 1740]) == 0,
       'the Wellington Straight carries no corner at all')
    ok(not any(440 < c.apex_s_m < 780 for c in m.corners),
       'no invented corner between Copse and Maggots')
    ok(not any(c.apex_s_m > 2580 for c in m.corners),
       'no invented corner on the National pits straight')
    o = json.loads(OUTLINE.read_text(encoding='utf-8'))
    ok(o['layout_name'] == 'national' and o['sim_track_name'] == TRACK_NAME,
       'outline exact layout identity')
    ok(o['lap_length_m'] == m.lap_length_m, 'map fractions use simulator axis, not geometric trace length')
    ok('reference_lap' not in o['alignment'],
       'outline provenance is a stable note, not a path to a superseded reference')
    ok('0:50.446' in o['alignment']['notes'], 'outline records the refreshed anchors reference')
    ok([x['id'] for x in o['turns']] == [z[0] for z in ZONES] and
       [x['name'] for x in o['turns']] == [z[1] for z in ZONES],
       'all six official names reach the map')
    ok([x['apex_s_m'] for x in o['turns']] == [round(c.apex_s_m, 1) for c in m.corners],
       'map anchors follow the refreshed model apices, not the old ones')
    for side in ('centerline', 'left_boundary', 'right_boundary'):
        ok(len(o[side]) == 500, f'{side}: 500 finite trajectory points')
    for side in ('left_boundary', 'right_boundary'):
        ok(all(abs(math.hypot(a['x']-b['x'], a['y']-b['y']) - 5) < 0.01
               for a, b in zip(o['centerline'], o[side])), f'{side}: explicitly synthetic 5m shell')
    for turn, c in zip(o['turns'], m.corners):
        i = min(range(len(d)), key=lambda i: abs(d[i] - c.apex_s_m))
        ok(math.hypot(turn['x']-t['pos_x_m'][i].as_py(), turn['y']-t['pos_z_m'][i].as_py()) < 3,
           f'{c.id}: map anchor matches the reference position')
    ok(resolve_reference_lap(TRACK_NAME, vehicle_name=VEHICLE) == ref,
       'live coach resolves the National/LMP3 reference')
    ok(resolve_track_model(TRACK_NAME, vehicle_name=VEHICLE) == MODEL,
       'live coach resolves the National/LMP3 model')
    ok(resolve_reference_lap('Silverstone International Circuit', vehicle_name=VEHICLE) != ref,
       'National is not aliased to the International reference')
    ok(resolve_track_model('Silverstone International Circuit', vehicle_name=VEHICLE) != MODEL,
       'National is not aliased to the International model')
    ok(resolve_reference_lap('Silverstone Grand Prix Circuit - ELMS', vehicle_name=VEHICLE) != ref,
       'National is not aliased to the GP-ELMS reference')


def test_writer():
    try:
        from create_silverstone_national_p3_assets import write_new
    except ImportError:
        ok(False, 'guarded new-layout writer exists')
        return
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        p = Path(directory) / 'curated.json'
        data = {'corners': [{'id': 'copse', 'name': 'Copse', 'target_throttle_pct': 100}]}
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
