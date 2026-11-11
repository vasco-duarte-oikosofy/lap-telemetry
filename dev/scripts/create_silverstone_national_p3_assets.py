"""Slice 51 initializer ONLY: reviewed Silverstone National / Ginetta P3 assets.

Layout identity: the National loop is the short Silverstone configuration. It
never touches the Arena complex (Abbey / Farm Curve / Village / The Link) and it
never reaches Becketts' left or the Hangar Straight: it runs the National pits
straight into Copse, the Maggots left flick, the Becketts right that peels onto
the Wellington Straight, then Brooklands, Luffield, Woodcote and back to the pits.
The lap stays within 9 m of the curated GP-ELMS reference line everywhere except
the National-only link at 1090-1180 m (max 35 m), which is exactly that
Maggots→Wellington peel-off.
Names: Silverstone's National corner list (Copse, Maggots, Becketts, Brooklands,
Luffield, Woodcote) + FIA turn-location plan; the GP-ELMS asset file is the
spelling reference. Maggots is the flat left flick and Becketts the braked right
(the "short left-right flick where the National peels off the Grand Prix track").
Geometry: valid practice lap 7, 50.859 s, source 20261111T172218Z.
The brake/lift detector finds only four events (Copse, Becketts, Brooklands,
Luffield): the flat Maggots left and the flat Woodcote right are invisible to it.
Refuse differing existing curation; future references use the guarded updater.
"""
import argparse
import copy
import json
import math
from pathlib import Path

import pyarrow.parquet as pq
from bake_outline_turns import bake_turns
from trajectory_to_outline import resample_polyline, compute_boundaries

ROOT = Path(__file__).resolve().parents[2]
TRACK = 'silverstone-national-circuit'
CAR = 'dkr-engineering-4-elms25'
TRACK_NAME = 'Silverstone National Circuit'
MODEL = ROOT / f'product/data/track-coaching/{TRACK}_{CAR}.json'
OUTLINE = ROOT / f'product/data/track-outlines/{TRACK}.json'
REFERENCE = f'{TRACK}_{CAR}_time_00.50.859.parquet'
LAP_TIME_S = 50.859
# Detector output this curation was reviewed against (apexes, metres).
DETECTED_APEXES = [358, 1045, 1906, 2084]
# id, official name, speech/map alias, start/apex/end, side, flat.
# Maggots (flat left) and Woodcote (flat right) carry no brake event at all, so
# they are curated by hand from the steering/throttle signals; the four detected
# events map to Copse, Becketts (the National peel-off), Brooklands and Luffield.
ZONES = [
    ('copse', 'Copse', None, 242, 359, 435, 'right', False),
    ('maggots', 'Maggots', None, 790, 836, 860, 'left', True),
    ('becketts', 'Becketts', None, 861, 1045, 1110, 'right', False),
    ('brooklands', 'Brooklands', None, 1744, 1906, 1955, 'left', False),
    ('luffield', 'Luffield', None, 2003, 2084, 2190, 'right', False),
    ('woodcote', 'Woodcote', None, 2360, 2469, 2580, 'right', True),
]


def curate(detected, ref):
    events = detected['corners']
    if (detected['track_id'] != TRACK or detected['reference_lap']['car_id'] != CAR
            or len(events) != len(DETECTED_APEXES)
            or any(abs(c['apex_s_m'] - a) > 2 for c, a in zip(events, DETECTED_APEXES))):
        raise ValueError('Unexpected track/car/detector geometry; review before curating')
    ref = ref.resolve()
    if ref.parent != ROOT / 'product/data/reference-laps' or ref.name != REFERENCE:
        raise ValueError('Only the guarded slice-51 practice reference is accepted')
    model = copy.deepcopy(detected)
    model['layout_id'] = 'national'
    model['reference_lap']['path'] = ref.relative_to(ROOT).as_posix()
    model['reference_lap']['lap_time_s'] = LAP_TIME_S
    model['corners'] = []
    for cid, name, short, start, apex, end, side, flat in ZONES:
        c = dict(id=cid, name=name, s_start_m=float(start), apex_s_m=float(apex),
                 s_end_m=float(end), apex_side=side, apex_side_source='manual')
        if short:
            c['short_name'] = short
        if flat:
            c['target_throttle_pct'] = 100
        model['corners'].append(c)
    return model


