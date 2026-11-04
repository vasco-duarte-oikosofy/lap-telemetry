"""Snapshot curated-asset hashes (product/data, generated static modules, dist)."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
ART = Path(__file__).resolve().parent

targets = []
for base in ('product/data', 'product/web/js', 'product/dist'):
    for p in sorted((ROOT / base).rglob('*')):
        if p.is_file() and p.suffix in {'.json', '.parquet', '.js', '.txt', '.html'}:
            targets.append(p)

hashes = {
    p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in targets
}
(ART / 'before-hashes.json').write_text(
    json.dumps(hashes, indent=2) + '\n', encoding='utf-8')
print(f'{len(hashes)} curated assets hashed')
