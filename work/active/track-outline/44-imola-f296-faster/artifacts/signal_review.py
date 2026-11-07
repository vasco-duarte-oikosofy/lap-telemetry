#!/usr/bin/env python3
"""Why Tamburello's zone is preserved instead of refreshed from the new lap.

The detector's Tamburello *exit* boundary is not a corner edge: it is where the
driver's throttle climbs back above 0.90 after the apex. That point moves by
tens of metres lap to lap (partial throttle, lift, tow), so refreshing it from a
single lap bakes one lap's throttle modulation into the model. Every other
corner's zone is stable within ~20 m, so only t1 is preserved.

Usage:
    py work/active/track-outline/44-imola-f296-faster/artifacts/signal_review.py
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
from update_reference_and_coaching_model import detect_corners  # noqa: E402

SESSION = ROOT / "sessions/session_20261107T125508Z_autodromo-enzo-e-dino-ferrari_lmu_practice.parquet"
MODEL = (ROOT / "product/data/track-coaching"
         / "autodromo-enzo-e-dino-ferrari_vista-af-corse-2026-21-lm.json")


def main() -> int:
    model = json.loads(MODEL.read_text(encoding="utf-8"))
    table = pq.read_table(SESSION)
    tmp = Path(tempfile.gettempdir()) / "imola_signal_review.parquet"

    laps = list(find_complete_laps(table))
    print(f"session: {SESSION.name}")
    print(f"laps: {', '.join(f'lap {lap} @ {dur:.3f}s' for lap, dur, _, _ in laps)}")
    print()
    print("Detector zones per lap - entry/apex/exit (m)")
    header = "corner".ljust(24) + "".join(f"lap{lap}".rjust(22) for lap, _, _, _ in laps)
    print(header)
    print("-" * len(header))
    for corner in model["corners"]:
        cells = []
        for lap, _, start, end in laps:
            pq.write_table(table.slice(start, end - start), tmp)
            candidates, _ = detect_corners(tmp)
            nearest = min(candidates, key=lambda c: abs(c.apex_m - corner["apex_s_m"]))
            cells.append(f"{nearest.s_start_m:.0f}/{nearest.apex_m:.0f}/{nearest.s_end_m:.0f}")
        print(f"{corner['id']:>3} {corner['name']:<20}" + "".join(c.rjust(22) for c in cells))

    tmp.unlink(missing_ok=True)
    print()
    print("Tamburello exit boundary spread:")
    exits = []
    for lap, _, start, end in laps:
        pq.write_table(table.slice(start, end - start), tmp)
        candidates, _ = detect_corners(tmp)
        exits.append(min(candidates, key=lambda c: c.apex_m).s_end_m)
    tmp.unlink(missing_ok=True)
    print(f"  min={min(exits):.0f}m max={max(exits):.0f}m spread={max(exits) - min(exits):.0f}m "
          f"-> throttle-modulation artefact, not a corner edge")
    print(f"  model keeps the reviewed zone: apex={model['corners'][0]['apex_s_m']:.0f}m "
          f"exit={model['corners'][0]['s_end_m']:.0f}m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
