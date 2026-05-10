"""lap-telemetry summary <file.parquet> — per-lap overview."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pyarrow.compute as pc
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

    lap_col = t.column("lap_number").to_pylist()
    all_laps = sorted(set(lap_col))
    first_lap = all_laps[0]
    last_lap  = all_laps[-1]

    # mLastSector* on a frame describes the *previously completed* lap, so the
    # first frame of lap N+1 supplies lap N's S1/S2.
    sector_for_lap: dict[int, tuple[float, float]] = {}
    if has_sectors:
        s1_col = t.column("last_sector_1_s").to_pylist()
        s2_col = t.column("last_sector_2_s").to_pylist()
        prev_lap: int | None = None
        for lap_num, s1_val, s2_val in zip(lap_col, s1_col, s2_col):
            if prev_lap is not None and lap_num != prev_lap:
                sector_for_lap.setdefault(prev_lap, (s1_val, s2_val))
            prev_lap = lap_num

    header = (
        f"{'lap':>4}   {'frames':>6}   {'duration':>10}   "
        f"{'s1':>8}   {'s2':>8}   {'s3':>8}   {'valid':>5}"
    )
    print(header)
    print("-" * len(header))

    for lap in all_laps:
        mask = pc.equal(t.column("lap_number"), lap)
        frames = int(pc.sum(mask).as_py())

        lap_t_col = pc.filter(t.column("lap_time_s"), mask)
        max_lap_t = pc.max(lap_t_col).as_py()
        duration_str = _fmt_duration(max_lap_t)

        # incomplete laps: first (no prior boundary) and last (recording cut off)
        is_incomplete = lap == first_lap or lap == last_lap

        if is_incomplete:
            valid_str = "-"
        elif not has_valid_col:
            valid_str = "?"
        else:
            valid_col = pc.filter(t.column("lap_valid"), mask).to_pylist()
            # lap is valid if all frames on that lap report valid
            valid_str = "yes" if all(valid_col) else "no"

        s1_str = s2_str = s3_str = "-"
        if not is_incomplete and lap in sector_for_lap:
            # SHM stores LastSector1 = S1 duration, LastSector2 = S1+S2
            # cumulative. Convert to individual sector durations for display.
            s1, cum_s2 = sector_for_lap[lap]
            if not (math.isnan(s1) or math.isnan(cum_s2)):
                s1_str = _fmt_sector(s1)
                s2_str = _fmt_sector(cum_s2 - s1)
                s3_str = _fmt_sector(max_lap_t - cum_s2)
            else:
                s1_str = _fmt_sector(s1)
                s2_str = _fmt_sector(cum_s2)

        print(
            f"{lap:>4}   {frames:>6}   {duration_str:>10}   "
            f"{s1_str:>8}   {s2_str:>8}   {s3_str:>8}   {valid_str:>5}"
        )

    return 0
