#!/usr/bin/env python3
"""Verify Delta-t calculation against actual lap times."""

import pyarrow.parquet as pq

# Load the session
file = 'sessions/session_20260510T131245Z_circuit-de-barcelona_lmu.parquet'
pf = pq.read_table(file, columns=['lap_number', 'lap_time_s', 'lap_distance_m', 'speed_kph'])
data = {col: pf[col].to_pylist() for col in pf.column_names}

print("=" * 80)
print("Delta-t Verification: session_20260510T131245Z_circuit-de-barcelona_lmu.parquet")
print("=" * 80)

# Group by lap
laps = {}
for i, lap_num in enumerate(data['lap_number']):
    if lap_num not in laps:
        laps[lap_num] = []
    laps[lap_num].append(i)

# Get lap info
lap_nums = sorted(laps.keys())
print("\nAvailable laps: " + str(lap_nums) + "\n")

# Find two complete laps (skip partial ones that are much shorter)
# Calculate lap times to find complete laps
lap_times = {}
for lap_num in lap_nums:
    frames = laps[lap_num]
    times = [data['lap_time_s'][i] for i in frames]
    lap_times[lap_num] = max(times) - min(times)

# Print all lap times to understand the data
print("Lap times:")
for ln in lap_nums:
    print("  Lap %d: %.1f s" % (ln, lap_times[ln]))

