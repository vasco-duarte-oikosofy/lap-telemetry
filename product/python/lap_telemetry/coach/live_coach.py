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
import os
import signal
import sys
from pathlib import Path

# Ensure product/python is in the path for imports.
_SCRIPT_DIR = Path(__file__).resolve().parent
_PRODUCT_PY = _SCRIPT_DIR.parent.parent
if str(_PRODUCT_PY) not in sys.path:
    sys.path.insert(0, str(_PRODUCT_PY))

from lap_telemetry.coach.coach_config import CoachMode, CoachRunConfig, UtteranceMode, load_config, load_tts_config
from lap_telemetry.coach.coach_tap import CoachTap
from lap_telemetry.coach.fuel_prompt import build_fuel_messages
from lap_telemetry.coach.live_corner_fact_generator import LiveCornerFactGenerator
from lap_telemetry.coach.live_fact_generator import LiveFactGenerator
from lap_telemetry.coach.live_fuel_fact_generator import LiveFuelFactGenerator
from lap_telemetry.coach.llm_adapter import _call_llm, generate_utterance
from lap_telemetry.coach.short_prompt import build_short_messages
from lap_telemetry.coach.speech_queue import SpeechQueue
from lap_telemetry.coach.template_adapter import TemplateAdapter
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
        choices=["lap", "turn", "all", "off"],
        default="lap",
        help="When to speak: lap, turn, all, or off (record only). Default: lap.",
    )
    parser.add_argument(
        "--utterance-mode",
        type=str,
        choices=["cloud-llm", "local-llm", "template"],
        default="cloud-llm",
        help="How to generate utterances: cloud-llm (default), local-llm (Ollama), or template (deterministic).",
    )
    parser.add_argument(
        "--local-model",
        type=str,
        default=None,
        help="Ollama model name for --utterance-mode local-llm (default: llama3.2).",
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
        "--fuel-calls",
        action="store_true",
        default=False,
        help="Enable fuel engineer calls after each race lap (disabled by default).",
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
    utterance_mode = UtteranceMode(args.utterance_mode)
    local_model = args.local_model or os.environ.get("COACH_LOCAL_MODEL", "llama3.2")
    coach_run_config = CoachRunConfig(
        mode=coach_mode,
        top=args.coach_top,
        fuel_calls=args.fuel_calls,
        utterance_mode=utterance_mode,
        local_model=local_model,
    )

    # Record-only mode: skip coach tap, speech queue, and TTS entirely.
    if coach_mode == CoachMode.OFF:
        bus = QueuedBus(maxsize=256)
        print(
            f"lap-telemetry: [coach] mode=off top={coach_run_config.top}",
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
            pass

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

    # Create the utterance functions based on utterance mode.
    def _template_utterance(facts):
        """Generate a deterministic coaching utterance via templates."""
        try:
            return TemplateAdapter.generate(facts)
        except Exception as e:
            log.exception("Template utterance generation failed")
            print(f"lap-telemetry: [coach] template error: {e}", file=sys.stderr, flush=True)
            return None

    def _local_llm_utterance(facts, max_words=None):
        """Generate a coaching utterance via a local Ollama model."""
        try:
            from lap_telemetry.coach.coach_config import LLMConfig
            local_config = LLMConfig(
                provider="ollama",
                model=local_model,
                api_key_env="OLLAMA_API_KEY",
                base_url="http://localhost:11434/v1",
            )
            if max_words is not None:
                facts_copy = facts
                if facts.constraints.get("max_words") != max_words:
                    # Override max_words for corner-exit context
                    facts_dict = facts.to_dict()
                    facts_dict["constraints"]["max_words"] = max_words
                    from lap_telemetry.coach.generate_utterance import _dict_to_facts
                    facts_copy = _dict_to_facts(facts_dict)
                messages = build_short_messages(facts_copy)
            else:
                messages = build_short_messages(facts)
            return _call_llm(local_config, messages)
        except Exception as e:
            log.exception("Local LLM utterance generation failed")
            print(f"lap-telemetry: [coach] local LLM error: {e}", file=sys.stderr, flush=True)
            return None

    def utterance_fn(facts):
        """Generate a coaching utterance (after-lap) based on utterance mode."""
        if utterance_mode == UtteranceMode.TEMPLATE:
            return _template_utterance(facts)
        if utterance_mode == UtteranceMode.LOCAL_LLM:
            return _local_llm_utterance(facts)
        # CLOUD_LLM (default)
        try:
            return generate_utterance(facts, config=llm_config)
        except Exception as e:
            log.exception("LLM utterance generation failed")
            print(f"lap-telemetry: [coach] LLM error: {e}", file=sys.stderr, flush=True)
            return None

    def corner_utterance_fn(facts, corner_name, top):
        """Generate a coaching utterance (corner-exit) based on utterance mode."""
        if utterance_mode == UtteranceMode.TEMPLATE:
            return _template_utterance(facts)
        if utterance_mode == UtteranceMode.LOCAL_LLM:
            return _local_llm_utterance(facts, max_words=20 if top == 1 else 30)
        # CLOUD_LLM (default)
        try:
            from lap_telemetry.coach.corner_exit_prompt import build_corner_exit_messages
            messages = build_corner_exit_messages(facts, corner_name, top)
            return _call_llm(llm_config, messages)
        except Exception as e:
            log.exception("Corner-exit LLM utterance generation failed")
            print(f"lap-telemetry: [coach] LLM error: {e}", file=sys.stderr, flush=True)
            return None

    def fuel_utterance_fn(facts):
        """Generate a fuel engineer utterance based on utterance mode."""
        if utterance_mode == UtteranceMode.TEMPLATE:
            from lap_telemetry.coach.template_adapter import TemplateAdapter
            try:
                return TemplateAdapter.generate_fuel_phrase(facts)
            except Exception as e:
                log.exception("Template fuel utterance generation failed")
                print(f"lap-telemetry: [coach] template error: {e}", file=sys.stderr, flush=True)
                return None
        if utterance_mode == UtteranceMode.LOCAL_LLM:
            try:
                from lap_telemetry.coach.coach_config import LLMConfig
                from lap_telemetry.coach.fuel_prompt import build_fuel_messages
                local_config = LLMConfig(
                    provider="ollama",
                    model=local_model,
                    api_key_env="OLLAMA_API_KEY",
                    base_url="http://localhost:11434/v1",
                )
                messages = build_fuel_messages(facts)
                return _call_llm(local_config, messages)
            except Exception as e:
                log.exception("Local LLM fuel utterance generation failed")
                print(f"lap-telemetry: [coach] local LLM error: {e}", file=sys.stderr, flush=True)
                return None
        # CLOUD_LLM (default)
        try:
            messages = build_fuel_messages(facts)
            return _call_llm(llm_config, messages)
        except Exception as e:
            log.exception("Fuel LLM utterance generation failed")
            print(f"lap-telemetry: [coach] LLM error: {e}", file=sys.stderr, flush=True)
            return None

    # Wire up the pipeline.
    bus = QueuedBus(maxsize=256)
    fact_generator = LiveFactGenerator(utterance_fn=utterance_fn)
    corner_fact_generator = LiveCornerFactGenerator(utterance_fn=corner_utterance_fn)
    fuel_fact_generator = LiveFuelFactGenerator(utterance_fn=fuel_utterance_fn)
    tap = CoachTap(
        bus,
        fact_generator=fact_generator,
        corner_fact_generator=corner_fact_generator,
        fuel_fact_generator=fuel_fact_generator,
        speech_queue=speech_queue,
        config=coach_run_config,
    )
    # Wire the lap-flush callback so the coach reads authoritative
    # Parquet data instead of potentially-dropped bus buffer data.
    bus.on_lap_flushed = tap.notify_parquet_flushed
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
        f"lap-telemetry: [coach] mode={coach_mode.value} top={coach_run_config.top} utterance={utterance_mode.value}",
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