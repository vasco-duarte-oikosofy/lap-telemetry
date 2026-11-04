"""Re-verify the Road Atlanta P3 reference refresh from retained scratch data.

Checks, in order:
1. Every source partN shard still hashes to the frozen manifest.
2. The frozen merged file still hashes to the manifest.
3. The exported reference is the selected lap-17 segment of the frozen file.
4. Every other curated asset under product/data (+ generated modules/dist) is
   byte-unchanged, and only the expected files changed.
5. The whole-folder reference validator passes (provenance included) with the
   frozen copy registered as a session dir.

Writes artifacts/selection.json and artifacts/scope-audit.json.
"""
import hashlib
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[5]
ART = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'dev/scripts'))
import validate_reference_laps as validator  # noqa: E402
from export_fastest_reference_laps import find_complete_laps  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = json.loads((ART / 'source-manifest.json').read_text(encoding='utf-8'))
frozen = ROOT / manifest['frozen_file']

assert sha(frozen) == manifest['frozen_sha256'], 'frozen merged file changed after freeze'
sources = {rel: sha(ROOT / rel) == digest for rel, digest in manifest['source_sha256'].items()}
assert all(sources.values()), 'an original session shard changed after freeze'

table = pq.read_table(frozen)
lap_num, lap_time, start, end = min(find_complete_laps(table), key=lambda x: x[1])
ref_name = ('michelin-raceway-road-atlanta_dkr-engineering-4-elms25_time_'
            f'{int(lap_time // 60):02d}.{lap_time % 60:06.3f}.parquet')
selection = {
    'lap_number': lap_num,
    'time_s': round(lap_time, 4),
    'start_row': start,
    'end_row': end,
    'rows': end - start,
    'reference_file': f'product/data/reference-laps/{ref_name}',
    'superseded_reference': 'product/data/reference-laps/michelin-raceway-road-atlanta_dkr-engineering-4-elms25_time_01.16.304.parquet',
    'improvement_s': round(76.304 - lap_time, 4),
}
(ART / 'selection.json').write_text(json.dumps(selection, indent=2) + '\n', encoding='utf-8')

ref = ROOT / selection['reference_file']
assert ref.exists(), f'missing exported reference {ref}'
actual = pq.read_table(ref)
expected = table.slice(start, end - start)
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

expected_changed = {
    'product/data/track-coaching/michelin-raceway-road-atlanta_dkr-engineering-4-elms25.json',
    'product/data/track-coaching/michelin-raceway-road-atlanta_dkr-engineering-4-elms25.diagnostics.txt',
    'product/data/track-outlines/michelin-raceway-road-atlanta.json',
    'product/web/js/staticMichelinRacewayRoadAtlantaOutlineData.js',
    'product/dist/compare.html',
}
expected_removed = {selection['superseded_reference']}
unexpected = sorted((set(changed) | set(removed)) - expected_changed - expected_removed)
assert not unexpected, f'unexpected curated-asset changes: {unexpected}'

# Reference folder validator, with the frozen copy registered as a session dir.
validator.SESSION_DIRS = [Path('dev/sessions'), Path('sessions'), frozen.parent]
rc = validator.main()

audit = {
    'source_files_unchanged': f'{len(sources)}/{len(sources)}',
    'frozen_file_unchanged': True,
    'exported_reference_equals_selected_segment': True,
    'selection': selection,
    'curated_assets_checked': len(before),
    'curated_assets_changed': changed,
    'curated_assets_removed': removed,
    'unexpected_changes': unexpected,
    'other_references_unchanged': len(before) and True,
    'validator_exit_code': rc,
}
(ART / 'scope-audit.json').write_text(json.dumps(audit, indent=2) + '\n', encoding='utf-8')
print(json.dumps(audit, indent=2))
sys.exit(rc)
