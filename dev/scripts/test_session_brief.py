#!/usr/bin/env python3
"""The coach on top of the facts: grounding, voice contract, validation.

Three things are being tested here, and only three: the model never sees more
than a few kilobytes, the numbers it is allowed to say are the numbers we have,
and the conversation is recognisably a driver-coach (one positive, one loss, one
question, one fix at a time). No network: the model is a fake adapter.

Protocol: prints [PASS]/[FAIL] lines and exits non-zero on any failure.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "product" / "python"))
sys.path.insert(0, str(ROOT / "dev" / "scripts"))

from lap_telemetry.coach.debrief_coach import (  # noqa: E402
    SYSTEM_PROMPT,
    DebriefCoach,
    validate_reply,
)
from lap_telemetry.session_brief import (  # noqa: E402
    CORNER_BUDGET_BYTES,
    GROUNDING_BUDGET_BYTES,
    build_grounding,
    corner_block,
    find_corner,
)
from lap_telemetry.session_facts import build_session_facts  # noqa: E402
from lap_telemetry.session_inputs import resolve_debrief_inputs  # noqa: E402
from lap_telemetry.session_laps import classify_laps  # noqa: E402
from lap_telemetry.session_source import load_session  # noqa: E402

PRACTICE = (ROOT / "dev" / "sessions"
            / "session_20260524T141613Z_paul-ricard---3a_lmu.parquet")

_passed = 0
_failed = 0


def check(condition: bool, name: str, detail: str = "") -> None:
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  [PASS] {name}{' — ' + detail if detail else ''}")
    else:
        _failed += 1
        print(f"  [FAIL] {name}{' — ' + detail if detail else ''}")


def _facts():
    session = load_session(PRACTICE)
    records = classify_laps(session.table, sample_rate_hz=session.sample_rate_hz)
    return build_session_facts(session, records, resolve_debrief_inputs(session))


class FakeModel:
    """Records what it was asked and replies with whatever the test wants."""

    def __init__(self, reply: str):
        self.reply = reply
        self.messages: list[dict[str, str]] = []
        self.calls = 0

    def __call__(self, messages: list[dict[str, str]]) -> str:
        self.calls += 1
        self.messages = messages
        return self.reply


def test_grounding() -> None:
    facts = _facts()
    grounding = build_grounding(facts)
    size = len(grounding.encode("utf-8"))
    check(size <= GROUNDING_BUDGET_BYTES, "the grounding fits the budget",
          f"{size} / {GROUNDING_BUDGET_BYTES} bytes")
    check("Paul Ricard" in grounding, "it names the track")
    check("1:19.135" in grounding and "1:17.166" in grounding,
          "it carries both baselines")
    for priority in facts.priorities[:3]:
        check(priority.corner_name in grounding or f"corner {priority.corner_name}" in grounding,
              f"the top priority {priority.corner_name!r} is in the grounding")
    check("envelope" in grounding.lower(), "it carries the repeatability number")
    check(str(facts.consistency.pace.clean_laps) in grounding,
          "it carries the clean-lap count")
    check("phases" not in grounding and "corner_id" not in grounding,
          "no raw per-lap history leaks into the grounding")


def test_find_corner() -> None:
    facts = _facts()
    check(find_corner(facts, "why was Bretelle so slow?") == "t1",
          "a corner is matched by name")
    check(find_corner(facts, "bretelle killed me") == "t1",
          "matching is case-insensitive")
    check(find_corner(facts, "what about corner 2?") == "t2",
          "a numeric corner is matched by number")
    check(find_corner(facts, "turn 12") is None, "an unknown corner matches nothing")
    check(find_corner(facts, "where do I lose time overall?") is None,
          "a question with no corner has no drill-down")


def test_corner_block() -> None:
    facts = _facts()
    block = corner_block(facts, "t2")
    size = len(block.encode("utf-8"))
    check(size <= CORNER_BUDGET_BYTES, "the corner block fits its budget",
          f"{size} / {CORNER_BUDGET_BYTES} bytes")
    check("gear" in block.lower() and "km/h" in block.lower(),
          "it carries the channel evidence")
    check("Spread" in block or "spread" in block, "it carries the spread")
    lines = [line for line in block.splitlines() if line.startswith("|")]
    check(len(lines) > 5, "it carries the per-lap detail", str(len(lines)))
    check(not re.search(r"\.\d{6,}", block),
          "floats are rounded for a human, not dumped raw",
          (re.search(r"\.\d{6,}", block) or [""])[0])


def test_messages() -> None:
    facts = _facts()
    model = FakeModel("Solid session. You are losing 0.7 s at corner 2. "
                      "Carry more minimum speed there. Did it feel understeery?")
    coach = DebriefCoach(model=model)
    answer = coach.ask("why was corner 2 slow?", facts)
    check(model.calls == 1, "the model is called once")
    system = model.messages[0]["content"]
    check(model.messages[0]["role"] == "system", "the contract is the system prompt")
    check("one question" in system.lower(), "the contract asks for one question")
    check("never invent" in system.lower() or "not in the grounding" in system.lower(),
          "the contract forbids invented numbers")
    user = model.messages[-1]["content"]
    check("why was corner 2 slow?" in user, "the question reaches the model")
    check("Per-lap detail" in user, "a named corner brings its drill-down")
    check(answer.text.startswith("Solid session."), "the answer is returned")
    check(not answer.warnings, "a grounded answer produces no warnings",
          str(answer.warnings))


def test_validation() -> None:
    facts = _facts()
    grounding = build_grounding(facts)

    good = validate_reply(
        "Your best lap was 1:19.135 against a 1:17.166 reference, so 1.969 s is "
        "there. Corner 2 costs you 0.702 s a lap. Does it feel like understeer?",
        grounding=grounding)
    check(not good, "numbers that exist in the facts pass", str(good))

    invented = validate_reply(
        "You are losing 4.7 s in turn 2 and your minimum speed is 62 km/h. "
        "Does that match the car?", grounding=grounding)
    check(any("4.7" in w for w in invented), "an invented number is flagged",
          str(invented))

    two_questions = validate_reply(
        "Corner 2 costs 0.702 s. Did it feel slow? Was the rear moving?",
        grounding=grounding)
    check(any("question" in w for w in two_questions),
          "two questions are flagged", str(two_questions))

    degenerate = validate_reply(
        "Count: Start(1) with(2) the(3) good(4): you(5) lose(6) 0.702 s. Was it?",
        grounding=grounding)
    check(any("annotation" in w for w in degenerate),
          "word-by-word annotation is flagged as degenerate", str(degenerate))

    truncated = validate_reply(
        "It is not how slow you go — your median there is 70.4 against 65.0 and",
        grounding=grounding)
    check(any("truncated" in w for w in truncated),
          "a reply that stops mid-sentence is flagged", str(truncated))

    long_reply = " ".join(["you are slow here"] * 80) + " 0.702 s. Was it?"
    check(any("words" in w for w in validate_reply(long_reply, grounding=grounding)),
          "a rambling reply is flagged")


def test_drilldown_numbers_are_grounded() -> None:
    """Numbers that only appear in the corner block are still the facts."""
    facts = _facts()
    from lap_telemetry.session_brief import corner_block

    block = corner_block(facts, "t1")
    spread = re.search(r"minimum speed spread: ([\d.]+) km/h", block)
    check(spread is not None, "the block states a minimum-speed spread",
          str(spread))
    value = spread.group(1)
    check(value not in build_grounding(facts),
          "the spread is not in the session grounding, only in the drill-down",
          value)

    model = FakeModel(f"You had {value} km/h of apex-speed spread at Bretelle. "
                      f"Did it feel like the same corner each lap?")
    answer = DebriefCoach(model=model).ask("why was Bretelle so bad?", facts)
    check(not answer.warnings,
          "a drill-down number is not reported as invented", str(answer.warnings))

    liar = FakeModel("You lost 4.7 s there. Did it feel slow?")
    check(DebriefCoach(model=liar).ask("why was Bretelle so bad?", facts).warnings,
          "an invented number is still caught when a drill-down is present")


def test_provider_failure_is_explained() -> None:
    """A dead provider is one sentence, not a traceback."""
    from lap_telemetry.coach.llm_adapter import LLMAdapterError
    from lap_telemetry.session_conversation import Conversation

    facts = _facts()
    import tempfile

    class DeadCoach:
        def ask(self, question, facts):
            raise LLMAdapterError("Error code: 410 — model retired")

    with tempfile.TemporaryDirectory() as tmp:
        convo = Conversation(facts, DeadCoach(), out_dir=Path(tmp))
        text = convo.handle("where am I losing time?")
        check("retired" in text or "model" in text.lower(),
              "the provider error reaches the driver", text[:100])
        check("--no-llm" in text, "with a way to recover", text[:140])
        check(convo.transcript[-1]["role"] == "coach",
              "and it is part of the transcript")


def test_provider_errors_are_wrapped() -> None:
    """Callers should only ever need to catch LLMAdapterError."""
    from lap_telemetry.coach import llm_adapter
    from lap_telemetry.coach.coach_config import LLMConfig

    original = llm_adapter._call_via_openai
    def boom(config, messages):
        raise RuntimeError("410 model retired")
    llm_adapter._call_via_openai = boom
    try:
        try:
            llm_adapter.call_llm(LLMConfig(provider="ollama"), [{"role": "user", "content": "hi"}])
        except llm_adapter.LLMAdapterError as exc:
            check("410" in str(exc), "a provider exception becomes LLMAdapterError", str(exc))
        else:
            check(False, "a provider exception becomes LLMAdapterError")
    finally:
        llm_adapter._call_via_openai = original


def test_template_adapter() -> None:
    facts = _facts()
    coach = DebriefCoach(model=None)  # no model: deterministic template
    answer = coach.ask("where am I losing the most time?", facts)
    check(answer.text, "the template adapter answers without a model")
    check(answer.text.count("?") == 1,
          "it asks exactly one question", answer.text[-80:])
    check(not answer.warnings, "its numbers are grounded", str(answer.warnings))
    check(any(priority.corner_name in answer.text for priority in facts.priorities[:2]),
          "it names the top priority", answer.text[:120])

    drilled = coach.ask("why was Bretelle so bad?", facts)
    check("Bretelle" in drilled.text, "a corner question is answered about that corner")
    check(not drilled.warnings, "the drill-down answer stays grounded",
          str(drilled.warnings))


def test_cli() -> None:
    import os
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "product" / "python")
    proc = subprocess.run(
        [sys.executable, "-m", "lap_telemetry", "debrief", str(PRACTICE),
         "--ask", "where am I losing time?", "--no-llm"],
        cwd=str(ROOT), capture_output=True, text=True, env=env)
    check(proc.returncode == 0, "debrief --ask --no-llm exits 0", proc.stderr[-400:])
    check("?" in proc.stdout, "it prints an answer with a question", proc.stdout[-120:])
    check("traceback" not in proc.stderr.lower(), "no traceback on the way")


def main() -> int:
    print("Session debrief coach")
    test_grounding()
    test_find_corner()
    test_corner_block()
    test_messages()
    test_validation()
    test_drilldown_numbers_are_grounded()
    test_provider_failure_is_explained()
    test_provider_errors_are_wrapped()
    test_template_adapter()
    test_cli()
    total = _passed + _failed
    print(f"\n  {_passed}/{total} assertions passed")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
