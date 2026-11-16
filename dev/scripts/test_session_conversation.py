#!/usr/bin/env python3
"""The interactive debrief: commands, history, and the two artifacts.

The conversation is where the mission's promise lands — you leave with two or
three numbers for the next stint — so the tests are about what is on disk
afterwards: the transcript that can be read back, and the plan a driver can
follow without opening the telemetry.

Protocol: prints [PASS]/[FAIL] lines and exits non-zero on any failure.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "product" / "python"))
sys.path.insert(0, str(ROOT / "dev" / "scripts"))

from lap_telemetry.coach.debrief_coach import DebriefCoach  # noqa: E402
from lap_telemetry.session_conversation import (  # noqa: E402
    Conversation,
    build_targets,
    render_plan,
    repl_filenames,
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


def _conversation(out_dir: Path) -> Conversation:
    return Conversation(_facts(), DebriefCoach(), out_dir=out_dir)


def test_laps_command() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        convo = _conversation(Path(tmp))
        text = convo.handle("/laps")
        check("1:19.135" in text, "the lap list shows lap times", text.splitlines()[0])
        check("seg" in text.lower(), "with the segment identity")
        short = convo.handle("/laps 4,5")
        check("1:22.491" in short and "1:21.225" in short,
              "a lap list restricts to the requested segments", short[:80])
        check("1:19.135" not in short, "and hides the others")
        check("lap" in convo.handle("/laps nonsense").lower(),
              "a bad list is answered, not crashed on")


def test_corner_command() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        convo = _conversation(Path(tmp))
        text = convo.handle("/corner Bretelle")
        check("Bretelle" in text, "the answer is about the named corner", text[:80])
        check("?" in text, "it still asks one question")
        roles = [turn["role"] for turn in convo.transcript]
        check(roles == ["driver", "facts", "coach"],
              "the command, the facts shown and the answer are recorded", str(roles))
        unknown = convo.handle("/corner nowhere")
        check("nowhere" in unknown.lower() or "no corner" in unknown.lower(),
              "an unknown corner is answered plainly", unknown[:80])


def test_questions_and_history() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        convo = _conversation(Path(tmp))
        convo.handle("where am I losing time?")
        convo.handle("why was corner 2 slow?")
        questions = [turn for turn in convo.transcript if turn["role"] == "driver"]
        check(len(questions) == 2, "every driver turn is kept", str(len(questions)))
        check(questions[1]["text"] == "why was corner 2 slow?",
              "in order", questions[1]["text"])
        check(len(convo.history) == 4 and convo.history[0][0] == "driver"
              and convo.history[-1][0] == "coach",
              "the coach sees the running history, alternating",
              str([role for role, _ in convo.history]))


def _inject_slip(facts, corner_id: str, apices, braking=None, non_clean=()):
    """Synthetic rear-slip values on one corner, then rebuilt priorities."""
    from lap_telemetry.session_priorities import build_priorities

    braking = braking or {}
    for lap in facts.laps:
        if lap.segment_index in non_clean:
            lap.clean = False
        for extra in lap.corners:
            if extra.corner_id != corner_id:
                continue
            extra.rear_slip_apex_deg = apices.get(lap.segment_index, 1.7)
            extra.rear_slip_braking_deg = braking.get(lap.segment_index)
    facts.priorities = build_priorities(
        facts.laps, facts.reference_corners,
        total_gap_s=(facts.consistency.pace.mean_gap_s
                     if facts.consistency.pace else None),
        unmeasurable=facts.session.unmeasurable_channels)
    return facts


def test_targets_respect_rear_instability() -> None:
    facts = _facts()
    target = build_targets(facts)[0]
    check("controlled test" in target.caveat,
          "an unmeasured session frames its targets as a test", target.caveat[:80])

    sliding = _inject_slip(_facts(), _facts().priorities[0].corner_id,
                           {5: 5.2}, {5: 4.9})
    target = build_targets(sliding)[0]
    check("peak rear slip under" in target.measure,
          "an instability-qualified target is a stability target", target.measure[:90])
    check("km/h" not in target.measure,
          "and it does not keep the old higher-speed number", target.measure[:90])
    check("measured sliding" in target.caveat,
          "the caveat says what was measured", target.caveat[:90])
    check("not clean" not in target.caveat,
          "a clean-lap slide carries no non-clean caveat", target.caveat[:120])
    check(target.action == sliding.priorities[0].suggestion,
          "the action and the suggestion are the same instruction")

    dirty = _facts()
    dirty_corner = dirty.priorities[0].corner_id
    dirty_segment = next(lap.segment_index for lap in dirty.laps if lap.clean)
    _inject_slip(dirty, dirty_corner, {dirty_segment: 5.2}, {dirty_segment: 4.9},
                 non_clean={dirty_segment})
    dirty_target = build_targets(dirty)[0]
    check("a lap excluded as not clean" in dirty_target.caveat,
          "a slide measured on a non-clean lap is labelled in the plan caveat",
          dirty_target.caveat[:140])
    dirty_plan = render_plan(dirty, build_targets(dirty))
    check("a lap excluded as not clean" in dirty_plan,
          "and the plan on disk says it too")

    text = render_plan(sliding, build_targets(sliding))
    check("Caveat:" in text and "peak rear slip under" in text,
          "the plan on disk carries the caveat next to the target",
          text[text.index("Caveat:"):][:80])

    # A slide outside the top targets still reaches the sheet the driver takes away.
    other = _facts()
    fourth = other.priorities[min(3, len(other.priorities) - 1)].corner_id
    _inject_slip(other, fourth, {5: 4.4}, {5: 4.2})
    text = render_plan(other, build_targets(other))
    check("Also measured:" in text and "4.40 deg" in text,
          "a measured slide outside the targets is still on the plan",
          text[text.index("Also measured:"):][:90])


def test_targets() -> None:
    facts = _facts()
    targets = build_targets(facts)
    check(2 <= len(targets) <= 3, "two or three targets, never more",
          str(len(targets)))
    check(all(target.measure for target in targets),
          "every target carries the number to hit")
    check(all(any(ch.isdigit() for ch in target.measure) for target in targets),
          "and that number is numeric", str([t.measure for t in targets]))
    check(len({target.corner_id for target in targets}) == len(targets),
          "no corner is targeted twice")
    check(not any("2th" in t.measure or "3th" in t.measure for t in targets),
          "gear ordinals read correctly", str([t.measure for t in targets]))
    for target in targets:
        if "against" not in target.measure:
            continue
        head, tail = target.measure.split("against", 1)
        if "km/h" in head:
            check(float(head.split()[0]) > float(tail.split()[0]),
                  f"{target.corner_name}: the target is faster than today",
                  target.measure)


def test_plan_command() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        convo = _conversation(Path(tmp))
        text = convo.handle("/plan")
        plan_name, _ = repl_filenames("stem")
        path = Path(tmp) / plan_name.replace("stem", convo.facts.session.stem)
        check(path.exists(), "the plan is written to disk", str(path))
        content = path.read_text()
        check(content in text, "what was written is what was printed")
        check(content.startswith("# Plan"), "the plan has a title", content[:40])
        check(content.count("1.") >= 1 and content.count("2.") >= 1,
              "the plan numbers its targets")
        check("Target:" in content, "each target says what to hit")


def test_save_command() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        convo = _conversation(Path(tmp))
        convo.handle("where am I losing time?")
        convo.handle("/plan")
        convo.handle("/save")
        _, transcript_name = repl_filenames(convo.facts.session.stem)
        path = Path(tmp) / transcript_name
        check(path.exists(), "the transcript is written", str(path))
        payload = json.loads(path.read_text())
        check(payload["session_id"] == convo.facts.session.stem,
              "it is keyed by session id", payload["session_id"])
        check(payload["schema_version"] == "1", "and by schema version")
        check(payload["track"] and payload["car_slug"],
              "it carries track and car for a future profile")
        check(len(payload["transcript"]) >= 4, "the turns are in it",
              str(len(payload["transcript"])))
        check(payload["targets"], "the targets are in it")
        check("laps" in payload and "priorities" in payload,
              "the facts travel with the transcript")


def test_repl_piped() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        convo = _conversation(Path(tmp))
        inputs = iter(["where am I losing time?", "/plan", "/quit"])
        printed: list[str] = []
        convo.run(inputs=lambda: next(inputs, "/quit"), printer=printed.append)
        joined = "\n".join(printed)
        check("1:19.135" in joined, "the REPL answers the question", joined[:60])
        check("Plan" in joined, "and runs the command")
        _, transcript_name = repl_filenames(convo.facts.session.stem)
        check((Path(tmp) / transcript_name).exists(),
              "quitting saves the transcript")
        check(any("Coach:" in line or "?" in line for line in printed),
              "the output is readable", printed[0][:50])


def test_cli_repl() -> None:
    import os
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "product" / "python")
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run(
            [sys.executable, "-m", "lap_telemetry", "debrief", str(PRACTICE),
             "--no-llm", "--out", tmp],
            input="where am I losing time?\n/plan\n/quit\n",
            cwd=str(ROOT), capture_output=True, text=True, env=env)
        check(proc.returncode == 0, "the CLI runs the REPL and exits 0",
              proc.stderr[-400:])
        check("?" in proc.stdout, "it prints the coach's answer")
        files = sorted(p.name for p in Path(tmp).iterdir())
        check(any(name.endswith("_plan.md") for name in files),
              "and writes the plan", str(files))
        check(any(name.endswith("_debrief.json") for name in files),
              "and the transcript", str(files))


def main() -> int:
    print("Session debrief conversation")
    test_laps_command()
    test_corner_command()
    test_questions_and_history()
    test_targets()
    test_targets_respect_rear_instability()
    test_plan_command()
    test_save_command()
    test_repl_piped()
    test_cli_repl()
    total = _passed + _failed
    print(f"\n  {_passed}/{total} assertions passed")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
