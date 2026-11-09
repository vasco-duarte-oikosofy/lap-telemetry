"""Signal review: should the Imola F296 compound/manual zones be preserved?

For every clean lap of the two 2026-11-09 sessions (quali + race), print the
braking events the throttle/brake detector finds, then for each *curated* zone
of the existing model print the brake/throttle/speed window so the decision to
refresh or preserve is made on the signals of many laps, not one lap.

Read-only. Writes nothing to product/data.

    $(node dev/scripts/python.js) work/active/track-outline/49-imola-f296-quali-race/artifacts/signal_review.py
"""
import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'product' / 'python'))
sys.path.insert(0, str(ROOT / 'dev' / 'scripts'))

from lap_telemetry.coach.lap_comparator import resample_column  # noqa: E402
from export_fastest_reference_laps import find_complete_laps  # noqa: E402
from generate_track_coaching_model_from_reference import (  # noqa: E402
    detect_corners_from_signals,
    finite_pairs,
)

SESSIONS = [
    ROOT / 'sessions/session_20261109T171239Z_autodromo-enzo-e-dino-ferrari_lmu_quali.parquet',
    ROOT / 'var/tmp/imola-f296-quali-race/'
            'session_20261109T172456Z_autodromo-enzo-e-dino-ferrari_lmu_race.parquet',
]
MODEL = (ROOT / 'product/data/track-coaching/'
                'autodromo-enzo-e-dino-ferrari_vista-af-corse-2026-21-lm.json')

import json  # noqa: E402

model = json.loads(MODEL.read_text(encoding='utf-8'))
corners = model['corners']


def lap_signals(table, start, end):
    sub = table.slice(start, end - start)
    d, v = finite_pairs(sub.column('lap_distance_m').to_pylist(), sub.column('speed_kph').to_pylist())
    _, t = finite_pairs(sub.column('lap_distance_m').to_pylist(), sub.column('throttle_norm').to_pylist())
    _, b = finite_pairs(sub.column('lap_distance_m').to_pylist(), sub.column('brake_norm').to_pylist())
    n = int(max(d))
    return n, resample_column(d, v, n), resample_column(d, t, n), resample_column(d, b, n)


def window(signal, lo, hi):
    lo, hi = max(0, int(lo)), min(len(signal) - 1, int(hi))
    vals = signal[lo:hi + 1]
    return sum(vals) / len(vals) if vals else float('nan')


laps = []
for session in SESSIONS:
    table = pq.read_table(session)
    for num, time_s, start, end in find_complete_laps(table):
        if time_s < 90.0:      # only real green laps (no out/formation/in-lap)
            continue
        n, speed, throttle, brake = lap_signals(table, start, end)
        laps.append((session.name.split('_lmu_')[1].split('.')[0], num, time_s, n, speed, throttle, brake))

laps.sort(key=lambda x: x[2])
print(f'{len(laps)} clean laps across both sessions\n')

print('== detected braking events per lap (apex_m / entry_m / exit_m, min speed kph)')
events_by_lap = {}
for tag, num, time_s, n, speed, throttle, brake in laps:
    evs = detect_corners_from_signals(speed, throttle, brake)
    events_by_lap[(tag, num)] = evs
    print(f'{tag:5s} lap {num:2d} {time_s:8.3f}  ' + '  '.join(
        f'{e.apex_m:.0f}[{e.s_start_m:.0f}-{e.s_end_m:.0f}]' for e in evs))

print('\n== curated zone review (±120 m around each curated apex, mean over all clean laps)')
for c in corners:
    apex = c['apex_s_m']
    print(f"\n{c['id']:4s} {c['name']:24s} apex={apex:6.1f} zone=({c['s_start_m']:.0f}, {c['s_end_m']:.0f})")
    rows = []
    for tag, num, time_s, n, speed, throttle, brake in laps:
        lo, hi = apex - 120, apex + 120
        apex_speed = min(speed[max(0, int(lo)):int(hi) + 1])
        rows.append((time_s, tag, num, window(brake, lo, hi), window(throttle, lo, hi), apex_speed))
    for time_s, tag, num, br, th, sp in rows:
        print(f'   {tag:5s} lap {num:2d} {time_s:8.3f}  brake_mean={br:.3f} throttle_mean={th:.3f} min_speed={sp:6.1f}')
    evs = [e.apex_m for e in events_by_lap[(laps[0][0], laps[0][1])]]
    near = min(evs, key=lambda a: abs(a - apex))
    print(f'   fastest-lap nearest event apex {near:.0f} m (delta {near - apex:+.0f} m)')
