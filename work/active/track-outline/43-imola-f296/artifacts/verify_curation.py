#!/usr/bin/env python3
"""Prove the F296 Imola model keeps every curated field of the source model.

Compares the curated Imola model (`dkr-engineering-4-elms25`) with the refreshed
F296 model (`vista-af-corse-2026-21-lm`) corner by corner. Curated fields must be
byte-identical; only the braking geometry (`s_start_m`, `apex_s_m`, `s_end_m`)
and the reference block may differ.

Usage:
    py work/active/track-outline/43-imola-f296/artifacts/verify_curation.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
COACHING_DIR = ROOT / "product" / "data" / "track-coaching"

TRACK_ID = "autodromo-enzo-e-dino-ferrari"
SOURCE_CAR = "dkr-engineering-4-elms25"
TARGET_CAR = "vista-af-corse-2026-21-lm"
GEOMETRY_FIELDS = {"s_start_m", "apex_s_m", "s_end_m"}


def main() -> int:
    source = json.loads((COACHING_DIR / f"{TRACK_ID}_{SOURCE_CAR}.json")
                        .read_text(encoding="utf-8"))
    target = json.loads((COACHING_DIR / f"{TRACK_ID}_{TARGET_CAR}.json")
                        .read_text(encoding="utf-8"))
    failures: list[str] = []

    if len(source["corners"]) != len(target["corners"]):
        failures.append(f"corner count {len(target['corners'])} != {len(source['corners'])}")

    for old, new in zip(source["corners"], target["corners"]):
        curated_old = {k: v for k, v in old.items() if k not in GEOMETRY_FIELDS}
        curated_new = {k: v for k, v in new.items() if k not in GEOMETRY_FIELDS}
        if curated_old != curated_new:
            failures.append(f"{old['id']} curated fields changed: {curated_old} -> {curated_new}")
        moved = [f"{f} {old[f]}->{new[f]}" for f in GEOMETRY_FIELDS if old[f] != new[f]]
        print(f"{new['id']:>4} {new['name']:<24} "
              f"short={str(new.get('short_name')):<14} side={new['apex_side']:<5} "
              f"flat={new.get('target_throttle_pct')} "
              f"{'| ' + ', '.join(moved) if moved else '| geometry unchanged (preserved)'}")

    flat = [c["id"] for c in target["corners"] if c.get("target_throttle_pct") == 100]
    print(f"\ncurated corners: {len(target['corners'])}")
    print(f"flat markers:    {flat or 'none in the curated Imola model'}")
    print(f"reference:       {target['reference_lap']['path']} "
          f"({target['reference_lap']['lap_time_s']}s)")

    if failures:
        print("\nFAIL")
        for line in failures:
            print(f"  - {line}")
        return 1
    print("\nOK - every name, id, short name, apex side and flat marker preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
