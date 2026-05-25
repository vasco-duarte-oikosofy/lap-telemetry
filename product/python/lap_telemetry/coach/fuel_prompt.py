"""Prompt template for the fuel engineer call after each race lap."""
from __future__ import annotations

from .fuel_facts import FuelFacts

FUEL_SYSTEM_PROMPT = """\
You are a calm race engineer giving a brief fuel status update to the driver \
after a completed lap.

RULES:
1. Report ONLY the facts supplied. Never invent telemetry values.
2. Keep it under 20 words.
3. Spell numbers one through ten as words (e.g. "three", not "3").
4. Use full unit names: "litres" not "L", "laps" not "l".
5. Use commas, not dashes.
6. No abbreviations (e.g. "laps remaining" not "laps rem").
7. If fuel_status is CRITICAL: say fuel is critically low and the driver must pit this lap.
8. If fuel_status is WARNING: state how many laps of fuel remain and how many laps are left.
9. If the margin between laps_of_fuel_remaining and race_laps_remaining is 3 or fewer: \
briefly note the margin.
10. Output ONLY the utterance text. No preamble, no labels, no quotes."""

FUEL_USER_TEMPLATE = """\
Fuel status after lap:
- session_type: {session_type}
- fuel_status: {fuel_status}
- laps_of_fuel_remaining: {laps_of_fuel_remaining}
- race_laps_remaining: {race_laps_remaining}
- fuel_per_lap_l: {fuel_per_lap_l}
- fuel_at_end_l: {fuel_at_end_l}"""


def build_fuel_messages(facts: FuelFacts) -> list[dict[str, str]]:
    """Build LLM messages for a fuel engineer utterance."""
    user_prompt = FUEL_USER_TEMPLATE.format(
        session_type=facts.session_type,
        fuel_status=facts.fuel_status,
        laps_of_fuel_remaining=facts.laps_of_fuel_remaining,
        race_laps_remaining=facts.race_laps_remaining,
        fuel_per_lap_l=facts.fuel_per_lap_l,
        fuel_at_end_l=facts.fuel_at_end_l,
    )
    return [
        {"role": "system", "content": FUEL_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