# Find median lap time - use that as threshold for "complete" lap
sorted_times = sorted(lap_times.values())
median_time = sorted_times[len(sorted_times)//2] if sorted_times else 0

# Filter for laps within 10% of median (roughly complete)
complete_laps = [ln for ln in lap_nums if abs(lap_times[ln] - median_time) < median_time * 0.1]
print("Complete laps (within 10% of median): " + str(complete_laps))

if len(complete_laps) < 2:
    # If not enough, just use the longest two laps
    sorted_by_time = sorted(lap_nums, key=lambda x: lap_times[x], reverse=True)
    complete_laps = sorted_by_time[:2]
    print("Using longest two laps instead: " + str(complete_laps))

if len(complete_laps) < 2:
    print("ERROR: Not enough laps to compare")
    exit(1)

# Use the last two complete laps
lap1_num = complete_laps[-2]
lap2_num = complete_laps[-1]

lap1_frames = laps[lap1_num]
lap2_frames = laps[lap2_num]

def get_lap_time(frames):
    """Get total lap time from frame indices."""
    times = [data['lap_time_s'][i] for i in frames]
    return max(times) - min(times)

lap1_time = get_lap_time(lap1_frames)
lap2_time = get_lap_time(lap2_frames)
actual_delta = (lap1_time - lap2_time) * 1000  # Convert to ms

print("Lap %d: %.3fs = %d:%.6f" % (lap1_num, lap1_time, int(lap1_time//60), lap1_time%60))
print("Lap %d: %.3fs = %d:%.6f" % (lap2_num, lap2_time, int(lap2_time//60), lap2_time%60))
print("\nActual time difference: %.1f ms (lap %d is %.1f ms %s)" % (
    actual_delta, lap1_num, abs(actual_delta), 'slower' if actual_delta > 0 else 'faster'))

# Now compute Dt using the resampler logic
def interpAt(xs, ys, x):
    """Interpolate value at distance x."""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]

    # Check if x matches any cluster exactly
    first_cluster_idx = -1
    for i in range(len(xs)):
        if xs[i] == x:
            first_cluster_idx = i
            break

    # If we found a cluster at distance x, average all values in the cluster
    if first_cluster_idx >= 0:
        cluster_vals = [ys[i] for i in range(len(xs)) if xs[i] == x]
        return sum(cluster_vals) / len(cluster_vals)

    # Otherwise do normal binary search interpolation
    lo, hi = 0, len(xs) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if xs[mid] <= x:
            lo = mid
        else:
            hi = mid

    # Linear interpolation
    t = (x - xs[lo]) / (xs[hi] - xs[lo])
    return ys[lo] + t * (ys[hi] - ys[lo])

def resample(distances, values, maxDist):
    """Resample to 1m bins."""
    # Sort by distance with stable sort (tie-break by index)
    sorted_pairs = sorted(enumerate(distances), key=lambda x: (x[1], x[0]))
    indices = [i for i, d in sorted_pairs]

    xs = [distances[i] for i in indices]
    ys = [values[i] for i in indices]

    # Debug: check for clusters
    clusters = {}
    for i, x in enumerate(xs):
        x_int = int(x)
        if x_int not in clusters:
            clusters[x_int] = 0
        clusters[x_int] += 1

    cluster_count = sum(1 for c in clusters.values() if c > 1)
    total_in_clusters = sum(c for c in clusters.values() if c > 1)
    print("  Clusters detected: %d bins with %d total frames" % (cluster_count, total_in_clusters))

    bins = [0] * (maxDist + 1)
    for bin_idx in range(maxDist + 1):
        bins[bin_idx] = interpAt(xs, ys, bin_idx)

    return bins

def computeDeltaT(sessionSpeed, refSpeed):
    """Compute Delta-t from speeds."""
    length = min(len(sessionSpeed), len(refSpeed))
    dt = [0] * length
    cumDt = 0

    for i in range(length):
        vs = max(sessionSpeed[i] / 3.6, 0.3)  # m/s, guard zero
        vr = max(refSpeed[i] / 3.6, 0.3)
        # Time to travel 1m at each speed (seconds), diff in ms
        cumDt += (1 / vs - 1 / vr) * 1000
        dt[i] = cumDt

    return dt

# Get raw data for lap 1
lap1_dist = [data['lap_distance_m'][i] for i in lap1_frames]
lap1_speed = [data['speed_kph'][i] for i in lap1_frames]

# Get raw data for lap 2
lap2_dist = [data['lap_distance_m'][i] for i in lap2_frames]
lap2_speed = [data['speed_kph'][i] for i in lap2_frames]

max_dist1 = int(max(lap1_dist)) + 1
max_dist2 = int(max(lap2_dist)) + 1
max_dist = max(max_dist1, max_dist2)

print("\nResampling %d frames to %d m bins..." % (len(lap1_dist), max_dist))

# Resample
lap1_speed_bins = resample(lap1_dist, lap1_speed, max_dist)
lap2_speed_bins = resample(lap2_dist, lap2_speed, max_dist)

# Compute Delta-t
dt_bins = computeDeltaT(lap1_speed_bins, lap2_speed_bins)

computed_delta = dt_bins[-1]  # Total Delta-t at end of lap

print("Computed Delta-t: %.1f ms" % computed_delta)
error_pct = 100*abs(actual_delta - computed_delta)/abs(actual_delta) if actual_delta != 0 else 0
print("\nDifference: %.1f ms (%.1f%%)" % (abs(actual_delta - computed_delta), error_pct))

if abs(actual_delta - computed_delta) < 10:
    print("PASS: Delta-t calculation is accurate (< 10ms error)")
elif abs(actual_delta - computed_delta) < 50:
    print("WARNING: Delta-t calculation has moderate error (10-50ms)")
else:
    print("FAIL: Delta-t calculation has large error (> 50ms)")

# Print median frame distance delta to show data quality
deltas = []
for i in range(1, len(lap1_dist)):
    d = lap1_dist[i] - lap1_dist[i-1]
    if d > 0:
        deltas.append(d)

if deltas:
    deltas.sort()
    median_delta = deltas[len(deltas)//2]
    print("\nData quality: median frame-distance delta = %.2f m" % median_delta)
    if median_delta > 2:
        print("Pre-F4 recording (coarse distance data)")
    else:
        print("Post-F4 recording (fine distance data)")
else:
    print("\nNo distance deltas found")
