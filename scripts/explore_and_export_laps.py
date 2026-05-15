#!/usr/bin/env python3
"""
Explore laps in a session parquet and export selected laps as JSON.

This script helps you:
1. List all laps in a session with their times and validity
2. Export specific laps as JSON for use with tools/manual_outline_align.html

Usage:
    # List laps in a session
    python3 scripts/explore_and_export_laps.py sessions/session_*.parquet

    # Export specific laps (e.g., laps 3 and 5)
    python3 scripts/explore_and_export_laps.py sessions/session_*.parquet --export 3,5

    # Export fastest 3 complete laps
    python3 scripts/explore_and_export_laps.py sessions/session_*.parquet --fastest 3

    # Export all complete laps
    python3 scripts/explore_and_export_laps.py sessions/session_*.parquet --export-all
"""

import argparse
import json
import sys
from pathlib import Path
import pandas as pd


def load_session(parquet_path):
    """Load a session parquet file and return DataFrame with lap info."""
    df = pd.read_parquet(parquet_path)
    return df


def get_lap_summary(df):
    """
    Get summary of all laps in the session.
    
    Returns list of dicts with:
    - lap_number
    - lap_time_s (final lap time, NaN for incomplete laps)
    - row_count (number of telemetry points)
    - is_complete (lap_time > 60s indicates full racing lap)
    - distance_m (lap distance)
    """
    laps = []
    
    for lap_num in sorted(df['lap_number'].unique()):
        lap_df = df[df['lap_number'] == lap_num]
        
        # Get lap time (use max as it's the final recorded time)
        lap_times = lap_df['lap_time_s'].dropna() if 'lap_time_s' in lap_df.columns else pd.Series()
        lap_time = float(lap_times.max()) if len(lap_times) > 0 else None
        
        # Get lap distance
        distances = lap_df['lap_distance_m'].dropna() if 'lap_distance_m' in lap_df.columns else pd.Series()
        distance = float(distances.max()) if len(distances) > 0 else None
        
        laps.append({
            'lap_number': int(lap_num),
            'lap_time_s': lap_time,
            'row_count': len(lap_df),
            'distance_m': distance,
            'is_complete': lap_time is not None and lap_time > 60.0
        })
    
    return laps


def print_lap_summary(parquet_path, laps):
    """Print a formatted summary of all laps."""
    print(f"\n{'='*80}")
    print(f"Session: {Path(parquet_path).name}")
    print(f"{'='*80}\n")
    
    # Header
    print(f"{'Lap':<6} {'Time (s)':<12} {'Points':<10} {'Distance (m)':<14} {'Status':<12}")
    print(f"{'-'*6} {'-'*12} {'-'*10} {'-'*14} {'-'*12}")
    
    for lap in laps:
        time_str = f"{lap['lap_time_s']:.2f}" if lap['lap_time_s'] is not None else "N/A"
        dist_str = f"{lap['distance_m']:.1f}" if lap['distance_m'] is not None else "N/A"
        status = "✅ Complete" if lap['is_complete'] else "⏳ Incomplete"
        
        print(f"{lap['lap_number']:<6} {time_str:<12} {lap['row_count']:<10} {dist_str:<14} {status:<12}")
    
    # Summary
    complete_laps = [l for l in laps if l['is_complete']]
    print(f"\n{'='*80}")
    print(f"Total laps: {len(laps)} | Complete laps (>60s): {len(complete_laps)}")
    
    if complete_laps:
        fastest = min(complete_laps, key=lambda x: x['lap_time_s'])
        print(f"Fastest: Lap {fastest['lap_number']} ({fastest['lap_time_s']:.2f}s)")
    print(f"{'='*80}\n")


def export_lap(df, lap_number, output_dir, track_name=None):
    """Export a single lap as JSON for use with manual_outline_align.html."""
    lap_df = df[df['lap_number'] == lap_number].sort_values('lap_distance_m')
    
    # Extract points
    points = []
    for _, row in lap_df.iterrows():
        x = row.get('pos_x_m')
        y = row.get('pos_z_m')  # LMU uses Z for lateral
        if x is not None and y is not None and pd.notna(x) and pd.notna(y):
            points.append({'x': float(x), 'y': float(y)})
    
    if len(points) < 100:
        print(f"  ⚠️  Lap {lap_number}: Only {len(points)} points, skipping")
        return None
    
    # Get lap time
    lap_times = lap_df['lap_time_s'].dropna()
    lap_time = float(lap_times.max()) if len(lap_times) > 0 else None
    
    # Build output
    output = {
        'track_name': track_name or 'Unknown',
        'trajectories': [
            {
                'name': f"session.parquet lap {lap_number}",
                'points': points,
                'lap_time_s': lap_time
            }
        ]
    }
    
    # Write output
    output_path = output_dir / f"lap{lap_number}.json"
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"  ✅ Exported lap {lap_number}: {len(points)} points → {output_path}")
    return output_path


