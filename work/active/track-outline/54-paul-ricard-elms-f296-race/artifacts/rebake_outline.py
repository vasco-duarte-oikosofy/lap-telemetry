"""Re-bake the Paul Ricard ELMS outline turn anchors from the refreshed model.

The outline's turn anchors must follow the curated model the baker selects
(repo contract). `paul-ricard---elms` has exactly one car model, so refreshing
the F296 model moves 7 apices and the outline goes STALE.

`bake_outline_turns.py` would rewrite the whole file with `indent=2` (~6000
lines, over the 437-line ceiling). This re-bakes in place with the compact
writer the slice-50 initializer uses, keeps the map-only `Ste-Baume` alias, and
re-points the provenance note at the new reference.

    py work/active/track-outline/54-paul-ricard-elms-f296-race/artifacts/rebake_outline.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'dev' / 'scripts'))

from bake_outline_turns import bake_turns
from create_paul_ricard_elms_assets import compact_outline

TRACK = 'paul-ricard---elms'
CAR = 'vista-af-corse-2026-21-lm'
OUTLINE = ROOT / f'product/data/track-outlines/{TRACK}.json'
MODEL = ROOT / f'product/data/track-coaching/{TRACK}_{CAR}.json'

model = json.loads(MODEL.read_text(encoding='utf-8'))
ref = ROOT / model['reference_lap']['path']
outline = json.loads(OUTLINE.read_text(encoding='utf-8'))

before = {turn['id']: turn['apex_s_m'] for turn in outline['turns']}

outline['turns'] = bake_turns(TRACK, outline, {'corners': model['corners']}, ref)
next(turn for turn in outline['turns'] if turn['id'] == 'sainte_baume')['short_name'] = 'Ste-Baume'
outline['alignment']['reference_lap'] = ref.resolve().relative_to(ROOT).as_posix()
outline['alignment']['notes'] = (
    'Guarded race lap 10 (2:06.440) of the 2026-11-14 race; 5.8 km 1C layout: '
    'Verrerie chicane + Chicane Nord.'
)

after = {turn['id']: turn['apex_s_m'] for turn in outline['turns']}
moved = {k: (before[k], after[k]) for k in before if abs(before[k] - after[k]) > 0.05}

text = compact_outline(outline)
lines = len(text.splitlines())
assert lines <= 437, f'line ceiling exceeded: {lines}'
OUTLINE.write_text(text, encoding='utf-8')
print(f'wrote {OUTLINE.relative_to(ROOT)} ({lines} lines), {len(moved)} anchors moved')
for key, (old, new) in moved.items():
    print(f'  {key:<18}{old:>8.1f} -> {new:>8.1f}  ({new - old:+.1f} m)')
