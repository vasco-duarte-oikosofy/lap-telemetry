"""lap-telemetry summary <file.parquet> — per-lap overview."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pyarrow.parquet as pq


def _fmt_duration(seconds: float) -> str:
    m, s = divmod(abs(seconds), 60)
    return f"{int(m)}:{s:06.3f}"


def _fmt_sector(seconds: float) -> str:
    if seconds is None or math.isnan(seconds):
        return "-"
    return f"{seconds:.3f}"


def run(path: Path) -> int:
    if not path.exists():
        print(f"lap-telemetry summary: path not found: {path}", file=sys.stderr)
        return 1

    if path.is_dir():
        return _run_dir(path)

    return _run_file(path)


def _run_dir(directory: Path) -> int:
    files = sorted(directory.glob("session_*.parquet"))
    # Exclude in-progress shards.
    files = [p for p in files if ".part" not in p.name]
    if not files:
        print(f"lap-telemetry summary: no session_*.parquet in {directory}")
        return 0

    rows: list[dict] = []
    for parquet_path in files:
        sidecar_path = parquet_path.with_suffix(".json")
        sidecar: dict = {}
        if sidecar_path.exists():
            try:
                sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                sidecar = {}
        rate_hz = sidecar.get("sample_rate_hz") or 50.0
        try:
            t = pq.read_table(parquet_path, columns=["lap_number"])
            row_count = t.num_rows
            laps = sorted(set(t.column("lap_number").to_pylist()))
            lap_count = len(laps)
        except Exception as exc:  # noqa: BLE001 — best-effort row aggregation
            row_count = sidecar.get("row_count") or 0
            lap_count = sidecar.get("lap_count") or 0
            del exc

        duration_s = row_count / rate_hz if rate_hz else 0.0
        rows.append({
            "started_utc": sidecar.get("started_utc") or "?",
            "sim":         sidecar.get("sim") or "?",
            "track":       sidecar.get("track") or "?",
            "vehicle":     sidecar.get("vehicle_name") or "?",
            "laps":        lap_count,
            "duration_s":  duration_s,
            "in_progress": bool(sidecar.get("in_progress")),
            "recovered":   bool(sidecar.get("recovered")),
        })

    rows.sort(key=lambda r: r["started_utc"])

    track_w   = max(5,  max(len(r["track"])   for r in rows))
    vehicle_w = max(7,  max(len(r["vehicle"]) for r in rows))
    sim_w     = max(3,  max(len(r["sim"])     for r in rows))

    header = (
        f"{'started_utc':<20}  {'sim':<{sim_w}}  {'track':<{track_w}}  "
        f"{'vehicle':<{vehicle_w}}  {'laps':>4}  {'duration':>10}  flags"
    )
    print(f"sessions in {directory.resolve()}  ({len(rows)} files)")
    print()
    print(header)
    print("-" * len(header))
    for r in rows:
        flags = ",".join(
            f for f, on in [("in_progress", r["in_progress"]), ("recovered", r["recovered"])] if on
        ) or "-"
        print(
            f"{r['started_utc']:<20}  {r['sim']:<{sim_w}}  {r['track']:<{track_w}}  "
            f"{r['vehicle']:<{vehicle_w}}  {r['laps']:>4}  "
            f"{_fmt_duration(r['duration_s']):>10}  {flags}"
        )
    return 0


def _run_file(path: Path) -> int:
    t = pq.read_table(path)
    schema_names = set(t.schema.names)
    has_valid_col = "lap_valid" in schema_names
    has_sectors = (
        "last_sector_1_s" in schema_names and "last_sector_2_s" in schema_names
    )

    # sidecar
    sidecar_path = path.with_suffix(".json")
    sidecar: dict = {}
    if sidecar_path.exists():
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))

    track   = sidecar.get("track")   or "?"
    vehicle = sidecar.get("vehicle_name") or "?"
    sim     = sidecar.get("sim")     or "?"
    started = sidecar.get("started_utc") or "?"
    ended   = sidecar.get("ended_utc")   or "?"
    rate_hz = sidecar.get("sample_rate_hz") or 50.0
    setup   = sidecar.get("setup_file_guess")

    duration_s = t.num_rows / rate_hz

    print(f"track  : {track}")
    print(f"vehicle: {vehicle}")
    if setup:
        print(f"setup  : {setup} (guess)")
    print(f"sim    : {sim}")
    print(f"period : {started} -> {ended}")
    print(f"rows   : {t.num_rows}  ({duration_s:.1f} s at {rate_hz} Hz)")
    print()

    # Iterate per-segment (contiguous run of constant lap_number) rather than
    # per-unique-lap_number. Frames are already in time order, so segments
    # come out chronologically. This handles race-restart rewinds (lap_number
    # going back to 0 mid-recording) and rolling-start out-laps without
    # mis-sorting or mis-detecting the first/last lap. See m3-plan.md §E1/§E2.
    lap_col      = t.column("lap_number").to_pylist()
    lap_t_col    = t.column("lap_time_s").to_pylist()
    valid_col    = t.column("lap_valid").to_pylist() if has_valid_col else None
    s1_col       = t.column("last_sector_1_s").to_pylist() if has_sectors else None
    s2_col       = t.column("last_sector_2_s").to_pylist() if has_sectors else None

    segments = _build_segments(lap_col)
    num_segs = len(segments)

    header = (
        f"{'lap':>4}   {'frames':>6}   {'duration':>10}   "
        f"{'s1':>8}   {'s2':>8}   {'s3':>8}   {'valid':>5}"
    )
    print(header)
    print("-" * len(header))

    for seg_idx, (lap_num, start_idx, end_idx) in enumerate(segments):
        frames = end_idx - start_idx
        seg_lap_t = lap_t_col[start_idx:end_idx]
        max_lap_t = max(seg_lap_t) if seg_lap_t else 0.0
        duration_str = _fmt_duration(max_lap_t)

        # Chronological first/last get the dash-out treatment — not min/max
        # by lap_number, which a restart breaks.
        is_incomplete = seg_idx == 0 or seg_idx == num_segs - 1

        if is_incomplete:
            valid_str = "-"
        elif valid_col is None:
            valid_str = "?"
        else:
            seg_valid = valid_col[start_idx:end_idx]
            valid_str = "yes" if all(seg_valid) else "no"

        s1_str = s2_str = s3_str = "-"
        if not is_incomplete and s1_col is not None and seg_idx + 1 < num_segs:
            # mLastSector* describes the previously-completed lap. The first
            # frame of the next segment *should* carry this lap's S1/S2, but
            # the SHM is sometimes mid-update at the exact boundary tick (O1)
            # or still holding the prior lap's values (O2). Walk up to 25
            # frames into the next segment to find settled values. See
            # DESIGN §10 O1/O2.
            next_seg_start = segments[seg_idx + 1][1]
            next_seg_end   = segments[seg_idx + 1][2]
            walk_end = min(next_seg_start + 25, next_seg_end)
            s1 = s2 = float("nan")
            for fi in range(next_seg_start, walk_end):
                _s1 = s1_col[fi]
                _cum = s2_col[fi]
                if (
                    not math.isnan(_s1)
                    and not math.isnan(_cum)
                    and _s1 > 0.0
                    and _cum > _s1
                ):
                    s1, cum_s2 = _s1, _cum
                    break
            valid_sectors = not math.isnan(s1)
            if valid_sectors:
                # SHM: LastSector1 = S1 dur, LastSector2 = S1+S2 cumulative.
                s1_str = _fmt_sector(s1)
                s2_str = _fmt_sector(cum_s2 - s1)
                s3_str = _fmt_sector(max_lap_t - cum_s2)

        print(
            f"{lap_num:>4}   {frames:>6}   {duration_str:>10}   "
            f"{s1_str:>8}   {s2_str:>8}   {s3_str:>8}   {valid_str:>5}"
        )

    return 0


def _build_segments(lap_col: list[int]) -> list[tuple[int, int, int]]:
    """Contiguous runs of constant lap_number, in time order.

    Returns list of (lap_number, start_idx, end_idx_exclusive). A race
    restart that rewinds mLapNumber produces multiple segments with the
    same lap_number; the user can tell them apart from session_time_s.
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
