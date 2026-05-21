#!/usr/bin/env python3
"""
Demo script for Interactive Race Coach — Slice 01: Offline Fact Generator

Compares a current lap against a reference lap and outputs structured coaching
facts. Use --imola to run the Imola preset (lap 9 of the 2026-05-17 session
vs the reference lap, using the throttle_brake_v1 coaching model).

Usage:
    python3 demo_coach_slice01.py
    python3 demo_coach_slice01.py --imola
    python3 demo_coach_slice01.py --current-lap <path> --reference-lap <path> --track-model <path>

Extracting a lap from a session on the fly:
    python3 demo_coach_slice01.py --imola --current-lap-session <session.parquet> --current-lap-number 5

Analysis algorithm: deterministic engine from
§5 of docs/specs/interactive-race-coach-and-engineer.md.
Per-corner per-phase output (min_speed / entry / exit), top-3 cap,
loss_s = speed_delta_kph/100 (ranking heuristic, not true time loss).

Requirements:
    - Python 3.10+
    - pyarrow
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

from lap_telemetry.coach.track_model import load_track_coaching_model
from lap_telemetry.coach.lap_comparator import compare_laps

# ---------------------------------------------------------------------------
# Track presets
# ---------------------------------------------------------------------------

PRESETS = {
    "imola": {
        "reference_lap": ROOT / "product" / "data" / "reference-laps" /
            "autodromo-enzo-e-dino-ferrari_dkr-engineering-4-elms25_time_01.40.916.parquet",
        "track_model": ROOT / "product" / "data" / "track-coaching" /
            "autodromo-enzo-e-dino-ferrari_dkr-engineering-4-elms25.json",
        "current_lap_session": ROOT / "sessions" /
            "session_20260517T174259Z_autodromo-enzo-e-dino-ferrari_lmu.parquet",
        "current_lap_number": 9,
    },
    "barcelona": {
        "reference_lap": ROOT / "product" / "data" / "reference-laps" /
            "circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.456.parquet",
        "track_model": ROOT / "product" / "data" / "track-coaching" /
            "circuit-de-barcelona_dkr-engineering-4-elms25.json",
        "current_lap": ROOT / "dev" / "fixtures" / "coach" /
            "barcelona_lap15_current.parquet",
        "current_lap_session": None,
        "current_lap_number": None,
    },
}


def extract_lap(session_path: Path, lap_number: int, tmp_dir: str) -> Path:
    """Extract a single lap from a session parquet into a temp file."""
    import pyarrow.parquet as pq
    import pyarrow as pa

    table = pq.read_table(session_path)
    if "lap_number" not in table.column_names:
        raise ValueError(f"Session file has no lap_number column: {session_path}")

    mask = [v == lap_number for v in table.column("lap_number").to_pylist()]
    if not any(mask):
        available = sorted(set(v for v in table.column("lap_number").to_pylist() if v is not None))
        raise ValueError(
            f"Lap {lap_number} not found in {session_path.name}. "
            f"Available: {available}"
        )

    indices = [i for i, m in enumerate(mask) if m]
    lap_table = table.take(indices)

    out_path = Path(tmp_dir) / f"lap_{lap_number}.parquet"
    pq.write_table(lap_table, out_path)
    return out_path


def main():
    parser = argparse.ArgumentParser(
        description="Demo: Compare a current lap against a reference and print coaching facts."
    )
    # Preset shortcuts
    parser.add_argument("--imola", action="store_true",
                        help="Use Imola preset (session_20260517T174259Z lap 9 vs reference)")
    parser.add_argument("--barcelona", action="store_true",
                        help="Use Barcelona preset (fixtures lap vs reference)")

    # Explicit paths
    parser.add_argument("--current-lap", type=Path, default=None,
                        help="Path to current lap Parquet file")
    parser.add_argument("--current-lap-session", type=Path, default=None,
                        help="Session parquet to extract current lap from")
    parser.add_argument("--current-lap-number", type=int, default=None,
                        help="Lap number to extract from --current-lap-session")
    parser.add_argument("--reference-lap", type=Path, default=None,
                        help="Path to reference lap Parquet file")
    parser.add_argument("--track-model", type=Path, default=None,
                        help="Path to track coaching model JSON")
    parser.add_argument("--verbose", action="store_true",
                        help="Print additional info about the comparison")

    args = parser.parse_args()

    # Apply preset (CLI explicit args override preset values)
    preset_name = "imola" if args.imola else ("barcelona" if args.barcelona else None)
    if preset_name is None and args.reference_lap is None:
        preset_name = "barcelona"  # default

    preset = PRESETS.get(preset_name, {})

    reference_lap = args.reference_lap or preset.get("reference_lap")
    track_model_path = args.track_model or preset.get("track_model")
    current_lap = args.current_lap
    current_lap_session = args.current_lap_session or preset.get("current_lap_session")
    current_lap_number = args.current_lap_number or preset.get("current_lap_number")

    if reference_lap is None or track_model_path is None:
        print("Error: --reference-lap and --track-model are required (or use --imola / --barcelona)",
              file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Resolve current lap: session extraction takes priority over file
        if current_lap is None and current_lap_session is not None and current_lap_number is not None:
            if args.verbose:
                print(f"Extracting lap {current_lap_number} from {Path(current_lap_session).name}...")
            try:
                current_lap = extract_lap(Path(current_lap_session), current_lap_number, tmp_dir)
            except Exception as e:
                print(f"Error extracting lap: {e}", file=sys.stderr)
                return 1

        if current_lap is None:
            print("Error: provide --current-lap or --current-lap-session + --current-lap-number",
                  file=sys.stderr)
            return 1

        for path, name in [(current_lap, "current lap"),
                           (reference_lap, "reference lap"),
                           (track_model_path, "track model")]:
            if not Path(path).exists():
                print(f"Error: {name} not found: {path}", file=sys.stderr)
                return 1

        if args.verbose:
            print(f"Current lap:   {current_lap}")
            print(f"Reference lap: {reference_lap}")
            print(f"Track model:   {track_model_path}")
            print()

        try:
            model = load_track_coaching_model(track_model_path)
            if args.verbose:
                print(f"Track: {model.track_id}  |  {len(model.corners)} corners")
                print()

            facts = compare_laps(current_lap, reference_lap, model)
            print(json.dumps(facts.to_dict(), indent=2))

            if args.verbose:
                print()
                print(f"Lap time delta: {facts.lap_time_delta_s:+.3f}s")
                print(f"Top losses: {len(facts.top_losses)}  |  Top gains: {len(facts.top_gains)}")

            return 0

        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            if args.verbose:
                import traceback
                traceback.print_exc()
            return 1


if __name__ == "__main__":
    sys.exit(main())
