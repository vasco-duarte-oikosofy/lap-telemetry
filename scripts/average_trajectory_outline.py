#!/usr/bin/env python3
"""
Generate a track outline by averaging multiple laps from multiple sessions.

Strategy:
1. Load multiple session parquets (GT3 and LMP3)
2. Extract full laps (skip lap 0 which is often out-lap)
3. Resample each lap to same point count
4. Average all laps point-by-point to get centerline
5. Compute left/right boundaries at ±5m perpendicular to track direction
6. Output schema v1 outline JSON

Usage:
    python3 scripts/average_trajectory_outline.py <output.json> [--sessions session1.json session2.json ...]
"""

import json
import math
import sys
from pathlib import Path
import pandas as pd
import numpy as np


def dist(a, b):
    """Euclidean distance between two points."""
    return math.hypot(a['x'] - b['x'], a['y'] - b['y'])


def resample_polyline(points, n):
    """Resample a polyline to n evenly-spaced points."""
    if len(points) < 2:
        return points
    
    # Compute cumulative arc length
    cum_len = [0.0]
    for i in range(1, len(points)):
        cum_len.append(cum_len[i - 1] + dist(points[i - 1], points[i]))
    
    total_len = cum_len[-1]
    if total_len == 0:
        return [points[0]]
    
    # Resample
    result = []
    for i in range(n):
        target_len = (i / (n - 1)) * total_len
        
        # Find segment
        seg = 1
        while seg < len(cum_len) - 1 and cum_len[seg] < target_len:
            seg += 1
        
        # Interpolate
        seg_len = cum_len[seg] - cum_len[seg - 1]
        t = (target_len - cum_len[seg - 1]) / seg_len if seg_len > 0 else 0
        
        result.append({
            'x': points[seg - 1]['x'] + t * (points[seg]['x'] - points[seg - 1]['x']),
            'y': points[seg - 1]['y'] + t * (points[seg]['y'] - points[seg - 1]['y'])
        })
    
    return result


def compute_boundaries(centerline, width_per_side=5.0):
    """Compute left and right boundaries at given width from centerline."""
    left = []
    right = []
    n = len(centerline)
    
    for i in range(n):
        # Get previous and next points (wrap around for closed loop)
        prev = centerline[(i - 1 + n) % n]
        next_pt = centerline[(i + 1) % n]
        
        # Compute tangent direction
        dx = next_pt['x'] - prev['x']
        dy = next_pt['y'] - prev['y']
        length = math.hypot(dx, dy)
        
        if length == 0:
            # Degenerate case - use previous normal
            left.append({'x': centerline[i]['x'], 'y': centerline[i]['y'] - width_per_side})
            right.append({'x': centerline[i]['x'], 'y': centerline[i]['y'] + width_per_side})
            continue
        
        # Normalize tangent
        tx, ty = dx / length, dy / length
        
        # Normal (perpendicular) - rotate 90° counter-clockwise
        nx, ny = -ty, tx
        
        # Left and right boundaries
        left.append({
            'x': centerline[i]['x'] - nx * width_per_side,
            'y': centerline[i]['y'] - ny * width_per_side
        })
        right.append({
            'x': centerline[i]['x'] + nx * width_per_side,
            'y': centerline[i]['y'] + ny * width_per_side
        })
    
    return left, right


