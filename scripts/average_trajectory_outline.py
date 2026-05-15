#!/usr/bin/env python3
"""
Generate a track outline using MEDIAN of provided laps.

Why MEDIAN instead of MEAN?
- Different drivers take different racing lines through corners
- Mean smears corners inward when averaging different apex points
- Median picks the middle line, preserving actual track geometry

Strategy:
1. Load provided lap JSON files OR session parquet files
2. Resample each lap to 500 points
3. Compute point-wise MEDIAN across all laps
4. Compute left/right boundaries at ±5m
5. Output schema v1 outline JSON

Usage:
    # From exported lap JSONs (recommended)
    python3 scripts/average_trajectory_outline.py data/track-outlines/bahrain_outline.json \
      --laps data/track-outlines/alignment-artifacts/exported-laps/lap*.json

    # From session parquets (auto-selects fastest 5)
    python3 scripts/average_trajectory_outline.py data/track-outlines/circuit-de-barcelona.json \
      --sessions sessions/session_*.parquet

    # Default (Barcelona sessions for backwards compatibility)
    python3 scripts/average_trajectory_outline.py data/track-outlines/circuit-de-barcelona.json
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


def load_lap_from_json(json_path):
    """Load a single lap from an exported JSON file."""
    with open(json_path) as f:
        data = json.load(f)
    
    if 'trajectories' not in data or len(data['trajectories']) == 0:
        print(f"  ⚠️  {json_path.name}: No trajectories found")
        return None
    
    traj = data['trajectories'][0]
    points = traj.get('points', [])
    
    if len(points) < 100:
        print(f"  ⚠️  {json_path.name}: Only {len(points)} points")
        return None
    
    return {
        'source': str(json_path),
        'lap_name': traj.get('name', json_path.stem),
        'lap_time_s': traj.get('lap_time_s'),
        'points': points,
        'track_name': data.get('track_name', 'Unknown')
    }


def extract_complete_laps_from_parquet(parquet_path, min_lap=1, min_lap_time_s=60.0):
    """Extract complete laps from a parquet session file."""
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
            'source': str(parquet_path),
            'lap_number': int(lap_num),
            'lap_time_s': lap_time,
            'points': points
        })
    
    return laps


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/average_trajectory_outline.py <output.json> [--laps lap*.json ...] [--sessions session*.parquet ...]")
        print()
        print("Options:")
        print("  --laps <files>     Load pre-exported lap JSON files (recommended)")
        print("  --sessions <files> Load session parquet files (auto-selects fastest 5)")
        print()
        print("Examples:")
        print("  # From exported laps")
        print("  python3 scripts/average_trajectory_outline.py data/track-outlines/bahrain.json \\")
        print("    --laps data/track-outlines/alignment-artifacts/exported-laps/lap*.json")
        print()
        print("  # From sessions (auto-select fastest 5)")
        print("  python3 scripts/average_trajectory_outline.py data/track-outlines/circuit-de-barcelona.json \\")
        print("    --sessions sessions/session_*.parquet")
        sys.exit(1)
    
    output_path = Path(sys.argv[1])
    
    # Parse arguments
    lap_json_files = []
    session_parquet_files = []
    
    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--laps':
            i += 1
            while i < len(sys.argv) and not sys.argv[i].startswith('--'):
                lap_json_files.extend(Path(p) for p in sys.argv[i].split())
                i += 1
        elif arg == '--sessions':
            i += 1
            while i < len(sys.argv) and not sys.argv[i].startswith('--'):
                session_parquet_files.extend(Path(p) for p in sys.argv[i].split())
                i += 1
        else:
            i += 1
    
    # Load laps
    all_laps = []
    
    # Load from JSON files first (explicit selection)
    if lap_json_files:
        print(f"Loading {len(lap_json_files)} lap JSON files...")
        for json_path in lap_json_files:
            if not json_path.exists():
                print(f"  ⚠️  {json_path} not found, skipping")
                continue
            
            lap = load_lap_from_json(json_path)
            if lap:
                all_laps.append(lap)
                print(f"  ✅ {json_path.name}: {len(lap['points'])} points" + 
                      (f" ({lap['lap_time_s']:.2f}s)" if lap['lap_time_s'] else ""))
    
    # Load from parquet sessions (auto-select fastest 5)
    if session_parquet_files:
        print(f"\nLoading {len(session_parquet_files)} session parquet files...")
        for session_path in session_parquet_files:
            if not session_path.exists():
                print(f"  ⚠️  {session_path} not found, skipping")
                continue
            
            laps = extract_complete_laps_from_parquet(session_path)
            print(f"  {session_path.name}: {len(laps)} complete laps")
            all_laps.extend(laps)
    
    # Fallback to default Barcelona sessions (backwards compatibility)
    if not all_laps and not lap_json_files and not session_parquet_files:
        print("No --laps or --sessions specified, using default Barcelona sessions...")
        session_parquet_files = [
            Path('sessions/session_20260510T124244Z_circuit-de-barcelona_lmu.parquet'),
            Path('sessions/session_20260511T151203Z_circuit-de-barcelona_lmu.parquet'),
            Path('sessions/session_20260514T141305Z_circuit-de-barcelona_lmu.parquet'),
        ]
        
        for session_path in session_parquet_files:
            if session_path.exists():
                laps = extract_complete_laps_from_parquet(session_path)
                print(f"  {session_path.name}: {len(laps)} complete laps")
                all_laps.extend(laps)
    
    if len(all_laps) == 0:
        print("\n❌ Error: No laps loaded")
        print("Use --laps <json files> or --sessions <parquet files>")
        sys.exit(1)
    
    print(f"\nTotal: {len(all_laps)} laps")
    
    # If loading from parquets, select fastest 5
    if session_parquet_files and not lap_json_files:
        all_laps_sorted = sorted(all_laps, key=lambda x: x.get('lap_time_s', 999))
        fastest_laps = all_laps_sorted[:5]
        
        print(f"\nSelecting fastest {len(fastest_laps)} laps:")
        for i, lap in enumerate(fastest_laps, 1):
            source = Path(lap['source']).name
            if 'lap_number' in lap:
                print(f"  {i}. {source} lap {lap['lap_number']}: {lap['lap_time_s']:.2f}s")
            else:
                print(f"  {i}. {lap.get('lap_name', source)}: {lap.get('lap_time_s', 'N/A')}")
    else:
        # Use all provided laps (from JSON files)
        fastest_laps = all_laps
        print(f"\nUsing all {len(fastest_laps)} provided laps")
    
    # Resample all laps to 500 points
    TARGET_POINTS = 500
    resampled_laps = []
    for lap in fastest_laps:
        resampled = resample_polyline(lap['points'], TARGET_POINTS)
        if len(resampled) == TARGET_POINTS:
            resampled_laps.append(resampled)
    
    if len(resampled_laps) < 2:
        print("❌ Error: Need at least 2 valid laps to average")
        sys.exit(1)
    
    # Compute MEDIAN centerline
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
    
    # Determine track name (use most common from laps)
    track_names = [lap.get('track_name', 'Unknown') for lap in fastest_laps]
    track_name = max(set(track_names), key=track_names.count) if track_names else 'Unknown'
    
    # Build outline
    outline = {
        "schema_version": 1,
        "source": f"Median trajectory from {len(fastest_laps)} laps",
        "track_name": track_name,
        "sim_track_name": track_name,
        "layout_name": "default",
        "coordinate_system": "sim_xy",
        "units": "sim_units",
        "track_name_mapping": {
            "canonical_sim_track_name": track_name.lower().replace(" ", "-"),
            "canonical_lmu_track_name": track_name,
            "accepted_sim_track_names": [track_name.lower().replace(" ", "-")],
            "accepted_lmu_track_names": [track_name],
            "notes": "Generated from user-provided laps."
        },
        "alignment": {
            "method": "median_trajectory_average",
            "width_per_side": 5.0,
            "lap_count": len(fastest_laps),
            "sources": [str(Path(lap.get('source', 'unknown')).name) for lap in fastest_laps],
            "notes": "Uses point-wise MEDIAN instead of mean - robust to different racing lines."
        },
        "visual_qa": {
            "status": "pending",
            "notes": "Generated from provided laps - verify in manual_outline_align.html"
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
    print(f"\n✅ Wrote {output_path}")
    print(f"  Track: {track_name}")
    print(f"  Centerline: {len(centerline)} points")
    print(f"  Bounds: X {min(xs):.0f}..{max(xs):.0f} (span: {max(xs)-min(xs):.0f}), Y {min(ys):.0f}..{max(ys):.0f} (span: {max(ys)-min(ys):.0f})")


if __name__ == '__main__':
    main()
