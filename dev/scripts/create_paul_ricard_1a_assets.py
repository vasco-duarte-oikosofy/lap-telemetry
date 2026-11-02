"""Slice 24 initializer ONLY: reviewed Paul Ricard 1A / Ginetta race assets.

Names: circuitpaulricard.com/images/2023/10/02/turnlocation.svg (official plan).
Geometry: valid race lap 10, 106.833862305s, source session 20261101T190458Z.
Six brake/lift events are NOT six corners. Restore the four WOT bends and
separate Hotel/Camp, the double Beausset and Lac/Pont from real steering/pedals.
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
TRACK = 'paul-ricard---1a'
CAR = 'dkr-engineering-4-elms25'
MODEL = ROOT / f'product/data/track-coaching/{TRACK}_{CAR}.json'
OUTLINE = ROOT / f'product/data/track-outlines/{TRACK}.json'
# id, official name (+ subdivision), speech alias, start/apex/end, side, flat.
# Two Beausset zones describe the two apices of ONE official double-right.
# Map numbers follow model ordinals, not the circuit's all-configurations T-list.
ZONES = [
    ('verrerie_1', 'S de la Verrerie 1', 'Verrerie 1', 560, 607, 710, 'left', True),
    ('verrerie_2', 'S de la Verrerie 2', 'Verrerie 2', 785, 852, 970, 'right', True),
    ('hotel_1', "Virage de l'Hôtel 1", 'Hôtel 1', 1102, 1279, 1298, 'right', False),
    ('hotel_2', "Virage de l'Hôtel 2", 'Hôtel 2', 1305, 1360, 1405, 'left', False),
    ('camp', 'Virage du Camp', 'Camp', 1406, 1480, 1496, 'right', False),
    ('sainte_baume', 'Virage de la Sainte-Baume', 'Sainte-Baume', 1544, 1600, 1640, 'right', False),
    ('mistral', 'Ligne Droite du Mistral', 'Mistral', 1780, 1841, 1910, 'left', True),
    ('signes', 'Courbe de Signes', 'Signes', 3674, 3871, 3880, 'right', False),
    ('beausset_1', 'Double Droite du Beausset 1', 'Beausset 1', 4053, 4265, 4330, 'right', False),
    ('beausset_2', 'Double Droite du Beausset 2', 'Beausset 2', 4331, 4394, 4431, 'right', False),
    ('bendor', 'Virage de Bendor', 'Bendor', 4569, 4732, 4769, 'left', False),
    ('garlaban', 'Courbe du Garlaban', 'Garlaban', 4810, 4846, 5070, 'right', True),
    ('lac', 'Virage du Lac', 'Lac', 5082, 5227, 5310, 'left', False),
    ('pont', 'Virage du Pont', 'Pont', 5311, 5377, 5398, 'right', False),
]


def curate(detected, ref):
    expected = [1480, 1600, 3871, 4394, 4732, 5377]
    events = detected['corners']
    if (detected['track_id'] != TRACK or detected['reference_lap']['car_id'] != CAR
            or len(events) != len(expected) or any(abs(c['apex_s_m'] - a) > 2
                                                  for c, a in zip(events, expected))):
        raise ValueError('Unexpected track/car/detector geometry; review before curating')
    ref = ref.resolve()
    if (ref.parent != ROOT / 'product/data/reference-laps' or
            ref.name != f'{TRACK}_{CAR}_time_01.46.834.parquet'):
        raise ValueError('Only the guarded slice-24 race reference is accepted')
    model = copy.deepcopy(detected)
    model['layout_id'] = '1a'
    model['reference_lap']['path'] = ref.relative_to(ROOT).as_posix()
    model['reference_lap']['lap_time_s'] = 106.834
    model['corners'] = []
    for cid, name, short, start, apex, end, side, flat in ZONES:
        c = dict(id=cid, name=name, short_name=short, s_start_m=float(start),
                 apex_s_m=float(apex), s_end_m=float(end), apex_side=side,
                 apex_side_source='manual')
        if flat:
            c['target_throttle_pct'] = 100
        model['corners'].append(c)
    return model


def make_outline(model, ref):
    t = pq.read_table(ref)
    duration = float(t.schema.metadata[b'authoritative_lap_time_s'])
    if (t.num_rows != 5323 or not all(t['lap_valid'].to_pylist()) or
            set(t['lap_number'].to_pylist()) != {10} or abs(duration - 106.834) > 0.001):
        raise ValueError('Reference differs from reviewed complete valid race lap 10')
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
        track_name='Paul Ricard - 1A', sim_track_name='Paul Ricard - 1A', layout_name='1a',
        coordinate_system='sim_xy', units='sim_units', lap_length_m=model['lap_length_m'],
        track_name_mapping=dict(canonical_sim_track_name=TRACK,
                                canonical_lmu_track_name='Paul Ricard - 1A',
                                accepted_sim_track_names=[TRACK, 'paul-ricard-1a'],
                                accepted_lmu_track_names=['Paul Ricard - 1A']),
        alignment=dict(method='trajectory_trace', width_per_side=5.0,
                       reference_lap=ref.resolve().relative_to(ROOT).as_posix(),
                       notes='Guarded race lap 10; original 1A Verrerie, no Mistral chicane.'),
        visual_qa=dict(status='pending', notes='Automated render checked; live by-eye approval pending.'),
        caveats=['Constant 5m shell is synthetic, not measured track limits.',
                 'Centerline follows a racing line, not the geometric track center.',
                 '14 model-ordinal labels: 13 layout bends with the double Beausset subdivided.',
                 'Names follow the official circuit plan; no shortcut/Tour placeholders.'],
    )
    for key, values in [('centerline', center), ('left_boundary', left), ('right_boundary', right)]:
        outline[key] = [dict(x=round(p['x'], 3), y=round(p['y'], 3)) for p in values]
    outline['turns'] = bake_turns(TRACK, outline, {'corners': model['corners']}, ref)
    # Map display aliases are independent of spoken aliases.
    next(turn for turn in outline['turns'] if turn['id'] == 'sainte_baume')['short_name'] = 'Ste-Baume'
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
    print('Created/verified ONLY Paul Ricard 1A / P3: 14 reviewed zones, four full flat bends')


if __name__ == '__main__':
    main()
