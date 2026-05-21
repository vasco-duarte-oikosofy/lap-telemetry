"""CLI entry point for speaking a coaching utterance.

Usage:
    python3 -m lap_telemetry.coach.speak \\
        --text "Lost time in turn 3 exit — minimum speed 10 km/h lower."
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .coach_config import load_tts_config
from .speech_queue import SpeechQueue
from .tts_adapter import create_adapter

DEFAULT_PHRASE = (
    "Lost time in turn 3 exit — minimum speed 10 km/h lower, "
    "released brakes 4m later, got to throttle 9m later. "
    "Gained in turn 5 — apexed earlier, back to throttle 10m earlier."
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="speak",
        description="Speak a text string through the local TTS adapter.",
    )
    parser.add_argument(
        "--text",
        type=str,
        default=None,
        help="Text to speak (required).",
    )
    parser.add_argument(
        "--engine",
        type=str,
        choices=["piper", "pyttsx3", "file"],
        default=None,
        help="Override TTS engine from config.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file path (for file adapter).",
    )
    parser.add_argument(
        "--no-play",
        action="store_true",
        help="Synthesize only, do not play audio.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to coach_config.toml.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print debug info to stderr.",
    )

    args = parser.parse_args(argv)

    # Setup logging
    level = logging.DEBUG if args.debug else logging.WARNING
    logging.basicConfig(level=level, format="%(name)s: %(message)s", stream=sys.stderr)

    if not args.text:
        parser.error("--text is required")
        return 1

    # Load TTS config
    config = load_tts_config(args.config)

    # Apply CLI overrides
    if args.engine:
        config.engine = args.engine
    if args.output:
        config.output_file = str(args.output)

    # For --no-play, force file adapter
    if args.no_play and args.engine is None:
        config.engine = "file"

    try:
        adapter = create_adapter(config)
    except (ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    # Use speech queue for proper semantics
    queue = SpeechQueue(adapter=adapter)
    queue.enqueue(args.text)
    queue.flush()
    queue.shutdown()

    print(f"Spoke: {args.text}", file=sys.stderr if not args.debug else sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())