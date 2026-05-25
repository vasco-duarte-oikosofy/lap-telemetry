#!/usr/bin/env python3
"""Test --print-facts flag on generate_utterance (slice 10).

Run: python3 dev/scripts/test_facts_inspector.py
"""
from __future__ import annotations

import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "product" / "python"))

from lap_telemetry.coach.generate_utterance import main

FIXTURE = str(ROOT / "dev" / "fixtures" / "coach" / "barcelona_lap15_facts.json")

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


print("-- --print-facts flag --")

# T1: exits with code 0
buf = io.StringIO()
with redirect_stdout(buf):
    rc = main(["--facts", FIXTURE, "--print-facts"])
ok(rc == 0, "T1: --print-facts exits 0", f"got {rc}")

# T2: stdout is valid JSON
output = buf.getvalue()
try:
    parsed = json.loads(output)
    ok(True, "T2: stdout is valid JSON")
except json.JSONDecodeError as e:
    ok(False, "T2: stdout is valid JSON", str(e))
    parsed = {}

# T3: contains top_losses key
ok("top_losses" in parsed, "T3: JSON contains 'top_losses'", f"keys={list(parsed.keys())}")

# T4: contains lap_number key
ok("lap_number" in parsed, "T4: JSON contains 'lap_number'", f"keys={list(parsed.keys())}")

# T5: --print-facts does NOT call the LLM
with patch("lap_telemetry.coach.generate_utterance.generate_utterance") as mock_llm:
    buf5 = io.StringIO()
    with redirect_stdout(buf5):
        main(["--facts", FIXTURE, "--print-facts"])
    ok(mock_llm.call_count == 0, "T5: LLM not called with --print-facts", f"called {mock_llm.call_count} times")

# T6: without --print-facts, LLM IS called
with patch("lap_telemetry.coach.generate_utterance.generate_utterance", return_value="Test utterance.") as mock_llm6:
    buf6 = io.StringIO()
    with redirect_stdout(buf6):
        main(["--facts", FIXTURE])
    ok(mock_llm6.call_count == 1, "T6: LLM called once without --print-facts", f"called {mock_llm6.call_count} times")

# T7: without --print-facts, stdout contains utterance (not JSON)
utterance_output = buf6.getvalue().strip()
ok(utterance_output == "Test utterance.", "T7: stdout is utterance not JSON", f"got: {utterance_output!r}")

print(f"\n{'-' * 60}")
if fail_count:
    print(f"  FAIL: {fail_count} FAILURES")
    sys.exit(1)
else:
    print(f"  PASS: {pass_count} assertions passed")
