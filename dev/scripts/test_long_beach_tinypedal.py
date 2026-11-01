"""Long Beach scoped export and lap-distance normalization; no sibling/Qt required."""
import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'dev/scripts'))
import export_turn_labels_for_tinypedal as exporter

TRACK = 'Grand Prix of Long Beach'
SLUG = 'grand-prix-of-long-beach'
FAILURES = 0


def check(value, label):
    global FAILURES
    print(f"{'[PASS]' if value else '[FAIL]'} {label}")
    FAILURES += not value


def cli(arguments):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            return exporter.main(arguments)
        except SystemExit as error:
            return error.code


def main():
    outline = json.loads((ROOT / f'product/data/track-outlines/{SLUG}.json').read_text())
    model = json.loads((ROOT / f'product/data/track-coaching/{SLUG}_ferrari-af-corse-2026-50-lm.json').read_text())
    length = model['lap_length_m']
    check(outline.get('lap_length_m') == length == 3185.3,
          'outline explicitly carries the coaching apices simulator-distance axis')
    payload = exporter.build_payload(outline, TRACK)
    check([t['number'] for t in payload['turns']] == list(range(1, 12)), 'export includes all 11 official turn numbers')
    check(all(t['name'] is None and t['short_name'] is None for t in payload['turns']),
          'map keeps T1..T11, not spoken Ten/Eleven aliases')
    check(payload['lap_length_m'] == length, 'normalization uses simulator lap length, not noisy geometric length')
    check(all(t['s_frac'] == round(c['apex_s_m'] / length, 6)
              and t['apex_s_m'] == c['apex_s_m']
              for t, c in zip(payload['turns'], model['corners'])),
          'every fraction matches its reviewed coaching apex on the same distance axis')
    check(payload['turns'][2]['apex_s_m'] == 950 and payload['turns'][6]['apex_s_m'] == 1725,
          'flat Turn 3 and Turn 7 anchors preserved')
    legacy = dict(outline)
    legacy.pop('lap_length_m', None)
    check(exporter.build_payload(legacy, TRACK)['lap_length_m'] ==
          round(exporter.centerline_length_m(outline['centerline']), 3),
          'legacy outlines retain unchanged geometry-based normalization')
    for value in [0, -1, True, float('nan'), float('inf')]:
        refused = False
        try:
            exporter.build_payload({**outline, 'lap_length_m': value}, TRACK)
        except ValueError:
            refused = True
        check(refused, f'invalid explicit distance axis rejected: {value!r}')

    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        (path / f'{TRACK}.svg').write_text('<svg/>')
        (path / 'Silverstone International Circuit.svg').write_text('<svg/>')
        other = path / 'Silverstone International Circuit.turns.json'
        other.write_bytes(b'other-track-untouched\n')
        args = ['--trackmap', directory, '--out', directory, '--track', TRACK.upper()]
        code = cli(args)
        check(code == 0, 'track-only CLI matches normalized name and exports successfully')
        target = path / f'{TRACK}.turns.json'
        check(target.exists(), 'export filename is the exact TinyPedal track-map name')
        check(other.read_bytes() == b'other-track-untouched\n', 'scoped export never rewrites other tracks')
        if target.exists():
            check(json.loads(target.read_text()) == payload, 'written data matches reviewed source payload')
            before = target.read_bytes()
            check(cli(args + ['--check']) == 0 and target.read_bytes() == before,
                  'scoped check is green and read-only')
            check(cli(args) == 0 and target.read_bytes() == before, 'scoped export is byte-idempotent')
            target.write_text('{}')
            check(cli(args + ['--check']) == 1 and target.read_text() == '{}', 'stale scoped check fails without repairing files')
        check(cli(['--trackmap', directory, '--out', directory, '--track', 'Unknown Track']) != 0,
              'unknown requested map fails instead of falling back to an all-track export')
        check(other.read_bytes() == b'other-track-untouched\n', 'other track survives rechecks and errors')
    return bool(FAILURES)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:
        print(f'[FAIL] Long Beach export regression crashed: {error}')
        sys.exit(1)
