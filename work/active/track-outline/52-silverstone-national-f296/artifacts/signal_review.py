"""Print the F296 reference lap's brake/throttle/speed profile around each curated zone.

Reads the exported reference parquet and prints one line per 10 m so the zone
boundaries can be reviewed against the real signals (not just the detector).

    py work/active/track-outline/52-silverstone-national-f296/artifacts/signal_review.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'product' / 'python'))

import pyarrow.parquet as pq

REF = ROOT / 'product/data/reference-laps/silverstone-national-circuit_vista-af-corse-2026-21-lm_time_00.54.295.parquet'

WINDOWS = [
    ('Copse (curated 242/359/435)', 180, 470),
    ('Maggots (curated 790/828/833, flat)', 760, 900),
    ('Becketts (curated 834/1068/1089)', 860, 1120),
    ('Brooklands (curated 1740/1921/1960)', 1700, 2000),
    ('Luffield (curated 2003/2102/2153)', 1980, 2200),
    ('Woodcote (curated 2360/2469/2580, flat)', 2320, 2630),
]

table = pq.read_table(REF)
dist = table.column('lap_distance_m').to_pylist()
spd = table.column('speed_kph').to_pylist()
thr = table.column('throttle_norm').to_pylist()
brk = table.column('brake_norm').to_pylist()

rows = [(d, s, t, b) for d, s, t, b in zip(dist, spd, thr, brk)
        if d is not None and s is not None]
rows.sort()

for title, lo, hi in WINDOWS:
    print(f'\n=== {title} ===')
    print(f"{'s_m':>8} {'kph':>7} {'thr':>6} {'brk':>6}")
    bucket = None
    for d, s, t, b in rows:
        if not (lo <= d <= hi):
            continue
        step = int(d // 10)
        if step == bucket:
            continue
        bucket = step
        print(f'{d:8.1f} {s:7.1f} {(t if t is not None else float("nan")):6.2f} '
              f'{(b if b is not None else float("nan")):6.2f}')
