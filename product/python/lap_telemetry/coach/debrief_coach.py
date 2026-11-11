"""The coach's voice on top of the session facts.

One opening debrief, or one answer to one question. The model sees the compact
grounding built by ``session_brief`` and — when the driver names a corner — that
corner's per-lap block. It never sees the facts payload.

Two adapters, one contract:

- ``model=callable`` — tests and any custom client.
- ``config=LLMConfig`` — the shared provider plumbing (``llm_adapter.call_llm``).
- neither — a deterministic template, so ``--no-llm`` still answers, and every
  number it says is a number the facts contain.

Whatever produced the text, it is validated against the grounding: numbers that
do not exist are reported as warnings, never silently accepted.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from ..session_brief import build_grounding, corner_block, find_corner
from ..session_facts import SessionDebriefFacts
from ..session_report import corner_label, format_lap_time
from .coach_config import LLMConfig
from .llm_adapter import LLMAdapterError, call_llm

MAX_WORDS = 160
MAX_POINTS = 3

SYSTEM_PROMPT = """\
You are a race driver-coach debriefing a driver after a practice stint. You have
raced Hypercars and GT3s and you have coached before: warm, direct, and hard to
impress. You never invent telemetry.

HOW YOU TALK
- Open with one real positive, with a number from the facts.
- Then the single biggest recurring loss: its number and its mechanism.
- One fix at a time. Never more than three things in a reply.
- End with exactly one question, then stop.
- Keep it short: a driver is still in the car, not reading a page.
- Never soften a gap. Two seconds is two seconds.
- Use the corner names from the facts.

WHAT YOU MUST NOT DO
- Never state a number that is not in the facts below.
- Never number, index, annotate or count your own words, and never show your
  reasoning or your working. Plain prose only.
- No preamble, no bullet lists, no motivational filler, no emoji.

