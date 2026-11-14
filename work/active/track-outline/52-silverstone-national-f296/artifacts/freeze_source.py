"""Freeze the unfinalized Silverstone National F296 race recording into one parquet.

The recorder never finalized the 2026-11-14T07:04:13Z race: the sidecar still
says `in_progress: true`, `ended_utc: null`, and there is no canonical parquet —
only `partN` shards plus `snapN` snapshots. Parts 100..104 are frozen-time
duplicates (the car sat parked after the race ended at session_time 2010.8 s).

Same procedure as slices 41 / 42 / 49:

- Takes the closed `partN` shards up to (but not including) the highest one,
  which may still be being written, in numeric order.
- Collapses exact-duplicate consecutive rows (parked tail + snapshot overlap).
- Writes the concatenation to `var/tmp/silverstone-national-f296-quali-race/`
  (git-ignored scratch) and records a SHA-256 manifest of the sources.

Run from the project root:

    py work/active/track-outline/52-silverstone-national-f296/artifacts/freeze_source.py
"""
import glob
import hashlib
import json
import re
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[5]
ART = Path(__file__).resolve().parent
SESSION = 'session_20261114T070413Z_silverstone-national-circuit_lmu_race'
OUT_DIR = ROOT / 'var' / 'tmp' / 'silverstone-national-f296-quali-race'
# Keep the canonical session basename so the export script's track-slug parser
# and the reference validator's provenance scan both resolve this source.
FROZEN = OUT_DIR / f'{SESSION}.parquet'
SIDECAR = OUT_DIR / f'{SESSION}.json'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


shards = []
for path in glob.glob(str(ROOT / 'sessions' / f'{SESSION}.part*.parquet')):
    m = re.search(r'\.part(\d+)\.parquet$', path)
    shards.append((int(m.group(1)), Path(path)))
shards.sort()

# The highest shard may be open; keep everything strictly below it.
closed = [p for n, p in shards if n < shards[-1][0]]
print(f'{len(shards)} shards found (0..{shards[-1][0]}), freezing {len(closed)} closed ones')
assert closed, 'no closed shards'

tables = [pq.read_table(p) for p in closed]
merged = pa.concat_tables(tables)
rows_before = merged.num_rows

# Collapse exact-duplicate consecutive rows (parked tail + snapshot overlap).
cols = merged.column_names
keep = []
prev = None
for row in zip(*[merged[c].to_pylist() for c in cols]):
    if row != prev:
        keep.append(row)
    prev = row
rows_after = len(keep)
print(f'rows: {rows_before} -> {rows_after} ({rows_before - rows_after} duplicates collapsed)')

OUT_DIR.mkdir(parents=True, exist_ok=True)
pq.write_table(pa.table({c: [r[i] for r in keep] for i, c in enumerate(cols)}, schema=merged.schema), FROZEN)
# Sidecar carries only what the export script needs: the vehicle identity.
SIDECAR.write_text(json.dumps({
    'track': 'Silverstone National Circuit',
    'vehicle_name': 'Vista AF Corse 2026 #21:LM',
    'session_type_label': 'race',
    'in_progress': True,
    'frozen_from_parts': len(closed),
}, indent=2) + '\n', encoding='utf-8')

manifest = {
    'session': SESSION,
    'frozen_from_parts': len(closed),
    'shards_found': len(shards),
    'highest_shard_excluded': shards[-1][0],
    'rows_before_dedup': rows_before,
    'rows_after_dedup': rows_after,
    'frozen_file': str(FROZEN.relative_to(ROOT)),
    'frozen_sha256': sha(FROZEN),
    'shards': {p.name: sha(p) for _, p in shards},
    'snapshots_excluded': sorted(
        Path(p).name for p in glob.glob(str(ROOT / 'sessions' / f'{SESSION}.snap*.parquet'))
    ),
}
(ART / 'source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
print(f'frozen -> {FROZEN} ({rows_after} rows, sha {manifest["frozen_sha256"][:12]}…)')
