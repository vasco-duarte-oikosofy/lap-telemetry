"""Print brake/throttle/speed around the corners the detector did not produce.

Compares the new race lap (2:06.440) with the existing reference (2:07.601) so
the decision "preserve the curated zone" vs "the corner is genuinely gone" is
made on signals, not on the detector's silence.

    py work/active/track-outline/54-paul-ricard-elms-f296-race/artifacts/signal_review.py
"""
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[5]
NEW = ROOT / 'var/tmp/paul-ricard-race-lap10.parquet'
OLD = ROOT / 'product/data/reference-laps/paul-ricard---elms_vista-af-corse-2026-21-lm_time_02.07.601.parquet'

WINDOWS = [
    ("Virage de l'Hotel 1+2 (curated 1307 / 1411, no event on the race lap)", 1150, 1470),
    ('Virage du Camp (curated 1521, event at 1507)', 1440, 1580),
    ('Beausset 1+2 (curated 4390 / 4482, one event at 4379)', 4150, 4560),
    ('Bendor -> Garlaban (curated 4831 / 4949 flat)', 4700, 5250),
    ('Virage du Lac + Pont (curated 5380 / 5470, one event at 5473)', 5150, 5520),
]


def profile(path):
    table = pq.read_table(path)
    rows = [(d, s, t, b) for d, s, t, b in zip(
        table.column('lap_distance_m').to_pylist(),
        table.column('speed_kph').to_pylist(),
        table.column('throttle_norm').to_pylist(),
        table.column('brake_norm').to_pylist()) if d is not None and s is not None]
    rows.sort()
    return rows


new_rows, old_rows = profile(NEW), profile(OLD)


def slice_rows(rows, lo, hi, step=20):
    out, bucket = [], None
    for d, s, t, b in rows:
        if not (lo <= d <= hi):
            continue
        key = int(d // step)
        if key == bucket:
            continue
        bucket = key
        out.append((d, s, t if t is not None else float('nan'), b if b is not None else float('nan')))
    return out


for title, lo, hi in WINDOWS:
    print(f'\n=== {title} ===')
    print(f"{'s_m':>8} {'new kph':>8} {'brk':>5} {'thr':>5} | {'old kph':>8} {'brk':>5} {'thr':>5}")
    new_slice = slice_rows(new_rows, lo, hi)
    old_slice = {round(r[0]): r for r in slice_rows(old_rows, lo, hi)}
    for d, s, t, b in new_slice:
        match = min(old_slice.items(), key=lambda kv: abs(kv[0] - d))[1]
        print(f'{d:8.1f} {s:8.1f} {b:5.2f} {t:5.2f} | {match[1]:8.1f} {match[3]:5.2f} {match[2]:5.2f}')
