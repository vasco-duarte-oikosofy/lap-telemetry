#!/usr/bin/env python3
"""
compare_session.py — Compare session laps against a reference lap.

Outputs structured JSON to stdout with corner-by-corner analysis,
distance-level delta traces, and ranked time-loss zones.

Usage:
  python compare_session.py <session_paths...> --ref <reference_parquet> [--coaching <coaching_json>] [--compare <session_paths...>]
  python compare_session.py <session_paths...> --ref <reference_parquet> [--coaching <coaching_json>] --label <name>

Modes:
  Single:   Analyze one set of sessions against the reference.
  Compare:  Analyze two session sets side-by-side (--compare provides the second set).

All paths are relative to the project root (CWD).
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_reference(path: str) -> dict:
    """Load reference lap and return dict with distance, speed, throttle, brake, cumulative time.

    Computes cumulative time from speed/distance, then normalizes to match the
    known reference lap time (extracted from filename pattern like _time_MM.SS.mmm).
    This is more reliable than session_time_s which may wrap in extracted laps.
    """
    df = pd.read_parquet(path).sort_values('lap_distance_m').reset_index(drop=True)
    dist = df['lap_distance_m'].values.astype(float)
    speed = df['speed_kph'].values.astype(float)

    # Compute raw cumulative time from speed and distance
    dt = np.diff(dist) / (speed[:-1] / 3.6 + 1e-10)  # avoid div-by-zero
    cum_time = np.zeros(len(dist))
    cum_time[1:] = np.cumsum(dt)

    # Normalize to known reference time from filename
    known_time = _parse_reference_time(path)
    total_time = known_time if known_time else cum_time[-1]
    if known_time and cum_time[-1] > 0:
        cum_time = cum_time * (known_time / cum_time[-1])

    return {
        'lap_distance_m': dist,
        'cum_time': cum_time,
        'speed_kph': speed,
        'throttle_norm': df['throttle_norm'].values.astype(float),
        'brake_norm': df['brake_norm'].values.astype(float),
        'total_dist': float(dist.max()),
        'total_time': float(total_time),
    }


def _parse_reference_time(path: str) -> float | None:
    """Extract reference lap time from filename pattern like _time_01.38.541.parquet."""
    import re
    m = re.search(r'_time_(\d+)\.(\d+)\.(\d+)', str(path))
    if m:
        minutes = int(m.group(1))
        seconds = int(m.group(2))
        millis = int(m.group(3))
        return minutes * 60 + seconds + millis / 1000.0
    return None


def load_corners(path: str) -> list[dict]:
    """Load corner definitions from coaching model JSON."""
    with open(path) as f:
        data = json.load(f)
    corners = data.get('corners', data.get('turns', []))
    normalized = []
    for c in corners:
        normalized.append({
            'id': c.get('id', ''),
            'name': c.get('name', ''),
            'entry_m': c.get('s_start_m', c.get('entry_distance_m', 0)),
            'apex_m': c.get('apex_s_m', c.get('apex_distance_m', 0)),
            'exit_m': c.get('s_end_m', c.get('exit_distance_m', 0)),
            'apex_side': c.get('apex_side', ''),
        })
    return normalized


def get_valid_laps(path: str, ref_total_dist: float,
                   min_time: float = 97, max_time: float = 110) -> list[dict]:
    """Extract valid complete laps from a session file."""
    df = pd.read_parquet(path)
    if 'lap_valid' not in df.columns:
        return []
    laps = []
    for ln in sorted(df['lap_number'].unique()):
        ldf = df[df['lap_number'] == ln].copy()
        if len(ldf) < 4000:
            continue
        if ldf['lap_valid'].iloc[0] != 1:
            continue
        lt = ldf['session_time_s'].iloc[-1] - ldf['session_time_s'].iloc[0]
        if lt < min_time or lt > max_time:
            continue
        if (ldf['lap_distance_m'].max() - ldf['lap_distance_m'].min()) < ref_total_dist * 0.9:
            continue
        laps.append({'lap_number': int(ln), 'lap_time': float(lt), 'df': ldf})
    return laps


# ---------------------------------------------------------------------------
# Analysis core
# ---------------------------------------------------------------------------

def interpolate_at_bins(lap_df: pd.DataFrame, bin_centers: np.ndarray,
                        *columns: str) -> list[np.ndarray]:
    """Interpolate lap data at reference distance bin centers."""
    lap = lap_df.sort_values('lap_distance_m').reset_index(drop=True)
    results = []
    for col in columns:
        results.append(np.interp(bin_centers, lap['lap_distance_m'].values,
                                  lap[col].values))
    return results


def compute_analysis(laps: list[dict], bin_centers: np.ndarray,
                     ref_cum_bins: np.ndarray, ref_speed_bins: np.ndarray,
                     ref_throttle_bins: np.ndarray, ref_brake_bins: np.ndarray) -> dict:
    """Compute delta and telemetry traces for a set of laps."""
    all_deltas = []
    all_speeds = []
    all_throttles = []
    all_brakes = []

    for lap in laps:
        ldf = lap['df'].sort_values('lap_distance_m').reset_index(drop=True)
        cum = ldf['session_time_s'].values - ldf['session_time_s'].iloc[0]
        # Extrapolate=clamp: for points beyond lap distance range, use last value
        lap_cum = np.interp(bin_centers, ldf['lap_distance_m'].values, cum,
                             left=float(cum[0]), right=float(cum[-1]))
        all_deltas.append(lap_cum - ref_cum_bins)

        spd, = interpolate_at_bins(ldf, bin_centers, 'speed_kph')
        thr, = interpolate_at_bins(ldf, bin_centers, 'throttle_norm')
        brk, = interpolate_at_bins(ldf, bin_centers, 'brake_norm')
        all_speeds.append(spd)
        all_throttles.append(thr)
        all_brakes.append(brk)

    all_deltas = np.array(all_deltas)
    all_speeds = np.array(all_speeds)
    all_throttles = np.array(all_throttles)
    all_brakes = np.array(all_brakes)

    return {
        'n_laps': len(laps),
        'lap_times': [lap['lap_time'] for lap in laps],
        'median_delta': np.median(all_deltas, axis=0).tolist(),
        'mean_delta': np.mean(all_deltas, axis=0).tolist(),
        'mean_speed': np.mean(all_speeds, axis=0).tolist(),
        'mean_throttle': np.mean(all_throttles, axis=0).tolist(),
        'mean_brake': np.mean(all_brakes, axis=0).tolist(),
        'all_deltas': all_deltas.tolist(),
        'deltas_per_lap': [row.tolist() for row in all_deltas],
    }


def corner_analysis(corners: list[dict], bin_centers: np.ndarray,
                    analysis: dict, ref_speed_bins: np.ndarray,
                    ref_throttle_bins: np.ndarray, ref_brake_bins: np.ndarray,
                    label: str = '') -> list[dict]:
    """Compute per-corner metrics from an analysis dict."""
    median_delta = np.array(analysis['median_delta'])
    all_deltas = np.array(analysis['all_deltas'])
    mean_speed = np.array(analysis['mean_speed'])
    mean_throttle = np.array(analysis['mean_throttle'])
    mean_brake = np.array(analysis['mean_brake'])

    results = []
    for c in corners:
        e_idx = int(np.argmin(np.abs(bin_centers - c['entry_m'])))
        a_idx = int(np.argmin(np.abs(bin_centers - c['apex_m'])))
        x_idx = int(np.argmin(np.abs(bin_centers - c['exit_m'])))

        time_lost = float(median_delta[x_idx] - median_delta[e_idx])
        consistency = float(np.mean(
            (all_deltas[:, x_idx] - all_deltas[:, e_idx]) > 0))

        results.append({
            'name': c['name'],
            'entry_m': c['entry_m'],
            'apex_m': c['apex_m'],
            'exit_m': c['exit_m'],
            'delta_entry': float(median_delta[e_idx]),
            'delta_apex': float(median_delta[a_idx]),
            'delta_exit': float(median_delta[x_idx]),
            'time_lost': time_lost,
            'consistency': consistency,
            'apex_speed': float(mean_speed[a_idx]),
            'ref_apex_speed': float(ref_speed_bins[a_idx]),
            'speed_diff': float(mean_speed[a_idx] - ref_speed_bins[a_idx]),
            'apex_throttle': float(mean_throttle[a_idx]),
            'ref_apex_throttle': float(ref_throttle_bins[a_idx]),
            'apex_brake': float(mean_brake[a_idx]),
            'ref_apex_brake': float(ref_brake_bins[a_idx]),
        })
    return results


def zone_analysis(corners: list[dict], bin_centers: np.ndarray,
                  analysis: dict, ref_total_dist: float) -> list[dict]:
    """Find worst 300m zones across the lap."""
    median_delta = np.array(analysis['median_delta'])
    all_deltas = np.array(analysis['all_deltas'])

    zone_width = 30  # 30 bins * 10m = 300m
    zones = []
    for start in range(0, len(bin_centers) - zone_width):
        end = start + zone_width
        growth = float(median_delta[end - 1] - median_delta[start])
        consist = float(np.mean(
            (all_deltas[:, end - 1] - all_deltas[:, start]) > 0))
        zones.append({
            'start_m': float(bin_centers[start]),
            'end_m': float(bin_centers[end - 1]),
            'time_lost': growth,
            'consistency': consist,
        })

    # Filter: consistency >= 70%, sort by time_lost descending
    zones = sorted([z for z in zones if z['consistency'] >= 0.7],
                   key=lambda z: z['time_lost'], reverse=True)

    # Deduplicate overlapping zones (keep best, skip within 200m)
    deduped = []
    for z in zones:
        if not any(abs(z['start_m'] - d['start_m']) < 200 for d in deduped):
            deduped.append(z)

    # Tag with nearest corner name
    for z in deduped:
        mid = (z['start_m'] + z['end_m']) / 2
        nearest = min(corners, key=lambda c: abs(c['apex_m'] - mid),
                      default=None)
        z['nearest_corner'] = nearest['name'] if nearest else ''

    return deduped[:10]


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def format_side_by_side(primary: dict, comparison: dict | None,
                       corners: list[dict], bin_centers: np.ndarray,
                       ref: dict, ref_speed_bins: np.ndarray,
                       ref_throttle_bins: np.ndarray,
                       ref_brake_bins: np.ndarray) -> str:
    """Format human-readable side-by-side analysis."""
    lines = []

    # Overall
    p = primary
    p_best = min(p['lap_times'])
    p_avg = np.mean(p['lap_times'])
    ref_time = ref['total_time']

    lines.append("=" * 100)
    lines.append("SESSION ANALYSIS VS REFERENCE")
    lines.append("=" * 100)
    lines.append(f"  Reference lap time:  {ref_time:.3f}s")
    lines.append(f"  Laps analyzed:        {p['n_laps']}")

    if comparison:
        c = comparison
        c_best = min(c['lap_times'])
        c_avg = np.mean(c['lap_times'])
        lines.append(f"  --- PRIMARY ---")
        lines.append(f"  Best lap:   {p_best:.3f}s  (+{p_best - ref_time:.3f}s)")
        lines.append(f"  Avg lap:    {p_avg:.3f}s  (+{p_avg - ref_time:.3f}s)")
        lines.append(f"  --- COMPARISON ---")
        lines.append(f"  Best lap:   {c_best:.3f}s  (+{c_best - ref_time:.3f}s)")
        lines.append(f"  Avg lap:    {c_avg:.3f}s  (+{c_avg - ref_time:.3f}s)")
        lines.append(f"  Delta (primary - comparison avg): {p_avg - c_avg:+.3f}s")
    else:
        lines.append(f"  Best lap:   {p_best:.3f}s  (+{p_best - ref_time:.3f}s)")
        lines.append(f"  Avg lap:    {p_avg:.3f}s  (+{p_avg - ref_time:.3f}s)")

    # Corner-by-corner
    p_corners = corner_analysis(corners, bin_centers, p,
                                ref_speed_bins, ref_throttle_bins, ref_brake_bins,
                                label='Primary')

    lines.append("")
    lines.append("=" * 100)
    lines.append("CORNER-BY-CORNER ANALYSIS")
    lines.append("=" * 100)

    if comparison:
        c_corners = corner_analysis(corners, bin_centers, c,
                                    ref_speed_bins, ref_throttle_bins, ref_brake_bins,
                                    label='Comparison')
        header = (f"{'Corner':>16} | {'Pri apex_d':>9} {'Cmp apex_d':>9} {'chng':>6} | "
                   f"{'Pri lost':>8} {'Cmp lost':>8} {'chng':>6} | "
                   f"{'Pri spd':>7} {'Cmp spd':>7} {'Ref spd':>7} | verdict")
        lines.append(header)
        lines.append("-" * len(header))

        for pc, cc in zip(p_corners, c_corners):
            change_lost = cc['time_lost'] - pc['time_lost']  # positive = primary was better
            change_apex = pc['delta_apex'] - cc['delta_apex']
            verdict = "BETTER" if change_lost > 0.05 else ("WORSE" if change_lost < -0.05 else "~same")
            # Note: change_lost is flipped perspective — positive means primary loses MORE time
            # Let's make it from primary's perspective: positive = primary improved over comparison
            # Actually change_lost = cmp - pri, so positive means cmp is worse = primary is BETTER
            # Let me recompute clearly:
            # pc['time_lost'] = time primary loses in this corner
            # cc['time_lost'] = time comparison loses in this corner
            # delta = pc['time_lost'] - cc['time_lost']
            # positive delta = primary loses more = WORSE
            delta = pc['time_lost'] - cc['time_lost']
            verdict = "WORSE" if delta > 0.05 else ("BETTER" if delta < -0.05 else "~same")
            spd_diff_p = pc['speed_diff']
            spd_diff_c = cc['speed_diff']

            lines.append(
                f"{pc['name']:>16} | {pc['delta_apex']:+.3f}s  {cc['delta_apex']:+.3f}s  {delta:+.3f}s | "
                f"{pc['time_lost']:+.3f}s  {cc['time_lost']:+.3f}s  {delta:+.3f}s | "
                f"{pc['apex_speed']:5.0f}   {cc['apex_speed']:5.0f}   {pc['ref_apex_speed']:5.0f}  | "
                f"{verdict}"
            )
    else:
        lines.append(f"\n{'Corner':>16} | {'apex delta':>10} | {'time lost':>10} {'consist':>8} | "
                      f"{'apex spd':>8} {'ref spd':>8} {'diff':>6} | {'thr':>4} {'brk':>4}")
        lines.append("-" * 95)
        for c in p_corners:
            spd_tag = "SLOW" if c['speed_diff'] < -3 else ("FAST" if c['speed_diff'] > 3 else "match")
            lines.append(
                f"{c['name']:>16} | {c['delta_apex']:+.3f}s    | {c['time_lost']:+.3f}s    {c['consistency']:.0%}     | "
                f"{c['apex_speed']:5.0f}   {c['ref_apex_speed']:5.0f}   {c['speed_diff']:+.0f} {spd_tag} | "
                f"{c['apex_throttle']:.0%} {c['apex_brake']:.0%}"
            )

    # Zone ranking
    p_zones = zone_analysis(corners, bin_centers, p, ref['total_dist'])
    lines.append("")
    lines.append("=" * 100)
    lines.append("WORST ZONES (300m windows where time is consistently lost)")
    lines.append("=" * 100)
    lines.append(f"\n{'Start':>6} {'End':>6} {'Time lost':>10} {'Consist':>8}  Nearest corner")
    lines.append("-" * 60)
    for z in p_zones:
        lines.append(f"  {z['start_m']:4.0f}m  {z['end_m']:4.0f}m  {z['time_lost']:+.3f}s     "
                      f"{z['consistency']:.0%}     {z['nearest_corner']}")

    # Distance trace (every 100m)
    lines.append("")
    lines.append("=" * 100)
    lines.append("DELTA TRACE (every 100m)")
    lines.append("=" * 100)

    if comparison:
        lines.append(f"\n{'Dist':>6} | {'Pri d':>8} {'Cmp d':>8} {'Change':>8} | "
                      f"{'Pri spd':>8} {'Cmp spd':>8} {'Ref spd':>8}")
        lines.append("-" * 75)
        p_med = np.array(p['median_delta'])
        c_med = np.array(c['median_delta'])
        p_spd = np.array(p['mean_speed'])
        c_spd = np.array(c['mean_speed'])
        for i in range(0, len(bin_centers), 10):
            d = bin_centers[i]
            pd_ = p_med[i]
            cd_ = c_med[i]
            ch = cd_ - pd_
            tag = " <-- WORSE" if ch > 0.05 else (" <-- BETTER" if ch < -0.05 else "")
            lines.append(f"  {d:4.0f}m | {pd_:+.3f}s  {cd_:+.3f}s  {ch:+.3f}s | "
                         f"{p_spd[i]:5.0f}   {c_spd[i]:5.0f}   {ref_speed_bins[i]:5.0f}{tag}")
    else:
        lines.append(f"\n{'Dist':>6} | {'Delta':>8} {'Speed':>8} {'Ref spd':>8} {'Diff':>6} | Corner")
        lines.append("-" * 65)
        p_med = np.array(p['median_delta'])
        p_spd = np.array(p['mean_speed'])
        for i in range(0, len(bin_centers), 10):
            d = bin_centers[i]
            # Find corner context
            ctx = ""
            for cr in corners:
                if cr['entry_m'] - 50 <= d <= cr['exit_m'] + 50:
                    ctx = cr['name']
                    break
            spd_diff = p_spd[i] - ref_speed_bins[i]
            tag = " SLOW" if spd_diff < -5 else (" FAST" if spd_diff > 5 else "")
            lines.append(f"  {d:4.0f}m | {p_med[i]:+.3f}s  {p_spd[i]:5.0f}   "
                         f"{ref_speed_bins[i]:5.0f}   {spd_diff:+.0f}{tag} | {ctx}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Session comparison analysis')
    parser.add_argument('sessions', nargs='+', help='Primary session parquet files')
    parser.add_argument('--ref', required=True, help='Reference lap parquet file')
    parser.add_argument('--coaching', help='Coaching model JSON (auto-detected if not given)')
    parser.add_argument('--compare', nargs='+', help='Comparison session files (for side-by-side)')
    parser.add_argument('--label', default='Primary', help='Label for primary session set')
    parser.add_argument('--compare-label', default='Comparison', help='Label for comparison set')
    parser.add_argument('--min-time', type=float, default=97, help='Min lap time filter')
    parser.add_argument('--max-time', type=float, default=110, help='Max lap time filter')
    parser.add_argument('--json', action='store_true', help='Output raw JSON instead of text')
    args = parser.parse_args()

    # Load reference
    ref = load_reference(args.ref)
    ref_total_dist = ref['total_dist']

    # Auto-detect coaching model from reference path
    coaching_path = args.coaching
    if not coaching_path:
        # Derive from reference filename: track_car_time.parquet -> track_car.json
        ref_stem = Path(args.ref).stem  # e.g. fuji-speedway-classic_vista-af-corsa-2026-54-wec_time_01.38.541
        track_car = '_'.join(ref_stem.split('_time_')[0].split('_')[:-1]) if '_time_' in ref_stem else ref_stem
        # Try product/data/track-coaching/<track_car>.json
        candidate = Path('product/data/track-coaching') / f"{track_car}.json"
        if candidate.exists():
            coaching_path = str(candidate)
        else:
            # Try matching by track part
            track_part = track_car.split('_')[0]
            candidates = list(Path('product/data/track-coaching').glob(f"{track_part}*.json"))
            if candidates:
                coaching_path = str(candidates[0])

    # Load corners
    corners = load_corners(coaching_path) if coaching_path else []

    # Build distance bins (10m resolution)
    bin_width = 10
    max_dist = ref['total_dist'] - 1  # Stay inside reference data range
    dist_bins = np.arange(0, max_dist, bin_width)
    bin_centers = (dist_bins[:-1] + dist_bins[1:]) / 2
    ref_cum_bins = np.interp(bin_centers, ref['lap_distance_m'], ref['cum_time'])
    ref_speed_bins = np.interp(bin_centers, ref['lap_distance_m'], ref['speed_kph'])
    ref_throttle_bins = np.interp(bin_centers, ref['lap_distance_m'], ref['throttle_norm'])
    ref_brake_bins = np.interp(bin_centers, ref['lap_distance_m'], ref['brake_norm'])

    # Load primary laps
    primary_laps = []
    for path in args.sessions:
        primary_laps.extend(get_valid_laps(path, ref_total_dist, args.min_time, args.max_time))
    if not primary_laps:
        print("ERROR: No valid laps found in primary sessions", file=sys.stderr)
        sys.exit(1)

    # Skip laps that match the reference lap time exactly (they ARE the reference)
    ref_lap_time = ref['total_time']
    primary_laps = [l for l in primary_laps if abs(l['lap_time'] - ref_lap_time) > 0.05]

    primary = compute_analysis(primary_laps, bin_centers, ref_cum_bins,
                              ref_speed_bins, ref_throttle_bins, ref_brake_bins)

    # Load comparison laps if given
    comparison = None
    if args.compare:
        comp_laps = []
        for path in args.compare:
            comp_laps.extend(get_valid_laps(path, ref_total_dist, args.min_time, args.max_time))
        comp_laps = [l for l in comp_laps if abs(l['lap_time'] - ref_lap_time) > 0.05]
        if comp_laps:
            comparison = compute_analysis(comp_laps, bin_centers, ref_cum_bins,
                                          ref_speed_bins, ref_throttle_bins, ref_brake_bins)

    # Output
    if args.json:
        output = {
            'reference_time': ref_total_dist,  # this is actually the total distance, not time
            'reference_lap_time': ref['total_time'],
            'primary': {
                'n_laps': primary['n_laps'],
                'lap_times': primary['lap_times'],
                'corners': corner_analysis(corners, bin_centers, primary,
                                           ref_speed_bins, ref_throttle_bins, ref_brake_bins),
                'zones': zone_analysis(corners, bin_centers, primary, ref['total_dist']),
                'bin_centers': bin_centers.tolist(),
                'median_delta': primary['median_delta'],
                'mean_speed': primary['mean_speed'],
            },
            'corners_defined': corners,
        }
        if comparison:
            output['comparison'] = {
                'n_laps': comparison['n_laps'],
                'lap_times': comparison['lap_times'],
                'corners': corner_analysis(corners, bin_centers, comparison,
                                           ref_speed_bins, ref_throttle_bins, ref_brake_bins),
                'zones': zone_analysis(corners, bin_centers, comparison, ref['total_dist']),
                'median_delta': comparison['median_delta'],
                'mean_speed': comparison['mean_speed'],
            }
        print(json.dumps(output, indent=2))
    else:
        text = format_side_by_side(primary, comparison, corners, bin_centers,
                                  ref, ref_speed_bins, ref_throttle_bins, ref_brake_bins)
        print(text)


if __name__ == '__main__':
    main()