def make_outline(model, ref):
    t = pq.read_table(ref)
    duration = float(t.schema.metadata[b'authoritative_lap_time_s'])
    if (t.num_rows != 2535 or not all(t['lap_valid'].to_pylist()) or
            set(t['lap_number'].to_pylist()) != {7} or abs(duration - LAP_TIME_S) > 0.001):
        raise ValueError('Reference differs from reviewed complete valid lap 7')
    rows = sorted((s, x, z) for s, x, z, lt in zip(
        t['lap_distance_m'].to_pylist(), t['pos_x_m'].to_pylist(),
        t['pos_z_m'].to_pylist(), t['lap_time_s'].to_pylist())
        if lt >= 0 and all(v is not None and math.isfinite(v) for v in (s, x, z)))
    points = [dict(x=x, y=z) for _, x, z in rows]
    points.append(points[0])
    center = resample_polyline(points, 500)
    left, right = compute_boundaries(center, 5.0)
    outline = dict(
        schema_version=1, source='Single lap trajectory (synthetic +/-5m width)',
        track_name=TRACK_NAME, sim_track_name=TRACK_NAME, layout_name='national',
        coordinate_system='sim_xy', units='sim_units', lap_length_m=model['lap_length_m'],
        track_name_mapping=dict(canonical_sim_track_name=TRACK,
                                canonical_lmu_track_name=TRACK_NAME,
                                accepted_sim_track_names=[TRACK],
                                accepted_lmu_track_names=[TRACK_NAME]),
        alignment=dict(method='trajectory_trace', width_per_side=5.0,
                       reference_lap=ref.resolve().relative_to(ROOT).as_posix(),
                       notes='Guarded practice lap 7; 2.64 km National loop: Copse, Maggots, '
                             'Becketts peel-off, Wellington Straight, Brooklands, Luffield, Woodcote.'),
        visual_qa=dict(status='pending', notes='Automated render checked; live by-eye approval pending.'),
        caveats=['Constant 5m shell is synthetic, not measured track limits.',
                 'Centerline follows a racing line, not the geometric track center.',
                 'Six official National turns; Maggots is the flat left flick and Woodcote the '
                 'flat right, neither of which the brake detector can see.',
                 'Not the International layout: no Abbey / Farm Curve / Village / The Link here.',
                 'Not the GP-ELMS layout: no Becketts complex, Hangar Straight, Stowe, Vale or Club.'],
    )
    for key, values in [('centerline', center), ('left_boundary', left), ('right_boundary', right)]:
        outline[key] = [dict(x=round(p['x'], 3), y=round(p['y'], 3)) for p in values]
    outline['turns'] = bake_turns(TRACK, outline, {'corners': model['corners']}, ref)
    return outline


def compact_outline(data):
    parts = []
    for key, value in data.items():
        if key in ('centerline', 'left_boundary', 'right_boundary', 'turns'):
            width = 1 if key == 'turns' else 5
            lines = [', '.join(json.dumps(v, ensure_ascii=False, separators=(',', ':'))
                               for v in value[i:i+width]) for i in range(0, len(value), width)]
            text = '[\n    ' + ',\n    '.join(lines) + '\n  ]'
        else:
            text = json.dumps(value, indent=2, ensure_ascii=False).replace('\n', '\n  ')
        parts.append('  ' + json.dumps(key) + ': ' + text)
    return '{\n' + ',\n'.join(parts) + '\n}\n'


def write_new(path, data, text):
    if path.exists():
        if json.loads(path.read_text(encoding='utf-8')) != data:
            raise ValueError(f'Refusing curated overwrite: {path}')
        return
    if len(text.splitlines()) > 437:
        raise ValueError(f'File line ceiling exceeded: {path}')
    path.write_text(text, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--detected', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    args = parser.parse_args()
    model = curate(json.loads(args.detected.read_text(encoding='utf-8')), args.reference)
    outline = make_outline(model, args.reference)
    for path, data in ((MODEL, model), (OUTLINE, outline)):
        if path.exists() and json.loads(path.read_text(encoding='utf-8')) != data:
            raise ValueError(f'Refusing curated overwrite before any asset write: {path}')
    write_new(MODEL, model, json.dumps(model, indent=2, ensure_ascii=False) + '\n')
    write_new(OUTLINE, outline, compact_outline(outline))
    print('Created/verified ONLY Silverstone National / Ginetta P3: 6 official zones, two flat bends')


if __name__ == '__main__':
    main()
