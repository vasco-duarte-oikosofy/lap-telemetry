"""Freeze only stable closed Barcelona race shards for the guarded updater.

Run from the project root using the project Python interpreter. Source files
are never changed; the highest possibly-open part and all snapshots are excluded.
"""
import hashlib
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[5]
ART = Path(__file__).resolve().parent
STEM = 'session_20261115T124448Z_circuit-de-barcelona_lmu_race'
OUT = ROOT / 'var/tmp/barcelona-p3-race-refresh'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parts = sorted((ROOT / 'sessions').glob(f'{STEM}.part*.parquet'),
                   key=lambda p: int(p.stem.rsplit('part', 1)[1]))
    assert len(parts) > 1, 'need at least one closed shard and one excluded tail'
    numbers = [int(p.stem.rsplit('part', 1)[1]) for p in parts]
    assert numbers == list(range(numbers[-1] + 1)), 'source shards must be contiguous'
    closed = parts[:-1]
    before = {p.name: sha(p) for p in closed}
    merged = pa.concat_tables([pq.read_table(p) for p in closed])
    assert before == {p.name: sha(p) for p in closed}, 'closed shards changed during freeze'
    # Drop exact consecutive duplicates only; never deduplicate by clock or lap.
    previous = None
    keep = []
    for index, row in enumerate(zip(*(merged[c].to_pylist() for c in merged.column_names))):
        if row != previous:
            keep.append(index)
        previous = row
    frozen = merged.take(pa.array(keep, type=pa.int64()))
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / f'{STEM}.parquet'
    pq.write_table(frozen, target)
    source_sidecar = ROOT / 'sessions' / f'{STEM}.json'
    meta = json.loads(source_sidecar.read_text(encoding='utf-8'))
    meta['frozen_from_parts'] = len(closed)
    meta['row_count'] = frozen.num_rows
    (OUT / f'{STEM}.json').write_text(json.dumps(meta, indent=2) + '\n', encoding='utf-8')
    manifest = {
        'session': STEM,
        'frozen_file': target.relative_to(ROOT).as_posix(),
        'frozen_sha256': sha(target),
        'highest_shard_excluded': parts[-1].name,
        'closed_shards': before,
        'snapshots_excluded': [p.name for p in sorted(
            (ROOT / 'sessions').glob(f'{STEM}.snap*.parquet'))],
        'rows_before_dedup': merged.num_rows,
        'rows_after_dedup': frozen.num_rows,
        'last_session_time_s': frozen['session_time_s'][-1].as_py(),
        'last_lap_number': frozen['lap_number'][-1].as_py(),
    }
    (ART / 'source-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n',
                                            encoding='utf-8')
    print(f'Froze {len(closed)} closed shards; excluded {parts[-1].name}')
    print(f'{merged.num_rows} -> {frozen.num_rows} rows; {target}')
    print(f'Last lap {manifest["last_lap_number"]}, clock {manifest["last_session_time_s"]}')


if __name__ == '__main__':
    main()
