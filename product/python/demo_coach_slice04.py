#!/usr/bin/env python3
"""
Demo script for Interactive Race Coach — Slice 04: Local TTS Smoke Path

Speaks a coaching utterance through the local TTS adapter with queue
semantics (non-blocking enqueue, worker thread, stale utterance dropping).

Usage:
    python3 demo_coach_slice04.py

Or with custom text:
    python3 demo_coach_slice04.py --text "Your coaching text here"

With file adapter (no speakers needed):
    python3 demo_coach_slice04.py --engine file --output demo_output.wav

Requirements:
    - Python 3.10+
    - Piper (optional, for primary engine): piper binary + voice model
    - pyttsx3 (optional, Windows fallback): pip install pyttsx3
    - sounddevice (optional, for audio playback): pip install sounddevice
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure the product/python directory is in the path
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lap_telemetry.coach.coach_config import load_tts_config
from lap_telemetry.coach.speech_queue import SpeechQueue
from lap_telemetry.coach.tts_adapter import create_adapter

DEFAULT_PHRASE = (
    "Lost time in turn 3 exit — minimum speed 10 km/h lower, "
    "released brakes 4m later, got to throttle 9m later. "
    "Gained in turn 5 — apexed earlier, back to throttle 10m earlier."
)


def main():
    parser = argparse.ArgumentParser(
        description="Demo: Speak a coaching utterance via local TTS adapter.",
    )
    parser.add_argument(
        "--text",
        type=str,
        default=DEFAULT_PHRASE,
        help="Text to speak (default: Barcelona coaching phrase).",
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
        "--verbose",
        action="store_true",
        help="Print debug info.",
    )

    args = parser.parse_args()

    # Setup logging
    level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(name)s: %(message)s", stream=sys.stderr)

    try:
        # Load config
        config = load_tts_config(args.config)

        # Apply CLI overrides
        if args.engine:
            config.engine = args.engine
        if args.output:
            config.output_file = str(args.output)
        if args.no_play and args.engine is None:
            config.engine = "file"

        print(f"Engine: {config.engine}")
        print(f"Text: {args.text}")

        # Create adapter and queue
        adapter = create_adapter(config)
        queue = SpeechQueue(adapter=adapter)

        # Enqueue and flush
        queue.enqueue(args.text)
        queue.flush()
        queue.shutdown()

        print("Done.")
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())