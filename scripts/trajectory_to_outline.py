#!/usr/bin/env python3
"""
Generate a track outline from simulator trajectory data.

Strategy:
1. Extract trajectory points from JSON
2. Resample to evenly-spaced points (~500 points for smooth outline)
3. Compute centerline by following the trajectory
4. Compute left/right boundaries at ±5m perpendicular to track direction
5. Output schema v1 outline JSON

Usage:
    python3 scripts/trajectory_to_outline.py <trajectory.json> <output.json>
"""

import json
import math
import sys
from pathlib import Path


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


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 scripts/trajectory_to_outline.py <trajectory.json> <output.json>")
        sys.exit(1)
    
    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    
    # Load trajectory JSON
    with open(input_path, 'r') as f:
        trajectory_data = json.load(f)
    
    # Extract points
    points = []
    if 'trajectories' in trajectory_data:
        for traj in trajectory_data['trajectories']:
            points.extend(traj.get('points', []))
    elif 'points' in trajectory_data:
        points = trajectory_data['points']
    
    print(f"Loaded {len(points)} trajectory points")
    
    # Resample to ~500 evenly-spaced points
    resampled = resample_polyline(points, 500)
    print(f"Resampled to {len(resampled)} points")
    
    # Compute boundaries at ±5m
    left, right = compute_boundaries(resampled, width_per_side=5.0)
    
    # Build schema v1 outline
    outline = {
        "schema_version": 1,
        "source": "Simulator trajectory trace (±5m width)",
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
            "notes": "Generated from simulator trajectory trace."
        },
        "alignment": {
            "method": "trajectory_trace",
            "width_per_side": 5.0,
            "notes": "Centerline traced from simulator trajectory, boundaries at ±5m. Ready for manual alignment refinement."
        },
        "visual_qa": {
            "status": "pending",
            "notes": "Generated from trajectory - needs visual verification and manual alignment refinement."
        },
        "caveats": [
            "Width is constant ±5m estimate - not measured from real track data.",
            "Centerline follows trajectory - may not match ideal racing line or track center.",
            "This outline is visual context only and is not authoritative simulator track-limits data."
        ],
        "centerline": resampled,
        "left_boundary": left,
        "right_boundary": right
    }
    
    # Write output
    with open(output_path, 'w') as f:
        json.dump(outline, f, indent=2)
        f.write('\n')
    
    print(f"Wrote {output_path}")
    print(f"  Centerline: {len(resampled)} points")
    print(f"  Left boundary: {len(left)} points")
    print(f"  Right boundary: {len(right)} points")


if __name__ == '__main__':
    main()
