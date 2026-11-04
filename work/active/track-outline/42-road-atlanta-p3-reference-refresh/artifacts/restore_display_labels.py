"""Restore curated outline display labels after bake_outline_turns.py.

The bake takes a turn's map label from the model's `short_name`, but the model's
`short_name` is a *speech* alias ("1", "Ten A") while the map label is curated
separately (Road Atlanta shows only "Esses"). `test_outline_turns.js` pins the
map labels in BAKED_SHORT_NAMES, so a re-bake must restore them.

Only `name` / `short_name` are copied from the pre-bake outline; every anchor
field (apex_s_m, x, y, outward, tangent) keeps the freshly baked value.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
SLUG = 'michelin-raceway-road-atlanta'
OUTLINE = ROOT / 'product/data/track-outlines' / f'{SLUG}.json'
BEFORE = ROOT / 'var/tmp/road-atlanta-p3/outline-before.json'

before = json.loads(BEFORE.read_text(encoding='utf-8'))
outline = json.loads(OUTLINE.read_text(encoding='utf-8'))

assert len(before['turns']) == len(outline['turns']), 'turn count changed'
restored = 0
for old, new in zip(before['turns'], outline['turns']):
    assert old['id'] == new['id'], f"turn order changed: {old['id']} vs {new['id']}"
    for field in ('name', 'short_name'):
        if new.get(field) != old.get(field):
            new[field] = old.get(field)
            restored += 1

OUTLINE.write_text(json.dumps(outline, indent=2) + '\n', encoding='utf-8')
print(f'restored {restored} display-label field(s) on {SLUG}')
