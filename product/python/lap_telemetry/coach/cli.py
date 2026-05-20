"""CLI for lap comparison coaching."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .lap_comparator import compare_laps
from .track_model import load_track_coaching_model


def run(current_lap: Path, reference_lap: Path, track_model: Path) -> int:
    """Run the lap comparison CLI.

    Args:
        current_lap: Path to current lap Parquet file.
        reference_lap: Path to reference lap Parquet file.
        track_model: Path to track coaching model JSON.

    Returns:
        Exit code (0 for success, non-zero for error).
    """
    try:
        # Load track model
        model = load_track_coaching_model(track_model)

        # Compare laps
        facts = compare_laps(current_lap, reference_lap, model)

        # Output as JSON
        output = facts.to_dict()
        print(json.dumps(output, indent=2))

        return 0

    except FileNotFoundError as e:
        print(f"Error: File not found: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
