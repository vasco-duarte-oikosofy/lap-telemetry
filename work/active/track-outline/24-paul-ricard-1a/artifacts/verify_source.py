"""Reproduce source/scope checks; retain ignored frozen data to rerun provenance."""
import hashlib
import json
import os
import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[5]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / 'dev/scripts'))
import validate_reference_laps as validator

ART = Path(__file__).resolve().parent
manifest = json.loads((ART / 'source-manifest.json').read_text())
selection = json.loads((ART / 'selection.json').read_text())
frozen = Path(manifest['derived_file'])
assert hashlib.sha256(frozen.read_bytes()).hexdigest() == manifest['derived_sha256']
originals = {r['path']: Path(r['path']).exists() and
             hashlib.sha256(Path(r['path']).read_bytes()).hexdigest() == r['sha256']
             for r in manifest['source_files']}
assert all(originals.values()), 'An original source shard changed/disappeared after freeze'
table = pq.read_table(frozen)
ref = Path('product/data/reference-laps/paul-ricard---1a_dkr-engineering-4-elms25_time_01.46.834.parquet')
actual = pq.read_table(ref)
expected = table.slice(selection['start'], selection['end'] - selection['start'])
assert actual.replace_schema_metadata(None).equals(expected.replace_schema_metadata(None))
protected = json.loads((ART / 'before-hashes.json').read_text())
unchanged = {p: Path(p).exists() and hashlib.sha256(Path(p).read_bytes()).hexdigest() == h
             for p, h in protected.items()}
assert all(unchanged.values()), 'An existing curated asset changed'
result = dict(original_source_files_unchanged=originals,
              selected_segment_equals_reference=True,
              all_existing_curated_assets_unchanged=unchanged,
              excluded_overlapping_snapshots=manifest['excluded_snapshots'],
              authoritative_time_s=selection['time_s'],
              qualification_improvement_s=107.09112548828125-selection['time_s'])
(ART / 'scope-audit.json').write_text(json.dumps(result, indent=2)+'\n')
print(f'[PASS] {len(originals)} original shards and {len(unchanged)} existing curated assets unchanged; exact selected segment exported', flush=True)
# The recorder has not finalized its race shards. Include the frozen full source
# alongside BOTH normal directories, never suppress other tracks' provenance.
validator.SESSION_DIRS.append(frozen.parent)
sys.exit(validator.main())
