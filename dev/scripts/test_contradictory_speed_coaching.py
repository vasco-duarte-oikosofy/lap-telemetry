#!/usr/bin/env python3
"""Test contradictory speed coaching — bug 04.

Bug: When driver_value > reference_value for minimum_speed (or exit speed)
but loss_s > 0, the LLM tells the driver to "slow down" — inverting the
correct advice. The driver was carrying MORE speed, not less. The time loss
comes from a different cause (late braking, running wide, etc.).

This test verifies:
1. The swapped-lap fixture produces the contradictory case (driver faster but
   losing time) — confirming the bug is reproducible with real data.
2. The prompt template contains rules explaining speed-vs-loss inversions.
3. The prompt rendered from the contradictory facts contains the raw data
   (driver_value > reference_value) that would confuse an LLM.

Run: python3 dev/scripts/test_contradictory_speed_coaching.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "product" / "python"))

from lap_telemetry.coach.facts import LapComparisonFacts, CornerLoss
from lap_telemetry.coach.prompt_templates import build_messages, SYSTEM_PROMPT_TEMPLATE

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


def load_facts(path: Path) -> tuple[LapComparisonFacts, dict]:
    """Load a facts JSON and return both the object and the raw dict."""
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
    facts = LapComparisonFacts(
        type=data.get("type", "lap_coaching_summary"),
        track_id=data.get("track_id", ""),
        lap_number=data.get("lap_number", 0),
        lap_time_delta_s=data.get("lap_time_delta_s", 0.0),
        top_losses=losses,
        top_gains=gains,
        constraints=data.get("constraints", {"max_words": 35, "style": "calm_concise_engineer"}),
    )
    return facts, data


def find_contradictory_losses(losses: list[CornerLoss]) -> list[CornerLoss]:
    """Find losses where driver was FASTER than reference.

    These are the cases that trigger bug 04: the LLM sees a time loss
    and higher driver speed, and may wrongly instruct the driver to
    slow down.
    """
    return [c for c in losses if c.loss_s > 0 and c.driver_value > c.reference_value]


def find_contradictory_gains(gains: list[CornerLoss]) -> list[CornerLoss]:
    """Find gains where driver was SLOWER than reference.

    These are the inverse case: gain despite lower speed. Also
    potentially confusing for an LLM.
    """
    return [c for c in gains if c.loss_s < 0 and c.driver_value < c.reference_value]


# ── Load fixtures ──────────────────────────────────────────────────────────

normal_path = ROOT / "dev" / "fixtures" / "coach" / "barcelona_lap15_facts.json"
swapped_path = ROOT / "dev" / "fixtures" / "coach" / "barcelona_swapped_faster_driver_facts.json"

ok(normal_path.exists(), "T00: normal fixture exists")
ok(swapped_path.exists(), "T01: swapped fixture exists")

if not normal_path.exists() or not swapped_path.exists():
    print("\n  ABORT: missing fixtures")
    sys.exit(1)

print("\n── Normal fixture (driver slower than reference) ──")

normal_facts, normal_dict = load_facts(normal_path)
normal_contradictory = find_contradictory_losses(normal_facts.top_losses)
normal_contra_gains = find_contradictory_gains(normal_facts.top_gains)

ok(
    len(normal_contradictory) == 0,
    "T02: normal fixture has no contradictory losses (driver faster with time loss)",
    f"found {len(normal_contradictory)}: {[(c.phase, c.driver_value, c.reference_value) for c in normal_contradictory]}",
)
ok(
    len(normal_contra_gains) >= 0,
    "T03: normal fixture may have gains where driver is slower (legitimate: different line can gain time despite lower apex speed)",
    f"found {len(normal_contra_gains)}",
)

print("\n── Swapped fixture (driver faster than reference) ──")

swapped_facts, swapped_dict = load_facts(swapped_path)
swapped_contradictory = find_contradictory_losses(swapped_facts.top_losses)

# The key assertion: the swapped fixture MUST contain at least one case
# where driver_value > reference_value AND loss_s > 0.
ok(
    len(swapped_contradictory) >= 1,
    "T04: swapped fixture has contradictory losses (driver faster with time loss)",
    f"found {len(swapped_contradictory)}",
)

if swapped_contradictory:
    c = swapped_contradictory[0]
    print(f"       Example: {c.corner_name} {c.phase}: "
          f"loss_s={c.loss_s:.3f}, driver={c.driver_value}, ref={c.reference_value}, "
          f"driver is {c.driver_value - c.reference_value:+.1f} {c.unit} faster")

# Specifically check T5 minimum_speed: driver 85.0 > reference 81.8 but loss 0.114s
t5_min_speed = [c for c in swapped_facts.top_losses
                if c.corner_id == "t5" and c.phase == "minimum_speed"]
ok(
    len(t5_min_speed) == 1,
    "T05: swapped fixture has T5 minimum_speed loss",
)
if t5_min_speed:
    t5 = t5_min_speed[0]
    ok(
        t5.driver_value > t5.reference_value,
        "T06: T5 minimum_speed — driver FASTER than reference (contradictory)",
        f"driver={t5.driver_value}, ref={t5.reference_value}",
    )
    ok(
        t5.loss_s > 0,
        "T07: T5 minimum_speed — loss_s > 0 (time loss despite higher speed)",
        f"loss_s={t5.loss_s}",
    )

# Check T7 exit: driver 171.6 > reference 157.8 but loss 0.095s
t7_exit = [c for c in swapped_facts.top_losses
           if c.corner_id == "t7" and c.phase == "exit"]
ok(
    len(t7_exit) == 1,
    "T08: swapped fixture has T7 exit loss",
)
if t7_exit:
    t7 = t7_exit[0]
    ok(
        t7.driver_value > t7.reference_value,
        "T09: T7 exit — driver FASTER than reference (contradictory)",
        f"driver={t7.driver_value}, ref={t7.reference_value}",
    )

# ── Prompt content checks ────────────────────────────────────────────────

print("\n── Prompt rules for speed-vs-loss inversions ──")

# Bug 04 fix: the prompt must contain dedicated rules explaining the
# relationship between speed values and loss direction. Without these,
# the LLM sees "loss_s > 0" + "driver_value > reference_value" and
# wrongly tells the driver to slow down.

prompt = SYSTEM_PROMPT_TEMPLATE
prompt_lower = prompt.lower()

ok(
    "minimum_speed" in prompt_lower,
    "T10: prompt mentions minimum_speed phase",
)

# T11: The prompt must contain a dedicated rule (not just Rule 5 example text)
# that explains: for minimum_speed, higher driver_value means MORE speed.
# The rule must explicitly mention that the LLM must NOT say "slow down"
# when the driver's speed is higher than reference.
# This rule must be a standalone numbered rule, not part of Rule 5.
has_no_slowdown_rule = bool(
    re.search(
        r'rule.\s*1[01]:'
        r'|11\.'
        r'|11\)',
        prompt,
    )
) and bool(
    re.search(
        r'do not.*slow.*(down|er)|never.*slow.*(down|er)|must not.*slow|slower.*not.*less',
        prompt_lower,
    )
)
ok(
    has_no_slowdown_rule,
    "T11: prompt has a rule telling the LLM NOT to say slow down when driver is faster",
    "Bug 04 fix: must add a numbered rule about speed direction",
)

# T12: The prompt must explain that driver_value and reference_value are
# raw telemetry measurements, and that for minimum_speed, higher = faster.
# This must be a dedicated interpretation rule, not just an example.
has_speed_interpretation = bool(
    re.search(
        r'driver_value.*(?:faster|more speed|higher speed|speed higher)'
        r'|minimum_speed.*(?:faster|higher.*value|driver.*faster)',
        prompt_lower,
    )
)
ok(
    has_speed_interpretation,
    "T12: prompt explains that driver_value > reference_value for minimum_speed means driver is FASTER",
    "Bug 04 fix: LLM must understand speed direction, not assume lower = slower",
)

# T13: The prompt must explain that positive loss_s means the driver was
# slower OVERALL in this phase, but individual metric values can diverge.
# A driver can lose time while carrying more speed (late braking, running wide).
has_loss_explanation = bool(
    re.search(
        r'loss_s\s+always\s+means.*slower\s+overall',
        SYSTEM_PROMPT_TEMPLATE.replace('\n', ' '),
    )
)
ok(
    has_loss_explanation,
    "T13: prompt explains that positive loss_s means slower overall, not that every metric is lower",
    "Bug 04 fix: loss_s direction != speed direction for every metric",
)

# ── Render prompt with contradictory facts ────────────────────────────────

print("\n── Rendered prompt from contradictory facts ──")

messages = build_messages(swapped_facts)

ok(len(messages) == 2, "T14: build_messages returns 2 messages (system + user)")
system_msg = messages[0]["content"]
user_msg = messages[1]["content"]

# Verify the contradictory data is present in the user prompt
ok(
    "85.0" in user_msg and "81.8" in user_msg,
    "T15: user prompt contains T5 minimum_speed values (85.0 vs 81.8)",
)

ok(
    "171.6" in user_msg and "157.8" in user_msg,
    "T16: user prompt contains T7 exit values (171.6 vs 157.8)",
)

# Verify loss_s values are present
ok(
    "0.114" in user_msg,
    "T17: user prompt contains T5 loss_s (0.114)",
)

ok(
    "-0.212" in user_msg,
    "T18: user prompt contains T3 gain loss_s (-0.212)",
)

# Print the rendered user prompt for manual inspection
print(f"\n{'─' * 60}")
print("USER PROMPT (contradictory facts):")
print(f"{'─' * 60}")
print(user_msg[:1500])
print(f"{'─' * 60}\n")

# ── Summary ───────────────────────────────────────────────────────────────

print(f"{'=' * 60}")
if fail_count:
    print(f"  FAIL: {fail_count} FAILURES")
    sys.exit(1)
else:
    print(f"  PASS: {pass_count} assertions passed")