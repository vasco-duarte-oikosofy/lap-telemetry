"""Live coach CLI — start the recorder with full coaching pipeline.

Wires together: recorder → QueuedBus → LapDetector → LiveFactGenerator →
LLM → SpeechQueue → TTS speaker.

Supports three coaching modes:

- ``lap`` (default) — after-lap summaries only.
- ``turn`` — turn-by-turn coaching only (no lap summary).
- ``all`` — both after-lap summaries and turn-by-turn coaching.

The ``--coach-top`` flag controls how many coaching items per call:
1 for the single biggest item, 3 for the top 3.

Usage::

    python -m lap_telemetry.coach.live_coach --out-dir sessions
    python -m lap_telemetry.coach.live_coach --out-dir sessions --coach-mode turn
    python -m lap_telemetry.coach.live_coach --out-dir sessions --coach-mode all --coach-top 1
    python -m lap_telemetry.coach.live_coach --out-dir sessions --tts-engine kokoro
    python -m lap_telemetry.coach.live_coach --out-dir sessions --tts-engine file --tts-output /tmp/coach.txt
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

from lap_telemetry.coach.coach_config import CoachMode, CoachRunConfig, load_config, load_tts_config
from lap_telemetry.coach.coach_tap import CoachTap
from lap_telemetry.coach.live_corner_fact_generator import LiveCornerFactGenerator
from lap_telemetry.coach.live_fact_generator import LiveFactGenerator
from lap_telemetry.coach.llm_adapter import generate_utterance
from lap_telemetry.coach.speech_queue import SpeechQueue
from lap_telemetry.coach.tts_adapter import create_adapter
from lap_telemetry.recorder.bus import QueuedBus
from lap_telemetry.recorder import record

log = logging.getLogger(__name__)


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
        "--coach-mode",
        type=str,
        choices=["lap", "turn", "all"],
        default="lap",
        help="When to speak: lap (after-lap only), turn (corner exits only), all (both). Default: lap.",
    )
    parser.add_argument(
        "--coach-top",
        type=int,
        choices=[1, 3],
        default=3,
        help="Number of coaching items per call: 1 or 3. Default: 3.",
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

    # Build coach run config.
    coach_mode = CoachMode(args.coach_mode)
    coach_run_config = CoachRunConfig(mode=coach_mode, top=args.coach_top)

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

    # Create the utterance functions that call the LLM.
    def utterance_fn(facts):
        """Generate a coaching utterance via the LLM adapter (after-lap)."""
        try:
            return generate_utterance(facts, config=llm_config)
        except Exception as e:
            log.exception("LLM utterance generation failed")
            print(f"lap-telemetry: [coach] LLM error: {e}", file=sys.stderr, flush=True)
            return None

    def corner_utterance_fn(facts, corner_name, top):
        """Generate a coaching utterance via the LLM adapter (corner-exit)."""
        try:
            from lap_telemetry.coach.corner_exit_prompt import build_corner_exit_messages
            messages = build_corner_exit_messages(facts, corner_name, top)
            from lap_telemetry.coach.llm_adapter import _call_llm
            return _call_llm(llm_config, messages)
        except Exception as e:
            log.exception("Corner-exit LLM utterance generation failed")
            print(f"lap-telemetry: [coach] LLM error: {e}", file=sys.stderr, flush=True)
            return None

    # Wire up the pipeline.
    bus = QueuedBus(maxsize=256)
    fact_generator = LiveFactGenerator(utterance_fn=utterance_fn)
    corner_fact_generator = LiveCornerFactGenerator(utterance_fn=corner_utterance_fn)
    tap = CoachTap(
        bus,
        fact_generator=fact_generator,
        corner_fact_generator=corner_fact_generator,
        speech_queue=speech_queue,
        config=coach_run_config,
    )
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

    print(
        f"lap-telemetry: [coach] mode={coach_mode.value} top={coach_run_config.top}",
        file=sys.stderr,
        flush=True,
    )

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