#!/usr/bin/env python3
"""
Full-output demo: ALL losses and ALL gains (no top-N cap).

Same pipeline as demo_coach_slice01.py but with top_n=0 (uncapped) so
you can inspect every corner-phase the engine produces.  The voice
coach needs the top-3 cap; this script is a diagnostics tool for
verifying the full output matches expectation.

Usage:
    python3 product/python/demo_coach_full_output.py

Or with custom paths:
    python3 demo_coach_full_output.py --current-lap <path> --reference-lap <path> --track-model <path>

Requirements:
    - Python 3.10+
    - pyarrow
    - Node.js (for JS telemetry pipeline)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lap_telemetry.coach.track_model import load_track_coaching_model
from lap_telemetry.coach.lap_comparator import compare_laps


def main():
    parser = argparse.ArgumentParser(
        description="Full-output demo: ALL losses and ALL gains (no top-N cap)."
    )
    parser.add_argument(
        "--current-lap",
        type=Path,
        default=SCRIPT_DIR.parent.parent / "dev" / "fixtures" / "coach" / "barcelona_lap15_current.parquet",
    )
    parser.add_argument(
        "--reference-lap",
        type=Path,
        default=SCRIPT_DIR.parent / "data" / "reference-laps" / "circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.456.parquet",
    )
    parser.add_argument(
        "--track-model",
        type=Path,
        default=SCRIPT_DIR.parent / "data" / "track-coaching" / "circuit-de-barcelona_dkr-engineering-4-elms25.json",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=0,
        help="Max losses/gains to show per category. 0 = uncapped (default).",
    )
    parser.add_argument(
        "--swap",
        action="store_true",
        help=(
            "Swap current and reference laps. Useful when the reference "
            "lap is faster and you want to see the gains the faster lap "
            "achieved over the slower one (e.g. swap the Barcelona fixture "
            "to see many gains instead of many losses)."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print additional info about the comparison.",
    )

    args = parser.parse_args()

    current_lap = args.reference_lap if args.swap else args.current_lap
    reference_lap = args.current_lap if args.swap else args.reference_lap

    for path, name in [(current_lap, "current lap"),
                        (reference_lap, "reference lap"),
                        (args.track_model, "track model")]:
        if not path.exists():
            print(f"Error: {name} not found: {path}", file=sys.stderr)
            return 1

    if args.verbose:
        print(f"Current lap: {current_lap}", file=sys.stderr)
        print(f"Reference lap: {reference_lap}", file=sys.stderr)
        if args.swap:
            print("(swapped: --current-lap and --reference-lap exchanged)", file=sys.stderr)
        print(f"Track model: {args.track_model}", file=sys.stderr)
        print(file=sys.stderr)

    try:
        model = load_track_coaching_model(args.track_model)
        if args.verbose:
            print(f"Track: {model.track_id}  Corners: {len(model.corners)}", file=sys.stderr)
            print(file=sys.stderr)

        # top_n=0 → return all (uncapped).  compare_laps treats 0 as
        # "no limit" since slicing [:0] would give an empty list, so
        # we pass a huge number instead.
        top_n = args.top_n if args.top_n > 0 else 999
        facts = compare_laps(current_lap, reference_lap, model, top_n=top_n)

        output = facts.to_dict()
        # Override the type label to distinguish from the capped version
        output["type"] = "lap_coaching_full_output"
        output["swapped"] = args.swap

        print(json.dumps(output, indent=2))

        if args.verbose:
            print(file=sys.stderr)
            print(f"Lap time delta: {facts.lap_time_delta_s:+.3f}s", file=sys.stderr)
            print(f"Losses: {len(facts.top_losses)}", file=sys.stderr)
            print(f"Gains: {len(facts.top_gains)}", file=sys.stderr)

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())