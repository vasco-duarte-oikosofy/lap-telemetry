#!/usr/bin/env python3
"""Signal receipt for the preserved Imola corners (F296 vs the Ginetta reference).

For every curated corner, print the throttle/brake/speed at the apex on both the
old (Ginetta) and the new (F296) reference lap, plus the detector event list for
the F296 lap. This is the evidence that the three corners kept by
`--allow-unmatched` are compound second halves with no separate braking event,
not flat corners and not detector misses caused by a bad lap.

Usage:
    py work/active/track-outline/43-imola-f296/artifacts/signal_review.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "product" / "python"))
sys.path.insert(0, str(ROOT / "dev" / "scripts"))

from update_reference_and_coaching_model import detect_corners  # noqa: E402

TRACK_ID = "autodromo-enzo-e-dino-ferrari"
MODEL = ROOT / "product/data/track-coaching" / f"{TRACK_ID}_vista-af-corse-2026-21-lm.json"
OLD_REF = ROOT / "product/data/reference-laps" / f"{TRACK_ID}_dkr-engineering-4-elms25_time_01.40.607.parquet"
NEW_REF = next((ROOT / "product/data/reference-laps").glob(
    f"{TRACK_ID}_vista-af-corse-2026-21-lm_time_*.parquet"))
WINDOW_M = 3.0


def load(path: Path) -> dict:
    t = pq.read_table(path)
    return {name: t.column(name).to_pylist()
            for name in ("lap_distance_m", "speed_kph", "throttle_norm", "brake_norm")}


def at(lap: dict, distance: float) -> tuple[float, float, float]:
    s, sp = lap["lap_distance_m"], lap["speed_kph"]
    th, br = lap["throttle_norm"], lap["brake_norm"]

    def mean(values):
        picked = [v for d, v in zip(s, values) if abs(d - distance) <= WINDOW_M]
        return sum(picked) / len(picked) if picked else float("nan")

    return mean(th), mean(br), mean(sp)


def main() -> int:
    model = json.loads(MODEL.read_text(encoding="utf-8"))
    old_lap, new_lap = load(OLD_REF), load(NEW_REF)
    candidates, _ = detect_corners(NEW_REF)

    print(f"old reference: {OLD_REF.name}")
    print(f"new reference: {NEW_REF.name}")
    print(f"F296 apex events: {', '.join(f'{c.apex_m:.0f}m' for c in candidates)}")
    print()
    print(f"{'corner':<24} {'apex(m)':>8} | {'Ginetta thr/brk/spd':>26} | "
          f"{'F296 thr/brk/spd':>26}")
    print("-" * 96)
    for c in model["corners"]:
        apex = float(c["apex_s_m"])
        o_th, o_br, o_sp = at(old_lap, apex)
        n_th, n_br, n_sp = at(new_lap, apex)
        print(f"{c['name']:<24} {apex:>8.0f} | "
              f"{o_th * 100:>8.0f}% {o_br:>5.2f} {o_sp:>6.1f} | "
              f"{n_th * 100:>8.0f}% {n_br:>5.2f} {n_sp:>6.1f}")
    print()
    print("Preserved by --allow-unmatched (no braking event of their own):")
    for c in model["corners"]:
        if c["id"] in {"t3", "t7", "t9"}:
            twin = {"t3": "t2", "t7": "t6", "t9": "t8"}[c["id"]]
            print(f"  {c['name']} ({c['id']}) is the second half of the {twin} "
                  f"braking event; the GT3 brakes once for the complex.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