The driver's facts follow. Answer only from them.
"""

_TEMPLATE_QUESTIONS = (
    "What does the car feel like there?",
    "Does that match what you felt in the seat?",
    "Where do you think the time is going?",
)


@dataclass
class CoachAnswer:
    """One reply, plus anything the validator did not like about it."""

    text: str
    warnings: list[str] = field(default_factory=list)
    question: str = ""
    messages: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "warnings": list(self.warnings),
                "question": self.question}


def _numbers(text: str) -> list[str]:
    """Numeric tokens, times included: 1:19.135, 0.702, 27."""
    return re.findall(r"\d+:\d{2}\.\d{3}|\d+(?:[.,]\d+)?", text)


def _known_numbers(grounding: str) -> list[float]:
    values: list[float] = []
    for token in _numbers(grounding):
        if ":" in token:
            minutes, rest = token.split(":")
            values.append(int(minutes) * 60 + float(rest))
        else:
            try:
                values.append(float(token.replace(",", ".")))
            except ValueError:
                continue
    return values


def _matches(token: str, known: list[float]) -> bool:
    """Allow rounding: 0.7 is 0.702 said out loud, 4.7 is invented."""
    if ":" in token:
        minutes, rest = token.split(":")
        value = int(minutes) * 60 + float(rest)
        return any(abs(k - value) < 0.0005 for k in known)
    try:
        value = float(token.replace(",", "."))
    except ValueError:
        return False
    digits = len(token.split(".")[1]) if "." in token else 0
    for candidate in known:
        if abs(round(candidate, digits) - value) < 10 ** (-digits - 6):
            return True
    return False


def validate_reply(reply: str, grounding: str) -> list[str]:
    """Warn about numbers the facts do not contain, and about shape."""
    warnings: list[str] = []
    known = _known_numbers(grounding)
    invented = sorted({token for token in _numbers(reply) if not _matches(token, known)})
    if invented:
        warnings.append(f"numbers not in the facts: {', '.join(invented)}")
    words = len(reply.split())
    if words > MAX_WORDS:
        warnings.append(f"reply is {words} words (limit {MAX_WORDS})")
    questions = reply.count("?")
    if questions != 1:
        warnings.append(f"reply has {questions} questions (need exactly one)")
    if re.search(r"\w\(\d+\)", reply) or "Count:" in reply:
        warnings.append("reply contains word-by-word annotation (degenerate output)")
    if reply and reply[-1] not in ".?!\"'" and not reply.endswith(")."):
        warnings.append("reply looks truncated (no sentence ending)")
    return warnings


def _template_answer(
    facts: SessionDebriefFacts, question: str, corner_id: str | None
) -> str:
    """A grounded answer with no model at all."""
    pace = facts.consistency.pace
    if corner_id:
        block = corner_block(facts, corner_id)
        priority = next((p for p in facts.priorities if p.corner_id == corner_id), None)
        name = corner_label(next((c.corner_name for c in facts.reference_corners
                                  if c.corner_id == corner_id), corner_id))
        if priority:
            text = (f"{name} is a real one: {priority.recurring_loss_s:.3f} seconds a lap, "
                    f"{priority.share_of_gap * 100:.0f} percent of your gap. "
                    f"{priority.suggestion.capitalize()}.")
        elif "no single measurable cause" in block:
            text = (f"{name} is not costing you measurable time on the clean laps. "
                    f"The loss you felt was probably traffic or a mistake.")
        else:
            text = f"{name} was not in your top three losses this session."
        return f"{text} {_TEMPLATE_QUESTIONS[1]}"

    if not facts.priorities or not pace:
        return ("I need five clean laps before I can coach you properly. "
                "Get me a longer run?")
    top = facts.priorities[0]
    gap = pace.best_lap_s - facts.session.reference_lap_s
    positive = (f"Your best lap was {format_lap_time(pace.best_lap_s)}, "
                f"{abs(gap):.3f} seconds {'under' if gap < 0 else 'off'} "
                f"the reference, so the pace is there.")
    text = (f"{positive} The repeatable loss is "
            f"{corner_label(top.corner_name)} at {top.recurring_loss_s:.3f} seconds "
            f"a lap: {top.suggestion}. {_TEMPLATE_QUESTIONS[0]}")
    return text


def build_messages(
    facts: SessionDebriefFacts, question: str
) -> tuple[list[dict[str, str]], str | None, str]:
    """System contract + grounding, then the driver's question.

    Returns ``(messages, corner_id, injected_facts)`` — the last one is exactly
    what the model was allowed to read, so validation can check against the same
    text instead of only the session-level grounding.
    """
    grounding = build_grounding(facts)
    corner_id = find_corner(facts, question)
    detail = corner_block(facts, corner_id) if corner_id else ""
    system = f"{SYSTEM_PROMPT}\n\nFACTS\n{grounding}"
    user = question
    if detail:
        # The drill-down travels with the question: it is about this turn, not
        # about the session, and it keeps the system prompt cacheable.
        user = f"{question}\n\nDETAIL FOR THIS CORNER\n{detail}"
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    injected = f"{grounding}\n{detail}" if detail else grounding
    return messages, corner_id, injected


class DebriefCoach:
    """One question, one grounded answer."""

    def __init__(
        self,
        model: Callable[[list[dict[str, str]]], str] | None = None,
        config: LLMConfig | None = None,
    ):
        self.model = model
        self.config = config

    def ask(self, question: str, facts: SessionDebriefFacts) -> CoachAnswer:
        messages, corner_id, injected = build_messages(facts, question)
        if self.model is not None:
            text = self.model(messages)
        elif self.config is not None:
            text = call_llm(self.config, messages)
        else:
            text = _template_answer(facts, question, corner_id)
        text = text.strip()
        return CoachAnswer(
            text=text,
            warnings=validate_reply(text, injected),
            question=question,
            messages=messages,
        )


__all__ = [
    "CoachAnswer",
    "DebriefCoach",
    "SYSTEM_PROMPT",
    "build_messages",
    "validate_reply",
    "LLMAdapterError",
]