def extract_laps_from_parquet(parquet_path, min_lap=1):
    """Extract laps from a parquet file, skipping early laps."""
    df = pd.read_parquet(parquet_path)
    
    if 'lap_number' not in df.columns:
        return []
    
    laps = []
    for lap_num in sorted(df['lap_number'].unique()):
        if lap_num < min_lap:
            continue
        
        lap_df = df[df['lap_number'] == lap_num].sort_values('lap_distance_m')
        
        # Extract x, y positions (use pos_x_m and pos_z_m for LMU)
        points = []
        for _, row in lap_df.iterrows():
            x = row.get('pos_x_m')
            y = row.get('pos_z_m')  # LMU uses Z for lateral
            if x is not None and y is not None and pd.notna(x) and pd.notna(y):
                points.append({'x': float(x), 'y': float(y)})
        
        if len(points) > 100:  # Minimum lap length
            laps.append({
                'session': parquet_path.name,
                'lap_number': lap_num,
                'points': points
            })
    
    return laps


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/average_trajectory_outline.py <output.json> [--sessions session1.json session2.json ...]")
        sys.exit(1)
    
    output_path = Path(sys.argv[1])
    
    # Default sessions (GT3 and LMP3 from Barcelona)
    default_sessions = [
        'sessions/session_20260510T124244Z_circuit-de-barcelona_lmu.parquet',  # LMP3, 7 laps
        'sessions/session_20260511T151203Z_circuit-de-barcelona_lmu.parquet',  # GT3, 7 laps
        'sessions/session_20260514T141305Z_circuit-de-barcelona_lmu.parquet',  # GT3, 8 laps
    ]
    
    # Parse --sessions argument
    sessions_to_use = default_sessions
    if '--sessions' in sys.argv:
        idx = sys.argv.index('--sessions')
        sessions_to_use = sys.argv[idx+1:]
    
    print(f"Loading {len(sessions_to_use)} sessions...")
    
    # Extract all laps
    all_laps = []
    for session_path in sessions_to_use:
        path = Path(session_path)
        if not path.exists():
            print(f"  Warning: {path} not found, skipping")
            continue
        
        laps = extract_laps_from_parquet(path, min_lap=1)
        print(f"  {path.name}: {len(laps)} laps")
        all_laps.extend(laps)
    
    print(f"\nTotal: {len(all_laps)} laps from {len(sessions_to_use)} sessions")
    
    if len(all_laps) < 2:
        print("Error: Need at least 2 laps to average")
        sys.exit(1)
    
    # Resample all laps to same point count
    TARGET_POINTS = 500
    resampled_laps = []
    for lap in all_laps:
        if len(lap['points']) < 100:
            print(f"  Skipping {lap['session']} lap {lap['lap_number']}: only {len(lap['points'])} points")
            continue
        resampled = resample_polyline(lap['points'], TARGET_POINTS)
        if len(resampled) == TARGET_POINTS:
            resampled_laps.append(resampled)
        else:
            print(f"  Warning: {lap['session']} lap {lap['lap_number']} resampled to {len(resampled)} points instead of {TARGET_POINTS}")
    
    if len(resampled_laps) < 2:
        print("Error: Need at least 2 valid laps to average")
        sys.exit(1)
    
    # Average all laps point-by-point
    print(f"\nAveraging {len(resampled_laps)} laps to {TARGET_POINTS} points...")
    centerline = []
    for i in range(TARGET_POINTS):
        avg_x = sum(lap[i]['x'] for lap in resampled_laps) / len(resampled_laps)
        avg_y = sum(lap[i]['y'] for lap in resampled_laps) / len(resampled_laps)
        centerline.append({'x': avg_x, 'y': avg_y})
    
    # Compute boundaries at ±5m
    left, right = compute_boundaries(centerline, width_per_side=5.0)
    
    # Build schema v1 outline
    outline = {
        "schema_version": 1,
        "source": f"Averaged trajectory from {len(all_laps)} laps ({len(sessions_to_use)} sessions)",
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
            "notes": "Generated from averaged GT3 and LMP3 session trajectories."
        },
        "alignment": {
            "method": "multi_lap_trajectory_average",
            "width_per_side": 5.0,
            "lap_count": len(all_laps),
            "session_count": len(sessions_to_use),
            "sessions": [Path(s).name for s in sessions_to_use],
            "notes": "Centerline averaged from multiple full laps, boundaries at ±5m. Ready for manual alignment refinement."
        },
        "visual_qa": {
            "status": "pending",
            "notes": "Generated from averaged trajectories - needs visual verification in tools/manual_outline_align.html"
        },
        "caveats": [
            "Width is constant ±5m estimate - not measured from real track data.",
            "Centerline follows averaged racing line from GT3 and LMP3 sessions.",
            "This outline is visual context only and is not authoritative simulator track-limits data."
        ],
        "centerline": centerline,
        "left_boundary": left,
        "right_boundary": right
    }
    
    # Write output
    with open(output_path, 'w') as f:
        json.dump(outline, f, indent=2)
        f.write('\n')
    
    print(f"\nWrote {output_path}")
    print(f"  Centerline: {len(centerline)} points")
    print(f"  Left boundary: {len(left)} points")
    print(f"  Right boundary: {len(right)} points")


if __name__ == '__main__':
    main()
