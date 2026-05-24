"""Live coach CLI — start the recorder with full coaching pipeline.

Wires together: recorder → QueuedBus → LapDetector → LiveFactGenerator →
LLM → SpeechQueue → TTS speaker.

Usage::

    python -m lap_telemetry.coach.live_coach --out-dir sessions
    python -m lap_telemetry.coach.live_coach --out-dir sessions --tts-engine kokoro
    python -m lap_telemetry.coach.live_coach --out-dir sessions --tts-engine file --tts-output /tmp/coach.txt

When a lap boundary is detected, the pipeline:

1. The LapDetector emits a ``LapCompleted`` event.
2. LiveFactGenerator resolves the reference lap and track model, converts
   frames to Parquet, runs ``compare_laps()``, and calls the LLM.
3. The utterance text is enqueued in the SpeechQueue for TTS playback.

All coaching work happens off the recorder thread. The recorder continues
writing Parquet at 50 Hz without interruption.
"""
from __future__ import annotations

import argparse
import logging
import signal
import sys
from pathlib import Path

# Ensure product/python is in the path for imports.
_SCRIPT_DIR = Path(__file__).resolve().parent
_PRODUCT_PY = _SCRIPT_DIR.parent.parent
if str(_PRODUCT_PY) not in sys.path:
    sys.path.insert(0, str(_PRODUCT_PY))

from lap_telemetry.coach.coach_config import load_config, load_tts_config
from lap_telemetry.coach.coach_tap import CoachTap
from lap_telemetry.coach.live_fact_generator import LiveFactGenerator
from lap_telemetry.coach.llm_adapter import generate_utterance
from lap_telemetry.coach.speech_queue import SpeechQueue
from lap_telemetry.coach.tts_adapter import create_adapter
from lap_telemetry.recorder.bus import QueuedBus
from lap_telemetry.recorder import record


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Start the recorder with live coaching (fact generation + LLM + TTS).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("sessions"),
        help="Directory for Parquet session output (default: sessions).",
    )
    parser.add_argument(
        "--tts-engine",
        type=str,
        choices=["kokoro", "pyttsx3", "file"],
        default=None,
        help="Override TTS engine from config (kokoro, pyttsx3, file).",
    )
    parser.add_argument(
        "--tts-output",
        type=Path,
        default=None,
        help="Output file path when using --tts-engine file.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Smoke-test mode: record one frame and exit.",
    )
    parser.add_argument(
        "--probe-timeout",
        type=float,
        default=0.0,
        help="Seconds to wait for a sim before giving up (0 = wait forever).",
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
        help="Enable debug logging.",
    )
    args = parser.parse_args()

    # Setup logging.
    level = logging.DEBUG if args.debug else logging.WARNING
    logging.basicConfig(level=level, format="%(name)s: %(message)s", stream=sys.stderr)

    # Load configs.
    llm_config = load_config(args.config)
    tts_config = load_tts_config(args.config)

    # Apply CLI overrides for TTS.
    if args.tts_engine:
        tts_config.engine = args.tts_engine
    if args.tts_output:
        tts_config.output_file = str(args.tts_output)

    # Create TTS adapter and speech queue.
    try:
        tts_adapter = create_adapter(tts_config)
    except (ValueError, RuntimeError) as e:
        print(f"lap-telemetry: [coach] TTS error: {e}", file=sys.stderr)
        return 1
    speech_queue = SpeechQueue(adapter=tts_adapter)

    # Create the utterance function that calls the LLM.
    def utterance_fn(facts):
        """Generate a coaching utterance via the LLM adapter."""
        try:
            return generate_utterance(facts, config=llm_config)
        except Exception as e:
            log = logging.getLogger(__name__)
            log.exception("LLM utterance generation failed")
            print(f"lap-telemetry: [coach] LLM error: {e}", file=sys.stderr, flush=True)
            return None

    # Wire up the pipeline.
    bus = QueuedBus(maxsize=256)
    fact_generator = LiveFactGenerator(utterance_fn=utterance_fn)
    tap = CoachTap(bus, fact_generator=fact_generator, speech_queue=speech_queue)
    tap.start()

    # Ensure clean shutdown on Ctrl+C.
    _shutting_down = False

    def _signal_handler(*_args: object) -> None:
        nonlocal _shutting_down
        if _shutting_down:
            return  # avoid double-shutdown
        _shutting_down = True
        tap.shutdown()

    signal.signal(signal.SIGINT, _signal_handler)
    if hasattr(signal, "SIGBREAK"):  # Windows
        signal.signal(signal.SIGBREAK, _signal_handler)

    try:
        return record.run(
            rate_hz=50.0,
            once=args.once,
            probe_timeout_s=args.probe_timeout,
            out_dir=args.out_dir,
            bus=bus,
        )
    finally:
        tap.shutdown()


if __name__ == "__main__":
    sys.exit(main())