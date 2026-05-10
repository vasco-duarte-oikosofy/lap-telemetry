"""lap-telemetry summary <file.parquet> — per-lap overview."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pyarrow.compute as pc
import pyarrow.parquet as pq


def _fmt_duration(seconds: float) -> str:
    m, s = divmod(abs(seconds), 60)
    return f"{int(m)}:{s:06.3f}"


def run(path: Path) -> int:
    if not path.exists():
        print(f"lap-telemetry summary: file not found: {path}", file=sys.stderr)
        return 1

    t = pq.read_table(path)
    has_valid_col = "lap_valid" in t.schema.names

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

    duration_s = t.num_rows / rate_hz

    print(f"track  : {track}")
    print(f"vehicle: {vehicle}")
    print(f"sim    : {sim}")
    print(f"period : {started} -> {ended}")
    print(f"rows   : {t.num_rows}  ({duration_s:.1f} s at {rate_hz} Hz)")
    print()

    lap_col = t.column("lap_number").to_pylist()
    all_laps = sorted(set(lap_col))
    first_lap = all_laps[0]
    last_lap  = all_laps[-1]

    header = f"{'lap':>4}   {'frames':>6}   {'duration':>10}   {'valid':>5}"
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

        print(f"{lap:>4}   {frames:>6}   {duration_str:>10}   {valid_str:>5}")

    return 0
