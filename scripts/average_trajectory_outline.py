#!/usr/bin/env python3
"""
Generate a track outline using MEDIAN of fastest complete laps.

Why MEDIAN instead of MEAN?
- Different drivers take different racing lines through corners
- Mean smears corners inward when averaging different apex points
- Median picks the middle line, preserving actual track geometry

Strategy:
1. Load multiple session parquets
2. Extract complete laps (lap_time_s > 60s)
3. Sort by lap time, pick fastest 5
4. Resample each lap to 500 points
5. Compute point-wise MEDIAN across all laps
6. Compute left/right boundaries at ±5m
7. Output schema v1 outline JSON

Usage:
    python3 scripts/average_trajectory_outline.py <output.json>
"""

import json
import math
import sys
from pathlib import Path
import pandas as pd
import numpy as np


def dist(a, b):
    return math.hypot(a['x'] - b['x'], a['y'] - b['y'])


def resample_polyline(points, n):
    if len(points) < 2:
        return points
    
    cum_len = [0.0]
    for i in range(1, len(points)):
        cum_len.append(cum_len[i - 1] + dist(points[i - 1], points[i]))
    
    total_len = cum_len[-1]
    if total_len == 0:
        return [points[0]]
    
    result = []
    for i in range(n):
        target_len = (i / (n - 1)) * total_len
        seg = 1
        while seg < len(cum_len) - 1 and cum_len[seg] < target_len:
            seg += 1
        seg_len = cum_len[seg] - cum_len[seg - 1]
        t = (target_len - cum_len[seg - 1]) / seg_len if seg_len > 0 else 0
        result.append({
            'x': points[seg - 1]['x'] + t * (points[seg]['x'] - points[seg - 1]['x']),
            'y': points[seg - 1]['y'] + t * (points[seg]['y'] - points[seg - 1]['y'])
        })
    return result


def compute_boundaries(centerline, width_per_side=5.0):
    left, right = [], []
    n = len(centerline)
    
    for i in range(n):
        prev = centerline[(i - 1 + n) % n]
        next_pt = centerline[(i + 1) % n]
        dx = next_pt['x'] - prev['x']
        dy = next_pt['y'] - prev['y']
        length = math.hypot(dx, dy)
        
        if length == 0:
            left.append({'x': centerline[i]['x'], 'y': centerline[i]['y'] - width_per_side})
            right.append({'x': centerline[i]['x'], 'y': centerline[i]['y'] + width_per_side})
            continue
        
        nx, ny = -dy / length, dx / length
        left.append({'x': centerline[i]['x'] - nx * width_per_side, 'y': centerline[i]['y'] - ny * width_per_side})
        right.append({'x': centerline[i]['x'] + nx * width_per_side, 'y': centerline[i]['y'] + ny * width_per_side})
    
    return left, right


