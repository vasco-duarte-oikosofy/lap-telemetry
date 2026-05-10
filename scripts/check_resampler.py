"""Python resampler cross-check — mirrors the browser resample() function.

Uses only pyarrow (no numpy) so it works with the system Python install.

Usage:
    python scripts/check_resampler.py <parquet_file> [--out <output.json>]

Reads lap_distance_m + speed_kph from the parquet (treats all rows as one lap),
resamples to 1 m bins via linear interpolation, writes JSON array.
"""
from __future__ import annotations

import argparse
import bisect
import json
import math
import sys
from pathlib import Path

import pyarrow.parquet as pq


def _interp(xs: list[float], ys: list[float], x: float) -> float:
    """Linear interpolation — identical logic to browser interpAt()."""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    hi = bisect.bisect_right(xs, x)
    lo = hi - 1
    t = (x - xs[lo]) / (xs[hi] - xs[lo])
    return ys[lo] + t * (ys[hi] - ys[lo])


def resample_lap(parquet_path: Path) -> list[float]:
    t = pq.read_table(parquet_path, columns=["lap_distance_m", "speed_kph"])
    xs_raw = t.column("lap_distance_m").to_pylist()
    ys_raw = t.column("speed_kph").to_pylist()

    # Sort by distance (mirrors JS sort before interp)
    pairs = sorted(zip(xs_raw, ys_raw), key=lambda p: p[0])
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]

    max_dist = int(math.ceil(xs[-1]))
    return [_interp(xs, ys, float(b)) for b in range(max_dist + 1)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("parquet", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if not args.parquet.exists():
        print(f"error: {args.parquet} not found", file=sys.stderr)
        return 1

    resampled = resample_lap(args.parquet)

    json_str = json.dumps(resampled)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json_str, encoding="utf-8")
        print(f"Wrote {len(resampled)} bins to {args.out}")
    else:
        print(json_str)

    return 0


if __name__ == "__main__":
    sys.exit(main())
