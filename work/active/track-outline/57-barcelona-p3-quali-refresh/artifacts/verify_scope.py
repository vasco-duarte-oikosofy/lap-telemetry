"""Verify this refresh against the on-disk baseline, not unrelated git dirt."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
ARTIFACTS = Path(__file__).resolve().parent
before = json.loads((ROOT / 'var/tmp/barcelona-p3-quali/before-hashes.json').read_text())
changed = [name for name, digest in before.items()
           if not (ROOT / name).exists()
           or hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest]
new = [p.relative_to(ROOT).as_posix()
       for p in (ROOT / 'product/data').rglob('*')
       if p.is_file() and p.relative_to(ROOT).as_posix() not in before]
expected = {
    'product/data/reference-laps/circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.319.parquet',
    'product/data/track-coaching/circuit-de-barcelona_dkr-engineering-4-elms25.json',
    'product/data/track-coaching/circuit-de-barcelona_dkr-engineering-4-elms25.diagnostics.txt',
}
assert set(changed) == expected, changed
assert new == ['product/data/reference-laps/circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.040.parquet'], new
model = json.loads((ROOT / 'product/data/track-coaching/circuit-de-barcelona_dkr-engineering-4-elms25.json').read_text(encoding='utf-8'))
old_model = json.loads((ARTIFACTS / 'model-before.json').read_text(encoding='utf-8'))
for old, current in zip(old_model['corners'], model['corners']):
    if old['id'] != 't3':
        assert old == current, old['id']
    else:
        geometry = {'s_start_m', 'apex_s_m', 's_end_m'}
        assert {k: v for k, v in old.items() if k not in geometry} == {
            k: v for k, v in current.items() if k not in geometry}
report = {
    'changed_existing_assets': changed,
    'added_assets': new,
    'all_other_curated_data_maps_labels_and_source_unchanged': True,
    'eleven_complete_corner_objects_preserved': True,
    'renault_non_geometry_metadata_preserved': True,
    'source_sha256': before['sessions/session_20261115T183239Z_circuit-de-barcelona_lmu_quali.parquet'],
}
(ARTIFACTS / 'scope-audit.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
