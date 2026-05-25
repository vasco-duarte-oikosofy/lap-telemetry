"""CLI entry point for generating a coaching utterance.

Usage:
    python3 -m lap_telemetry.coach.generate_utterance \\
        --facts dev/fixtures/coach/barcelona_lap15_facts.json \\
        --track-config product/data/track-coaching/circuit-de-barcelona_dkr-engineering-4-elms25.json

Or with live fact generation:
    python3 -m lap_telemetry.coach.generate_utterance \\
        --lap --current-lap dev/fixtures/coach/barcelona_lap15_current.parquet \\
        --reference-lap product/data/reference-laps/circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.456.parquet \\
        --track-config product/data/track-coaching/circuit-de-barcelona_dkr-engineering-4-elms25.json
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .coach_config import load_config
from .facts import LapComparisonFacts, CornerLoss
from .llm_adapter import generate_utterance


def _load_facts_from_json(path: Path) -> LapComparisonFacts:
    """Load LapComparisonFacts from a JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return _dict_to_facts(data)


def _dict_to_facts(data: dict) -> LapComparisonFacts:
    """Reconstruct LapComparisonFacts from a dict (e.g. from JSON)."""
    losses = [_dict_to_corner_loss(c) for c in data.get("top_losses", [])]
    gains = [_dict_to_corner_loss(c) for c in data.get("top_gains", [])]
    return LapComparisonFacts(
        type=data.get("type", "lap_coaching_summary"),
        track_id=data.get("track_id", ""),
        lap_number=data.get("lap_number", 0),
        lap_time_delta_s=data.get("lap_time_delta_s", 0.0),
        top_losses=losses,
        top_gains=gains,
        constraints=data.get("constraints", {"max_words": 35, "style": "calm_concise_engineer"}),
    )


def _dict_to_corner_loss(d: dict) -> CornerLoss:
    """Reconstruct CornerLoss from a dict."""
    return CornerLoss(
        corner_id=d["corner_id"],
        corner_name=d["corner_name"],
        apex_distance_m=d["apex_distance_m"],
        phase=d["phase"],
        loss_s=d["loss_s"],
        driver_value=d["driver_value"],
        reference_value=d["reference_value"],
        unit=d["unit"],
        confidence=d["confidence"],
        phase_distance_m=d.get("phase_distance_m"),
        driver_apex_distance_m=d.get("driver_apex_distance_m"),
        reference_apex_distance_m=d.get("reference_apex_distance_m"),
        apex_offset_m=d.get("apex_offset_m"),
        gain_end_distance_m=d.get("gain_end_distance_m"),
        entry_distance_delta_m=d.get("entry_distance_delta_m"),
        exit_distance_delta_m=d.get("exit_distance_delta_m"),
        reference_phase_distance_m=d.get("reference_phase_distance_m"),
    )


def _generate_facts(current_lap: Path, reference_lap: Path, track_config: Path) -> LapComparisonFacts:
    """Generate facts from parquet files using the comparison engine."""
    from .track_model import load_track_coaching_model
    from .lap_comparator import compare_laps

    model = load_track_coaching_model(track_config)
    return compare_laps(current_lap, reference_lap, model)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="generate_utterance",
        description="Generate a coaching utterance from lap comparison facts.",
    )
    parser.add_argument(
        "--facts",
        type=Path,
        help="Path to canned facts JSON file (skips fact generation).",
    )
    parser.add_argument(
        "--lap",
        action="store_true",
        help="Generate facts from parquet files instead of --facts JSON.",
    )
    parser.add_argument(
        "--current-lap",
        type=Path,
        help="Path to current lap Parquet file (requires --lap).",
    )
    parser.add_argument(
        "--reference-lap",
        type=Path,
        help="Path to reference lap Parquet file (requires --lap).",
    )
    parser.add_argument(
        "--track-config",
        type=Path,
        help="Path to track coaching model JSON (required for --lap).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to coach_config.toml (default: COACH_CONFIG env or ./coach_config.toml).",
    )
    parser.add_argument(
        "--print-facts",
        action="store_true",
        help="Print facts JSON to stdout and exit without calling the LLM.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print full facts JSON and debug info to stderr.",
    )

    args = parser.parse_args(argv)

    # Setup logging
    level = logging.DEBUG if args.debug else logging.WARNING
    logging.basicConfig(level=level, format="%(name)s: %(message)s", stream=sys.stderr)

    # Load config
    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        return 1

    # Load or generate facts
    if args.facts:
        if not args.facts.exists():
            print(f"Error: Facts file not found: {args.facts}", file=sys.stderr)
            return 1
        facts = _load_facts_from_json(args.facts)
    elif args.lap:
        for path, name in [
            (args.current_lap, "current lap"),
            (args.reference_lap, "reference lap"),
            (args.track_config, "track config"),
        ]:
            if not path or not path.exists():
                print(f"Error: {name} file not found: {path}", file=sys.stderr)
                return 1
        facts = _generate_facts(args.current_lap, args.reference_lap, args.track_config)
    else:
        parser.error("Provide --facts <json> or --lap with --current-lap, --reference-lap, --track-config.")
        return 1

    # Print facts and exit without calling the LLM
    if args.print_facts:
        print(json.dumps(facts.to_dict(), indent=2))
        return 0

    # Debug: print full facts JSON
    if args.debug:
        facts_json = json.dumps(facts.to_dict(), indent=2)
        print(f"Facts JSON:\n{facts_json}", file=sys.stderr)

    # Generate utterance
    try:
        utterance = generate_utterance(facts, config)
    except Exception as e:
        print(f"Error generating utterance: {e}", file=sys.stderr)
        return 1

    print(utterance)
    return 0


if __name__ == "__main__":
    sys.exit(main())