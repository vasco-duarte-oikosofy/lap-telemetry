#!/usr/bin/env python3
"""Evidence for the 2026-11-07 Fuji P3 reference decision (read-only).

Question: is the fast quali lap (1:36.544, 20 ms quicker than the 1:36.564
reference) a better reference/model source?

Answer: no. This script prints the three facts that decide it:
  1. the lap yields the same 9 braking events as the current reference;
  2. the two curated corners it "loses" (13th Corner, Netz) have no event of
     their own even on the current reference — they are manual markers;
  3. the greedy matcher (bug 29) would hand the Netz Hairpin event to Netz,
     moving it +75 m in apex and +136 m in exit — corruption, not a refresh;
  4. the corners it *would* refresh move by lap-to-lap noise amounts
     (100R's event apex spans ~85 m across today's laps).

Usage:
    py work/active/track-outline/46-fuji-p3-quali-reference/artifacts/decision_evidence.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "product" / "python"))
sys.path.insert(0, str(ROOT / "dev" / "scripts"))

from export_fastest_reference_laps import find_complete_laps  # noqa: E402
from update_reference_and_coaching_model import (  # noqa: E402
    detect_corners, match_corners,
)

SESSIONS = [
    ROOT / "sessions/session_20261107T141839Z_fuji-speedway_lmu_quali.parquet",
    ROOT / "sessions/session_20261107T142746Z_fuji-speedway_lmu_race.parquet",
]
MODEL = (ROOT / "product/data/track-coaching"
         / "fuji-speedway_dkr-engineering-4-elms25.json")
REF = (ROOT / "product/data/reference-laps"
       / "fuji-speedway_dkr-engineering-4-elms25_time_01.36.564.parquet")


def events_for(path: Path, start: int | None = None, end: int | None = None):
    table = pq.read_table(path)
    if start is not None:
        tmp = Path(tempfile.gettempdir()) / "fuji_decision_lap.parquet"
        pq.write_table(table.slice(start, end - start), tmp)
        candidates, _ = detect_corners(tmp)
        tmp.unlink(missing_ok=True)
        return candidates
    return detect_corners(path)[0]


def main() -> int:
    model = json.loads(MODEL.read_text(encoding="utf-8"))
    corners = model["corners"]

    print(f"current reference: {REF.name} ({model['reference_lap']['lap_time_s']}s)")
    ref_events = events_for(REF)
    print(f"  detected events: {len(ref_events)} -> "
          + ", ".join(f"{c.apex_m:.0f}" for c in ref_events))
    print(f"model corners:     {len(corners)}")

    print("\n1. events per lap in today's quali + race")
    per_lap = []
    for session in SESSIONS:
        table = pq.read_table(session)
        print(f"   {session.name}")
        for lap, duration, start, end in find_complete_laps(table):
            candidates = events_for(session, start, end)
            per_lap.append((session.name[8:24], lap, duration, candidates))
            print(f"     lap {lap:>2} {duration:8.3f}s -> {len(candidates):>2} events: "
                  + ", ".join(f"{c.apex_m:.0f}" for c in candidates))

    fastest = min(per_lap, key=lambda row: row[2])
    print(f"\n2. fastest lap: {fastest[0]} lap {fastest[1]} @ {fastest[2]:.3f}s")

    print("\n3. what the greedy matcher would do (bug 29)")
    pairs, leftover = match_corners(corners, fastest[3])
    for old, match in pairs:
        if match is None:
            print(f"   {old['name']:<14} {old['apex_s_m']:>6.0f} -> UNMATCHED (keeps geometry)")
            continue
        moved = max(abs(match.s_start_m - old["s_start_m"]),
                    abs(match.apex_m - old["apex_s_m"]),
                    abs(match.s_end_m - old["s_end_m"]))
        flag = "  <-- STEALS ITS NEIGHBOUR'S EVENT" if old["id"] == "netz" else ""
        print(f"   {old['name']:<14} {old['apex_s_m']:>6.0f} -> "
              f"{match.s_start_m:>6.0f}/{match.apex_m:>6.0f}/{match.s_end_m:>6.0f} "
              f"(max move {moved:>5.0f} m){flag}")
    if leftover:
        print(f"   leftover events: {', '.join(f'{c.apex_m:.0f}' for c in leftover)}")

    print("\n4. the manual markers have no event even on the current reference")
    for corner_id in ("11", "12", "13th_corner", "netz", "netz_hairpin"):
        corner = next(c for c in corners if c["id"] == corner_id)
        near = [c for c in ref_events
                if abs(c.apex_m - corner["apex_s_m"]) <= 150]
        own = any(abs(c.apex_m - corner["apex_s_m"]) <= 5 for c in near)
        print(f"   {corner['name']:<14} apex {corner['apex_s_m']:>6.0f}  "
              f"zone {corner['s_start_m']:>6.0f}-{corner['s_end_m']:<6.0f} "
              f"event within 5 m: {'yes' if own else 'NO (manual)'}")

    print("\n5. noise in the corners the refresh would touch (clean laps only)")
    clean = [row for row in per_lap if row[2] <= fastest[2] + 1.5]
    print(f"   clean laps used: {len(clean)} of {len(per_lap)}")
    for corner_id in ("100r", "panasonic"):
        corner = next(c for c in corners if c["id"] == corner_id)
        apexes = []
        for _, _, _, candidates in clean:
            nearest = min(candidates, key=lambda c: abs(c.apex_m - corner["apex_s_m"]))
            apexes.append(nearest.apex_m)
        print(f"   {corner['name']:<14} model {corner['apex_s_m']:>6.0f} | "
              f"today's laps span {min(apexes):.0f}-{max(apexes):.0f} "
              f"({max(apexes) - min(apexes):.0f} m)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
