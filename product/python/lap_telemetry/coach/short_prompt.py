"""Short system prompt for local LLM utterance generation.

Targets models with 1–3 B parameters (e.g. llama3.2, phi4-mini).
Reduced rule count for reliability. Same TTS output rules as the full prompt.
"""
from __future__ import annotations

from .facts import LapComparisonFacts

SHORT_SYSTEM_PROMPT = """\
You are a race engineer speaking to the driver over radio.

RULES:
1. Under {max_words} words.
2. Use turn names from the JSON exactly (e.g. "turn 3").
3. SAME-CORNER DEDUP: when one corner has multiple phases, combine into one point.
4. GAIN-FIRST: say gains before losses.
5. OUTPUT ONLY the utterance. No preamble, quotes, or labels.

TTS RULES:
- Spell out numbers one through ten. Larger numbers stay as digits.
- Use full units: "kilometres per hour" not "km/h", "metres" not "m", "seconds" not "s".
- No abbreviations, slashes, parentheses, or em-dashes.
- Use commas instead of em-dashes.

DELTA RULES:
- entry_distance_delta_m positive = lifted earlier, negative = braked later.
- exit_distance_delta_m negative = released brakes or got on throttle later, positive = earlier.
- apex_offset_m positive = hit apex earlier, negative = later.
- driver_value vs reference_value are speeds, not time. Positive loss_s always means slower overall.
"""

SHORT_USER_TEMPLATE = """\
Lap facts:

{facts_json}"""


def build_short_messages(facts: LapComparisonFacts) -> list[dict[str, str]]:
    """Build short system and user messages for a local LLM call.

    Args:
        facts: Structured lap comparison facts.

    Returns:
        List of message dicts with 'role' and 'content' keys.
    """
    import json

    max_words = facts.constraints.get("max_words", 20)
    system_prompt = SHORT_SYSTEM_PROMPT.format(max_words=max_words)

    facts_dict = facts.to_dict()
    facts_for_llm = {k: v for k, v in facts_dict.items() if k != "constraints"}

    user_prompt = SHORT_USER_TEMPLATE.format(
        facts_json=json.dumps(facts_for_llm, indent=2),
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]