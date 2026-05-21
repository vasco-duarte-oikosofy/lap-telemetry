#!/usr/bin/env python3
"""
Demo script for Interactive Race Coach — Slice 01: Offline Fact Generator

This script demonstrates the lap comparison CLI without requiring manual
PYTHONPATH setup. It compares a current lap against a reference lap and
outputs structured coaching facts. Defaults use the car-specific Barcelona
track model generated from the bundled reference lap, while still exercising
only production comparison code.

Analysis algorithm: uses the deterministic analysis engine defined in
§5 "Deterministic analysis engine" of docs/specs/interactive-race-coach-and-engineer.md.
Key properties — per-corner per-phase output (a corner can appear up to three
times: minimum_speed, entry, exit), top-3 cap on losses/gains, and loss_s
as speed_delta_kph/100 (a ranking heuristic, not true integrated time loss).

Usage:
    python3 demo_coach_slice01.py

Or with custom paths:
    python3 demo_coach_slice01.py --current-lap <path> --reference-lap <path> --track-model <path>

Requirements:
    - Python 3.10+
    - pyarrow

Output:
    JSON with top corner losses/gains, lap time delta, and coaching constraints.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure the product/python directory is in the path
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lap_telemetry.coach.track_model import load_track_coaching_model
from lap_telemetry.coach.lap_comparator import compare_laps


def main():
    parser = argparse.ArgumentParser(
        description="Demo: Compare a current lap against a reference and print coaching facts."
    )
    parser.add_argument(
        "--current-lap",
        type=Path,
        default=SCRIPT_DIR.parent.parent / "dev" / "fixtures" / "coach" / "barcelona_lap15_current.parquet",
        help="Path to current lap Parquet file (default: dev/fixtures/coach/barcelona_lap15_current.parquet)",
    )
    parser.add_argument(
        "--reference-lap",
        type=Path,
        default=SCRIPT_DIR.parent / "data" / "reference-laps" / "circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.456.parquet",
        help="Path to reference lap Parquet file (default: product/data/reference-laps/...)",
    )
    parser.add_argument(
        "--track-model",
        type=Path,
        default=SCRIPT_DIR.parent / "data" / "track-coaching" / "circuit-de-barcelona_dkr-engineering-4-elms25.json",
        help="Path to track coaching model JSON (default: car-specific Barcelona reference-lap-derived model)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print additional info about the comparison",
    )

    args = parser.parse_args()

    # Validate files exist
    for path, name in [(args.current_lap, "current lap"),
                        (args.reference_lap, "reference lap"),
                        (args.track_model, "track model")]:
        if not path.exists():
            print(f"Error: {name} not found: {path}", file=sys.stderr)
            return 1

    if args.verbose:
        print(f"Current lap: {args.current_lap}")
        print(f"Reference lap: {args.reference_lap}")
        print(f"Track model: {args.track_model}")
        print()

    try:
        # Load track model
        model = load_track_coaching_model(args.track_model)
        if args.verbose:
            print(f"Loaded track model: {model.track_id}")
            print(f"  Corners: {len(model.corners)}")
            print(f"  Straight zones: {len(model.straight_zones)}")
            print()

        # Compare laps
        facts = compare_laps(args.current_lap, args.reference_lap, model)

        # Output as JSON
        output = facts.to_dict()
        print(json.dumps(output, indent=2))

        if args.verbose:
            print()
            print(f"Lap time delta: {facts.lap_time_delta_s:+.3f}s")
            print(f"Top losses: {len(facts.top_losses)}")
            print(f"Top gains: {len(facts.top_gains)}")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
