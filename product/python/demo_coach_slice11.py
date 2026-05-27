#!/usr/bin/env python3
"""
Demo script for Interactive Race Coach — Slice 11: Low-Latency Utterance

Exercises the three utterance modes introduced in this slice:

  1. **template**  — deterministic phrase generation, zero latency, no network
  2. **local-llm** — short prompt via Ollama on localhost (requires running)
  3. **cloud-llm** — full LLM call (requires API key, default behaviour)

And the two new CLI surface features:

  4. **--coach-mode off** — record-only, no coaching pipeline at all
  5. **UtteranceMode enum** — verified programmatically

For template mode, the demo also shows:
  - Time formatting (tenths, hundredths, half a second, etc.)
  - Same-corner deduplication (3 phases → single sentence)
  - Gain-first ordering
  - TTS output rules (spelled-out numbers, full units)
  - Fuel engineer phrases (CRITICAL / WARNING / OK / UNKNOWN)

Usage::

    # Template mode — instant, no network:
    python3 product/python/demo_coach_slice11.py

    # Template mode with specific fixture:
    python3 product/python/demo_coach_slice11.py --facts dev/fixtures/coach/barcelona_mixed_gains_and_losses_facts.json

    # Local LLM mode (requires Ollama running with the model):
    python3 product/python/demo_coach_slice11.py --utterance-mode local-llm --local-model llama3.2

    # Cloud LLM mode (requires API key):
    python3 product/python/demo_coach_slice11.py --utterance-mode cloud-llm

    # Coach-mode off configuration check:
    python3 product/python/demo_coach_slice11.py --coach-mode-off
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lap_telemetry.coach.coach_config import CoachMode, CoachRunConfig, UtteranceMode
from lap_telemetry.coach.facts import CornerLoss, LapComparisonFacts
from lap_telemetry.coach.fuel_facts import FuelFacts
from lap_telemetry.coach.template_adapter import TemplateAdapter, format_time

FIXTURES_DIR = SCRIPT_DIR.parent.parent / "dev" / "fixtures" / "coach"
DEFAULT_FACTS = FIXTURES_DIR / "barcelona_mixed_gains_and_losses_facts.json"

SEPARATOR = "=" * 72


def _load_facts(path: Path) -> LapComparisonFacts:
    """Load LapComparisonFacts from a JSON fixture file."""
    from lap_telemetry.coach.generate_utterance import _dict_to_facts
    data = json.loads(path.read_text(encoding="utf-8"))
    return _dict_to_facts(data)


def demo_enums():
    """Show UtteranceMode and CoachMode.OFF."""
    print(SEPARATOR)
    print("  UtteranceMode & CoachMode.OFF")
    print(SEPARATOR)
    print()
    print(f"  UtteranceMode.CLOUD_LLM  = {UtteranceMode.CLOUD_LLM.value!r}")
    print(f"  UtteranceMode.LOCAL_LLM   = {UtteranceMode.LOCAL_LLM.value!r}")
    print(f"  UtteranceMode.TEMPLATE    = {UtteranceMode.TEMPLATE.value!r}")
    print()
    print(f"  CoachMode.LAP  = {CoachMode.LAP.value!r}")
    print(f"  CoachMode.TURN = {CoachMode.TURN.value!r}")
    print(f"  CoachMode.ALL  = {CoachMode.ALL.value!r}")
    print(f"  CoachMode.OFF  = {CoachMode.OFF.value!r}")
    print()
    cfg_off = CoachRunConfig(mode=CoachMode.OFF)
    print(f"  CoachRunConfig(mode=OFF) → mode={cfg_off.mode.value}")
    cfg_tmpl = CoachRunConfig(utterance_mode=UtteranceMode.TEMPLATE)
    print(f"  CoachRunConfig(utterance_mode=TEMPLATE) → utterance_mode={cfg_tmpl.utterance_mode.value}")
    cfg_local = CoachRunConfig(utterance_mode=UtteranceMode.LOCAL_LLM, local_model="phi4-mini")
    print(f"  CoachRunConfig(utterance_mode=LOCAL_LLM, local_model='phi4-mini')")
    print(f"    → utterance_mode={cfg_local.utterance_mode.value}, local_model={cfg_local.local_model}")
    print()


def demo_time_formatting():
    """Show time formatting for TTS-spoken English."""
    print(SEPARATOR)
    print("  Time Formatting (loss_s → spoken English)")
    print(SEPARATOR)
    print()

    values = [0.03, 0.05, 0.10, 0.15, 0.19, 0.20, 0.30, 0.50, 0.75, 0.80, 1.00, 1.20, 2.00, 3.50]
    for t in values:
        print(f"    {t:6.2f}s  →  \"{format_time(t)}\"")
    print()

    values_neg = [-0.20, -1.00, -2.50]
    for t in values_neg:
        print(f"    {t:6.2f}s  →  \"{format_time(t)}\"  (absolute value)")
    print()


def demo_template_all_fixtures():
    """Run the template adapter against all fixture files."""
    print(SEPARATOR)
    print("  Template Adapter — All Fixtures")
    print(SEPARATOR)
    print()

    fixtures = sorted(FIXTURES_DIR.glob("barcelona_*_facts.json"))
    for fpath in fixtures:
        fname = fpath.name
        facts = _load_facts(fpath)
        result = TemplateAdapter.generate(facts)
        wc = len(result.split()) if result else 0
        max_words = facts.constraints.get("max_words", 35)

        print(f"  ┌─ {fname}")
        print(f"  │  max_words={max_words}  output_words={wc}")
        if result:
            # Wrap long lines at 66 chars for readability
            words = result.split()
            line = "  │  "
            for w in words:
                if len(line) + len(w) + 1 > 70:
                    print(line)
                    line = "  │  " + w
                else:
                    line += (" " if line.endswith("  │  ") else " ") + w
            if line.strip():
                print(line)
        else:
            print("  │  (empty — no losses or gains)")
        print(f"  └")
        print()


def demo_template_specific_fixture(path: Path):
    """Run the template adapter on a single fixture with extra detail."""
    print(SEPARATOR)
    print(f"  Template Adapter — {path.name}")
    print(SEPARATOR)
    print()

    facts = _load_facts(path)
    facts_dict = facts.to_dict()

    print(f"  Track: {facts.track_id}")
    print(f"  Lap:   {facts.lap_number}")
    print(f"  Delta: {facts.lap_time_delta_s:+.3f}s")
    print(f"  Losses: {len(facts.top_losses)}  Gains: {len(facts.top_gains)}")
    print(f"  max_words: {facts.constraints.get('max_words', 35)}")
    print()

    for loss in facts.top_losses:
        phase = loss.phase
        delta = ""
        if loss.entry_distance_delta_m is not None and loss.entry_distance_delta_m != 0:
            delta = f"  entry_delta={loss.entry_distance_delta_m:+.0f}m"
        if loss.exit_distance_delta_m is not None and loss.exit_distance_delta_m != 0:
            delta += f"  exit_delta={loss.exit_distance_delta_m:+.0f}m"
        if loss.apex_offset_m is not None and loss.apex_offset_m != 0:
            delta += f"  apex_offset={loss.apex_offset_m:+.0f}m"
        speed_diff = abs(loss.driver_value - loss.reference_value)
        print(f"  LOSS  {loss.corner_name}  {phase:16s}  "
              f"loss_s={loss.loss_s:+.3f}  "
              f"speed_diff={speed_diff:.0f}km/h{delta}")
    print()

    for gain in facts.top_gains:
        phase = gain.phase
        delta = ""
        if gain.entry_distance_delta_m is not None and gain.entry_distance_delta_m != 0:
            delta = f"  entry_delta={gain.entry_distance_delta_m:+.0f}m"
        if gain.exit_distance_delta_m is not None and gain.exit_distance_delta_m != 0:
            delta += f"  exit_delta={gain.exit_distance_delta_m:+.0f}m"
        if gain.apex_offset_m is not None and gain.apex_offset_m != 0:
            delta += f"  apex_offset={gain.apex_offset_m:+.0f}m"
        speed_diff = abs(gain.driver_value - gain.reference_value)
        print(f"  GAIN  {gain.corner_name}  {phase:16s}  "
              f"gain_s={gain.loss_s:+.3f}  "
              f"speed_diff={speed_diff:.0f}km/h{delta}")
    print()

    result = TemplateAdapter.generate(facts)
    wc = len(result.split()) if result else 0
    print(f"  Utterance ({wc} words):")
    print()
    if result:
        print(f"    \"{result}\"")
    else:
        print("    (empty — no losses or gains)")
    print()


def demo_fuel_phrases():
    """Show fuel engineer phrases for each status."""
    print(SEPARATOR)
    print("  Fuel Engineer Phrases")
    print(SEPARATOR)
    print()

    scenarios = [
        ("CRITICAL — race, 1.4 laps of fuel",
         FuelFacts(track_name="spa", session_type="race", race_laps_total=10,
                   race_laps_remaining=3, fuel_at_start_l=80.0, fuel_at_end_l=10.0,
                   fuel_used_l=70.0, laps_completed=7, fuel_per_lap_l=7.0,
                   laps_of_fuel_remaining=1.4, fuel_status="CRITICAL")),
        ("WARNING — race, 3 laps fuel / 8 laps to go",
         FuelFacts(track_name="spa", session_type="race", race_laps_total=10,
                   race_laps_remaining=8, fuel_at_start_l=80.0, fuel_at_end_l=20.0,
                   fuel_used_l=60.0, laps_completed=2, fuel_per_lap_l=7.0,
                   laps_of_fuel_remaining=2.9, fuel_status="WARNING")),
        ("OK — race, 6 laps fuel / 5 laps to go",
         FuelFacts(track_name="spa", session_type="race", race_laps_total=10,
                   race_laps_remaining=5, fuel_at_start_l=80.0, fuel_at_end_l=45.0,
                   fuel_used_l=35.0, laps_completed=5, fuel_per_lap_l=7.0,
                   laps_of_fuel_remaining=6.4, fuel_status="OK")),
        ("OK — race, large margin (>5 laps)",
         FuelFacts(track_name="spa", session_type="race", race_laps_total=10,
                   race_laps_remaining=3, fuel_at_start_l=80.0, fuel_at_end_l=65.0,
                   fuel_used_l=15.0, laps_completed=7, fuel_per_lap_l=7.0,
                   laps_of_fuel_remaining=9.3, fuel_status="OK")),
        ("OK — practice (always brief)",
         FuelFacts(track_name="spa", session_type="practice", race_laps_total=None,
                   race_laps_remaining=None, fuel_at_start_l=80.0, fuel_at_end_l=45.0,
                   fuel_used_l=35.0, laps_completed=5, fuel_per_lap_l=7.0,
                   laps_of_fuel_remaining=6.4, fuel_status="OK")),
        ("UNKNOWN — no fuel data",
         FuelFacts(track_name="spa", session_type="race", race_laps_total=None,
                   race_laps_remaining=None, fuel_at_start_l=None, fuel_at_end_l=None,
                   fuel_used_l=None, laps_completed=0, fuel_per_lap_l=None,
                   laps_of_fuel_remaining=None, fuel_status="UNKNOWN")),
    ]

    for label, facts in scenarios:
        phrase = TemplateAdapter.generate_fuel_phrase(facts)
        status = facts.fuel_status
        print(f"  {label}")
        print(f"    status={status}  laps_remaining={facts.laps_of_fuel_remaining}")
        if phrase:
            print(f'    → "{phrase}"')
        else:
            print(f"    → (empty — don't speak)")
        print()


def demo_coach_mode_off():
    """Show the --coach-mode off configuration."""
    print(SEPARATOR)
    print("  --coach-mode off (Record Only)")
    print(SEPARATOR)
    print()
    print("  When --coach-mode off is used with live_coach.py:")
    print("    - The recorder starts and writes Parquet as normal")
    print("    - No CoachTap is created (no bus tap, no fact generation)")
    print("    - No LLM calls, no TTS, no speech queue")
    print("    - All coach-related flags (--utterance-mode, --coach-top, etc.) are accepted but ignored")
    print()
    print("  Example:")
    print("    python3 -m lap_telemetry.coach.live_coach --out-dir sessions --coach-mode off")
    print()
    print("  The UtteranceMode enum is still available:")
    print(f"    UtteranceMode.CLOUD_LLM = {UtteranceMode.CLOUD_LLM.value!r}")
    print(f"    UtteranceMode.LOCAL_LLM  = {UtteranceMode.LOCAL_LLM.value!r}")
    print(f"    UtteranceMode.TEMPLATE    = {UtteranceMode.TEMPLATE.value!r}")
    print()


def demo_llm_mode(args_facts: Path, utterance_mode: str, local_model: str, config_path: Path | None):
    """Run the utterance through an LLM (cloud or local)."""
    from lap_telemetry.coach.generate_utterance import _load_facts_from_json

    mode_label = "Cloud LLM" if utterance_mode == "cloud-llm" else f"Local LLM ({local_model})"
    print(SEPARATOR)
    print(f"  {mode_label} Mode")
    print(SEPARATOR)
    print()

    facts = _load_facts_from_json(args_facts)
    print(f"  Fixture: {args_facts.name}")
    print(f"  Losses: {len(facts.top_losses)}  Gains: {len(facts.top_gains)}")
    print()

    # First show what template would produce for comparison
    template_result = TemplateAdapter.generate(facts)
    print(f"  Template (for comparison):")
    print(f'    "{template_result}"')
    print()

    if utterance_mode == "cloud-llm":
        from lap_telemetry.coach.llm_adapter import generate_utterance
        from lap_telemetry.coach.coach_config import load_config
        try:
            config = load_config(config_path)
            result = generate_utterance(facts, config)
            print(f"  Cloud LLM utterance:")
            print(f'    "{result}"')
        except Exception as e:
            print(f"  Cloud LLM error: {e}")
            print("  (Set ANTHROPIC_API_KEY or another provider key to use cloud-llm)")
    elif utterance_mode == "local-llm":
        from lap_telemetry.coach.coach_config import LLMConfig
        from lap_telemetry.coach.llm_adapter import _call_llm
        from lap_telemetry.coach.short_prompt import build_short_messages
        try:
            local_config = LLMConfig(
                provider="ollama",
                model=local_model,
                api_key_env="OLLAMA_API_KEY",
                base_url="http://localhost:11434/v1",
            )
            messages = build_short_messages(facts)
            print(f"  Connecting to Ollama at localhost:11434 with model '{local_model}'...")
            result = _call_llm(local_config, messages)
            print(f"  Local LLM utterance:")
            print(f'    "{result}"')
        except Exception as e:
            print(f"  Local LLM error: {e}")
            print(f"  (Make sure Ollama is running and '{local_model}' model is available)")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Demo: Low-latency utterance generation (slice 11).",
    )
    parser.add_argument(
        "--facts",
        type=Path,
        default=DEFAULT_FACTS,
        help="Path to canned facts JSON file (default: barcelona mixed gains/losses).",
    )
    parser.add_argument(
        "--utterance-mode",
        type=str,
        choices=["template", "cloud-llm", "local-llm"],
        default="template",
        help="Utterance mode: template (instant, no network), cloud-llm, local-llm (Ollama).",
    )
    parser.add_argument(
        "--local-model",
        type=str,
        default="llama3.2",
        help="Ollama model name for --utterance-mode local-llm (default: llama3.2).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to coach_config.toml (for cloud-llm mode).",
    )
    parser.add_argument(
        "--coach-mode-off",
        action="store_true",
        help="Show the --coach-mode off configuration (record only).",
    )

    args = parser.parse_args()

    # ── 1. Enums ─────────────────────────────────────────────────────────
    demo_enums()

    # ── 2. Time formatting ───────────────────────────────────────────────
    demo_time_formatting()

    # ── 3. Fuel phrases ──────────────────────────────────────────────────
    demo_fuel_phrases()

    # ── 4. Coach-mode off configuration ───────────────────────────────────
    if args.coach_mode_off:
        demo_coach_mode_off()

    # ── 5. Template mode: all fixtures ────────────────────────────────────
    demo_template_all_fixtures()

    # ── 6. Template mode: specific fixture ────────────────────────────────
    if args.facts.exists():
        demo_template_specific_fixture(args.facts)

    # ── 7. LLM mode (if requested) ──────────────────────────────────────
    if args.utterance_mode in ("cloud-llm", "local-llm"):
        demo_llm_mode(args.facts, args.utterance_mode, args.local_model, args.config)

    # ── Summary ───────────────────────────────────────────────────────────
    print(SEPARATOR)
    print("  Summary")
    print(SEPARATOR)
    print()
    print("  Utterance modes available:")
    print("    template   — deterministic, zero latency, no network")
    print("    local-llm  — Ollama on localhost, sub-5s round-trip (requires local model)")
    print("    cloud-llm  — full cloud LLM, ~50s round-trip (requires API key)")
    print()
    print("  CLI flags:")
    print("    --utterance-mode (cloud-llm|local-llm|template)  on live_coach.py & generate_utterance.py")
    print("    --local-model MODEL                               for local-llm mode")
    print("    --coach-mode off                                  record only, no coaching pipeline")
    print()
    print("  Run with --utterance-mode cloud-llm or --utterance-mode local-llm")
    print("  to compare LLM output against the template phrases above.")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())