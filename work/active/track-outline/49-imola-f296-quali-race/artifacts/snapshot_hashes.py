"""Hash every curated asset before the Imola F296 refresh (scope-audit baseline).

Covers product/data (references, coaching models, outlines, catalog) plus the
generated static outline modules and the bundle, so the slice can prove it only
touched the intended files.

    $(node dev/scripts/python.js) work/active/track-outline/49-imola-f296-quali-race/artifacts/snapshot_hashes.py --before
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
ART = Path(__file__).resolve().parent
PATTERNS = [
    'product/data/**/*',
    'product/web/js/static*OutlineData.js',
    'dist/compare.html',
]
SKIP_SUFFIXES = {'.pyc'}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser()
parser.add_argument('--before', action='store_true')
args = parser.parse_args()
name = 'before-hashes.json' if args.before else 'after-hashes.json'

hashes = {}
for pattern in PATTERNS:
    for path in ROOT.glob(pattern):
        if not path.is_file() or path.suffix in SKIP_SUFFIXES:
            continue
        hashes[str(path.relative_to(ROOT)).replace('\\', '/')] = sha(path)

(ART / name).write_text(json.dumps(dict(sorted(hashes.items())), indent=2) + '\n', encoding='utf-8')
print(f'{len(hashes)} files hashed -> artifacts/{name}')
