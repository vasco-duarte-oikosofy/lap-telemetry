"""Slice 52: Silverstone National Circuit / Ferrari 296 GT3 — new car, existing track.

The track already carries curated assets for the Ginetta LMP3 (slice 51). The
live coach resolves by (track, canonical car) — bug 27 — so the 296 GT3 needed
its own reference lap and coaching model or it resolved to nothing.

What this pins:

- the guarded export of the fastest complete lap (0:54.295, lap 8 of the
  2026-11-14 quali) and the frozen race session it was scanned against;
- the six official Silverstone National zones, seeded from the curated P3 model
  so names/IDs/apex sides and the two flat-bend `target_throttle_pct: 100`
  markers (`Maggots`, `Woodcote`) are byte-identical across both car models;
- that the geometry of the four braked corners comes from *this* car's lap;
- that the existing outline was NOT re-baked (it still follows the P3 model the
  baker selects), and both models agree on the simulator distance axis.
"""
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'product/python'))
from lap_telemetry.coach.reference_resolver import resolve_reference_lap
from lap_telemetry.coach.track_model import load_track_coaching_model
from lap_telemetry.coach.track_model_resolver import resolve_track_model
from lap_telemetry.parquet_utils import build_segments

TRACK = 'silverstone-national-circuit'
CAR = 'vista-af-corse-2026-21-lm'
VEHICLE = 'Vista AF Corse 2026 #21:LM'
P3_CAR = 'dkr-engineering-4-elms25'
P3_VEHICLE = 'DKR Engineering #4:ELMS25'
SESSION = ROOT / 'sessions/session_20261114T065241Z_silverstone-national-circuit_lmu_quali.parquet'
MODEL = ROOT / f'product/data/track-coaching/{TRACK}_{CAR}.json'
P3_MODEL = ROOT / f'product/data/track-coaching/{TRACK}_{P3_CAR}.json'
OUTLINE = ROOT / f'product/data/track-outlines/{TRACK}.json'
REF_NAME = f'{TRACK}_{CAR}_time_00.54.295.parquet'
# Official Silverstone National corner list, in lap order.
ZONES = [
    ('copse', 'Copse', 'right'),
    ('maggots', 'Maggots', 'left'),
    ('becketts', 'Becketts', 'right'),
    ('brooklands', 'Brooklands', 'left'),
    ('luffield', 'Luffield', 'right'),
    ('woodcote', 'Woodcote', 'right'),
]
FLAT = {'maggots', 'woodcote'}
# The flat left/right have no braking event on any lap, so they are preserved
# from the curated P3 model rather than refreshed from the detected events.
PRESERVED = {'maggots', 'woodcote'}
CURATION_FIELDS = ('id', 'name', 'apex_side', 'apex_side_source', 'target_throttle_pct', 'short_name')
passed = failed = 0


def ok(value, label):
    global passed, failed
    passed += bool(value)
    failed += not bool(value)
    print(f'[{"PASS" if value else "FAIL"}] {label}')


