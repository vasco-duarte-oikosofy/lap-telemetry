"""Seed the Ferrari 296 GT3 coaching model for Silverstone National from the curated P3 model.

There is no `silverstone-national-circuit_vista-af-corse-2026-21-lm.json` yet.
The track already has a curated 6-corner model for the Ginetta LMP3 (slice 51),
so the new car's model is seeded from it — official names, IDs, apex sides,
`apex_side_source` and the two flat-bend `target_throttle_pct: 100` markers are
copied verbatim — and its geometry is then refreshed from the new reference by
`update_reference_and_coaching_model.py --ref …`.

`lap_length_m` stays 2639.1: it is the same simulator distance axis the P3 model
and the baked outline use, and the outline's turn anchors are normalised by it.

    py work/active/track-outline/52-silverstone-national-f296/artifacts/seed_model_from_curated.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
COACHING = ROOT / 'product/data/track-coaching'
SRC = COACHING / 'silverstone-national-circuit_dkr-engineering-4-elms25.json'
DST = COACHING / 'silverstone-national-circuit_vista-af-corse-2026-21-lm.json'
REF = 'product/data/reference-laps/silverstone-national-circuit_vista-af-corse-2026-21-lm_time_00.54.295.parquet'

src = json.loads(SRC.read_text(encoding='utf-8'))

model = {
    'schema_version': src['schema_version'],
    'track_id': src['track_id'],
    'layout_id': src['layout_id'],
    'reference_lap': {
        'path': REF,
        'car_id': 'vista-af-corse-2026-21-lm',
        'lap_time_s': 54.295,
        'detection_method': 'throttle_brake_v1',
    },
    'lap_length_m': src['lap_length_m'],
    # Copy the curation verbatim; only the geometry will be refreshed.
    'corners': [dict(c) for c in src['corners']],
    'straight_zones': list(src.get('straight_zones', [])),
}

assert not DST.exists(), f'{DST} already exists - this initializer is one-shot'
DST.write_text(json.dumps(model, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print(f'seeded {DST.relative_to(ROOT)} with {len(model["corners"])} curated corners')
