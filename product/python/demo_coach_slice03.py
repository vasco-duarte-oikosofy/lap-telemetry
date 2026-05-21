#!/usr/bin/env python3
"""
Demo script for Interactive Race Coach — Slice 03: LLM Text Adapter

Runs the full pipeline end-to-end:
1. Generates facts from current/reference parquets (same as slice 01)
2. Sends facts through the LLM adapter
3. Prints the utterance

Or with --facts, skips fact generation and uses canned JSON input.

Usage:
    python3 demo_coach_slice03.py

Or with custom paths:
    python3 demo_coach_slice03.py --current-lap <path> --reference-lap <path> --track-model <path>

Or with canned facts:
    python3 demo_coach_slice03.py --facts dev/fixtures/coach/barcelona_lap15_facts.json

Requirements:
    - Python 3.10+
    - pyarrow
    - litellm (or openai SDK)
    - A valid LLM API key in the environment (e.g. ANTHROPIC_API_KEY)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Ensure the product/python directory is in the path
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lap_telemetry.coach.coach_config import load_config
from lap_telemetry.coach.facts import LapComparisonFacts, CornerLoss
from lap_telemetry.coach.llm_adapter import generate_utterance
from lap_telemetry.coach.track_model import load_track_coaching_model
from lap_telemetry.coach.lap_comparator import compare_laps


DEFAULT_CURRENT_LAP = SCRIPT_DIR.parent.parent / "dev" / "fixtures" / "coach" / "barcelona_lap15_current.parquet"
DEFAULT_REFERENCE_LAP = SCRIPT_DIR.parent / "data" / "reference-laps" / "circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.456.parquet"
DEFAULT_TRACK_MODEL = SCRIPT_DIR.parent / "data" / "track-coaching" / "circuit-de-barcelona_dkr-engineering-4-elms25.json"


def main():
    parser = argparse.ArgumentParser(
        description="Demo: Generate a coaching utterance from lap comparison facts via LLM."
    )
    parser.add_argument(
        "--facts",
        type=Path,
        default=None,
        help="Path to canned facts JSON file (skips fact generation).",
    )
    parser.add_argument(
        "--current-lap",
        type=Path,
        default=DEFAULT_CURRENT_LAP,
        help="Path to current lap Parquet file.",
    )
    parser.add_argument(
        "--reference-lap",
        type=Path,
        default=DEFAULT_REFERENCE_LAP,
        help="Path to reference lap Parquet file.",
    )
    parser.add_argument(
        "--track-model",
        type=Path,
        default=DEFAULT_TRACK_MODEL,
        help="Path to track coaching model JSON.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to coach_config.toml.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print facts JSON and debug info.",
    )

    args = parser.parse_args()

    # Setup logging
    level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(name)s: %(message)s", stream=sys.stderr)

    try:
        # Load config
        config = load_config(args.config)

        # Get facts
        if args.facts:
            if not args.facts.exists():
                print(f"Error: Facts file not found: {args.facts}", file=sys.stderr)
                return 1
            from lap_telemetry.coach.generate_utterance import _load_facts_from_json
            facts = _load_facts_from_json(args.facts)
        else:
            for path, name in [(args.current_lap, "current lap"),
                              (args.reference_lap, "reference lap"),
                              (args.track_model, "track model")]:
                if not path.exists():
                    print(f"Error: {name} not found: {path}", file=sys.stderr)
                    return 1

            model = load_track_coaching_model(args.track_model)
            facts = compare_laps(args.current_lap, args.reference_lap, model)

        # Print facts JSON
        facts_json = json.dumps(facts.to_dict(), indent=2)
        print("Facts:")
        print(facts_json)
        print()

        # Generate utterance
        utterance = generate_utterance(facts, config)

        print("Utterance:")
        print(utterance)

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())