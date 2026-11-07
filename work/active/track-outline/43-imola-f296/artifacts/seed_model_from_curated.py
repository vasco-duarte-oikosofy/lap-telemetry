#!/usr/bin/env python3
"""Seed the F296 model for Imola from the curated Ginetta LMP3 model.

Imola already has a hand-curated coaching model (11 official turn names, manual
apex sides, curated short names). The Ferrari 296 GT3 is a new car for this
track, so its model does not exist — but nothing about the circuit changed,
only the braking distances. The live coach resolves by (track, canonical car),
so without this file the 296 resolves to nothing.

This copies the curated content verbatim into the new combo's file and points it
at the new reference lap. Geometry is then refreshed from that reference by
`dev/scripts/update_reference_and_coaching_model.py --ref ... --allow-unmatched`,
which is the only writer: it re-checks every curated corner against the new lap
and keeps the old geometry for the ones a GT3 lap cannot reproduce (the three
compound second halves: Villeneuve 2, Acque 2, Alta 2).

Usage:
    py work/active/track-outline/43-imola-f296/artifacts/seed_model_from_curated.py
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
COACHING_DIR = ROOT / "product" / "data" / "track-coaching"
REF_DIR = ROOT / "product" / "data" / "reference-laps"

TRACK_ID = "autodromo-enzo-e-dino-ferrari"
# The Ginetta model is the alphabetically first of the two curated Imola models
# and the one the outline turns are baked from; it also carries the curated
# short names for Rivazza 1/2 that the 499P model lost.
SOURCE_CAR = "dkr-engineering-4-elms25"
TARGET_CAR = "vista-af-corse-2026-21-lm"


def lap_time_from_name(reference: Path) -> float:
    stamp = reference.stem.split("_time_")[1]      # "01.46.173"
    minutes, seconds, millis = stamp.split(".")
    return int(minutes) * 60 + int(seconds) + int(millis) / 1000


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
    lap_time = lap_time_from_name(reference)

    seeded = copy.deepcopy(model)
    seeded["reference_lap"] = {
        "path": reference.relative_to(ROOT).as_posix(),
        "car_id": TARGET_CAR,
        "lap_time_s": round(lap_time, 3),
        "detection_method": model["reference_lap"].get("detection_method",
                                                       "throttle_brake_v1"),
    }
    target.write_text(json.dumps(seeded, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8")

    flat = [c["name"] for c in seeded["corners"] if c.get("target_throttle_pct") == 100]
    print(f"Seeded {target.name} from {source.name}")
    print(f"  reference: {reference.name} ({lap_time:.3f}s)")
    print(f"  corners:   {len(seeded['corners'])} (names/ids/apex sides/short names copied)")
    print(f"  flat:      {', '.join(flat) if flat else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
