"""Freeze the unfinalized Imola F296 race recording into one read-only parquet.

The recorder never finalized the 2026-11-09T17:24:56Z race session: the sidecar
still says `in_progress: true`, `ended_utc: null`, and there is no canonical
`.parquet` — only `partN` shards plus overlapping `snapN` snapshots.

What this does (same procedure as slices 41 and 42):

- Takes the closed `partN` shards up to (but not including) the highest one,
  which may still be being written, in numeric order.
- Collapses exact-duplicate consecutive rows (restart/snapshot overlap).
- Writes the concatenation to `var/tmp/imola-f296-quali-race/` (git-ignored
  scratch) and records a SHA-256 manifest of the source shards + frozen file.

Run from the project root:

    $(node dev/scripts/python.js) work/active/track-outline/49-imola-f296-quali-race/artifacts/freeze_source.py
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
SESSION = 'session_20261109T172456Z_autodromo-enzo-e-dino-ferrari_lmu_race'
OUT_DIR = ROOT / 'var' / 'tmp' / 'imola-f296-quali-race'
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

# Collapse exact-duplicate consecutive rows (restart overlap).
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
    'track': 'Autodromo Enzo e Dino Ferrari',
    'vehicle_name': 'Vista AF Corse 2026 #21:LM',
    'session_type_label': 'race',
    'in_progress': True,
    'frozen_from_parts': len(closed),
}, indent=2) + '\n', encoding='utf-8')

manifest = {
    'session': SESSION,
    'frozen_file': str(FROZEN.relative_to(ROOT)).replace('\\', '/'),
    'frozen_sha256': sha(FROZEN),
    'rows_before_dedupe': rows_before,
    'rows_after_dedupe': rows_after,
    'excluded_highest_shard': f'{SESSION}.part{shards[-1][0]}.parquet',
    'excluded_snapshots': len(glob.glob(str(ROOT / 'sessions' / f'{SESSION}.snap*.parquet'))),
    'source_sha256': {
        str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for _, p in shards if p in closed
    },
}
(ART / 'source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
print(f'frozen -> {manifest["frozen_file"]}')
