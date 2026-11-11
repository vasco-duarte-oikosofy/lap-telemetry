"""The interactive debrief: commands, history, and the two artifacts.

A debrief that ends without something to do next stint is just a report. This
module holds the conversation state, answers the slash commands, writes the
transcript and turns the priorities into two or three measurable targets.

Targets are built from the priorities, not invented by the model: the coach may
phrase them, but the number to hit is the reference's own value.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from .coach.debrief_coach import DebriefCoach
from .coach.llm_adapter import LLMAdapterError
from .session_brief import corner_block, find_corner
from .session_facts import SessionDebriefFacts
from .session_priorities import ordinal
from .session_report import corner_label, format_lap_time

MAX_TARGETS = 3

# Where the evidence value is measured, per phase.
_PHASE_PLACE = {
    "minimum_speed": "at the apex",
    "entry": "at the braking point",
    "exit_brake": "at the brake release",
    "exit_throttle": "onto the straight",
    "exit": "onto the straight",
}
MIN_TARGET_LOSS_S = 0.10
_MIN_TARGET_CORNER = 2


@dataclass
class Target:
    """One measurable goal for the next stint."""

    corner_id: str
    corner_name: str
    action: str
    measure: str
    loss_s: float
    share_of_gap: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "corner_id": self.corner_id,
            "corner_name": self.corner_name,
            "action": self.action,
            "measure": self.measure,
            "loss_s": round(self.loss_s, 3),
            "share_of_gap": round(self.share_of_gap, 3),
        }


def repl_filenames(stem: str) -> tuple[str, str]:
    """``(plan, transcript)`` file names for a session stem."""
    return f"{stem}_plan.md", f"{stem}_debrief.json"


def build_targets(facts: SessionDebriefFacts) -> list[Target]:
    """Two or three targets from the top priorities, with the number to hit."""
    targets: list[Target] = []
    for priority in facts.priorities:
        if len(targets) >= MAX_TARGETS:
            break
        if targets and priority.recurring_loss_s < MIN_TARGET_LOSS_S:
            continue
        evidence = priority.evidence
        measure = ""
        # Only a deficit is a target: "65 km/h against 71 today" is not.
        if (evidence.get("reference_value") is not None
                and evidence.get("driver_value") is not None
                and evidence["driver_value"] < evidence["reference_value"]):
            unit = evidence.get("unit", "")
            place = _PHASE_PLACE.get(priority.phase, "at the apex")
            measure = (f"{evidence['reference_value']:.1f} {unit} {place}, "
                       f"against {evidence['driver_value']:.1f} {unit} today")
        if evidence.get("reference_gear") and evidence.get("driver_gear") \
                and evidence["reference_gear"] != evidence["driver_gear"]:
            gear = (f"{ordinal(evidence['reference_gear'])} gear at the apex, "
                    f"against {ordinal(evidence['driver_gear'])} today")
            measure = f"{measure}; {gear}" if measure else gear
        targets.append(Target(
            corner_id=priority.corner_id,
            corner_name=priority.corner_name,
            action=priority.suggestion,
            measure=measure or f"no more than {priority.recurring_loss_s:.3f} s lost here",
            loss_s=priority.recurring_loss_s,
            share_of_gap=priority.share_of_gap,
        ))
    return targets


def render_plan(facts: SessionDebriefFacts, targets: list[Target]) -> str:
    """The Markdown plan a driver takes to the next stint."""
    session = facts.session
    pace = facts.consistency.pace
    lines = [f"# Plan — {session.track}", ""]
    if pace:
        lines.append(f"Session best {format_lap_time(pace.best_lap_s)}, "
                     f"{pace.mean_gap_s:.3f} s off the reference on average, "
                     f"spread {pace.spread_s:.3f} s over {pace.clean_laps} clean laps.")
        lines.append("")
    if not targets:
        lines.append("Nothing repeated enough to target. Get more clean laps.")
        return "\n".join(lines) + "\n"
    for index, target in enumerate(targets, start=1):
        lines += [
            f"{index}. **{corner_label(target.corner_name)}** — {target.action}.",
            f"   Measured now: {target.loss_s:.3f} s lost per lap, "
            f"{target.share_of_gap * 100:.0f}% of your gap.",
            f"   Target: {target.measure}.",
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"


@dataclass
class Conversation:
    """One session's debrief: state, commands and the coach."""

    facts: SessionDebriefFacts
    coach: DebriefCoach
    out_dir: Path
    transcript: list[dict[str, Any]] = field(default_factory=list)
    history: list[tuple[str, str]] = field(default_factory=list)
    targets: list[Target] = field(default_factory=list)

    # -- artifacts ---------------------------------------------------------
    @property
    def plan_path(self) -> Path:
        return self.out_dir / repl_filenames(self.facts.session.stem)[0]

    @property
    def transcript_path(self) -> Path:
        return self.out_dir / repl_filenames(self.facts.session.stem)[1]

    def write_plan(self) -> Path:
        targets = build_targets(self.facts)
        self.targets = targets
        text = render_plan(self.facts, targets)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.plan_path.write_text(text, encoding="utf-8")
        return self.plan_path

    def write_transcript(self) -> Path:
        payload = self.facts.to_dict()
        payload["session_id"] = self.facts.session.stem
        payload["track"] = self.facts.session.track
        payload["car_slug"] = self.facts.session.car_slug
        payload["transcript"] = self.transcript
        payload["targets"] = [target.to_dict() for target in self.targets]
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.transcript_path.write_text(json.dumps(payload, indent=2),
                                        encoding="utf-8")
        return self.transcript_path

    # -- commands ----------------------------------------------------------
    def _record(self, role: str, text: str, **extra: Any) -> None:
        entry: dict[str, Any] = {"role": role, "text": text}
        entry.update({k: v for k, v in extra.items() if v})
        self.transcript.append(entry)

    def _ask(self, question: str) -> str:
        self._record("driver", question)
        try:
            answer = self.coach.ask(question, self.facts)
        except LLMAdapterError as exc:
            # A retired model or a dead network must not end the session with a
            # traceback: say what happened and how to keep working.
            text = (f"I could not reach the coach model ({exc}). "
                    f"Fix coach_config.toml and the API key, or run with --no-llm "
                    f"for the same facts without a model.")
            self._record("coach", text, warnings=["provider error"])
            self.history.append(("driver", question))
            self.history.append(("coach", text))
            return text
        self._record("coach", answer.text, warnings=answer.warnings or None)
        self.history.append(("driver", question))
        self.history.append(("coach", answer.text))
        return answer.text

    def _corner(self, name: str) -> str:
        corner_id = find_corner(self.facts, name)
        if corner_id is None:
            self._record("driver", f"/corner {name}")
            text = (f"I do not have a corner called {name!r}. "
                    f"Try one of: " + ", ".join(
                        corner_label(c.corner_name)
                        for c in self.facts.reference_corners[:6]) + ".")
            self._record("coach", text)
            return text
        block = corner_block(self.facts, corner_id)
        self._record("driver", f"/corner {name}")
        self._record("facts", block)
        answer = self.coach.ask(f"what am I losing in {name}?", self.facts)
        self._record("coach", answer.text, warnings=answer.warnings or None)
        return f"{block}\n{answer.text}"

    def _laps(self, spec: str) -> str:
        wanted: set[int] | None = None
        if spec.strip():
            try:
                wanted = {int(part) for part in spec.replace(" ", "").split(",") if part}
            except ValueError:
                return ("Give me segment numbers, e.g. /laps 4,5 or /laps 10. "
                        "The segment column is in the report.")
        rows = ["seg | lap | time | vs reference | clean"]
        for lap in self.facts.laps:
            if wanted is not None and lap.segment_index not in wanted:
                continue
            rows.append(f"{lap.segment_index} | {lap.lap_number} | "
                        f"{format_lap_time(lap.lap_time_s)} | "
                        f"{lap.delta_s:+.3f} | {'yes' if lap.clean else 'no'}")
        if len(rows) == 1:
            return f"No analysed lap matches {spec!r}."
        return "\n".join(rows)

    def handle(self, line: str) -> str:
        """One input line in, one answer out."""
        text = line.strip()
        if not text:
            return ""
        if text.startswith("/"):
            command, _, argument = text[1:].partition(" ")
            command = command.lower()
            if command in ("quit", "exit", "q"):
                self.write_transcript()
                return "__QUIT__"
            if command == "help":
                return ("/corner <name>  per-lap detail and coaching for one corner\n"
                        "/laps [3,4]     the analysed laps (segments)\n"
                        "/plan           two or three targets, written to disk\n"
                        "/save           write the transcript\n"
                        "/quit           save and exit\n"
                        "Anything else is a question for the coach.")
            if command == "corner":
                return self._corner(argument.strip())
            if command == "laps":
                return self._laps(argument)
            if command == "plan":
                self._record("driver", "/plan")
                path = self.write_plan()
                text = render_plan(self.facts, self.targets)
                self._record("coach", text)
                return f"{text}\nWritten to {path}"
            if command == "save":
                self._record("driver", "/save")
                path = self.write_transcript()
                return f"Transcript written to {path}"
            return f"Unknown command /{command}. Try /help."
        return self._ask(text)

    # -- the loop ----------------------------------------------------------
    def run(
        self,
        inputs: Callable[[], str | None] | None = None,
        printer: Callable[[str], None] = print,
    ) -> int:
        """Read lines until /quit or end of input, then save."""
        read = inputs or (lambda: input("You:   "))
        printer("Commands: /corner <name>, /laps, /plan, /save, /help, /quit")
        first = self._ask("give me the debrief")
        printer(f"Coach: {first}")
        while True:
            try:
                line = read()
            except (EOFError, StopIteration):
                line = None
            if line is None:
                break
            answer = self.handle(line)
            if answer == "__QUIT__":
                break
            if answer:
                # Commands print their own output; only questions are the coach
                # speaking.
                printer(answer if line.strip().startswith("/") else f"Coach: {answer}")
        self.write_transcript()
        if not self.plan_path.exists():
            self.write_plan()
        printer(f"Saved: {self.transcript_path}")
        return 0


def run_repl(
    facts: SessionDebriefFacts,
    out_dir: Path,
    *,
    no_llm: bool = False,
    coach: DebriefCoach | None = None,
) -> int:
    """Entry point used by the CLI."""
    from .coach.coach_config import load_config

    if coach is None:
        coach = DebriefCoach(config=None if no_llm else load_config())
    conversation = Conversation(facts, coach, out_dir=out_dir)
    return conversation.run()
