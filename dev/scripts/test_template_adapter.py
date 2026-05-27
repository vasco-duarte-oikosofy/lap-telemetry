#!/usr/bin/env python3
"""Test the template adapter for deterministic coaching phrases.

Run: python3 dev/scripts/test_template_adapter.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "product" / "python"))

from lap_telemetry.coach.coach_config import CoachMode, CoachRunConfig, UtteranceMode
from lap_telemetry.coach.facts import CornerLoss, LapComparisonFacts
from lap_telemetry.coach.fuel_facts import FuelFacts
from lap_telemetry.coach.template_adapter import TemplateAdapter, format_time, _spell_number

pass_count = 0
fail_count = 0


def ok(condition: bool, label: str, detail: str = "") -> None:
    global pass_count, fail_count
    if condition:
        pass_count += 1
        print(f"  [PASS] {label}")
    else:
        fail_count += 1
        print(f"  [FAIL] {label}{' — ' + detail if detail else ''}")


# ── Helper ─────────────────────────────────────────────────────────────────

def make_loss(
    corner_id: str = "t3",
    corner_name: str = "turn 3",
    phase: str = "minimum_speed",
    loss_s: float = 0.20,
    driver_value: float = 150.0,
    reference_value: float = 160.0,
    apex_distance_m: float = 1161.0,
    unit: str = "km/h",
    confidence: str = "high",
    apex_offset_m: float | None = None,
    entry_distance_delta_m: float | None = None,
    exit_distance_delta_m: float | None = None,
) -> CornerLoss:
    return CornerLoss(
        corner_id=corner_id,
        corner_name=corner_name,
        apex_distance_m=apex_distance_m,
        phase=phase,
        loss_s=loss_s,
        driver_value=driver_value,
        reference_value=reference_value,
        unit=unit,
        confidence=confidence,
        apex_offset_m=apex_offset_m,
        entry_distance_delta_m=entry_distance_delta_m,
        exit_distance_delta_m=exit_distance_delta_m,
    )


def make_facts(
    losses: list[CornerLoss] | None = None,
    gains: list[CornerLoss] | None = None,
    max_words: int = 35,
) -> LapComparisonFacts:
    return LapComparisonFacts(
        type="lap_coaching_summary",
        track_id="test-track",
        lap_number=1,
        lap_time_delta_s=0.5,
        top_losses=losses or [],
        top_gains=gains or [],
        constraints={"max_words": max_words, "style": "calm_concise_engineer"},
    )


# ══════════════════════════════════════════════════════════════════════════
# 1. Enum values
# ══════════════════════════════════════════════════════════════════════════

print("\n── Enum Values ──\n")

ok(UtteranceMode.CLOUD_LLM.value == "cloud-llm", "CLOUD_LLM value is cloud-llm")
ok(UtteranceMode.LOCAL_LLM.value == "local-llm", "LOCAL_LLM value is local-llm")
ok(UtteranceMode.TEMPLATE.value == "template", "TEMPLATE value is template")

ok(CoachMode.OFF.value == "off", "CoachMode.OFF value is off")
ok(CoachMode.LAP.value == "lap", "CoachMode.LAP value is lap")

cfg = CoachRunConfig()
ok(cfg.utterance_mode == UtteranceMode.CLOUD_LLM, "Default utterance_mode is CLOUD_LLM")
ok(cfg.local_model == "llama3.2", "Default local_model is llama3.2")

cfg2 = CoachRunConfig(utterance_mode=UtteranceMode.TEMPLATE)
ok(cfg2.utterance_mode == UtteranceMode.TEMPLATE, "Can set utterance_mode to TEMPLATE")

cfg3 = CoachRunConfig(mode=CoachMode.OFF)
ok(cfg3.mode == CoachMode.OFF, "Can set mode to OFF")


# ══════════════════════════════════════════════════════════════════════════
# 2. Number spelling
# ══════════════════════════════════════════════════════════════════════════

print("\n── Number Spelling ──\n")

ok(_spell_number(1) == "one", "Spell 1 → one")
ok(_spell_number(5) == "five", "Spell 5 → five")
ok(_spell_number(10) == "ten", "Spell 10 → ten")
ok(_spell_number(11) == "11", "Spell 11 → 11 (digits)")
ok(_spell_number(100) == "100", "Spell 100 → 100 (digits)")


# ══════════════════════════════════════════════════════════════════════════
# 3. Time formatting
# ══════════════════════════════════════════════════════════════════════════

print("\n── Time Formatting ──\n")

ok(format_time(0.03) == "three hundredths", "0.03 → three hundredths")
ok(format_time(0.05) == "five hundredths", "0.05 → five hundredths")
ok(format_time(0.10) == "a tenth", "0.10 → a tenth")
ok(format_time(0.15) == "just over a tenth", "0.15 → just over a tenth")
ok(format_time(0.20) == "two tenths", "0.20 → two tenths")
ok(format_time(0.30) == "three tenths", "0.30 → three tenths")
ok(format_time(0.50) == "half a second", "0.50 → half a second")
ok(format_time(0.60) == "six tenths", "0.60 → six tenths")
ok(format_time(0.75) == "three quarters of a second", "0.75 → three quarters of a second")
ok(format_time(0.80) == "eight tenths", "0.80 → eight tenths")
ok(format_time(1.00) == "one second", "1.00 → one second")
ok(format_time(1.20) == "one point two seconds", "1.20 → one point two seconds")
ok(format_time(2.00) == "two seconds", "2.00 → two seconds")
ok(format_time(3.50) == "four seconds", "3.50 → four seconds (rounded up)")
# Negative values (loss_s can be negative for gains)
ok(format_time(-0.20) == "two tenths", "-0.20 → two tenths (abs)")


# ══════════════════════════════════════════════════════════════════════════
# 4. Single loss phrases
# ══════════════════════════════════════════════════════════════════════════

print("\n── Single Loss Phrases ──\n")

# minimum_speed with apex offset
result = TemplateAdapter.generate(make_facts(
    losses=[make_loss(phase="minimum_speed", loss_s=0.20, driver_value=150.0, reference_value=160.0, apex_offset_m=-9.0)]
))
ok("You lost" in result and "at the apex of" in result, "minimum_speed loss: has lead sentence",
   result)
ok("carried ten kilometres per hour less" in result, "minimum_speed loss: has speed diff",
   result)
ok("hit the apex nine metres later" in result, "minimum_speed loss: has apex offset",
   result)

# minimum_speed without apex offset
result = TemplateAdapter.generate(make_facts(
    losses=[make_loss(phase="minimum_speed", loss_s=0.30, driver_value=140.0, reference_value=150.0, apex_offset_m=None)]
))
ok("carried ten kilometres per hour less" in result, "minimum_speed loss without offset: speed diff",
   result)
ok("hit the apex" not in result, "minimum_speed loss without offset: no apex offset",
   result)

# entry with positive delta (lifted earlier)
result = TemplateAdapter.generate(make_facts(
    losses=[make_loss(phase="entry", loss_s=0.15, driver_value=150.0, reference_value=155.0, entry_distance_delta_m=5.0)]
))
ok("lifted five metres earlier" in result, "entry loss: positive delta = lifted earlier",
   result)

# entry with negative delta (braked later)
result = TemplateAdapter.generate(make_facts(
    losses=[make_loss(phase="entry", loss_s=0.15, driver_value=150.0, reference_value=155.0, entry_distance_delta_m=-5.0)]
))
ok("braked five metres later" in result, "entry loss: negative delta = braked later",
   result)

# entry without delta
result = TemplateAdapter.generate(make_facts(
    losses=[make_loss(phase="entry", loss_s=0.15, entry_distance_delta_m=None)]
))
ok("going into" in result, "entry loss without delta: uses going into",
   result)

# exit_brake with negative delta (released later)
result = TemplateAdapter.generate(make_facts(
    losses=[make_loss(phase="exit_brake", loss_s=0.19, exit_distance_delta_m=-4.0)]
))
ok("released the brakes four metres later" in result, "exit_brake loss: negative delta",
   result)

# exit_throttle with negative delta (got on throttle later)
result = TemplateAdapter.generate(make_facts(
    losses=[make_loss(phase="exit_throttle", loss_s=0.18, exit_distance_delta_m=-9.0)]
))
ok("got back on throttle nine metres later" in result, "exit_throttle loss: negative delta",
   result)

# generic exit (no specific brake/throttle data)
result = TemplateAdapter.generate(make_facts(
    losses=[make_loss(phase="exit", loss_s=0.10, exit_distance_delta_m=None)]
))
ok("carried less speed through" in result, "generic exit loss: carried less speed through",
   result)

# generic exit with exit_distance_delta_m
result = TemplateAdapter.generate(make_facts(
    losses=[make_loss(phase="exit", loss_s=0.10, exit_distance_delta_m=-5.0)]
))
ok("got back on throttle five metres later" in result, "generic exit loss with delta",
   result)


# ══════════════════════════════════════════════════════════════════════════
# 5. Single gain phrases
# ══════════════════════════════════════════════════════════════════════════

print("\n── Single Gain Phrases ──\n")

# minimum_speed gain
result = TemplateAdapter.generate(make_facts(
    gains=[make_loss(phase="minimum_speed", loss_s=-0.20, driver_value=165.0, reference_value=155.0, apex_offset_m=6.0)]
))
ok("You gained" in result, "minimum_speed gain: uses 'gained'", result)
ok("carried ten kilometres per hour more" in result, "minimum_speed gain: speed diff",
   result)
ok("hitting the apex six metres earlier" in result, "minimum_speed gain: apex offset",
   result)

# entry gain (negative delta = braked later)
result = TemplateAdapter.generate(make_facts(
    gains=[make_loss(phase="entry", loss_s=-0.16, driver_value=267.0, reference_value=258.0, entry_distance_delta_m=-5.0)]
))
ok("braked five metres later" in result, "entry gain: negative delta = braked later",
   result)

# entry gain without delta
result = TemplateAdapter.generate(make_facts(
    gains=[make_loss(phase="entry", loss_s=-0.16, entry_distance_delta_m=None)]
))
ok("carried more speed into the corner" in result, "entry gain no delta: uses fallback",
   result)

# exit_brake gain (positive delta = released earlier)
result = TemplateAdapter.generate(make_facts(
    gains=[make_loss(phase="exit_brake", loss_s=-0.10, exit_distance_delta_m=5.0)]
))
ok("released the brakes five metres earlier" in result, "exit_brake gain: positive delta",
   result)

# exit_throttle gain (positive delta = got on throttle earlier)
result = TemplateAdapter.generate(make_facts(
    gains=[make_loss(phase="exit_throttle", loss_s=-0.10, exit_distance_delta_m=10.0)]
))
ok("got back on throttle ten metres earlier" in result, "exit_throttle gain: positive delta",
   result)

# generic exit gain with delta
result = TemplateAdapter.generate(make_facts(
    gains=[make_loss(phase="exit", loss_s=-0.10, exit_distance_delta_m=10.0)]
))
ok("got back on throttle ten metres earlier" in result, "generic exit gain with delta",
   result)


# ══════════════════════════════════════════════════════════════════════════
# 6. Same-corner deduplication
# ══════════════════════════════════════════════════════════════════════════

print("\n── Same-corner Deduplication ──\n")

# Three loss phases for same corner (matching spec example for turn 3)
result = TemplateAdapter.generate(make_facts(
    losses=[
        make_loss(corner_id="t3", corner_name="turn 3", phase="exit_brake",
                  loss_s=0.194, driver_value=155.1, reference_value=167.1,
                  exit_distance_delta_m=-4.0),
        make_loss(corner_id="t3", corner_name="turn 3", phase="minimum_speed",
                  loss_s=0.190, driver_value=155.0, reference_value=165.6,
                  apex_offset_m=-9.0),
        make_loss(corner_id="t3", corner_name="turn 3", phase="exit_throttle",
                  loss_s=0.179, driver_value=155.5, reference_value=168.1,
                  exit_distance_delta_m=-9.0),
    ],
    max_words=50,
))

ok("You lost" in result, "Loss dedup: starts with You lost", result)
ok("exiting turn 3" in result, "Loss dedup: dominant phase (exit_brake) leads", result)
# All three details should be present
ok("released the brakes" in result, "Loss dedup: exit_brake detail", result)
ok("through the apex" in result, "Loss dedup: minimum_speed detail has through the apex", result)
ok("got back on throttle" in result, "Loss dedup: exit_throttle detail", result)
# Corner name should appear only once
ok(result.count("turn 3") == 1, "Loss dedup: corner name appears once", result)

# Two gain phases for same corner (matching spec example for turn 5)
result = TemplateAdapter.generate(make_facts(
    gains=[
        make_loss(corner_id="t5", corner_name="turn 5", phase="minimum_speed",
                  loss_s=-0.118, driver_value=81.8, reference_value=85.0,
                  apex_offset_m=6.0),
        make_loss(corner_id="t5", corner_name="turn 5", phase="exit_throttle",
                  loss_s=-0.105, exit_distance_delta_m=10.0),
    ],
    max_words=50,
))

ok("You gained" in result, "Gain dedup: starts with You gained", result)
ok("at the apex of turn 5" in result, "Gain dedup: dominant minimum_speed leads", result)
ok("three kilometres per hour more" in result, "Gain dedup: speed diff present", result)
ok("got back on throttle" in result, "Gain dedup: exit detail present", result)
ok(result.count("turn 5") == 1, "Gain dedup: corner name appears once", result)


# ══════════════════════════════════════════════════════════════════════════
# 7. Gain-first ordering
# ══════════════════════════════════════════════════════════════════════════

print("\n── Gain-first Ordering ──\n")

result = TemplateAdapter.generate(make_facts(
    losses=[
        make_loss(corner_id="t10", corner_name="turn 10", phase="minimum_speed", loss_s=0.25),
    ],
    gains=[
        make_loss(corner_id="t3", corner_name="turn 3", phase="minimum_speed", loss_s=-0.18),
    ],
    max_words=50,
))

gain_pos = result.find("gained")
loss_pos = result.find("lost")
ok(gain_pos < loss_pos, "Gain comes before loss in mixed utterance", result)


# ══════════════════════════════════════════════════════════════════════════
# 8. Empty facts
# ══════════════════════════════════════════════════════════════════════════

print("\n── Empty Facts ──\n")

result = TemplateAdapter.generate(make_facts(losses=[], gains=[]))
ok(result == "", "Empty facts → empty string", f"'{result}'")


# ══════════════════════════════════════════════════════════════════════════
# 9. Fuel phrases
# ══════════════════════════════════════════════════════════════════════════

print("\n── Fuel Phrases ──\n")

# CRITICAL
result = TemplateAdapter.generate_fuel_phrase(FuelFacts(
    track_name="spa", session_type="race", race_laps_total=10,
    race_laps_remaining=3, fuel_at_start_l=80.0, fuel_at_end_l=10.0,
    fuel_used_l=70.0, laps_completed=7, fuel_per_lap_l=7.0,
    laps_of_fuel_remaining=1.4, fuel_status="CRITICAL"
))
ok(result == "Fuel critical. Pit this lap.", f"CRITICAL fuel: {result}")

# WARNING
result = TemplateAdapter.generate_fuel_phrase(FuelFacts(
    track_name="spa", session_type="race", race_laps_total=10,
    race_laps_remaining=8, fuel_at_start_l=80.0, fuel_at_end_l=20.0,
    fuel_used_l=60.0, laps_completed=2, fuel_per_lap_l=7.0,
    laps_of_fuel_remaining=2.9, fuel_status="WARNING"
))
ok("Warning:" in result and "laps of fuel remaining" in result, f"WARNING fuel: {result}")

# OK in race
result = TemplateAdapter.generate_fuel_phrase(FuelFacts(
    track_name="spa", session_type="race", race_laps_total=10,
    race_laps_remaining=5, fuel_at_start_l=80.0, fuel_at_end_l=45.0,
    fuel_used_l=35.0, laps_completed=5, fuel_per_lap_l=7.0,
    laps_of_fuel_remaining=6.4, fuel_status="OK"
))
ok("Fuel OK" in result and "laps remaining" in result, f"OK fuel (race): {result}")

# OK in practice (no race laps)
result = TemplateAdapter.generate_fuel_phrase(FuelFacts(
    track_name="spa", session_type="practice", race_laps_total=None,
    race_laps_remaining=None, fuel_at_start_l=80.0, fuel_at_end_l=45.0,
    fuel_used_l=35.0, laps_completed=5, fuel_per_lap_l=7.0,
    laps_of_fuel_remaining=6.4, fuel_status="OK"
))
ok(result == "Fuel OK.", f"OK fuel (practice): {result}")

# UNKNOWN
result = TemplateAdapter.generate_fuel_phrase(FuelFacts(
    track_name="spa", session_type="race", race_laps_total=None,
    race_laps_remaining=None, fuel_at_start_l=None, fuel_at_end_l=None,
    fuel_used_l=None, laps_completed=0, fuel_per_lap_l=None,
    laps_of_fuel_remaining=None, fuel_status="UNKNOWN"
))
ok(result == "", f"UNKNOWN fuel: '{result}'")

# OK with large margin (>5 laps)
result = TemplateAdapter.generate_fuel_phrase(FuelFacts(
    track_name="spa", session_type="race", race_laps_total=10,
    race_laps_remaining=3, fuel_at_start_l=80.0, fuel_at_end_l=65.0,
    fuel_used_l=15.0, laps_completed=7, fuel_per_lap_l=7.0,
    laps_of_fuel_remaining=9.3, fuel_status="OK"
))
ok(result == "Fuel OK.", f"OK fuel (large margin): {result}")

# TTS rules: numbers 1-10 spelled out
result = TemplateAdapter.generate_fuel_phrase(FuelFacts(
    track_name="spa", session_type="race", race_laps_total=10,
    race_laps_remaining=3, fuel_at_start_l=80.0, fuel_at_end_l=30.0,
    fuel_used_l=50.0, laps_completed=7, fuel_per_lap_l=7.0,
    laps_of_fuel_remaining=4.3, fuel_status="OK"
))
ok("four laps remaining" in result, f"Fuel TTS: numbers spelled out: {result}")
ok("three laps to go" in result, f"Fuel TTS: race remaining spelled out: {result}")


# ══════════════════════════════════════════════════════════════════════════
# 10. TTS output rules
# ══════════════════════════════════════════════════════════════════════════

print("\n── TTS Output Rules ──\n")

# Numbers 1-10 spelled out
result = TemplateAdapter.generate(make_facts(
    losses=[make_loss(phase="minimum_speed", loss_s=0.20, driver_value=150.0, reference_value=155.0, apex_offset_m=8.0)]
))
ok("eight metres" in result, "TTS: number <10 spelled out", result)
ok("8 metres" not in result, "TTS: no digits for numbers ≤10", result)

# Numbers >10 stay as digits
result = TemplateAdapter.generate(make_facts(
    losses=[make_loss(phase="minimum_speed", loss_s=0.20, driver_value=100.0, reference_value=123.0, apex_offset_m=15.0)]
))
ok("23 kilometres per hour" in result, "TTS: speed diff >10 stays as digits", result)
ok("15 metres" in result, "TTS: distance >10 stays as digits", result)

# Units in full
ok("kilometres per hour" in result, "TTS: km/h expanded", result)
# No abbreviations in a sample
result_text = TemplateAdapter.generate(make_facts(
    losses=[make_loss(phase="entry", loss_s=0.15, entry_distance_delta_m=5.0)]
))
ok("km/h" not in result_text, "TTS: no abbreviation km/h", result_text)


# ══════════════════════════════════════════════════════════════════════════
# 11. Fixture-based tests
# ══════════════════════════════════════════════════════════════════════════

print("\n── Fixture-based Tests ──\n")

from lap_telemetry.coach.generate_utterance import _dict_to_facts

# barcelona_lap15_facts.json — the canonical multi-phase example
# With large max_words so truncation doesn't drop the loss part
with open(ROOT / "dev" / "fixtures" / "coach" / "barcelona_lap15_facts.json") as f:
    data = json.load(f)
facts = _dict_to_facts(data)
# Override max_words to 200 so we can test both gain and loss appear
facts_wide = LapComparisonFacts(
    type=facts.type, track_id=facts.track_id, lap_number=facts.lap_number,
    lap_time_delta_s=facts.lap_time_delta_s,
    top_losses=facts.top_losses, top_gains=facts.top_gains,
    constraints={"max_words": 200, "style": "calm_concise_engineer"},
)
result = TemplateAdapter.generate(facts_wide)
ok(len(result) > 0, "barcelona_lap15: non-empty output", result[:100])
ok("You gained" in result, "barcelona_lap15: has gain phrase", result)
ok("You lost" in result, "barcelona_lap15: has loss phrase", result)
# Gain-first: "gained" should appear before "lost"
gained_pos = result.find("gained")
lost_pos = result.find("lost")
ok(gained_pos < lost_pos, "barcelona_lap15: gains before losses", result)

# barcelona_single_corner_facts.json
with open(ROOT / "dev" / "fixtures" / "coach" / "barcelona_single_corner_facts.json") as f:
    data = json.load(f)
facts = _dict_to_facts(data)
result = TemplateAdapter.generate(facts)
ok(len(result) > 0, "single_corner: non-empty output", result)
ok("You lost" in result, "single_corner: has loss phrase", result)

# barcelona_gains_only_facts.json
with open(ROOT / "dev" / "fixtures" / "coach" / "barcelona_gains_only_facts.json") as f:
    data = json.load(f)
facts = _dict_to_facts(data)
result = TemplateAdapter.generate(facts)
ok(len(result) > 0, "gains_only: non-empty output", result)
ok("You gained" in result, "gains_only: has gain phrase", result)
ok("You lost" not in result, "gains_only: no loss phrase", result)

# barcelona_losses_only_facts.json
with open(ROOT / "dev" / "fixtures" / "coach" / "barcelona_losses_only_facts.json") as f:
    data = json.load(f)
facts = _dict_to_facts(data)
result = TemplateAdapter.generate(facts)
ok(len(result) > 0, "losses_only: non-empty output", result)
ok("You lost" in result, "losses_only: has loss phrase", result)
ok("You gained" not in result, "losses_only: no gain phrase", result)

# barcelona_mixed_gains_and_losses_facts.json
with open(ROOT / "dev" / "fixtures" / "coach" / "barcelona_mixed_gains_and_losses_facts.json") as f:
    data = json.load(f)
facts = _dict_to_facts(data)
# Override max_words to 200 so both gain and loss appear
facts_wide = LapComparisonFacts(
    type=facts.type, track_id=facts.track_id, lap_number=facts.lap_number,
    lap_time_delta_s=facts.lap_time_delta_s,
    top_losses=facts.top_losses, top_gains=facts.top_gains,
    constraints={"max_words": 200, "style": "calm_concise_engineer"},
)
result = TemplateAdapter.generate(facts_wide)
ok(len(result) > 0, "mixed: non-empty output", result)
ok("You gained" in result, "mixed: has gain phrase", result)
ok("You lost" in result, "mixed: has loss phrase", result)


# ══════════════════════════════════════════════════════════════════════════
# 12. CLI flag parsing
# ══════════════════════════════════════════════════════════════════════════

print("\n── CLI Flag Parsing ──\n")

import subprocess

# Test --utterance-mode on generate_utterance.py
res = subprocess.run(
    [sys.executable, "-m", "lap_telemetry.coach.generate_utterance",
     "--facts", str(ROOT / "dev" / "fixtures" / "coach" / "barcelona_single_corner_facts.json"),
     "--utterance-mode", "template"],
    capture_output=True, text=True,
    timeout=30,
    env={**os.environ, "PYTHONPATH": str(ROOT / "product" / "python")},
)
ok(res.returncode == 0, "generate_utterance --utterance-mode template exits 0")
ok("You lost" in res.stdout, "generate_utterance template mode produces loss phrase")

# Test generate_utterance.py --utterance-mode template --print-facts
res2 = subprocess.run(
    [sys.executable, "-m", "lap_telemetry.coach.generate_utterance",
     "--facts", str(ROOT / "dev" / "fixtures" / "coach" / "barcelona_single_corner_facts.json"),
     "--print-facts"],
    capture_output=True, text=True,
    timeout=30,
    env={**os.environ, "PYTHONPATH": str(ROOT / "product" / "python")},
)
ok(res2.returncode == 0, "generate_utterance --print-facts exits 0")
import json as _json
facts_json = _json.loads(res2.stdout)
ok(facts_json["type"] == "lap_coaching_summary", "--print-facts outputs valid facts")


# ── Summary ───────────────────────────────────────────────────────────────

print(f"\n{'-' * 60}")
if fail_count:
    print(f"  FAIL: {fail_count} FAILURES")
    sys.exit(1)
else:
    print(f"  PASS: {pass_count} assertions passed")