#!/usr/bin/env python3
"""Test utterance readability — bug 09.

Bug: When spoken aloud during a lap, coaching utterances are hard to parse
because (1) gains and losses are interleaved, (2) there is no lead verdict
("you gained" / "you lost"), and (3) sentences drop the subject.

This test:
1. Loads the test corpus fixtures (gains-only, losses-only, mixed,
   single-corner, and contradictory).
2. Verifies each fixture loads and produces valid messages via build_messages.
3. Checks the prompt template contains readability structure rules.

This test does NOT validate the LLM output — that requires a live call.
It validates that the prompt and data structures support the desired patterns.

Run: python3 dev/scripts/test_utterance_readability.py
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

# ── Expected utterance patterns per corpus entry ─────────────────────────
#
# Each corpus entry has:
#   expected_phrases: strings that should appear in a GOOD utterance
#   not_expected_phrases: strings that should NOT appear (common current failures)

CORPUS_EXPECTATIONS = {
    "barcelona_gains_only_facts.json": {
        "expected_phrases": ["you gained", "turn 3"],
        "not_expected_phrases": ["you lost", "slow down"],
    },
    "barcelona_losses_only_facts.json": {
        "expected_phrases": ["you lost", "turn 5"],
        "not_expected_phrases": ["you gained"],
    },
    "barcelona_mixed_gains_and_losses_facts.json": {
        "expected_phrases": ["you gained", "you lost"],
        "not_expected_phrases": [],
    },
    "barcelona_single_corner_facts.json": {
        "expected_phrases": ["you lost", "turn 3"],
        "not_expected_phrases": ["you gained"],
    },
    "barcelona_swapped_faster_driver_facts.json": {
        "expected_phrases": ["you gained", "you lost"],
        "not_expected_phrases": ["slow down"],
    },
}


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


def classify_corner(loss_s: float) -> str:
    """Return 'gain' if loss_s < 0, 'loss' if loss_s > 0."""
    return "gain" if loss_s < 0 else "loss"


# ── Fixture existence ─────────────────────────────────────────────────────

fixtures_dir = ROOT / "dev" / "fixtures" / "coach"

print("── Corpus fixtures ──")

for filename in CORPUS_EXPECTATIONS:
    path = fixtures_dir / filename
    ok(path.exists(), f"T_fixture_exists: {filename}")

# ── Load and classify each fixture ─────────────────────────────────────────

print("\n── Fixture classification ──")

test_idx = 0
for filename, expectations in CORPUS_EXPECTATIONS.items():
    path = fixtures_dir / filename
    if not path.exists():
        continue

    facts, data = load_facts(path)
    n_losses = len(facts.top_losses)
    n_gains = len(facts.top_gains)
    label_prefix = filename.replace("barcelona_", "").replace("_facts.json", "")

    has_losses = n_losses > 0
    has_gains = n_gains > 0

    test_idx += 1
    if "gains_only" in filename:
        ok(has_gains and not has_losses,
           f"T{test_idx:02d}: {label_prefix} — has gains, no losses",
           f"gains={n_gains}, losses={n_losses}")
    elif "losses_only" in filename:
        ok(has_losses and not has_gains,
           f"T{test_idx:02d}: {label_prefix} — has losses, no gains",
           f"gains={n_gains}, losses={n_losses}")
    elif "single_corner" in filename:
        total = n_losses + n_gains
        ok(total == 1,
           f"T{test_idx:02d}: {label_prefix} — has exactly one coaching point",
           f"gains={n_gains}, losses={n_losses}")
    elif "mixed" in filename or "swapped" in filename:
        ok(has_losses and has_gains,
           f"T{test_idx:02d}: {label_prefix} — has both gains and losses",
           f"gains={n_gains}, losses={n_losses}")

# ── build_messages works for each fixture ───────────────────────────────────

print("\n── build_messages produces valid prompts ──")

test_idx = 10
for filename in CORPUS_EXPECTATIONS:
    path = fixtures_dir / filename
    if not path.exists():
        continue
    facts, _ = load_facts(path)
    messages = build_messages(facts)
    test_idx += 1
    ok(len(messages) == 2,
       f"T{test_idx:02d}: {filename} — build_messages returns 2 messages",
       f"got {len(messages)}")
    system_content = messages[0]["content"]
    user_content = messages[1]["content"]
    test_idx += 1
    ok(len(system_content) > 100,
       f"T{test_idx:02d}: {filename} — system prompt non-empty",
       f"len={len(system_content)}")
    test_idx += 1
    ok(len(user_content) > 50,
       f"T{test_idx:02d}: {filename} — user prompt non-empty",
       f"len={len(user_content)}")

# ── Prompt structure rules ──────────────────────────────────────────────────

print("\n── Prompt readability rules ──")

prompt = SYSTEM_PROMPT_TEMPLATE
prompt_lower = prompt.lower()

# The prompt must instruct the LLM to lead with "you gained" or "you lost"
# so the driver hears the verdict first.
has_gain_loss_lead = bool(
    re.search(r"you (gained|lost)", prompt_lower)
    or re.search(r"gain.*loss|loss.*gain", prompt_lower)
)
ok(
    has_gain_loss_lead,
    "T30: prompt instructs to lead with gain/loss verdict",
    "Bug 09: prompt should tell LLM to start coaching points with 'you gained' or 'you lost'",
)

# The prompt must instruct the LLM to group gains before losses (or separate them)
has_separation = bool(
    re.search(
        r"gains?\s+(before|first|then).*loss|loss.*after.*gain"
        r"|separate.*gain.*loss|group.*gain|group.*loss",
        prompt_lower,
    )
)
ok(
    has_separation,
    "T31: prompt instructs to separate gains from losses",
    "Bug 09: prompt should tell LLM to report gains first, then losses",
)

# The prompt should encourage "you" as subject, not imperative or passive
has_you_subject = bool(
    re.search(r"you (gained|lost|carried|braked|released)", prompt_lower)
    or re.search(r'use "you"|use you|subject.*you|start with "you', prompt_lower)
)
ok(
    has_you_subject,
    "T32: prompt encourages 'you' as subject for coaching points",
    "Bug 09: prompt should prefer 'you gained time' over 'turn 3 gained time'",
)

# ── Mixed fixture: gains and losses must both reach the prompt ─────────────

print("\n── Mixed fixture: both gains and losses in user prompt ──")

mixed_path = fixtures_dir / "barcelona_mixed_gains_and_losses_facts.json"
if mixed_path.exists():
    mixed_facts, mixed_data = load_facts(mixed_path)
    messages = build_messages(mixed_facts)
    user_msg = messages[1]["content"]

    # Gains present
    ok(
        any(g["loss_s"] < 0 for g in mixed_data.get("top_gains", [])),
        "T40: mixed fixture has gains in data",
    )
    # Losses present
    ok(
        any(l["loss_s"] > 0 for l in mixed_data.get("top_losses", [])),
        "T41: mixed fixture has losses in data",
    )
    # Both appear in the rendered prompt
    ok(
        "loss_s" in user_msg,
        "T42: mixed fixture user prompt contains loss_s",
    )
    ok(
        "turn 10" in user_msg.lower() or "t10" in user_msg.lower() or "campsa" in user_msg.lower(),
        "T43: mixed fixture user prompt contains loss corner (T10/Campsa)",
    )
    ok(
        "turn 3" in user_msg.lower() or "t3" in user_msg.lower() or "renault" in user_msg.lower(),
        "T44: mixed fixture user prompt contains gain corner (T3/Renault)",
    )

# ── Contradictory fixture: both gains and losses, with speed inversion ─────

print("\n── Contradictory fixture: speed inversion still reachable ──")

swapped_path = fixtures_dir / "barcelona_swapped_faster_driver_facts.json"
if swapped_path.exists():
    swapped_facts, swapped_data = load_facts(swapped_path)
    messages = build_messages(swapped_facts)
    user_msg = messages[1]["content"]

    # The contradictory data point (driver faster but time loss) must be present
    ok(
        "85.0" in user_msg and "81.8" in user_msg,
        "T50: contradictory fixture contains T5 speed values",
    )
    ok(
        "0.114" in user_msg,
        "T51: contradictory fixture contains T5 loss_s value",
    )

# ── Summary ───────────────────────────────────────────────────────────────

print(f"\n{'=' * 60}")
if fail_count:
    print(f"  FAIL: {fail_count} FAILURES")
    sys.exit(1)
else:
    print(f"  PASS: {pass_count} assertions passed")