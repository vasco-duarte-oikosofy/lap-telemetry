"""Slice 38: curate ONLY the new Long Beach/499P combo; refuse curated overwrites.

Input is the new-track generator's eight-event JSON (--detected). Reference must
already have been exported/validated by the guarded reference scripts. Official
turn numbering comes from https://www.gplb.com/circuit-map; manual flat geometry
comes from this reference's position/steering trace, not neighbouring brake events.
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
TRACK = 'grand-prix-of-long-beach'
CAR = 'ferrari-af-corse-2026-50-lm'
REF = ROOT / f'product/data/reference-laps/{TRACK}_{CAR}_time_01.15.889.parquet'
MODEL = ROOT / f'product/data/track-coaching/{TRACK}_{CAR}.json'
OUTLINE = ROOT / f'product/data/track-outlines/{TRACK}.json'
# Official T1..T11: negative steering = left (calibrated at T1), positive = right.
SIDES = ['left', 'right', 'left', 'right', 'right', 'left',
         'left', 'right', 'right', 'left', 'right']
# Full flat-turn geometry, reviewed on position/steering and the official map.
# These are not braking events, and must never be snapped to adjacent minima.
FLAT_ZONES = {3: (940.0, 950.0, 990.0), 7: (1680.0, 1725.0, 1760.0)}


def curate(detected):
    if detected['track_id'] != TRACK or detected['reference_lap']['car_id'] != CAR:
        raise ValueError('Wrong track/car generator input')
    events = detected['corners']
    if len(events) != 8 or any(abs(c['apex_s_m'] - apex) > 2 for c, apex in
                              zip(events, [730, 909, 1063, 1204, 1606, 1920, 2540, 2821])):
        raise ValueError('Unexpected detection geometry; review before curating')
    model = copy.deepcopy(detected)
    # Detector event -> official corner number. Two flat turns and T10 were missed.
    by_number = {n: copy.deepcopy(c) for n, c in zip([1, 2, 4, 5, 6, 8, 9, 11], events)}
    for number, (start, apex, end) in FLAT_ZONES.items():
        by_number[number] = dict(s_start_m=start, apex_s_m=apex, s_end_m=end,
                                 target_throttle_pct=100)
    # Last detected event spanned the left-hand T10 and the right-hand T11 hairpin.
    by_number[10] = dict(s_start_m=2620.0, apex_s_m=2690.0, s_end_m=2760.0)
    by_number[11]['s_start_m'] = 2761.0
    model['corners'] = []
    for number in range(1, 12):
        corner = by_number[number]
        corner.update(id=f't{number}', name=f'Turn {number}',
                      short_name=str(number) if number < 10 else {10: 'Ten', 11: 'Eleven'}[number],
                      apex_side=SIDES[number - 1], apex_side_source='manual')
        model['corners'].append(corner)
    model['reference_lap']['path'] = REF.relative_to(ROOT).as_posix()
    model['straight_zones'] = [
        dict(id='after-hairpin', s_start_m=2900.0, s_end_m=3180.0),
        dict(id='shoreline', s_start_m=0.0, s_end_m=450.0),
        dict(id='seaside', s_start_m=2000.0, s_end_m=2320.0),
    ]
    return model


def outline_from_ref(model):
    table = pq.read_table(REF)
    rows = sorted((s, x, z) for s, x, z, t in zip(
        table['lap_distance_m'].to_pylist(), table['pos_x_m'].to_pylist(),
        table['pos_z_m'].to_pylist(), table['lap_time_s'].to_pylist())
        if t >= 0 and all(v is not None and math.isfinite(v) for v in (s, x, z)))
    points = [dict(x=x, y=z) for _, x, z in rows]
    points.append(points[0])  # close the small start/finish sampling gap
    centerline = resample_polyline(points, 500)
    left, right = compute_boundaries(centerline, 5.0)
    outline = dict(
        schema_version=1, source='Single lap trajectory (synthetic +/-5m width)',
        track_name='Grand Prix of Long Beach', sim_track_name='Grand Prix of Long Beach',
        layout_name='default', coordinate_system='sim_xy', units='sim_units',
        track_name_mapping=dict(canonical_sim_track_name=TRACK,
                                canonical_lmu_track_name='Grand Prix of Long Beach',
                                accepted_sim_track_names=[TRACK],
                                accepted_lmu_track_names=['Grand Prix of Long Beach']),
        alignment=dict(method='trajectory_trace', width_per_side=5.0,
                       reference_lap=REF.relative_to(ROOT).as_posix(),
                       notes='Fastest guarded complete lap 10; full flat-turn shape retained.'),
        visual_qa=dict(status='pending', notes='Automated rendering check; by-eye live approval pending.'),
        caveats=['Constant 5m shell is synthetic, not measured street walls or track limits.',
                 'Centerline follows a racing line, not the geometric track center.'],
    )
    for key, values in [('centerline', centerline), ('left_boundary', left), ('right_boundary', right)]:
        outline[key] = [dict(x=round(p['x'], 3), y=round(p['y'], 3)) for p in values]
    # All numbered turns are official here, not an unreviewed detector sequence.
    outline['turns'] = bake_turns(TRACK, outline, {'corners': model['corners']}, REF)
    for turn in outline['turns']:
        turn['name'] = None
        turn['short_name'] = None  # map speaks T10 visually, not the speech alias Ten
    return outline


def outline_text(outline):
    # Five coordinates per line keeps 1500 points below the 437-line ceiling.
    parts = []
    for key, value in outline.items():
        if key in ('centerline', 'left_boundary', 'right_boundary', 'turns'):
            width = 1 if key == 'turns' else 5
            lines = [', '.join(json.dumps(v, separators=(',', ':')) for v in value[i:i + width])
                     for i in range(0, len(value), width)]
            encoded = '[\n    ' + ',\n    '.join(lines) + '\n  ]'
        else:
            encoded = json.dumps(value, indent=2, ensure_ascii=False).replace('\n', '\n  ')
        parts.append('  ' + json.dumps(key) + ': ' + encoded)
    return '{\n' + ',\n'.join(parts) + '\n}\n'


def write_new(path, data, text):
    if path.exists():
        if json.loads(path.read_text(encoding='utf-8')) != data:
            raise ValueError(f'Refusing to overwrite curated data: {path}')
        return
    if len(text.splitlines()) > 437:
        raise ValueError(f'Line ceiling exceeded: {path}')
    path.write_text(text, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--detected', required=True, type=Path)
    args = parser.parse_args()
    model = curate(json.loads(args.detected.read_text(encoding='utf-8')))
    outline = outline_from_ref(model)
    # Verify existing data before any write, not after partially replacing assets.
    for path, data in ((MODEL, model), (OUTLINE, outline)):
        if path.exists() and json.loads(path.read_text(encoding='utf-8')) != data:
            raise ValueError(f'Refusing to overwrite curated data: {path}')
    write_new(MODEL, model, json.dumps(model, indent=2, ensure_ascii=False) + '\n')
    write_new(OUTLINE, outline, outline_text(outline))
    print(f'Created/verified ONLY {TRACK}/{CAR}: 11 official turns, flat T3/T7 geometry intact')


if __name__ == '__main__':
    main()
