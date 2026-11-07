#!/usr/bin/env python3
"""Stamp the simulator lap-length axis onto the Fuji Speedway base outline.

`apex_s_m` in the baked `turns` block comes from the coaching model, i.e. from
the simulator's `lap_distance_m` axis (model `lap_length_m` = 4538.9 m). The
outline's geometric centreline is only 4489.5 m, so exporting turn-label
fractions with the legacy geometric denominator would place the later corners
about 1 % late on the TinyPedal map (~50 m at Panasonic).

Long Beach (3185.3 m) and Paul Ricard 1A (5696.9 m) already carry the explicit
`lap_length_m` for exactly this reason. This stamps the same value the coaching
model uses, in the same key position, and touches nothing else in the file.

Usage:
    py work/active/track-outline/45-fuji-tinypedal-turns/artifacts/stamp_lap_length.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
OUTLINE = ROOT / "product/data/track-outlines/fuji-speedway_outline.json"
MODEL = (ROOT / "product/data/track-coaching"
         / "fuji-speedway_dkr-engineering-4-elms25.json")
# Same key position as grand-prix-of-long-beach.json / paul-ricard---1a.json.
AFTER_KEY = "units"


def main() -> int:
    outline = json.loads(OUTLINE.read_text(encoding="utf-8"))
    model = json.loads(MODEL.read_text(encoding="utf-8"))
    lap_length_m = float(model["lap_length_m"])

    if outline.get("lap_length_m") == lap_length_m:
        print(f"lap_length_m already {lap_length_m} - nothing written")
        return 0

    rebuild = {}
    for key, value in outline.items():
        rebuild[key] = value
        if key == AFTER_KEY:
            rebuild["lap_length_m"] = lap_length_m
    if "lap_length_m" not in rebuild:      # key absent -> append at the end
        rebuild["lap_length_m"] = lap_length_m

    OUTLINE.write_text(json.dumps(rebuild, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
    print(f"stamped lap_length_m={lap_length_m} (model {MODEL.name}) onto "
          f"{OUTLINE.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
