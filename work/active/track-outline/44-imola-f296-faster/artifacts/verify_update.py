#!/usr/bin/env python3
"""Prove the faster-lap refresh kept every curated field of the Imola F296 model.

Compares `artifacts/model-before.json` (1:46.173 refresh) with the model on disk
(1:45.534 refresh). Curated fields must be identical; only `s_start_m`,
`apex_s_m`, `s_end_m` and the reference block may change.

Usage:
    py work/active/track-outline/44-imola-f296-faster/artifacts/verify_update.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
MODEL = (ROOT / "product/data/track-coaching"
         / "autodromo-enzo-e-dino-ferrari_vista-af-corse-2026-21-lm.json")
BEFORE = Path(__file__).resolve().parent / "model-before.json"
GEOMETRY = {"s_start_m", "apex_s_m", "s_end_m"}


def curated(corner: dict) -> dict:
    return {k: v for k, v in corner.items() if k not in GEOMETRY}


def main() -> int:
    before = json.loads(BEFORE.read_text(encoding="utf-8"))
    after = json.loads(MODEL.read_text(encoding="utf-8"))
    failures: list[str] = []

    if len(before["corners"]) != len(after["corners"]):
        failures.append(f"corner count {len(after['corners'])} != {len(before['corners'])}")

    for old, new in zip(before["corners"], after["corners"]):
        if curated(old) != curated(new):
            failures.append(f"{old['id']} curated fields changed")
        moved = [f"{f} {old[f]}->{new[f]}" for f in ("s_start_m", "apex_s_m", "s_end_m")
                 if old[f] != new[f]]
        print(f"{new['id']:>4} {new['name']:<24} "
              f"short={str(new.get('short_name')):<14} side={new['apex_side']:<5} "
              f"flat={new.get('target_throttle_pct')} "
              f"{'| ' + ', '.join(moved) if moved else '| geometry unchanged'}")

    print(f"\nreference before: {before['reference_lap']['lap_time_s']}s "
          f"({Path(before['reference_lap']['path']).name})")
    print(f"reference now:    {after['reference_lap']['lap_time_s']}s "
          f"({Path(after['reference_lap']['path']).name})")

    if failures:
        print("\nFAIL")
        for line in failures:
            print(f"  - {line}")
        return 1
    print("\nOK - every name, id, short name, apex side and flat marker preserved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
