#!/usr/bin/env python3
"""Test LLM utterance guard — filters meta-output leaking from the model.

Bug: 03-llm-reasoning-leak
Run: python3 dev/scripts/test_llm_utterance_guard.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "product" / "python"))

from lap_telemetry.coach.live_fact_generator import _is_meta_output

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


# ── Known bad outputs (leaked reasoning) ─────────────────────────────────

print("-- Detected as meta-output (should filter) --")

ok(_is_meta_output("- this seems like a hard rule. Let me include it:"),
   "T1: bullet + 'let me' phrase")

ok(_is_meta_output("Let me include the key coaching point here."),
   "T2: starts with 'let me'")

ok(_is_meta_output("I will now summarize the coaching points:"),
   "T3: 'i will' preamble")

ok(_is_meta_output("As a race engineer, I will provide feedback:"),
   "T4: 'as a race engineer' with colon-trailing preamble")

ok(_is_meta_output("This seems like a critical corner. Here is my analysis:"),
   "T5: 'this seems' reasoning")

ok(_is_meta_output("Sure, here is the coaching note for the driver:"),
   "T6: 'sure, here is' preamble")

ok(_is_meta_output("- Lost two seconds in turn three."),
   "T7: leading dash (bullet leak)")

ok(_is_meta_output(""),
   "T8: empty string")

ok(_is_meta_output("   "),
   "T9: whitespace-only string")

ok(_is_meta_output("Here is the utterance:"),
   "T10: ends with colon")

ok(_is_meta_output("Coaching note: turn three exit was slow."),
   "T11: 'coaching note:' label prefix")

# ── Valid utterances (should pass through) ────────────────────────────────

print("\n-- Valid utterances (should NOT filter) --")

ok(not _is_meta_output("Lost two seconds in turn three exit. Brake ten metres later."),
   "T12: clean coaching utterance")

ok(not _is_meta_output("Turn one exit, three seconds lost. Minimum speed low."),
   "T13: comma-separated clean utterance")

ok(not _is_meta_output("Fuel warning. Three laps of fuel, five to go."),
   "T14: fuel update utterance")

ok(not _is_meta_output("Turn two entry, gained one second, carried more speed."),
   "T15: gain utterance")

ok(not _is_meta_output("Lost three point six seconds in turn one. Slow down more."),
   "T16: 'slow down' is valid coaching language")

ok(not _is_meta_output("Turn three, you lifted two hundred metres earlier than reference."),
   "T17: distance reference utterance")

ok(not _is_meta_output("Sector two looks strong. Focus on turn one braking."),
   "T18: multi-sentence coaching")

# ── Prompt contains required guardrail text ───────────────────────────────

print("\n-- Prompt guardrail content --")

from lap_telemetry.coach.prompt_templates import SYSTEM_PROMPT_TEMPLATE

ok("empty string" in SYSTEM_PROMPT_TEMPLATE.lower() or "no useful" in SYSTEM_PROMPT_TEMPLATE.lower(),
   "T19: prompt instructs model to output empty string when no useful fact")

ok(SYSTEM_PROMPT_TEMPLATE.lower().count("output only") >= 1 or
   "output only the utterance" in SYSTEM_PROMPT_TEMPLATE.lower(),
   "T20: prompt contains 'output only the utterance'")

# ── Summary ───────────────────────────────────────────────────────────────

print(f"\n{'-' * 60}")
if fail_count:
    print(f"  FAIL: {fail_count} FAILURES")
    sys.exit(1)
else:
    print(f"  PASS: {pass_count} assertions passed")
