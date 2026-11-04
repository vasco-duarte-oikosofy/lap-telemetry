"""Per-corner signal receipt: old reference lap vs the candidate new lap.

For every curated corner, look at brake / throttle / steering / speed within
+/-0.5 s of the apex on both laps. This is what justifies refreshing geometry
for matched corners and preserving reviewed geometry for flat ones.

Writes artifacts/signal-review.txt.
"""
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[5]
ART = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'dev/scripts'))
from export_fastest_reference_laps import find_complete_laps  # noqa: E402

OLD_REF = ROOT / 'product/data/reference-laps/michelin-raceway-road-atlanta_dkr-engineering-4-elms25_time_01.16.304.parquet'
FROZEN = ROOT / 'var/tmp/road-atlanta-p3/session_20261104T180435Z_michelin-raceway-road-atlanta_lmu_race.parquet'
MODEL = ROOT / 'product/data/track-coaching/michelin-raceway-road-atlanta_dkr-engineering-4-elms25.json'


def load_lap(table):
    return table.to_pandas()


def window(df, apex_m, half_s=0.5):
    i = (df['lap_distance_m'] - apex_m).abs().idxmin()
    t = df.at[i, 'session_time_s']
    w = df[(df['session_time_s'] >= t - half_s) & (df['session_time_s'] <= t + half_s)]
    return i, w


def describe(df, apex_m):
    i, w = window(df, apex_m)
    return {
        'apex_row_dist': round(float(df.at[i, 'lap_distance_m']), 1),
        'speed_min': round(float(w['speed_kph'].min()), 1),
        'speed_at_apex': round(float(df.at[i, 'speed_kph']), 1),
        'throttle_min': round(float(w['throttle_norm'].min()), 3),
        'throttle_mean': round(float(w['throttle_norm'].mean()), 3),
        'brake_max': round(float(w['brake_norm'].max()), 3),
        'steer_min': round(float(w['steering_norm'].min()), 3),
        'steer_max': round(float(w['steering_norm'].max()), 3),
    }


old = load_lap(pq.read_table(OLD_REF))
frozen = pq.read_table(FROZEN)
laps = find_complete_laps(frozen)
lap_num, lap_time, start, end = min(laps, key=lambda x: x[1])
new = frozen.slice(start, end - start).to_pandas().reset_index(drop=True)
# lap-local time axis
new['session_time_s'] = new['session_time_s'] - new['session_time_s'].iloc[0]

model = json.loads(MODEL.read_text(encoding='utf-8'))
flat_ids = {c['id'] for c in model['corners'] if c.get('target_throttle_pct')}
preserved_ids = {'t3', 't4', 't8', 't9', 't11', 't12'}

lines = [
    f'Candidate lap: lap {lap_num}, authoritative {lap_time:.3f}s '
    f'({len(new)} rows) from {FROZEN.name}',
    f'Old reference: 1:16.304 ({len(old)} rows) {OLD_REF.name}',
    'Window: +/-0.5 s around the curated apex distance on each lap.',
    '',
    f"{'corner':<22} {'apex_m':>7} {'lap':<4} {'v@apex':>7} {'vmin':>7} "
    f"{'thr_min':>8} {'thr_mean':>9} {'brake_max':>10} {'steer':>14}  verdict",
    '-' * 112,
]

for c in model['corners']:
    for label, df in (('old', old), ('new', new)):
        d = describe(df, c['apex_s_m'])
        if d['brake_max'] <= 0.02 and d['throttle_min'] >= 0.90:
            verdict = 'flat (no braking event)'
        elif d['brake_max'] <= 0.02:
            verdict = f'lift only (throttle min {d["throttle_min"]:.2f})'
        else:
            verdict = 'braking event'
        lines.append(
            f"{c['name']:<22} {c['apex_s_m']:>7.1f} {label:<4} "
            f"{d['speed_at_apex']:>7.1f} {d['speed_min']:>7.1f} "
            f"{d['throttle_min']:>8.3f} {d['throttle_mean']:>9.3f} "
            f"{d['brake_max']:>10.3f} "
            f"{d['steer_min']:>6.3f}/{d['steer_max']:<7.3f}  {verdict}"
        )
    tag = []
    if c['id'] in flat_ids:
        tag.append('curated flat marker')
    if c['id'] in preserved_ids:
        tag.append('GEOMETRY PRESERVED')
    if tag:
        lines.append(f"{'':<22} -> {', '.join(tag)}")
    lines.append('')

out = ART / 'signal-review.txt'
out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print('\n'.join(lines))
