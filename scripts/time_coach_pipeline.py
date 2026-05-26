#!/usr/bin/env python3
"""Time the coach pipeline: facts → LLM utterance → TTS audio start.

Measures both the LLM round-trip and the TTS synthesis latency to
understand where time is spent before the driver hears anything.

Usage:
    python3 scripts/time_coach_pipeline.py [--runs N] [--facts PATH] [--no-play]

--runs N     Number of iterations to average over (default 5)
--no-play    Synthesize audio but don't play it (measures synth time only)
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

# Add product to path so we can import lap_telemetry
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "product" / "python"))

from lap_telemetry.coach.coach_config import load_config, load_tts_config, LLMConfig, TTSConfig
from lap_telemetry.coach.facts import LapComparisonFacts, CornerLoss
from lap_telemetry.coach.llm_adapter import generate_utterance, _call_llm
from lap_telemetry.coach.prompt_templates import build_messages
from lap_telemetry.coach.tts_adapter import create_adapter, KokoroAdapter


def load_facts(path: Path) -> LapComparisonFacts:
    """Load LapComparisonFacts from a JSON file."""
    data = json.loads(path.read_text(encoding="utf-8"))
    losses = [
        CornerLoss(
            corner_id=c["corner_id"],
            corner_name=c["corner_name"],
            apex_distance_m=c["apex_distance_m"],
            phase=c["phase"],
            loss_s=c["loss_s"],
            driver_value=c["driver_value"],
            reference_value=c["reference_value"],
            unit=c["unit"],
            confidence=c["confidence"],
            phase_distance_m=c.get("phase_distance_m"),
            driver_apex_distance_m=c.get("driver_apex_distance_m"),
            reference_apex_distance_m=c.get("reference_apex_distance_m"),
            apex_offset_m=c.get("apex_offset_m"),
            gain_end_distance_m=c.get("gain_end_distance_m"),
            entry_distance_delta_m=c.get("entry_distance_delta_m"),
            exit_distance_delta_m=c.get("exit_distance_delta_m"),
            reference_phase_distance_m=c.get("reference_phase_distance_m"),
        )
        for c in data.get("top_losses", [])
    ]
    gains = [
        CornerLoss(
            corner_id=c["corner_id"],
            corner_name=c["corner_name"],
            apex_distance_m=c["apex_distance_m"],
            phase=c["phase"],
            loss_s=c["loss_s"],
            driver_value=c["driver_value"],
            reference_value=c["reference_value"],
            unit=c["unit"],
            confidence=c["confidence"],
            phase_distance_m=c.get("phase_distance_m"),
            driver_apex_distance_m=c.get("driver_apex_distance_m"),
            reference_apex_distance_m=c.get("reference_apex_distance_m"),
            apex_offset_m=c.get("apex_offset_m"),
            gain_end_distance_m=c.get("gain_end_distance_m"),
            entry_distance_delta_m=c.get("entry_distance_delta_m"),
            exit_distance_delta_m=c.get("exit_distance_delta_m"),
            reference_phase_distance_m=c.get("reference_phase_distance_m"),
        )
        for c in data.get("top_gains", [])
    ]
    return LapComparisonFacts(
        type=data.get("type", "lap_coaching_summary"),
        track_id=data.get("track_id", ""),
        lap_number=data.get("lap_number", 0),
        lap_time_delta_s=data.get("lap_time_delta_s", 0.0),
        top_losses=losses,
        top_gains=gains,
        constraints=data.get("constraints", {"max_words": 35, "style": "calm_concise_engineer"}),
    )


def measure_llm(facts: LapComparisonFacts, config: LLMConfig) -> tuple[str, float]:
    """Time the LLM call and return (utterance, elapsed_seconds)."""
    messages = build_messages(facts)
    t0 = time.perf_counter()
    utterance = _call_llm(config, messages)
    t1 = time.perf_counter()
    return utterance, t1 - t0


def measure_tts_synthesis(text: str, config: TTSConfig) -> tuple[float, float]:
    """Time TTS synthesis (not playback). Returns (synth_seconds, first_audio_seconds).

    first_audio_seconds is our best estimate of when audio would start playing.
    For Kokoro, we measure create() time = synth time, since playback is blocking.
    """
    adapter = create_adapter(config)
    if not isinstance(adapter, KokoroAdapter):
        raise ValueError(f"Timing only supports Kokoro adapter, got {type(adapter).__name__}")

    # Force lazy-load first (one-time cost)
    adapter._ensure_loaded()

    # Measure synthesis only
    t0 = time.perf_counter()
    samples, sample_rate = adapter._kokoro.create(
        text, voice=adapter._voice, speed=adapter._speed
    )
    t1 = time.perf_counter()

    synth_time = t1 - t0
    audio_duration = len(samples) / sample_rate

    return synth_time, audio_duration


def main() -> int:
    parser = argparse.ArgumentParser(description="Time the coach pipeline: facts → LLM → TTS")
    parser.add_argument(
        "--runs", type=int, default=5,
        help="Number of iterations to average over (default 5)",
    )
    parser.add_argument(
        "--facts", type=Path,
        default=Path("dev/fixtures/coach/barcelona_lap15_facts.json"),
        help="Path to facts JSON file",
    )
    parser.add_argument(
        "--config", type=Path, default=None,
        help="Path to coach_config.toml",
    )
    parser.add_argument(
        "--no-play", action="store_true",
        help="Don't play audio (synth timing only)",
    )
    parser.add_argument(
        "--skip-llm", action="store_true",
        help="Skip LLM timing (use a canned utterance for TTS timing)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)

    # Load facts
    if not args.facts.exists():
        print(f"Error: Facts file not found: {args.facts}", file=sys.stderr)
        return 1
    facts = load_facts(args.facts)

    # Load configs
    llm_config = load_config(args.config)

    print("=" * 60)
    print("COACH PIPELINE TIMING TEST")
    print("=" * 60)
    print(f"Provider : {llm_config.provider}")
    print(f"Model    : {llm_config.model}")
    print(f"Runs     : {args.runs}")
    print(f"Facts    : {args.facts}")
    print()

    # ---- LLM Timing ----
    llm_times: list[float] = []
    utterances: list[str] = []

    if not args.skip_llm:
        print("--- LLM Timing ---")
        for i in range(args.runs):
            utterance, elapsed = measure_llm(facts, llm_config)
            llm_times.append(elapsed)
            utterances.append(utterance)
            print(f"  Run {i+1}: {elapsed:.3f}s — \"{utterance[:80]}\"")

        avg_llm = sum(llm_times) / len(llm_times)
        min_llm = min(llm_times)
        max_llm = max(llm_times)
        print(f"\n  LLM avg: {avg_llm:.3f}s | min: {min_llm:.3f}s | max: {max_llm:.3f}s")
        print()
    else:
        # Use a representative utterance for TTS timing
        utterances = [
            "You gained time in turn five, apexed earlier, back on throttle ten metres earlier. "
            "You lost time in turn three exit, minimum speed ten kilometres per hour lower, "
            "released brakes four metres later."
        ]
        print("--- LLM Timing: SKIPPED (using canned utterance) ---")

    # ---- TTS Timing ----
    print("--- TTS Timing ---")
    tts_config = load_tts_config(args.config)

    # Warm up Kokoro (one-time model load)
    print("  Loading Kokoro model...")
    adapter = create_adapter(tts_config)
    if not isinstance(adapter, KokoroAdapter):
        print(f"  Error: Timing requires Kokoro adapter, got {type(adapter).__name__}", file=sys.stderr)
        return 1
    t_load_start = time.perf_counter()
    adapter._ensure_loaded()
    t_load_end = time.perf_counter()
    print(f"  Model load: {t_load_end - t_load_start:.3f}s (one-time cost)")
    print()

    tts_times: list[float] = []
    audio_durations: list[float] = []

    for i in range(args.runs):
        utterance = utterances[i] if i < len(utterances) else utterances[-1]
        synth_time, audio_duration = measure_tts_synthesis(utterance, tts_config)
        tts_times.append(synth_time)
        audio_durations.append(audio_duration)
        print(f"  Run {i+1}: synth={synth_time:.3f}s | audio_len={audio_duration:.2f}s | \"{utterance[:60]}\"")

    avg_tts = sum(tts_times) / len(tts_times)
    min_tts = min(tts_times)
    max_tts = max(tts_times)
    avg_audio = sum(audio_durations) / len(audio_durations)
    print(f"\n  TTS synth avg: {avg_tts:.3f}s | min: {min_tts:.3f}s | max: {max_tts:.3f}s")
    print(f"  Audio duration avg: {avg_audio:.2f}s")

    # ---- Summary ----
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    if not args.skip_llm:
        total_avg = avg_llm + avg_tts
        print(f"  LLM round-trip (avg):   {avg_llm:.3f}s")
        print(f"  TTS synthesis (avg):    {avg_tts:.3f}s")
        print(f"  ─────────────────────────────────")
        print(f"  Total facts→audio (avg): {total_avg:.3f}s")
        print(f"  Spoken utterance (avg):  {avg_audio:.2f}s")
        print(f"  LLM % of total:         {avg_llm/total_avg*100:.1f}%")
        print(f"  TTS % of total:         {avg_tts/total_avg*100:.1f}%")
    else:
        print(f"  TTS synthesis (avg):    {avg_tts:.3f}s")
        print(f"  Spoken utterance (avg): {avg_audio:.2f}s")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())