def export_fastest_laps(df, laps, n, output_dir, track_name=None):
    """Export the N fastest complete laps."""
    complete_laps = [l for l in laps if l['is_complete']]
    
    if len(complete_laps) == 0:
        print("  ❌ No complete laps found (lap_time > 60s)")
        return []
    
    # Sort by lap time
    complete_laps_sorted = sorted(complete_laps, key=lambda x: x['lap_time_s'])
    
    # Take fastest N
    fastest = complete_laps_sorted[:n]
    
    print(f"\nExporting fastest {len(fastest)} complete laps:\n")
    
    exported = []
    for lap in fastest:
        path = export_lap(df, lap['lap_number'], output_dir, track_name)
        if path:
            exported.append((path, lap['lap_time_s']))
    
    print(f"\nExported {len(exported)} laps:")
    for i, (path, time) in enumerate(exported, 1):
        print(f"  {i}. {path.name} ({time:.2f}s)")
    
    return exported


def main():
    parser = argparse.ArgumentParser(
        description='Explore laps in a session parquet and export selected laps as JSON.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List laps in a session
  python3 scripts/explore_and_export_laps.py sessions/session_*.parquet

  # Export specific laps (e.g., laps 3 and 5)
  python3 scripts/explore_and_export_laps.py sessions/session_*.parquet --export 3,5

  # Export fastest 3 complete laps
  python3 scripts/explore_and_export_laps.py sessions/session_*.parquet --fastest 3

  # Export all complete laps
  python3 scripts/explore_and_export_laps.py sessions/session_*.parquet --export-all
        """
    )
    
    parser.add_argument('parquet_file', type=Path, help='Session parquet file')
    parser.add_argument('--export', type=str, help='Export specific laps (comma-separated, e.g., "3,5")')
    parser.add_argument('--fastest', type=int, help='Export N fastest complete laps')
    parser.add_argument('--export-all', action='store_true', help='Export all complete laps')
    parser.add_argument('--output-dir', type=Path, default=Path('data/track-outlines/alignment-artifacts/exported-laps'),
                        help='Output directory for exported JSON files')
    
    args = parser.parse_args()
    
    # Check file exists
    if not args.parquet_file.exists():
        print(f"❌ File not found: {args.parquet_file}")
        sys.exit(1)
    
    # Load session
    print(f"Loading {args.parquet_file.name}...")
    df = load_session(args.parquet_file)
    
    # Try to get track name from sidecar JSON
    track_name = None
    sidecar_path = args.parquet_file.with_suffix('.json')
    if sidecar_path.exists():
        try:
            with open(sidecar_path) as f:
                meta = json.load(f)
                track_name = meta.get('track', args.parquet_file.stem)
                print(f"Track: {track_name}")
        except Exception as e:
            print(f"Warning: Could not read sidecar: {e}")
    
    # Get lap summary
    laps = get_lap_summary(df)
    
    # Print summary
    print_lap_summary(args.parquet_file, laps)
    
    # Export requested laps
    if args.export:
        # Parse lap numbers
        lap_numbers = [int(x.strip()) for x in args.export.split(',')]
        
        # Create output directory
        args.output_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\nExporting laps: {', '.join(map(str, lap_numbers))}\n")
        
        for lap_num in lap_numbers:
            # Check lap exists
            lap_info = next((l for l in laps if l['lap_number'] == lap_num), None)
            if not lap_info:
                print(f"  ⚠️  Lap {lap_num} not found in session")
                continue
            
            export_lap(df, lap_num, args.output_dir, track_name)
    
    elif args.fastest:
        # Create output directory
        args.output_dir.mkdir(parents=True, exist_ok=True)
        
        export_fastest_laps(df, laps, args.fastest, args.output_dir, track_name)
    
    elif args.export_all:
        # Create output directory
        args.output_dir.mkdir(parents=True, exist_ok=True)
        
        complete_laps = [l for l in laps if l['is_complete']]
        print(f"\nExporting all {len(complete_laps)} complete laps:\n")
        
        for lap in complete_laps:
            export_lap(df, lap['lap_number'], args.output_dir, track_name)
    
    else:
        # Just show summary
        print("Use --export, --fastest, or --export-all to export laps.")
        print("\nExample: python3 scripts/explore_and_export_laps.py sessions/session_*.parquet --fastest 3")


if __name__ == '__main__':
    main()
