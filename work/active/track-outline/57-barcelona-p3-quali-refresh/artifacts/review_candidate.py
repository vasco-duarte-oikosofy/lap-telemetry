"""Read-only reproducible quali selection and retained-zone control review."""
import hashlib
import json
import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[5]
sys.path[:0] = [str(ROOT / 'dev/scripts'), str(ROOT / 'product/python')]
from export_fastest_reference_laps import (
    find_complete_laps, segment_covers_full_lap, segment_wall_clock_span,
)
from lap_telemetry.parquet_utils import authoritative_duration, build_segments
from update_reference_and_coaching_model import detect_corners, match_corners

ARTIFACTS = Path(__file__).resolve().parent
SOURCE = ROOT / 'sessions/session_20261115T183239Z_circuit-de-barcelona_lmu_quali.parquet'
MODEL = json.loads((ARTIFACTS / 'model-before.json').read_text(encoding='utf-8'))
table = pq.read_table(SOURCE)
segments = build_segments(table['lap_number'].to_pylist())
candidates = find_complete_laps(table)
best = min(candidates, key=lambda item: item[1])
lap, duration, start, end = best
selected = table.slice(start, end - start)
temp = ROOT / 'var/tmp/barcelona-p3-quali/candidate.parquet'
temp.parent.mkdir(parents=True, exist_ok=True)
pq.write_table(selected, temp)
detected, method = detect_corners(temp)
pairs, _ = match_corners(MODEL['corners'], detected)

lines = [
    '# Qualifying candidate review', '',
    f'Source: `{SOURCE.name}`',
    f'SHA256: `{hashlib.sha256(SOURCE.read_bytes()).hexdigest()}`', '',
    '| lap | rows | authoritative s | clock span s | distance min/max/end m | all valid | full coverage |',
    '|---:|---:|---:|---:|---|---|---|',
]
for i, (number, first, last) in enumerate(segments):
    following = segments[i + 1] if i + 1 < len(segments) else (None, None, None)
    distances = table['lap_distance_m'].to_pylist()[first:last]
    timing = authoritative_duration(table, first, last, following[1], following[2])
    lines.append(f'| {number} | {last-first} | {timing:.6f} | '
                 f'{segment_wall_clock_span(table, first, last):.3f} | '
                 f'{min(distances):.2f}/{max(distances):.2f}/{distances[-1]:.2f} | '
                 f'{all(table["lap_valid"].to_pylist()[first:last])} | '
                 f'{segment_covers_full_lap(table, first, last)} |')
lines += [
    '', f'Winner: lap {lap}, {duration:.6f} s, rows [{start}, {end}), {end-start} rows.',
    'Lap 6 ends 358 m before its recorded peak; its 91.518 s is not a complete lap.',
    '', f'Detector: `{method}`. Zones below use the existing curated model.', '',
    '| id | curated entry/apex/exit | detected entry/apex/exit | maximum change m | min speed kph | min throttle | max brake |',
    '|---|---|---|---:|---:|---:|---:|',
]
rows = selected.to_pylist()
for old, new in pairs:
    geometry = [old[k] for k in ('s_start_m', 'apex_s_m', 's_end_m')]
    window = [row for row in rows if geometry[0] <= row['lap_distance_m'] <= geometry[2]]
    new_geometry = [new.s_start_m, new.apex_m, new.s_end_m] if new else None
    delta = max(abs(a-b) for a, b in zip(geometry, new_geometry)) if new else None
    lines.append(f'| {old["id"]} | {geometry} | {new_geometry} | {delta} | '
                 f'{min(row["speed_kph"] for row in window):.2f} | '
                 f'{min(row["throttle_norm"] for row in window):.3f} | '
                 f'{max(row["brake_norm"] for row in window):.3f} |')
lines += [
    '', 'Decision: refresh only t3 (8/4/5 m entry/apex/exit changes). Preserve all other',
    'eleven complete corner objects with --preserve-geometry, keeping a 40 m guard.',
    't2 and t7 are secondary turns without independent detected events. t8 would',
    'start at 2821 m and overlap retained t7 ending at 2850 m. The other eight',
    'matches exceed 40 m (mostly full-braking-event starts versus curated tight',
    'corner windows); t11 also shifts apex by 47 m. The original windows still',
    'contain the recorded corner controls/speed features. Preserve their reviewed',
    'definitions rather than silently broadening or merging them on a PB refresh.',
    'No --allow-unmatched, raised tolerance, renaming or reclassification is used.',
    '', 'The shared 14-turn Barcelona outline is Ferrari-model-backed, not this',
    '12-corner P3 model. Leave map anchors and TinyPedal assets unchanged.',
]
(ARTIFACTS / 'candidate-review.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print('\n'.join(lines))
