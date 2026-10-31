#!/usr/bin/env python3
"""Seed the F296 model for Monza Curva Grande from the curated Ginetta model.

The track already has a hand-curated model (official turn names, manual apex
sides, and `target_throttle_pct: 100` markers on the two flat corners that the
throttle/brake detector can never see: Curva Grande and Curva del Serraglio).
The Ferrari 296 GT3 is a new car for this track, so its model does not exist,
but nothing about the circuit changed — only the braking distances will.

This copies the curated content verbatim into the new combo's file and points it
at the new reference lap. The geometry is then refreshed from that reference by
`dev/scripts/update_reference_and_coaching_model.py --ref ... --allow-unmatched`,
which is the only writer: it re-checks every curated corner against the new lap
and keeps the old geometry for the ones the lap cannot reproduce (the flat ones).

Usage:
    py work/active/track-outline/37-monza-curva-grande-f296/artifacts/seed_model_from_curated.py
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
COACHING_DIR = ROOT / "product" / "data" / "track-coaching"
REF_DIR = ROOT / "product" / "data" / "reference-laps"

TRACK_ID = "monza-curva-grande-circuit"
SOURCE_CAR = "dkr-engineering-4-elms25"
TARGET_CAR = "vista-af-corse-2026-54-wec"


def main() -> int:
    source = COACHING_DIR / f"{TRACK_ID}_{SOURCE_CAR}.json"
    target = COACHING_DIR / f"{TRACK_ID}_{TARGET_CAR}.json"
    references = sorted(REF_DIR.glob(f"{TRACK_ID}_{TARGET_CAR}_time_*.parquet"))
    if not references:
        print(f"ERROR: no reference lap for {TRACK_ID}/{TARGET_CAR}", file=sys.stderr)
        return 1
    if target.exists():
        print(f"ERROR: {target.name} already exists - not overwriting", file=sys.stderr)
        return 1

    model = json.loads(source.read_text(encoding="utf-8"))
    reference = references[-1]

    # Filename is `..._time_MM.SS.mmm.parquet` -> seconds.
    stamp = reference.stem.split("_time_")[1]      # "01.39.398"
    minutes, seconds = stamp.split(".")[:2]
    millis = stamp.split(".")[-1]
    lap_time = int(minutes) * 60 + int(seconds) + int(millis) / 1000

    seeded = copy.deepcopy(model)
    seeded["reference_lap"] = {
        "path": str(reference.relative_to(ROOT)),
        "car_id": TARGET_CAR,
        "lap_time_s": round(lap_time, 3),
        "detection_method": model["reference_lap"].get("detection_method",
                                                       "throttle_brake_v1"),
    }
    target.write_text(json.dumps(seeded, indent=2) + "\n", encoding="utf-8")

    flat = [c["name"] for c in seeded["corners"] if c.get("target_throttle_pct") == 100]
    print(f"Seeded {target.name} from {source.name}")
    print(f"  reference: {reference.name} ({lap_time:.3f}s)")
    print(f"  corners:   {len(seeded['corners'])} (names/ids/apex sides copied)")
    print(f"  flat:      {', '.join(flat) if flat else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
