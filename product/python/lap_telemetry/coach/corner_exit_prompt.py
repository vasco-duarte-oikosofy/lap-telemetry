"""Prompt template for corner-exit coaching notes.

Shorter and more immediate than the after-lap prompt. Word limit scales
with ``top``: ≤ 20 words for ``top=1``, ≤ 30 words for ``top=3``.
Only the exited corner's facts are included.
"""
from __future__ import annotations

import json

from .facts import LapComparisonFacts

CORNER_EXIT_SYSTEM_TEMPLATE = """\
You are a calm race engineer giving immediate corner-exit feedback to the \
driver during a live session.

RULES:
1. Report ONLY the facts supplied in the JSON below. Never invent telemetry values.
2. Keep it under {max_words} words.
3. Be direct and action-oriented. Reference the turn by name.
4. Focus on what the driver can change on the next lap through this corner.
5. Do NOT suggest improvements to other corners — only the corner just exited.

Output ONLY the utterance text. No preamble, no labels, no quotes."""

CORNER_EXIT_USER_TEMPLATE = """\
Corner-exit comparison facts for {corner_name}:

{facts_json}"""


def build_corner_exit_messages(
    facts: LapComparisonFacts,
    corner_name: str,
    top: int = 1,
) -> list[dict[str, str]]:
    """Build messages for a corner-exit coaching prompt.

    Args:
        facts: LapComparisonFacts filtered to the exited corner only.
        corner_name: Human-readable corner name (e.g. "turn 4").
        top: Number of coaching items (1 or 3). Controls word limit.

    Returns:
        List of message dicts with 'role' and 'content' keys.
    """
    max_words = 20 if top == 1 else 30
    system_prompt = CORNER_EXIT_SYSTEM_TEMPLATE.format(max_words=max_words)

    facts_dict = facts.to_dict()
    facts_for_llm = {k: v for k, v in facts_dict.items() if k != "constraints"}

    user_prompt = CORNER_EXIT_USER_TEMPLATE.format(
        corner_name=corner_name,
        facts_json=json.dumps(facts_for_llm, indent=2),
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]