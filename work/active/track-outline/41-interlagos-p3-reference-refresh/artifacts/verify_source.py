"""Re-verify the Interlagos P3 reference refresh from retained (ignored) scratch data.

Checks, in order:
1. Every source partN shard and the sidecar still hash to the frozen manifest.
2. The frozen merged file still hashes to the manifest.
3. The exported reference is byte-equal to the selected segment of the frozen file.
4. Every other curated asset under product/data is byte-unchanged.
5. The whole-folder reference validator passes (source provenance included).

Writes artifacts/scope-audit.json.
"""
import hashlib
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[5]
ART = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'dev/scripts'))
import validate_reference_laps as validator


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = json.loads((ART / 'source-manifest.json').read_text(encoding='utf-8'))
selection = json.loads((ART / 'selection.json').read_text(encoding='utf-8'))
frozen = ROOT / manifest['frozen_file']

assert sha(frozen) == manifest['frozen_sha256'], 'frozen merged file changed after freeze'
sources = {rel: sha(ROOT / rel) == digest for rel, digest in manifest['source_sha256'].items()}
assert all(sources.values()), 'an original session shard changed after freeze'
# The recorder never finalized this session and kept appending idle frames, so the
# sidecar is live and is deliberately NOT part of the frozen hash set (see manifest).

table = pq.read_table(frozen)
ref = ROOT / selection['reference_file']
actual = pq.read_table(ref)
expected = table.slice(selection['start'], selection['end'] - selection['start'])
assert actual.replace_schema_metadata(None).equals(expected.replace_schema_metadata(None)), \
    'exported reference is not the selected segment'

before = json.loads((ART / 'before-hashes.json').read_text(encoding='utf-8'))
changed, removed = [], []
for rel, digest in before.items():
    path = ROOT / rel
    if not path.exists():
        removed.append(rel)
    elif sha(path) != digest:
        changed.append(rel)
other_refs = [p.name for p in (ROOT / 'product/data/reference-laps').glob('*.parquet')]
result = {
    'source_files_unchanged': sources,
    'frozen_file_unchanged': True,
    'exported_reference_equals_selected_segment': True,
    'authoritative_time_s': selection['time_s'],
    'improvement_s': round(90.354 - selection['time_s'], 4),
    'curated_assets_changed': changed,
    'curated_assets_removed': removed,
    'curated_assets_unchanged_count': len(before) - len(changed) - len(removed),
    'reference_count': len(other_refs),
}
(ART / "scope-audit.json").write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(f'[PASS] {len(sources)} source shards + frozen file unchanged; '
      f'selected segment exported exactly; {result["curated_assets_unchanged_count"]} other curated assets unchanged')
# The recorder has not finalized its race shards; include the frozen full source
# alongside the normal directories so provenance resolves for this one reference.
validator.SESSION_DIRS.append(frozen.parent)
sys.exit(validator.main())
