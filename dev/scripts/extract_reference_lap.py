"""Extract one chronological lap segment from a session parquet.

Usage:
    python scripts/extract_reference_lap.py <session.parquet> --segment N [--out <output.parquet>]

--segment N      1-indexed chronological position (1 = first recorded segment,
                 which is usually an out-lap; pick a middle one for a clean reference).
--valid-only     Skip segments where any row has lap_valid=False (track-limit
                 violations, penalties, etc.).  The segment listing marks each
                 segment [valid] or [INVALID] accordingly; --segment / --lap will refuse to
                 extract a segment that fails this check.

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
    parser.add_argument("--segment", type=int, default=None, help="1-indexed chronological segment to extract")
    parser.add_argument("--lap", type=int, default=None, help="Lap number to extract (matches lap_number column)")
    parser.add_argument("--out", type=Path, default=None, help="Output path (default: auto-named next to session)")
    parser.add_argument("--valid-only", action="store_true",
                        help="Only consider segments where all rows have lap_valid=True")
    args = parser.parse_args()

    if not args.session.exists():
        print(f"error: file not found: {args.session}", file=sys.stderr)
        return 1

    t = pq.read_table(args.session)
    lap_col = t.column("lap_number").to_pylist()
    segments = _build_segments(lap_col)

    valid_col = t.column("lap_valid").to_pylist() if "lap_valid" in t.schema.names else None

    def _is_valid_seg(start: int, end: int) -> bool:
        if valid_col is None:
            return True
        return all(v is True for v in valid_col[start:end])

    print(f"Session: {args.session}")
    print(f"Total segments: {len(segments)}")
    for i, (lap_num, start, end) in enumerate(segments):
        lap_t_col = t.column("lap_time_s").to_pylist()[start:end]
        duration = max(lap_t_col) if lap_t_col else 0.0
        m, s = divmod(duration, 60)
        valid_tag = f"  {'[valid]' if _is_valid_seg(start, end) else '[INVALID]'}" if valid_col is not None else ""
        print(f"  Segment {i+1}: lap_number={lap_num}, frames={end-start}, duration={int(m)}:{s:06.3f}{valid_tag}")

    if args.segment is None and args.lap is None:
        print("error: --segment or --lap is required", file=sys.stderr)
        return 1
    if args.segment is not None and args.lap is not None:
        print("error: specify --segment or --lap, not both", file=sys.stderr)
        return 1

    if args.lap is not None:
        # Find the segment(s) matching this lap number; pick the fastest one
        matching = [(i, seg) for i, seg in enumerate(segments) if seg[0] == args.lap]
        if not matching:
            print(f"error: lap_number {args.lap} not found in session", file=sys.stderr)
            return 1
        if args.valid_only:
            matching = [(i, seg) for i, seg in matching if _is_valid_seg(seg[1], seg[2])]
            if not matching:
                print(f"error: no valid segment found for lap_number {args.lap} (--valid-only)", file=sys.stderr)
                return 1
        # Pick the segment with the shortest lap time (handles multi-stint sessions)
        best_i, _ = min(
            matching,
            key=lambda x: max(t.column('lap_time_s').to_pylist()[x[1][1]:x[1][2]])
        )
        n = best_i + 1
        lap_num, start, end = segments[best_i]
        duration = max(t.column('lap_time_s').to_pylist()[start:end])
        m, s = divmod(duration, 60)
        print(f"Using segment {n} for lap_number={lap_num} ({end - start} rows, {int(m)}:{s:06.3f})")
    else:
        n = args.segment
        if n < 1 or n > len(segments):
            print(f"error: --segment {n} out of range (1..{len(segments)})", file=sys.stderr)
            return 1
        lap_num, start, end = segments[n - 1]
        if args.valid_only and not _is_valid_seg(start, end):
            print(f"error: segment {n} (lap_number={lap_num}) has invalid rows (--valid-only)", file=sys.stderr)
            return 1
    slice_table = t.slice(start, end - start)
    extracted_duration = max(t.column('lap_time_s').to_pylist()[start:end])
    mins, secs = divmod(extracted_duration, 60)

    out_path = args.out
    if out_path is None:
        stem = args.session.stem
        out_path = args.session.parent / f"reference_lap_{stem}_seg{n}.parquet"

    pq.write_table(slice_table, out_path, compression="snappy")
    print(f"\nExtracted segment {n} (lap_number={lap_num}, {end-start} rows) -> {out_path}")
    print(f"Lap time: {int(mins)}:{secs:06.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
