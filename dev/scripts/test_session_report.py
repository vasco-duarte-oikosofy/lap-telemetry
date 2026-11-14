#!/usr/bin/env python3
"""The deterministic Markdown report.

The report is the product for anyone who never talks to the coach, so it is
tested for content (every number it claims), structure (the sections a driver
reads in order) and determinism (two renders, one file). Nothing here may
compute a new number: it formats what the facts already say.

Protocol: prints [PASS]/[FAIL] lines and exits non-zero on any failure.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "product" / "python"))
sys.path.insert(0, str(ROOT / "dev" / "scripts"))

from lap_telemetry.session_facts import build_session_facts  # noqa: E402
from lap_telemetry.session_inputs import resolve_debrief_inputs  # noqa: E402
from lap_telemetry.session_laps import classify_laps  # noqa: E402
from lap_telemetry.session_report import render_session_report  # noqa: E402
from lap_telemetry.session_source import load_session  # noqa: E402

PRACTICE = (ROOT / "dev" / "sessions"
            / "session_20260524T141613Z_paul-ricard---3a_lmu.parquet")
LUSAIL = (ROOT / "dev" / "sessions"
          / "session_20260905T065812Z_lusail-international-circuit_lmu_practice.parquet")

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


def test_sections() -> None:
    report = render_session_report(_facts())
    headings = re.findall(r"^#{1,2} (.+)$", report, flags=re.MULTILINE)
    expected = ["Session debrief", "Headline", "Lap by lap", "Consistency",
                "What to change", "Corners", "Excluded laps",
                "Not measurable", "How to read this"]
    trimmed = [h.split(" — ")[0] for h in headings[:len(expected)]]
    check(trimmed == expected, "the report has its sections in order",
          str(trimmed))
    check(report.startswith("# Session debrief"), "it starts with the title")
    check("Paul Ricard" in report.splitlines()[0],
          "the title names the track", report.splitlines()[0])


def test_content() -> None:
    facts = _facts()
    report = render_session_report(facts)

    check("1:19.135" in report, "the best lap appears as m:ss.mmm",
          str(facts.consistency.pace.best_lap_s))
    check("1:17.166" in report, "the certified reference time appears")
    check("1:16.376" in report, "the envelope appears")
    check("16" in report and "18" in report,
          "the clean and eligible lap counts appear")

    top = facts.priorities[0]
    check(top.corner_name in report, "the top priority names its corner", top.corner_name)
    check(top.suggestion in report, "the top priority carries its computed fix",
          top.suggestion)

    check("short" in report, "the rejected duplicated-row lap is listed")
    check("6235 rows" in report, "and the rejection reason is quoted")

    check(report.count("|") > 40, "the lap table and the corner table are tables")


def test_determinism() -> None:
    facts = _facts()
    first, second = render_session_report(facts), render_session_report(facts)
    check(first == second, "two renders of the same facts are byte-identical")
    check(not re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", first),
          "no wall-clock timestamp leaks into the report")


def test_refusals() -> None:
    report = render_session_report(_facts())
    check("rear slip" in report.lower(),
          "the unmeasurable slip channels are named")
    check("atan2" in report.lower(), "with their reason")
    slip_lines = [line for line in report.splitlines()
                  if "rear slip" in line.lower()]
    check(all(not re.search(r"\d+\.\d+\s*°", line) for line in slip_lines),
          "and never a slip number", str(slip_lines))
    check("ABS" in report, "the unusable ABS channel is named")


def test_baselines_explained() -> None:
    report = render_session_report(_facts())
    lower = report.lower()
    check("reference lap" in lower and "session best" in lower,
          "both baselines are explained")
    check("optimistic" in lower, "the envelope's optimism is stated")
    check("not a target for one lap" in lower,
          "time available is not sold as achievable in one lap")


def _run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    import os
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "product" / "python")
    return subprocess.run([sys.executable, "-m", "lap_telemetry", "debrief", *args],
                          cwd=str(cwd), capture_output=True, text=True, env=env)


def test_cli_out_dir() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "reports"
        proc = _run_cli([str(PRACTICE), "--report-only", "--out", str(out)], ROOT)
        check(proc.returncode == 0, "debrief --report-only exits 0", proc.stderr[-300:])
        files = sorted(p.name for p in out.glob("*.md"))
        check(files == [f"{PRACTICE.stem}_debrief.md"],
              "one report named after the session", str(files))
        text = (out / files[0]).read_text()
        check("Paul Ricard" in text, "the written report has the content")
        check(str(out / files[0]) in proc.stdout,
              "the path of the written report is printed", proc.stdout.strip())


def test_cli_default_location() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        session = Path(tmp) / "sessions"
        session.mkdir()
        copy = session / PRACTICE.name
        shutil.copy(PRACTICE, copy)
        sidecar = PRACTICE.with_suffix(".json")
        if sidecar.exists():
            shutil.copy(sidecar, copy.with_suffix(".json"))
        proc = _run_cli([str(copy), "--report-only"], ROOT)
        check(proc.returncode == 0, "it exits 0 without --out", proc.stderr[-300:])
        expected = session / f"{copy.stem}_debrief.md"
        check(expected.exists(), "the report lands next to the session", str(expected))


def test_gate_writes_nothing() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "reports"
        proc = _run_cli([str(LUSAIL), "--report-only", "--out", str(out)], ROOT)
        check(proc.returncode == 1, "a session under the gate still exits 1")
        check(not out.exists() or not list(out.glob("*.md")),
              "and writes no report")
        check("at least 5" in proc.stderr or "at least" in proc.stderr,
              "the gate explains itself", proc.stderr.strip().splitlines()[0][:80])


def main() -> int:
    print("Session debrief report")
    test_sections()
    test_content()
    test_determinism()
    test_refusals()
    test_baselines_explained()
    test_cli_out_dir()
    test_cli_default_location()
    test_gate_writes_nothing()
    total = _passed + _failed
    print(f"\n  {_passed}/{total} assertions passed")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
