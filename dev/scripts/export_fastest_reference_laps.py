#!/usr/bin/env python3
"""
Export the fastest complete lap of ONE (track, vehicle) combo as a
reference-lap parquet file.

Usage:
    python export_fastest_reference_laps.py <session.parquet | dir> [...]

Scope is explicit and SINGLE-combo (bug 22): all targets must resolve to the
same track and vehicle, otherwise the run aborts before writing anything.
Bulk export of all tracks is intentionally impossible — one run changes at
most one reference lap, and a mandatory post-export audit verifies that on
disk. An existing reference for the same (track, vehicle) is only replaced
when the new lap is faster by more than 1 ms; the superseded file is deleted
so duplicates never accumulate.

See dev/scripts/EXTRACT_AND_STORE_REFERENCE_LAP.md for the full workflow.

Output: product/data/reference-laps/<track-slug>_<vehicle-slug>_time_<mm>.<ss>.<xxx>.parquet
"""

import argparse
import json
import sys
import re
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).parents[2] / "product" / "python"))
from lap_telemetry.parquet_utils import authoritative_duration, build_segments

OUTPUT_DIR = Path("product/data/reference-laps")

MIN_LAP_TIME_S = 60.0
MIN_LAP_POINTS = 100

TIME_SUFFIX_RE = re.compile(r"_time_(\d+)\.(\d+)\.(\d+)\.parquet$")


