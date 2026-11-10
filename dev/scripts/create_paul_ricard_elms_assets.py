"""Slice 50 initializer ONLY: reviewed Paul Ricard ELMS / Ferrari 296 GT3 assets.

Layout identity: measured against the curated 1A reference line this lap leaves
the 1A path in exactly two places — the tight Verrerie `S` and the Chicane Nord
pair in the middle of the Mistral — which is the 5.8 km 1C/ELMS configuration
LMU records as "Paul Ricard - ELMS". 1A has neither.
Names: circuitpaulricard.com official turn-location plan + FIA turn-location list
(`S de la Verrerie V1/V2`, `Chicane Nord`) and the circuit's own corner guide for
the 1C layout; the LMU track guide uses the same Chicane Nord pair (T8/T9).
Geometry: valid practice lap 8, 127.601 s, source 20261110T175322Z.
Eleven detected brake/lift events are NOT sixteen corners: both flat WOT bends
are invisible to a brake/lift detector, the Hôtel/Camp/Lac groups are only
partly separated, and the compound Beausset is rejected by the detector's local
prominence rule. Refuse differing existing curation; future references use the
guarded updater.
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
TRACK = 'paul-ricard---elms'
CAR = 'vista-af-corse-2026-21-lm'
TRACK_NAME = 'Paul Ricard - ELMS'
MODEL = ROOT / f'product/data/track-coaching/{TRACK}_{CAR}.json'
OUTLINE = ROOT / f'product/data/track-outlines/{TRACK}.json'
REFERENCE = f'{TRACK}_{CAR}_time_02.07.601.parquet'
# Detector output this curation was reviewed against (apexes, metres).
DETECTED_APEXES = [621, 739, 1307, 1411, 1521, 1663, 2960, 3044, 3954, 4831, 5470]
# id, official name (+ subdivision), speech alias, start/apex/end, side, flat.
# Chicane Nord and the double Beausset are each split into their two apices.
# Map numbers follow model ordinals, not the circuit's all-configurations T-list
# (T8 Chicane Sud / T9 Chicane Montréal / T9b Chicane Nord are other options).
ZONES = [
    ('verrerie_1', 'S de la Verrerie 1', 'Verrerie 1', 484, 621, 690, 'left', False),
    ('verrerie_2', 'S de la Verrerie 2', 'Verrerie 2', 699, 739, 790, 'right', False),
    ('hotel_1', "Virage de l'Hôtel 1", 'Hôtel 1', 1187, 1307, 1340, 'right', False),
    ('hotel_2', "Virage de l'Hôtel 2", 'Hôtel 2', 1346, 1411, 1449, 'left', False),
    ('camp', 'Virage du Camp', 'Camp', 1462, 1521, 1550, 'right', False),
    ('sainte_baume', 'Virage de la Sainte-Baume', 'Sainte-Baume', 1610, 1663, 1690, 'right', False),
    ('mistral', 'Ligne Droite du Mistral', 'Mistral', 1815, 1886, 1920, 'left', True),
    ('chicane_nord_1', 'Chicane Nord 1', 'Chicane 1', 2805, 2960, 2992, 'left', False),
    ('chicane_nord_2', 'Chicane Nord 2', 'Chicane 2', 2994, 3044, 3072, 'right', False),
    ('signes', 'Courbe de Signes', 'Signes', 3780, 3954, 3995, 'right', False),
    ('beausset_1', 'Double Droite du Beausset 1', 'Beausset 1', 4178, 4390, 4442, 'right', False),
    ('beausset_2', 'Double Droite du Beausset 2', 'Beausset 2', 4442, 4482, 4530, 'right', False),
    ('bendor', 'Virage de Bendor', 'Bendor', 4688, 4831, 4895, 'left', False),
    ('garlaban', 'Courbe du Garlaban', 'Garlaban', 4900, 4949, 5170, 'right', True),
    ('lac', 'Virage du Lac', 'Lac', 5198, 5380, 5415, 'left', False),
    ('pont', 'Virage du Pont', 'Pont', 5415, 5470, 5500, 'right', False),
]


def curate(detected, ref):
    events = detected['corners']
    if (detected['track_id'] != TRACK or detected['reference_lap']['car_id'] != CAR
            or len(events) != len(DETECTED_APEXES)
            or any(abs(c['apex_s_m'] - a) > 2 for c, a in zip(events, DETECTED_APEXES))):
        raise ValueError('Unexpected track/car/detector geometry; review before curating')
    ref = ref.resolve()
    if ref.parent != ROOT / 'product/data/reference-laps' or ref.name != REFERENCE:
        raise ValueError('Only the guarded slice-50 practice reference is accepted')
    model = copy.deepcopy(detected)
    model['layout_id'] = 'elms'
    model['reference_lap']['path'] = ref.relative_to(ROOT).as_posix()
    model['reference_lap']['lap_time_s'] = 127.601
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
    if (t.num_rows != 6361 or not all(t['lap_valid'].to_pylist()) or
            set(t['lap_number'].to_pylist()) != {8} or abs(duration - 127.601) > 0.001):
        raise ValueError('Reference differs from reviewed complete valid lap 8')
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
        track_name=TRACK_NAME, sim_track_name=TRACK_NAME, layout_name='elms',
        coordinate_system='sim_xy', units='sim_units', lap_length_m=model['lap_length_m'],
        track_name_mapping=dict(canonical_sim_track_name=TRACK,
                                canonical_lmu_track_name=TRACK_NAME,
                                # The filename fallback flattens the " - " run, so
                                # replay without a sidecar slugs to paul-ricard-elms.
                                accepted_sim_track_names=[TRACK, 'paul-ricard-elms'],
                                accepted_lmu_track_names=[TRACK_NAME]),
        alignment=dict(method='trajectory_trace', width_per_side=5.0,
                       reference_lap=ref.resolve().relative_to(ROOT).as_posix(),
                       notes='Guarded practice lap 8; 5.8 km 1C layout: Verrerie chicane + Chicane Nord.'),
        visual_qa=dict(status='pending', notes='Automated render checked; live by-eye approval pending.'),
        caveats=['Constant 5m shell is synthetic, not measured track limits.',
                 'Centerline follows a racing line, not the geometric track center.',
                 '16 model-ordinal labels: 15 official turns with Chicane Nord and Beausset subdivided.',
                 'Two flat WOT bends (Mistral entry, Garlaban); the Verrerie is a real braking chicane here.',
                 'Not 1A / 1A-V2-Short / 3A: this layout has the Mistral chicane.'],
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
    print('Created/verified ONLY Paul Ricard ELMS / F296: 16 reviewed zones, two full flat bends')


if __name__ == '__main__':
    main()
