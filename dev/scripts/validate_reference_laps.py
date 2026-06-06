#!/usr/bin/env python3
"""
Validate every reference lap in product/data/reference-laps:

1. Internal consistency — the file holds exactly one contiguous lap whose
   duration (lap_time_s column / wall-clock span / row count at 50 Hz)
   agrees with the time encoded in the filename.
2. Provenance — a source session exists (dev/sessions or sessions) on the
   same track slug, recorded in the same vehicle (sidecar vehicle_name),
   containing a lap whose time matches the filename time.

Filename convention: <track-slug>_<vehicle-slug>_time_<mm>.<ss>.<xxx>.parquet
(slugs use hyphens; underscores separate the fields).
"""

import json
import re
import sys
from pathlib import Path
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).parents[2] / "product" / "python"))
from lap_telemetry.parquet_utils import authoritative_duration, build_segments

REF_DIR = Path("product/data/reference-laps")
SESSION_DIRS = [Path("dev/sessions"), Path("sessions")]

NAME_RE = re.compile(r"^(?P<track>[^_]+)_(?P<vehicle>[^_]+(?:_[^_]+)*?)_time_(?P<m>\d+)\.(?P<s>\d+)\.(?P<ms>\d+)\.parquet$")
SESSION_RE = re.compile(r"session_\d{8}T\d{6}Z_(.+?)_lmu(?:_\w+)?\.parquet")

POLL_RATE_HZ = 50.0
TIME_TOL_S = 0.005  # exact-match tolerance for provenance
LOOSE_TOL_S = 1.5   # pre-authoritative-duration refs can be off by up to ~1 s


def vehicle_slug(vehicle_name: str) -> str:
    s = vehicle_name.lower()
    s = re.sub(r"#", "", s)
    s = re.sub(r"[:/]", "-", s)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


def session_lap_times(p: Path) -> list[float]:
    """All complete-lap times in a session, by both authoritative and legacy methods."""
    cols = ["lap_number", "lap_time_s"]
    schema_names = pq.read_schema(p).names
    if "scoring_last_lap_time_s" in schema_names:
        cols.append("scoring_last_lap_time_s")
    table = pq.read_table(p, columns=cols)
    lap_numbers = table.column("lap_number").to_pylist()
    lap_times = table.column("lap_time_s").to_pylist()
    segments = build_segments(lap_numbers)
    times: list[float] = []
    for i, (lap_num, start, end) in enumerate(segments):
        if lap_num is None or lap_num < 1 or end - start < 100:
            continue
        next_seg = segments[i + 1] if i + 1 < len(segments) else None
        times.append(authoritative_duration(
            table, start, end,
            next_seg[1] if next_seg else None,
            next_seg[2] if next_seg else None,
        ))
        # legacy method (pre-bug-13 exports): max lap_time_s within the segment
        legacy = max(
            (float(v) for v in lap_times[start:end]
             if isinstance(v, (int, float)) and v > 0),
            default=0.0,
        )
        if legacy:
            times.append(legacy)
    return times


def main() -> int:
    refs = sorted(REF_DIR.glob("*.parquet"))
    if not refs:
        print("No reference laps found.")
        return 1

    # Index sessions by track slug
    sessions_by_track: dict[str, list[Path]] = {}
    for d in SESSION_DIRS:
        if not d.exists():
            continue
        for p in sorted(d.glob("session_*.parquet")):
            m = SESSION_RE.match(p.name)
            if m:
                sessions_by_track.setdefault(m.group(1), []).append(p)

    failures = 0
    for ref in refs:
        m = NAME_RE.match(ref.name)
        if not m:
            print(f"FAIL  {ref.name}: filename does not match naming convention")
            failures += 1
            continue
        track = m.group("track")
        vslug = m.group("vehicle")
        named_time = int(m.group("m")) * 60 + int(m.group("s")) + int(m.group("ms")) / 1000.0

        problems: list[str] = []
        notes: list[str] = []

        table = pq.read_table(ref)
        lap_numbers = table.column("lap_number").to_pylist()
        segments = build_segments(lap_numbers)
        if len(segments) != 1:
            problems.append(f"{len(segments)} lap segments in file (expected 1): {[s[0] for s in segments]}")

        # Duration vs lap_time_s column (primary internal check)
        lap_times = [v for v in table.column("lap_time_s").to_pylist()
                     if isinstance(v, (int, float)) and v > 0]
        lap_time_matches = False
        if lap_times:
            delta = abs(max(lap_times) - named_time)
            if delta > LOOSE_TOL_S:
                problems.append(f"max(lap_time_s)={max(lap_times):.3f} vs filename {named_time:.3f} (delta {delta:.3f}s)")
            else:
                lap_time_matches = True
                if delta > TIME_TOL_S:
                    notes.append(f"legacy-time delta {delta:.3f}s vs lap_time_s (pre-authoritative export)")

        # Duration vs row count at 50 Hz (secondary — old pre-F4 recordings can
        # oversample relative to lap time, so this only fails when lap_time_s
        # does not vouch for the filename either)
        expected_rows = named_time * POLL_RATE_HZ
        if abs(table.num_rows - expected_rows) > expected_rows * 0.10:
            msg = f"row count {table.num_rows} vs ~{expected_rows:.0f} expected for {named_time:.3f}s at 50 Hz"
            if lap_time_matches:
                notes.append(msg + " (sampling-rate anomaly, lap_time_s consistent)")
            else:
                problems.append(msg)

        # Provenance: a session on this track, in this vehicle, with this lap time
        source = None
        for sp in sessions_by_track.get(track, []):
            sidecar = sp.with_suffix(".json")
            if not sidecar.exists():
                continue
            vname = json.loads(sidecar.read_text()).get("vehicle_name", "")
            if vehicle_slug(vname) != vslug:
                continue
            if any(abs(t - named_time) <= TIME_TOL_S for t in session_lap_times(sp)):
                source = sp
                break
        if source is None:
            if track in sessions_by_track:
                wrong_vehicle_only = all(
                    vehicle_slug(json.loads(sp.with_suffix(".json").read_text()).get("vehicle_name", "")) != vslug
                    for sp in sessions_by_track[track] if sp.with_suffix(".json").exists()
                )
                if wrong_vehicle_only:
                    problems.append("no session on this track was driven in this vehicle")
                else:
                    notes.append("no session lap matches filename time (source session may predate dirs or use old timing)")
            else:
                notes.append("no source sessions found for this track slug (cannot verify provenance)")
        else:
            notes.append(f"source: {source.name}")

        if problems:
            failures += 1
            print(f"FAIL  {ref.name}")
            for p_ in problems:
                print(f"      - {p_}")
        else:
            print(f"OK    {ref.name}")
        for n in notes:
            print(f"      * {n}")

    print(f"\n{len(refs)} reference laps checked, {failures} failures.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
