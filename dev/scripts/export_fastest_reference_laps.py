#!/usr/bin/env python3
"""
Find the fastest complete lap per track across all session directories
and export each as a reference-lap parquet file.

Output: product/data/reference-laps/<track-slug>_time_<mm>.<ss>.<xxx>.parquet
"""

import sys
import re
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.compute as pc

SESSION_DIRS = [
    Path("dev/sessions"),
    Path("sessions"),
]

OUTPUT_DIR = Path("product/data/reference-laps")

MIN_LAP_TIME_S = 60.0
MIN_LAP_POINTS = 100


def format_lap_time(seconds: float) -> str:
    minutes = int(seconds // 60)
    remaining = seconds - minutes * 60
    secs = int(remaining)
    millis = int(round((remaining - secs) * 1000))
    if millis == 1000:
        secs += 1
        millis = 0
    return f"{minutes:02d}.{secs:02d}.{millis:03d}"


def track_slug_from_path(p: Path) -> str:
    m = re.match(r"session_\d{8}T\d{6}Z_(.+)_lmu\.parquet", p.name)
    return m.group(1) if m else p.stem


def find_complete_laps(table: pa.Table) -> list[tuple[int, float]]:
    """Return (lap_number, lap_time_s) for every complete lap.

    Filters out partial laps whose row count is below 80 % of the median
    row count for all candidate laps — catches sessions where the lap counter
    incremented mid-lap and produced an impossibly short time.
    """
    if "lap_number" not in table.schema.names or "lap_time_s" not in table.schema.names:
        return []

    lap_numbers = table.column("lap_number").to_pylist()
    lap_times_col = table.column("lap_time_s").to_pylist()

    # Group lap times by lap number
    lap_time_map: dict[int, float] = {}
    for ln, lt in zip(lap_numbers, lap_times_col):
        if ln is None or ln < 1:
            continue
        if lt is not None and not (lt != lt):  # not NaN
            cur = lap_time_map.get(int(ln), 0.0)
            lap_time_map[int(ln)] = max(cur, float(lt))

    # Count rows per lap and collect candidates
    candidates = []
    for lap_num, lap_time in lap_time_map.items():
        if lap_time <= MIN_LAP_TIME_S:
            continue
        mask = pc.equal(table.column("lap_number"), lap_num)
        row_count = pc.sum(mask.cast(pa.int32())).as_py()
        if row_count < MIN_LAP_POINTS:
            continue
        candidates.append((lap_num, lap_time, row_count))

    if not candidates:
        return []

    # Compute median row count and drop outliers below 80 %
    row_counts = sorted(c[2] for c in candidates)
    median_rows = row_counts[len(row_counts) // 2]
    threshold = median_rows * 0.95

    return [(lap_num, lap_time) for lap_num, lap_time, rc in candidates if rc >= threshold]


def main():
    # Collect all parquet files per track slug
    track_sessions: dict[str, list[Path]] = {}
    for d in SESSION_DIRS:
        if not d.exists():
            print(f"  Skipping missing dir: {d}")
            continue
        for p in sorted(d.glob("session_*.parquet")):
            slug = track_slug_from_path(p)
            track_sessions.setdefault(slug, []).append(p)

    if not track_sessions:
        print("No session files found.")
        sys.exit(1)

    total = sum(len(v) for v in track_sessions.values())
    print(f"Found {total} sessions across {len(track_sessions)} tracks\n")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for slug, paths in sorted(track_sessions.items()):
        print(f"Track: {slug}  ({len(paths)} sessions)")

        best_time: float | None = None
        best_lap_num: int | None = None
        best_table: pa.Table | None = None
        best_session: Path | None = None

        for p in paths:
            table = pq.read_table(p)
            for lap_num, lap_time in find_complete_laps(table):
                if best_time is None or lap_time < best_time:
                    best_time = lap_time
                    best_lap_num = lap_num
                    best_table = table
                    best_session = p

        if best_table is None:
            print(f"  No complete laps found, skipping.\n")
            continue

        time_str = format_lap_time(best_time)
        out_path = OUTPUT_DIR / f"{slug}_time_{time_str}.parquet"

        mask = pc.equal(best_table.column("lap_number"), best_lap_num)
        lap_table = best_table.filter(mask)
        pq.write_table(lap_table, out_path)

        print(f"  Fastest: lap {best_lap_num} in {best_session.name} -> {best_time:.3f}s")
        print(f"  Exported {lap_table.num_rows} rows -> {out_path}\n")

    print("Done.")


if __name__ == "__main__":
    main()