def format_lap_time(seconds: float) -> str:
    minutes = int(seconds // 60)
    remaining = seconds - minutes * 60
    secs = int(remaining)
    millis = int(round((remaining - secs) * 1000))
    if millis == 1000:
        secs += 1
        millis = 0
    return f"{minutes:02d}.{secs:02d}.{millis:03d}"


def parse_lap_time_from_name(p: Path) -> float | None:
    m = TIME_SUFFIX_RE.search(p.name)
    if not m:
        return None
    mins, secs, millis = (int(g) for g in m.groups())
    return mins * 60 + secs + millis / 1000.0


def track_slug_from_path(p: Path) -> str:
    m = re.match(r"session_\d{8}T\d{6}Z_(.+?)_lmu(?:_\w+)?\.parquet", p.name)
    return m.group(1) if m else p.stem


def vehicle_slug(vehicle_name: str) -> str:
    s = vehicle_name.lower()
    s = re.sub(r"#", "", s)
    s = re.sub(r"[:/]", "-", s)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


def read_vehicle_name(session_parquet: Path) -> str:
    sidecar = session_parquet.with_suffix(".json")
    if sidecar.exists():
        return json.loads(sidecar.read_text()).get("vehicle_name", "")
    return ""


def segment_wall_clock_span(table: pa.Table, seg_start: int, seg_end: int) -> float | None:
    """Wall-clock span of a segment from session_time_s (None if unavailable)."""
    if "session_time_s" not in table.schema.names:
        return None
    values = table.column("session_time_s").to_pylist()[seg_start:seg_end]
    numeric = [float(v) for v in values if isinstance(v, (int, float))]
    if len(numeric) < 2:
        return None
    return numeric[-1] - numeric[0]


def find_complete_laps(table: pa.Table) -> list[tuple[int, float, int, int]]:
    """Return (lap_number, lap_time_s, seg_start, seg_end) for every complete lap.

    Uses authoritative_duration (prefers scoring_last_lap_time_s from the sim's
    official scorer over max(lap_time_s)) to avoid the undercount caused by
    mLapStartET resetting before all frames for the outgoing lap are recorded.

    Bug 22 guards:
    - Each candidate is a contiguous SEGMENT, not a lap number — sessions
      recorded across sim restarts repeat lap numbers, and the same lap number
      can name two different laps.
    - The segment's wall-clock span must agree with the claimed lap time
      (rejects restart-truncated segments with bogus authoritative times).

    Filters out partial laps whose row count is below 95 % of the median.
    """
    if "lap_number" not in table.schema.names or "lap_time_s" not in table.schema.names:
        return []

    lap_numbers = table.column("lap_number").to_pylist()
    segments = build_segments(lap_numbers)

    candidates = []
    for i, (lap_num, seg_start, seg_end) in enumerate(segments):
        if lap_num is None or lap_num < 1:
            continue
        row_count = seg_end - seg_start
        if row_count < MIN_LAP_POINTS:
            continue
        next_seg = segments[i + 1] if i + 1 < len(segments) else None
        lap_time = authoritative_duration(
            table, seg_start, seg_end,
            next_seg[1] if next_seg else None,
            next_seg[2] if next_seg else None,
        )
        if lap_time <= MIN_LAP_TIME_S:
            continue
        span = segment_wall_clock_span(table, seg_start, seg_end)
        if span is not None and abs(span - lap_time) > max(3.0, 0.05 * lap_time):
            continue
        candidates.append((lap_num, lap_time, seg_start, seg_end))

    if not candidates:
        return []

    # Drop outliers below 95 % of median row count (catches partial laps)
    row_counts = sorted(end - start for _, _, start, end in candidates)
    median_rows = row_counts[len(row_counts) // 2]
    threshold = median_rows * 0.95

    return [c for c in candidates if (c[3] - c[2]) >= threshold]


def collect_session_files(targets: list[Path]) -> list[Path]:
    files: list[Path] = []
    for t in targets:
        if t.is_dir():
            files.extend(sorted(t.glob("session_*.parquet")))
        elif t.is_file():
            files.append(t)
        else:
            print(f"  Skipping missing target: {t}")
    return files


def existing_refs(track_slug: str, vslug: str) -> list[tuple[Path, float]]:
    """Existing reference files for this (track, vehicle), with parsed times."""
    out = []
    for p in OUTPUT_DIR.glob(f"{track_slug}_{vslug}_time_*.parquet"):
        t = parse_lap_time_from_name(p)
        if t is not None:
            out.append((p, t))
    return out


def snapshot_output_dir() -> dict[str, tuple[int, float]]:
    """Name -> (size, mtime) for every reference parquet currently on disk."""
    return {
        p.name: (p.stat().st_size, p.stat().st_mtime)
        for p in OUTPUT_DIR.glob("*.parquet")
    }


def audit_single_lap_change(
    before: dict[str, tuple[int, float]],
    after: dict[str, tuple[int, float]],
    tslug: str,
    vslug: str,
) -> list[str]:
    """Mandatory post-export audit (bug 22): at most ONE reference lap may
    change per run — one new file for the target (track, vehicle), plus
    deletions of the references it superseded. Anything else is a violation."""
    prefix = f"{tslug}_{vslug}_time_"
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    modified = sorted(n for n in set(before) & set(after) if before[n] != after[n])

    violations = []
    if len(added) > 1:
        violations.append(f"more than one reference written: {added}")
    for name in added + removed + modified:
        if not name.startswith(prefix):
            violations.append(
                f"file outside target (track, vehicle) changed: {name} "
                f"(expected only {prefix}*)"
            )
    if modified:
        violations.append(
            f"existing reference overwritten in place: {modified} "
            "(references must only ever be added or superseded, never rewritten)"
        )
    return violations


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Export the fastest complete lap of ONE (track, vehicle) combo as a "
            "reference-lap parquet into product/data/reference-laps/. "
            "The targets must all belong to the same track and vehicle; the run "
            "aborts before writing anything if they don't. Bulk export of all "
            "tracks is intentionally impossible (bug 22): one run = at most one "
            "reference lap changed, verified by a mandatory post-export audit."
        ),
        epilog=(
            "examples:\n"
            "  # export from one session file (the normal case)\n"
            "  python dev/scripts/export_fastest_reference_laps.py \\\n"
            "      sessions/session_20260606T064918Z_autdromo-jos-carlos-pace_lmu_practice.parquet\n"
            "\n"
            "  # consider several sessions of the SAME track+vehicle at once\n"
            "  python dev/scripts/export_fastest_reference_laps.py \\\n"
            "      sessions/session_*_fuji-speedway_lmu*.parquet\n"
            "\n"
            "An existing reference for the same (track, vehicle) is kept unless the\n"
            "new lap is faster by more than 1 ms; when replaced, the superseded file\n"
            "is deleted so at most one reference per (track, vehicle) exists."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "targets", nargs="+", type=Path, metavar="SESSION",
        help=(
            "session parquet file(s) and/or directories containing them; all "
            "must resolve to a single (track, vehicle) combo"
        ),
    )
    args = parser.parse_args()

    session_files = collect_session_files(args.targets)
    if not session_files:
        print("No session files found.")
        sys.exit(1)

    # Group sessions by (track slug, vehicle slug)
    groups: dict[tuple[str, str], list[Path]] = {}
    for p in session_files:
        tslug = track_slug_from_path(p)
        vname = read_vehicle_name(p)
        vslug = vehicle_slug(vname) if vname else "unknown"
        groups.setdefault((tslug, vslug), []).append(p)

    # Hard scope guard (bug 22): exactly one (track, vehicle) combo per run.
    # We NEVER export all reference laps at the same time.
    if len(groups) != 1:
        combos = "\n".join(
            f"  {t} / {v}  ({len(ps)} sessions)" for (t, v), ps in sorted(groups.items())
        )
        parser.error(
            f"targets span {len(groups)} (track, vehicle) combos — a run may "
            f"only export ONE reference lap. Re-run once per combo:\n{combos}"
        )

    (tslug, vslug), paths = next(iter(groups.items()))
    print(f"Track: {tslug}  Vehicle: {vslug}  ({len(paths)} sessions)")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    before = snapshot_output_dir()

    best_time: float | None = None
    best_lap_num: int | None = None
    best_seg: tuple[int, int] | None = None
    best_table: pa.Table | None = None
    best_session: Path | None = None

    for p in paths:
        table = pq.read_table(p)
        for lap_num, lap_time, seg_start, seg_end in find_complete_laps(table):
            if best_time is None or lap_time < best_time:
                best_time = lap_time
                best_lap_num = lap_num
                best_seg = (seg_start, seg_end)
                best_table = table
                best_session = p

    if best_table is None:
        print("  No complete laps found - nothing exported.")
        sys.exit(1)

    # Only replace an existing reference when strictly faster (bug 22).
    # Filename times are ms-resolution, so require a >1 ms improvement —
    # float jitter must not count as "faster".
    existing = existing_refs(tslug, vslug)
    existing_best = min((t for _, t in existing), default=None)
    if existing_best is not None and best_time > existing_best - 0.001:
        print(
            f"  Fastest found {best_time:.3f}s is not faster than existing "
            f"reference {existing_best:.3f}s - keeping existing."
        )
        print("\nAUDIT: 0 reference laps changed.")
        return

    time_str = format_lap_time(best_time)
    out_path = OUTPUT_DIR / f"{tslug}_{vslug}_time_{time_str}.parquet"

    # Slice the exact segment — never filter by lap_number, which merges
    # repeated lap numbers across sim restarts (bug 22 / bug 19 pattern)
    seg_start, seg_end = best_seg
    lap_table = best_table.slice(seg_start, seg_end - seg_start)
    pq.write_table(lap_table, out_path)

    print(f"  Fastest: lap {best_lap_num} in {best_session.name} -> {best_time:.3f}s")
    print(f"  Exported {lap_table.num_rows} rows -> {out_path}")
    for old_path, old_time in existing:
        if old_path == out_path:
            continue  # never delete the file just written
        old_path.unlink()
        print(f"  Removed superseded reference ({old_time:.3f}s): {old_path.name}")

    # Mandatory audit: verify on disk that only this one reference changed
    after = snapshot_output_dir()
    violations = audit_single_lap_change(before, after, tslug, vslug)
    if violations:
        print("\nAUDIT FAILED - more than one reference lap changed:")
        for v in violations:
            print(f"  - {v}")
        print("Inspect product/data/reference-laps and recover via git before committing.")
        sys.exit(1)

    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    print(f"\nAUDIT: 1 reference lap changed (added: {added}, superseded: {removed}). OK.")


if __name__ == "__main__":
    main()
