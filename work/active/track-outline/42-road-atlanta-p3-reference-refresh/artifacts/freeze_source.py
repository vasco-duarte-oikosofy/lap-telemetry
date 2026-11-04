"""Freeze the closed partN shards of the in-progress Road Atlanta race.

The recorder never finalized this session (sidecar in_progress, no canonical
parquet) and it keeps appending idle frames after the race timer expired.
We copy the closed shards read-only into ignored scratch, record their hashes,
then concatenate in numeric order and collapse consecutive exact-duplicate rows
(the recorder re-writes a boundary frame between shards).

Writes artifacts/source-manifest.json.
"""
import glob
import hashlib
import json
import os
import re
import shutil
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[5]
ART = Path(__file__).resolve().parent
SCRATCH = ROOT / 'var/tmp/road-atlanta-p3'
SLUG = 'session_20261104T180435Z_michelin-raceway-road-atlanta_lmu_race'

all_parts = sorted(
    glob.glob(str(ROOT / 'sessions' / f'{SLUG}.part*.parquet')),
    key=lambda p: int(re.search(r'part(\d+)\.parquet', p).group(1)),
)
closed = all_parts[:-1]          # the recorder still writes the highest shard
print(f'parts present: {len(all_parts)} - freezing {len(closed)} closed shards')

frozen_dir = SCRATCH / 'frozen-parts'
frozen_dir.mkdir(parents=True, exist_ok=True)

manifest = {'session': SLUG, 'source_sha256': {}}
for p in closed:
    rel = Path(p).relative_to(ROOT).as_posix()
    manifest['source_sha256'][rel] = hashlib.sha256(Path(p).read_bytes()).hexdigest()
    dst = frozen_dir / Path(p).name
    shutil.copyfile(p, dst)
    os.chmod(dst, 0o444)

concat = pa.concat_tables([pq.read_table(p) for p in closed])
before = concat.num_rows

cols = [c for c in concat.column_names]
frame = concat.select(cols).to_pandas()
dupe = frame.eq(frame.shift()).all(axis=1)          # consecutive duplicates only
keep = (~dupe).tolist()
frozen = concat.filter(pa.array(keep))
out = SCRATCH / f'{SLUG}.parquet'
pq.write_table(frozen, out)
print(f'concat rows: {before}  frozen rows: {frozen.num_rows}  '
      f'dropped consecutive duplicates: {before - frozen.num_rows}')

# Sidecar so the guarded exporter can resolve the vehicle for this scratch file.
sidecar = json.loads((ROOT / 'sessions' / f'{SLUG}.json').read_text(encoding='utf-8'))
sidecar['row_count'] = frozen.num_rows
out.with_suffix('.json').write_text(
    json.dumps(sidecar, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

manifest.update({
    'frozen_file': out.relative_to(ROOT).as_posix(),
    'frozen_sha256': hashlib.sha256(out.read_bytes()).hexdigest(),
    'parts_present_at_freeze': len(all_parts),
    'frozen_from_parts': len(closed),
    'concat_rows': before,
    'frozen_rows': frozen.num_rows,
    'dropped_consecutive_duplicate_rows': before - frozen.num_rows,
    'note': (
        'Recorder never finalized this session: no canonical parquet, sidecar '
        'in_progress=true with ended_utc=null (race timer expired; the recorder '
        'keeps appending idle frames). Closed partN shards were frozen read-only; '
        'the higher overlapping snapN snapshots were excluded. The live sidecar is '
        'deliberately not hashed because it is still being rewritten.'
    ),
})
(ART / 'source-manifest.json').write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
print('frozen sha256:', manifest['frozen_sha256'])
