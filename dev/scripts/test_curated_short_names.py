"""Slice 13: corpus-wide spoken-name coverage and guarded writer regressions."""
import copy
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'dev/scripts'))
sys.path.insert(0, str(ROOT / 'product/python'))
from curate_short_names import plan_changes, apply_changes, spell_numbers
from lap_telemetry.coach.track_model import load_track_coaching_model
from lap_telemetry.coach.facts import CornerLoss, LapComparisonFacts
from lap_telemetry.coach.template_adapter import TemplateAdapter

passed = failed = 0


def ok(condition, label):
    global passed, failed
    if condition:
        passed += 1
        print(f'[PASS] {label}')
    else:
        failed += 1
        print(f'[FAIL] {label}')


def test_corpus():
    paths = sorted((ROOT / 'product/data/track-coaching').glob('*.json'))
    ok(len(paths) >= 33, f'all {len(paths)} coaching models are audited')
    expected = {
        'Farm Curve': 'Farm', 'Turn 10A': 'Ten A', 'Turn 10B': 'Ten B',
        'Turn 1': '1', 'Turn 9': '9', '100R': 'One Hundred R',
        'Lesmo 1': 'Lesmo 1', 'Lesmo 2': 'Lesmo 2',
        'Variante della Roggia 1': 'Roggia 1',
        'Variante della Roggia 2': 'Roggia 2',
        'Variante Ascari 3': 'Ascari 3',
        'Acque Minerali 1': 'Acque 1', 'Acque Minerali 2': 'Acque 2',
        'Netz Hairpin': 'Netz Hairpin',
        'Becketts Entry': 'Becketts Entry', 'Becketts Exit': 'Becketts Exit',
        'Turn 2 (Kink)': 'Kink 2', 'Turn 4 (Kink)': 'Kink 4',
        '13th Corner': 'Thirteenth',
        'Turn 12': 'Twelve', 'turn 69': 'Sixty Nine',
    }
    seen = set()
    for path in paths:
        model = load_track_coaching_model(path)
        missing = [c.name for c in model.corners
                   if len(c.name.split()) >= 2 and not c.short_name]
        ok(not missing, f'{path.name}: all multiword corners have short names: {missing}')
        raw_digits = [c.display_name for c in model.corners
                      if re.search(r'\d{2,}', c.display_name)]
        ok(not raw_digits, f'{path.name}: no digit-by-digit 10+ speech: {raw_digits}')
        for c in model.corners:
            if c.name in expected:
                seen.add(c.name)
                ok(c.display_name == expected[c.name],
                   f'{path.stem}/{c.id}: {c.name} -> {expected[c.name]} (got {c.display_name})')
        ok(len(path.read_text(encoding='utf-8').splitlines()) <= 437,
           f'{path.name}: within file line ceiling')
    ok(set(expected) <= seen, 'all named regressions exercise real corpus entries')
    ok(not plan_changes(), 'whole corpus is curated, consistent across cars, and idempotent')
    ok(spell_numbers('Example 12') == 'Example Twelve',
       'existing aliases also get 10+ spelling without changing their words')
    ok(spell_numbers('Ascari 3') == 'Ascari 3', 'single digit subdivision stays in place')


def test_writer():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'fixture.json'
        # Keep CRLF, compact objects, Unicode escapes, fields and final-newline style.
        original = ('{\r\n  "corners": [\r\n'
                    '    { "id": "farm", "name": "Farm Curve", "s_start_m": 5 },\r\n'
                    '    { "id": "ten", "name": "Turn 10A", "s_end_m": 42 },\r\n'
                    '    { "id": "curated", "name": "Curva Caf\\u00e9", "short_name": "Cafe" }\r\n'
                    '  ],\r\n  "reference_lap": { "path": "unchanged.parquet" }\r\n}')
        path.write_bytes(original.encode('utf-8'))
        before = json.loads(original)
        changes = plan_changes(Path(directory))
        ok(len(changes) == 2, 'preview proposes missing names only; curated alias survives')
        ok(path.read_bytes() == original.encode('utf-8'), 'preview never writes')
        apply_changes(changes)
        after_bytes = path.read_bytes()
        after = json.loads(after_bytes)
        ok(after['corners'][0].get('short_name') == 'Farm', 'writer persists Farm alias')
        ok(after['corners'][1].get('short_name') == 'Ten A', 'writer persists Ten A alias')
        ok(after['corners'][2]['short_name'] == 'Cafe', 'writer preserves existing curation')
        stripped = copy.deepcopy(after)
        for c in stripped['corners'][:2]:
            c.pop('short_name', None)
        ok(stripped == before, 'writer changes only short_name, no metadata or geometry')
        ok(b'\\u00e9' in after_bytes and not after_bytes.endswith(b'\n'),
           'writer preserves escaped Unicode and missing final newline')
        ok(b'\n' not in after_bytes.replace(b'\r\n', b''), 'writer preserves CRLF')
        ok(not plan_changes(Path(directory)), 'second preview is empty')
        apply_changes(plan_changes(Path(directory)))
        ok(path.read_bytes() == after_bytes, 'second write is byte-idempotent')
        path.write_bytes(original.encode('utf-8'))
        stale_changes = plan_changes(Path(directory))
        stale_bytes = original.replace('"s_end_m": 42', '"s_end_m": 43').encode('utf-8')
        path.write_bytes(stale_bytes)
        refused = False
        try:
            apply_changes(stale_changes)
        except ValueError:
            refused = True
        ok(refused and path.read_bytes() == stale_bytes,
           'writer refuses stale previews without overwriting changed geometry')


def test_spoken_template():
    model = load_track_coaching_model(
        ROOT / 'product/data/track-coaching/michelin-raceway-road-atlanta_dkr-engineering-4-elms25.json')
    corner = next(c for c in model.corners if c.name == 'Turn 10A')
    loss = CornerLoss(corner.id, corner.display_name, corner.apex_s_m,
                      'minimum_speed', 0.3, 100.0, 110.0, 'km/h', 'high')
    facts = LapComparisonFacts('lap_coaching_summary', model.track_id, 1, 0.3,
                               top_losses=[loss])
    text = TemplateAdapter.generate(facts)
    ok('Ten A' in text and '10A' not in text, f'template speaks the spelled turn: {text}')


if __name__ == '__main__':
    test_corpus()
    test_writer()
    test_spoken_template()
    print(f'{passed}/{passed + failed} assertions passed')
    sys.exit(bool(failed))
