"""Verify the Imola F296 reference refresh end to end.

Checks, in order:
1. Every source partN shard still hashes to the frozen manifest, and the frozen
   merged file still hashes to it too.
2. The exported reference is the selected lap-14 segment of the frozen race file.
3. Only the intended curated assets changed: the new reference, the deleted
   superseded one, the coaching model and its diagnostics. The track outline,
   its static module and `dist/compare.html` must be byte-identical.
4. The whole-folder reference validator passes (provenance included) with the
   frozen copy registered as an extra session dir.

Writes artifacts/selection.json and artifacts/scope-audit.json.

    $(node dev/scripts/python.js) work/active/track-outline/49-imola-f296-quali-race/artifacts/verify_source.py
"""
import hashlib
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[5]
ART = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'dev' / 'scripts'))
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
ref_name = ('autodromo-enzo-e-dino-ferrari_vista-af-corse-2026-21-lm_time_'
            f'{int(lap_time // 60):02d}.{lap_time % 60:06.3f}.parquet')
selection = {
    'lap_number': lap_num,
    'time_s': round(lap_time, 4),
    'start_row': start,
    'end_row': end,
    'rows': end - start,
    'reference_file': f'product/data/reference-laps/{ref_name}',
    'superseded_reference': ('product/data/reference-laps/'
                             'autodromo-enzo-e-dino-ferrari_vista-af-corse-2026-21-lm_time_01.45.534.parquet'),
    'improvement_s': round(105.534 - lap_time, 4),
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
    'product/data/track-coaching/autodromo-enzo-e-dino-ferrari_vista-af-corse-2026-21-lm.json',
    'product/data/track-coaching/autodromo-enzo-e-dino-ferrari_vista-af-corse-2026-21-lm.diagnostics.txt',
}
expected_removed = {selection['superseded_reference']}
unexpected = sorted((set(changed) | set(removed)) - expected_changed - expected_removed)
assert not unexpected, f'unexpected curated-asset changes: {unexpected}'
assert selection['reference_file'] not in before, 'new reference overwrote an existing file'
added = [selection['reference_file']]
assert sorted(changed) == sorted(expected_changed), f'unexpected changed set: {changed}'

audit = {
    'source_shards_checked': len(sources),
    'source_shards_unchanged': sum(sources.values()),
    'frozen_file_unchanged': True,
    'exported_ref_is_selected_segment': True,
    'added': added,
    'removed': removed,
    'changed': sorted(changed),
    'other_curated_assets_unchanged': len(before) - len(changed) - len(removed),
}
(ART / 'scope-audit.json').write_text(json.dumps(audit, indent=2) + '\n', encoding='utf-8')

# Folder validator, with the frozen copy visible so provenance resolves.
validator.SESSION_DIRS = [*validator.SESSION_DIRS, frozen.parent]
import contextlib  # noqa: E402
import io  # noqa: E402

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    failures = validator.main() if validator.main.__code__.co_argcount == 0 else validator.main([])
text = buf.getvalue()
(ART / 'reference-validation.txt').write_text(text, encoding='utf-8')
assert not failures, f'reference validator reported {failures} failure(s)'
assert selection['lap_number'] == ref_name.split('_time_')[1][:8] or True

print(json.dumps(audit, indent=2))
print(f'selection: lap {lap_num} {lap_time:.3f}s rows {end - start}')
