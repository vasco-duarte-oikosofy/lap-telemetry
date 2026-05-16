"""Extract one chronological lap segment from a session parquet.

Usage:
    python scripts/extract_reference_lap.py <session.parquet> --segment N [--out <output.parquet>]

--segment N  1-indexed chronological position (1 = first recorded segment,
             which is usually an out-lap; pick a middle one for a clean reference).

Example — extract lap 5 (fastest) from the 6-lap Barcelona session:
    python scripts/extract_reference_lap.py \\
        dev/sessions/session_20260510T093245Z_circuit-de-barcelona_lmu.parquet \\
        --segment 5 \\
        --out dev/sessions/reference_lap_circuit-de-barcelona_lap5.parquet
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pyarrow.parquet as pq
import pyarrow as pa


def _build_segments(lap_col: list[int]) -> list[tuple[int, int, int]]:
    """Contiguous runs of constant lap_number, in time order.
    Returns list of (lap_number, start_idx, end_idx_exclusive).
    """
    if not lap_col:
        return []
    segs: list[tuple[int, int, int]] = []
    prev = lap_col[0]
    start = 0
    for i in range(1, len(lap_col)):
        if lap_col[i] != prev:
            segs.append((prev, start, i))
            prev = lap_col[i]
            start = i
    segs.append((prev, start, len(lap_col)))
    return segs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("session", type=Path, help="Session parquet file")
    parser.add_argument("--segment", type=int, required=True, help="1-indexed chronological segment to extract")
    parser.add_argument("--out", type=Path, default=None, help="Output path (default: auto-named next to session)")
    args = parser.parse_args()

    if not args.session.exists():
        print(f"error: file not found: {args.session}", file=sys.stderr)
        return 1

    t = pq.read_table(args.session)
    lap_col = t.column("lap_number").to_pylist()
    segments = _build_segments(lap_col)

    print(f"Session: {args.session}")
    print(f"Total segments: {len(segments)}")
    for i, (lap_num, start, end) in enumerate(segments):
        lap_t_col = t.column("lap_time_s").to_pylist()[start:end]
        duration = max(lap_t_col) if lap_t_col else 0.0
        m, s = divmod(duration, 60)
        print(f"  Segment {i+1}: lap_number={lap_num}, frames={end-start}, duration={int(m)}:{s:06.3f}")

    n = args.segment
    if n < 1 or n > len(segments):
        print(f"error: --segment {n} out of range (1..{len(segments)})", file=sys.stderr)
        return 1

    lap_num, start, end = segments[n - 1]
    slice_table = t.slice(start, end - start)

    out_path = args.out
    if out_path is None:
        stem = args.session.stem
        out_path = args.session.parent / f"reference_lap_{stem}_seg{n}.parquet"

    pq.write_table(slice_table, out_path, compression="snappy")
    print(f"\nExtracted segment {n} (lap_number={lap_num}, {end-start} rows) -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