def main():
    refs = list((ROOT / 'product/data/reference-laps').glob(f'{TRACK}_{CAR}_time_*.parquet'))
    ok(len(refs) == 1, 'exactly one Silverstone National / Ferrari 296 GT3 reference exists')
    ok(refs and refs[0].name == REF_NAME, 'reference is the guarded fastest-lap file')
    ok(MODEL.exists(), 'new National/F296 coaching model exists')
    ok(not any('time_' in p.name and p.name.startswith(f'{TRACK}_{CAR}_time_00.50')
               for p in (ROOT / 'product/data/reference-laps').iterdir()),
       'the P3 50s reference was not reused for the GT3')
    if not refs or not MODEL.exists():
        return

    raw = json.loads(MODEL.read_text(encoding='utf-8'))
    ref = ROOT / raw['reference_lap']['path']
    ok(ref.exists() and ref.name == REF_NAME, 'model points at the exported reference')
    ok('\\' not in raw['reference_lap']['path'], 'committed reference path is portable')
    t = pq.read_table(ref)
    duration = float(t.schema.metadata[b'authoritative_lap_time_s'])
    ok(len(build_segments(t['lap_number'].to_pylist())) == 1, 'reference is a contiguous segment')
    ok(set(t['lap_number'].to_pylist()) == {8}, 'quali lap 8 selected, not a lap_number filter')
    ok(all(t['lap_valid'].to_pylist()), 'reference is valid in every frame')
    ok(t.num_rows == 2703, 'reference contains exactly the selected 2703 source rows')
    ok(abs(duration - 54.295) < 0.001, 'authoritative quali time 0:54.295')
    ok(abs(raw['reference_lap']['lap_time_s'] - duration) < 0.001,
       'model and reference authoritative times agree')
    ok(raw['reference_lap']['car_id'] == CAR, 'reference is attributed to the F296 car id')

    m = load_track_coaching_model(MODEL)
    ok(m.track_id == TRACK and m.layout_id == 'national', 'model is the National layout itself')
    ok(2630 < m.lap_length_m <= 2639.1,
       f'model uses the same 2.64 km simulator axis as the P3 model ({m.lap_length_m})')
    ok([c.id for c in m.corners] == [z[0] for z in ZONES], 'six reviewed zones in lap order')
    ok([c.name for c in m.corners] == [z[1] for z in ZONES], 'official Silverstone National names')
    ok([c.apex_side for c in m.corners] == [z[2] for z in ZONES], 'apex sides match the official plan')
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
           f'{cid}: this reference is at full throttle and zero brake across the zone')
    ok(all(a.s_end_m <= b.s_start_m for a, b in zip(m.corners, m.corners[1:])),
       'the six zones stay non-overlapping in lap order')
    ok(len([c for c in m.corners if c.s_start_m < 1746 and 1086 <= c.apex_s_m <= 1746]) == 0,
       'the Wellington Straight carries no corner at all')

    # Geometry of the four braked corners comes from this car's lap, not the P3.
    p3 = load_track_coaching_model(P3_MODEL)
    p3_by_id = {c.id: c for c in p3.corners}
    for c in m.corners:
        if c.id in PRESERVED:
            ok(c.apex_s_m == p3_by_id[c.id].apex_s_m,
               f'{c.id}: flat bend keeps the reviewed geometry verbatim')
        else:
            ok(abs(c.apex_s_m - p3_by_id[c.id].apex_s_m) > 0.5,
               f'{c.id}: braked corner geometry refreshed from the F296 lap')

    # Curated content is byte-identical across both car models.
    p3_raw = json.loads(P3_MODEL.read_text(encoding='utf-8'))
    raw_corners = {c['id']: c for c in raw['corners']}
    for a in p3_raw['corners']:
        b = raw_corners[a['id']]
        for field in CURATION_FIELDS:
            ok(a.get(field) == b.get(field), f"{b['name']}: curated {field} preserved ({b.get(field)!r})")

    # The outline was deliberately not re-baked: it still follows the P3 model.
    o = json.loads(OUTLINE.read_text(encoding='utf-8'))
    ok(o['lap_length_m'] == m.lap_length_m, 'outline and F296 model share the simulator axis')
    ok([x['id'] for x in o['turns']] == [z[0] for z in ZONES], 'outline still carries the six names')
    ok([x['apex_s_m'] for x in o['turns']] == [round(c.apex_s_m, 1) for c in p3.corners],
       'outline anchors still follow the P3 model it was baked from (no re-bake in this slice)')
    ok([x['apex_s_m'] for x in o['turns']] != [round(c.apex_s_m, 1) for c in m.corners],
       'outline was not re-baked from the new F296 model (out of scope in this slice)')

    # Live coach resolution by (track, car) — bug 27.
    ok(resolve_reference_lap('Silverstone National Circuit', vehicle_name=VEHICLE) == ref,
       'live coach resolves the National/F296 reference')
    ok(resolve_track_model('Silverstone National Circuit', vehicle_name=VEHICLE) == MODEL,
       'live coach resolves the National/F296 model')
    ok(resolve_track_model('Silverstone National Circuit', vehicle_name=P3_VEHICLE) == P3_MODEL,
       'the P3 keeps resolving to its own National model')
    ok(resolve_reference_lap('Silverstone National Circuit', vehicle_name=P3_VEHICLE) != ref,
       'the GT3 reference is not handed to the P3')


if __name__ == '__main__':
    main()
    print(f'{passed}/{passed + failed} assertions passed')
    sys.exit(bool(failed))
