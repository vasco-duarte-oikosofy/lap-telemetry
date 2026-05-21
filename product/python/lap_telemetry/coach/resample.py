"""Pure data-resampling helpers used by the coaching pipeline and tests.

These are kept separate from the JS pipeline wrapper because they
operate on already-resampled or synthetic data and don't need the
Node.js subprocess.
"""
from __future__ import annotations


def resample_column(distances: list[float], values: list[float], max_dist: int) -> list[float]:
    """Resample a column onto a 1-meter distance grid using linear interpolation.

    Args:
        distances: Lap distance values in meters.
        values: Corresponding values to resample.
        max_dist: Maximum distance to resample to (exclusive).

    Returns:
        List of resampled values, one per meter.
    """
    if not distances:
        return []

    sorted_pairs = sorted(zip(distances, values), key=lambda x: x[0])
    xs = [p[0] for p in sorted_pairs]
    ys = [p[1] if p[1] is not None else 0.0 for p in sorted_pairs]

    def interp(x: float) -> float:
        if x <= xs[0]:
            return ys[0]
        if x >= xs[-1]:
            return ys[-1]
        lo, hi = 0, len(xs) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if xs[mid] <= x:
                lo = mid
            else:
                hi = mid
        if xs[hi] == xs[lo]:
            return ys[lo]
        t = (x - xs[lo]) / (xs[hi] - xs[lo])
        return ys[lo] + t * (ys[hi] - ys[lo])

    return [interp(float(d)) for d in range(max_dist)]


def compute_delta_time_trace(
    driver_lap_time: list[float],
    ref_lap_time: list[float],
    track_length: int,
) -> list[float]:
    """Compute cumulative time delta at each meter from lap_time_s columns.

    This is the Python-only version for synthetic test data that doesn't
    need the full JS pipeline. For real data, use run_js_pipeline() from
    js_pipeline.py which applies all 6 pipeline steps.

    Positive = driver behind (slower cumulative time to this point).
    Negative = driver ahead (faster cumulative time to this point).
    """
    return [driver_lap_time[s] - ref_lap_time[s] for s in range(track_length)]