def extract_complete_laps_from_parquet(parquet_path, min_lap=1, min_lap_time_s=60.0):
    df = pd.read_parquet(parquet_path)
    
    if 'lap_number' not in df.columns or 'lap_time_s' not in df.columns:
        return []
    
    laps = []
    for lap_num in sorted(df['lap_number'].unique()):
        if lap_num < min_lap:
            continue
        
        lap_df = df[df['lap_number'] == lap_num].sort_values('lap_distance_m')
        lap_times = lap_df['lap_time_s'].dropna()
        
        if len(lap_times) == 0:
            continue
        
        lap_time = float(lap_times.max())
        
        if lap_time < min_lap_time_s:
            continue
        
        points = []
        for _, row in lap_df.iterrows():
            x = row.get('pos_x_m')
            y = row.get('pos_z_m')
            if x is not None and y is not None and pd.notna(x) and pd.notna(y):
                points.append({'x': float(x), 'y': float(y)})
        
        if len(points) < 100:
            continue
        
        laps.append({
            'session': str(parquet_path),
            'lap_number': int(lap_num),
            'lap_time_s': lap_time,
            'points': points
        })
    
    return laps


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/average_trajectory_outline.py <output.json>")
        sys.exit(1)
    
    output_path = Path(sys.argv[1])
    
    default_sessions = [
        'sessions/session_20260510T124244Z_circuit-de-barcelona_lmu.parquet',
        'sessions/session_20260511T151203Z_circuit-de-barcelona_lmu.parquet',
        'sessions/session_20260514T141305Z_circuit-de-barcelona_lmu.parquet',
    ]
    
    sessions_to_use = default_sessions
    if '--sessions' in sys.argv:
        idx = sys.argv.index('--sessions')
        sessions_to_use = sys.argv[idx+1:]
    
    print(f"Loading {len(sessions_to_use)} sessions...")
    
    all_laps = []
    for session_path in sessions_to_use:
        path = Path(session_path)
        if not path.exists():
            print(f"  Warning: {path} not found, skipping")
            continue
        
        laps = extract_complete_laps_from_parquet(path, min_lap=1, min_lap_time_s=60.0)
        print(f"  {path.name}: {len(laps)} complete laps")
        for lap in laps:
            print(f"    Lap {lap['lap_number']}: {lap['lap_time_s']:.2f}s")
        all_laps.extend(laps)
    
    print(f"\nTotal: {len(all_laps)} complete laps")
    
    if len(all_laps) == 0:
        print("Error: No complete laps found")
        sys.exit(1)
    
    # Sort by lap time and pick fastest 5
    all_laps_sorted = sorted(all_laps, key=lambda x: x['lap_time_s'])
    fastest_laps = all_laps_sorted[:5]
    
    print(f"\nSelecting fastest {len(fastest_laps)} laps:")
    for i, lap in enumerate(fastest_laps):
        print(f"  {i+1}. {Path(lap['session']).name} lap {lap['lap_number']}: {lap['lap_time_s']:.2f}s")
    
    # Resample all selected laps
    TARGET_POINTS = 500
    resampled_laps = []
    for lap in fastest_laps:
        resampled = resample_polyline(lap['points'], TARGET_POINTS)
        if len(resampled) == TARGET_POINTS:
            resampled_laps.append(resampled)
    
    if len(resampled_laps) < 2:
        print("Error: Need at least 2 valid laps")
        sys.exit(1)
    
    # Compute MEDIAN (not mean!) - robust to different racing lines
    print(f"\nComputing MEDIAN centerline from {len(resampled_laps)} laps...")
    centerline = []
    for i in range(TARGET_POINTS):
        xs = [lap[i]['x'] for lap in resampled_laps]
        ys = [lap[i]['y'] for lap in resampled_laps]
        median_x = float(np.median(xs))
        median_y = float(np.median(ys))
        centerline.append({'x': median_x, 'y': median_y})
    
    # Compute boundaries
    left, right = compute_boundaries(centerline, width_per_side=5.0)
    
    # Build outline
    outline = {
        "schema_version": 1,
        "source": f"Median trajectory from {len(fastest_laps)} fastest complete laps",
        "track_name": "Circuit de Barcelona-Catalunya",
        "sim_track_name": "Circuit de Barcelona",
        "layout_name": "default",
        "coordinate_system": "sim_xy",
        "units": "sim_units",
        "track_name_mapping": {
            "canonical_sim_track_name": "circuit-de-barcelona",
            "canonical_lmu_track_name": "Circuit de Barcelona-Catalunya",
            "accepted_sim_track_names": ["circuit-de-barcelona"],
            "accepted_lmu_track_names": ["Circuit de Barcelona-Catalunya"],
            "notes": "Generated using MEDIAN of fastest laps (robust to different racing lines)."
        },
        "alignment": {
            "method": "median_trajectory_average",
            "width_per_side": 5.0,
            "lap_count": len(fastest_laps),
            "session_count": len(sessions_to_use),
            "sessions": [str(Path(s).name) for s in sessions_to_use],
            "fastest_laps": [
                {
                    "session": str(Path(lap['session']).name),
                    "lap_number": int(lap['lap_number']),
                    "lap_time_s": round(float(lap['lap_time_s']), 2)
                }
                for lap in fastest_laps
            ],
            "notes": "Uses point-wise MEDIAN instead of mean - robust to different racing lines through corners."
        },
        "visual_qa": {
            "status": "pending",
            "notes": "Median-based outline preserves corner geometry better than mean."
        },
        "caveats": [
            "Width is constant ±5m estimate.",
            "Median racing line - may not match any single driver's exact line.",
            "Visual context only, not authoritative track-limits data."
        ],
        "centerline": centerline,
        "left_boundary": left,
        "right_boundary": right
    }
    
    with open(output_path, 'w') as f:
        json.dump(outline, f, indent=2)
        f.write('\n')
    
    xs = [p['x'] for p in centerline]
    ys = [p['y'] for p in centerline]
    print(f"\nWrote {output_path}")
    print(f"  Centerline: {len(centerline)} points")
    print(f"  Bounds: X {min(xs):.0f}..{max(xs):.0f} (span: {max(xs)-min(xs):.0f}), Y {min(ys):.0f}..{max(ys):.0f} (span: {max(ys)-min(ys):.0f})")


if __name__ == '__main__':
    main()
