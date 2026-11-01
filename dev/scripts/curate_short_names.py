#!/usr/bin/env python3
"""Preview/check/write reviewed coaching aliases, changing short_name ONLY.

No blanket word stripping: e.g. Netz Hairpin must remain distinct from Netz.
Existing curated aliases are reused across cars, except explicit user-selected
full-name exceptions. Numbers >=10 are spelt for TTS.
Run without flags to review, --check to audit, --write to persist and audit.
"""
import argparse
import copy
import json
import re
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parents[2] / 'product/data/track-coaching'
# User-selected proper names stay intact, even if older curation shortened them.
FULL_NAME_EXCEPTIONS = {
    'Curva Grande', 'Descida do Lago', 'Descida do Lago 1', 'Descida do Lago 2',
}
# Reviewed additions. Other existing hand-curated aliases are authoritative.
REVIEWED = {
    'Farm Curve': 'Farm', 'The Link': 'Link', 'The Loop': 'Loop',
    'Andretti Hairpin': 'Andretti',
    'Dunlop Curve': 'Dunlop', 'Dunlop Bypass': 'Dunlop',
    'First Corner': 'First', '13th Corner': 'Thirteenth',
    'Double left of Pouhon': 'Pouhon', 'Courbe Paul-Frère': 'Paul-Frère',
    "Speaker's Corner": "Speaker's", 'Sunset Bend': 'Sunset',
    'Flat to Mistral': 'Mistral', 'Hairpin Shortcut': 'Shortcut',
    'La Bretelle': 'Bretelle', 'S du Village': 'Village',
    'Ford Chicane 1': 'Ford 1', 'Ford Chicane 2': 'Ford 2',
    'Turn 1 — Elf': 'Elf', 'Turn 5 — Seat': 'Seat',
    # Do not conflate two different kinks or discard their turn numbers.
    'Turn 2 (Kink)': 'Kink 2', 'Turn 4 (Kink)': 'Kink 4',
    'Corkscrew 8a': 'Corkscrew 8 A',
}
ONES = ('Zero One Two Three Four Five Six Seven Eight Nine Ten Eleven Twelve '
        'Thirteen Fourteen Fifteen Sixteen Seventeen Eighteen Nineteen').split()
TENS = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety']


def spoken_number(value):
    if value < 10:
        return str(value)
    if value < 20:
        return ONES[value]
    if value < 100:
        tens, ones = divmod(value, 10)
        return TENS[tens] + (' ' + ONES[ones] if ones else '')
    if value == 100:
        return 'One Hundred'
    raise ValueError(f'Unreviewed corner number: {value}')


def spell_numbers(name):
    return re.sub(r'(?<!\w)(\d+)([A-Za-z]?)(?!\w)',
                  lambda m: spoken_number(int(m[1])) + (' ' + m[2].upper() if m[2] else ''), name)


def plan_changes(directory=MODELS_DIR):
    models = [(p, json.loads(p.read_text(encoding='utf-8')))
              for p in sorted(directory.glob('*.json'))]
    aliases = dict(REVIEWED)
    curated = {}
    for _, model in models:
        for corner in model['corners']:
            if corner.get('short_name') and corner['name'] not in FULL_NAME_EXCEPTIONS:
                choices = curated.setdefault(corner['name'], set())
                choices.add(corner['short_name'])
    for name, choices in curated.items():
        if len(choices) != 1:
            raise ValueError(f'Conflicting curated aliases for {name}: {choices}')
        aliases[name] = next(iter(choices))
    changes = []
    for path, model in models:
        ids = [c['id'] for c in model['corners']]
        if len(set(ids)) != len(ids):
            raise ValueError(f'Duplicate corner IDs in {path}')
        for corner in model['corners']:
            name = corner['name']
            alias = (name if name in FULL_NAME_EXCEPTIONS
                     else corner.get('short_name') or aliases.get(name, name))
            numbered = re.fullmatch(r'turn\s+(\d+[A-Za-z]?)', name, re.I)
            if numbered and not corner.get('short_name'):
                alias = numbered[1]
            alias = spell_numbers(alias)
            if len(name.split()) < 2 and alias == name and not corner.get('short_name'):
                continue
            if alias != corner.get('short_name'):
                changes.append((path, corner, name, alias))
    return changes


def without_aliases(model):
    result = copy.deepcopy(model)
    for corner in result['corners']:
        corner.pop('short_name', None)
    return result


def apply_changes(changes):
    pending = {}
    for path, corner, _, alias in changes:
        pending.setdefault(path, {})[corner['id']] = (corner, alias)
    staged = {}
    for path, items in pending.items():
        raw = path.read_bytes()
        text = raw.decode('utf-8')
        newline = '\r\n' if b'\r\n' in raw else '\n'
        before = json.loads(text)
        expected = copy.deepcopy(before)
        for corner in expected['corners']:
            if corner['id'] in items:
                old, alias = items[corner['id']]
                if corner != old:
                    raise ValueError(f'Stale preview: {path}/{corner["id"]}')
                corner['short_name'] = alias
        compact = len(text.splitlines()) > 437
        seen = set()

        def replace(match):
            block = match[0]
            obj = json.loads(block)
            if 'name' not in obj or obj.get('id') not in items:
                return block
            old, alias = items[obj['id']]
            if obj != old:
                raise ValueError(f'Ambiguous object: {path}/{obj["id"]}')
            seen.add(obj['id'])
            if compact:
                obj['short_name'] = alias
                return json.dumps(obj, ensure_ascii=True)
            value = json.dumps(alias, ensure_ascii=b'\\u' in raw)
            if 'short_name' in obj:
                return re.sub(r'("short_name"\s*:\s*)("(?:\\.|[^"\\])*"|null)',
                              lambda m: m[1] + value, block)
            # Insert next to name, retaining original newlines/indentation.
            field = re.search(r'(?P<indent>[ \t]*)"name"\s*:\s*"(?:\\.|[^"\\])*"', block)
            spacer = newline + field['indent'] if '\n' in block else ' '
            return (block[:field.end()] + ',' + spacer + '"short_name": '
                    + value + block[field.end():])

        updated = re.sub(r'\{[^{}]*\}', replace, text)
        if seen != set(items):
            raise ValueError(f'Unmatched corners: {path}: {set(items) - seen}')
        after = json.loads(updated)
        if after != expected or without_aliases(after) != without_aliases(before):
            raise ValueError(f'Non-alias change refused: {path}')
        if len(updated.splitlines()) > 437:
            raise ValueError(f'File line ceiling exceeded: {path}')
        staged[path] = updated.encode('utf-8')
    for path, raw in staged.items():
        path.write_bytes(raw)
    return len(staged)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true')
    mode.add_argument('--write', action='store_true')
    args = parser.parse_args()
    changes = plan_changes()
    for path, _, name, alias in changes:
        print(f'{path.name}: {name} -> {alias}')
    print(f'{len(changes)} alias changes in {len({c[0] for c in changes})} models')
    if args.write:
        print(f'Written and audited {apply_changes(changes)} models')
    return int(bool(changes) and args.check)


if __name__ == '__main__':
    raise SystemExit(main())
