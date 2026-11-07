#!/usr/bin/env python3
"""Before/after evidence for bug 29: model-order vs nearest-first matching.

`match_corners()` now ranks every legal (corner, candidate) pair by apex
distance and serves the closest first, instead of serving corners in model order
and letting each claim its nearest *unclaimed* candidate. This script runs both
algorithms on the real reference laps already in the repo and prints every
ownership difference, so the change can be judged on data rather than argument.

Usage:
    py work/active/track-outline/47-bug29-nearest-first-matching/artifacts/matching_before_after.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / "product" / "python"))
sys.path.insert(0, str(ROOT / "dev" / "scripts"))

from update_reference_and_coaching_model import (  # noqa: E402
    MAX_APEX_DELTA_M, detect_corners, match_corners,
)

CASES = [
    ("fuji-speedway", "fuji-speedway_dkr-engineering-4-elms25", 0),
    ("autodromo-enzo-e-dino-ferrari", "autodromo-enzo-e-dino-ferrari_vista-af-corse-2026-21-lm", 0),
    ("michelin-raceway-road-atlanta", "michelin-raceway-road-atlanta_dkr-engineering-4-elms25", 0),
    ("autodromo-jose-carlos-pace", "autodromo-jose-carlos-pace_dkr-engineering-4-elms25", 0),
    ("grand-prix-of-long-beach", "grand-prix-of-long-beach_ferrari-af-corse-2026-50-lm", 0),
]


def legacy_match_corners(existing_corners: list[dict], candidates: list):
    """The pre-fix algorithm, verbatim: claim in model order (bug 29)."""
    apexes = [float(c.apex_m) for c in candidates]
    claimed = [False] * len(candidates)

    def nearest(old_apex: float):
        best_idx, best_dist = None, float("inf")
        for i, apex in enumerate(apexes):
            if claimed[i]:
                continue
            dist = abs(apex - old_apex)
            if dist < best_dist:
                best_dist, best_idx = dist, i
        if best_idx is not None and best_dist <= MAX_APEX_DELTA_M:
            return best_idx
        return None

    pairs = []
    for old_c in existing_corners:
        idx = nearest(float(old_c["apex_s_m"]))
        if idx is not None:
            claimed[idx] = True
            pairs.append((old_c, candidates[idx]))
        else:
            pairs.append((old_c, None))
    return pairs, [candidates[i] for i, used in enumerate(claimed) if not used]


def describe(pair) -> str:
    old_c, match = pair
    if match is None:
        return "UNMATCHED"
    return f"{match.s_start_m:.0f}/{match.apex_m:.0f}/{match.s_end_m:.0f}"


def main() -> int:
    differences = 0
    for track_id, car_id, _ in CASES:
        model = json.loads(
            (ROOT / f"product/data/track-coaching/{car_id}.json")
            .read_text(encoding="utf-8"))
        reference = (ROOT / "product/data/reference-laps"
                     / Path(model["reference_lap"]["path"]).name)
        candidates, _ = detect_corners(reference)
        old_pairs, _ = legacy_match_corners(model["corners"], candidates)
        new_pairs, _ = match_corners(model["corners"], candidates)

        print(f"\n== {track_id} / {car_id}")
        print(f"   reference {reference.name} ({model['reference_lap']['lap_time_s']}s), "
              f"{len(candidates)} events, {len(model['corners'])} corners")
        changed = False
        for old_pair, new_pair in zip(old_pairs, new_pairs):
            if describe(old_pair) != describe(new_pair):
                changed = True
                differences += 1
                print(f"   {old_pair[0]['name']:<24} model {old_pair[0]['apex_s_m']:>6.0f} | "
                      f"was {describe(old_pair):<20} -> now {describe(new_pair)}")
        if not changed:
            print("   no ownership differences on this lap")

    print(f"\n{differences} ownership difference(s) across {len(CASES)} real laps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
