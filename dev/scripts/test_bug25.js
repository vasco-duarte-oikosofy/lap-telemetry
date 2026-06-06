#!/usr/bin/env node
// Wrapper for test_bug25.py — runs the Python test and translates output
// to the [PASS]/[FAIL] protocol expected by test-summary.sh.
const { spawnSync } = require("child_process");
const path = require("path");

const script = path.resolve(__dirname, "test_bug25.py");
const result = spawnSync("python", [script], { encoding: "utf-8" });

if (result.error) {
  console.error(result.error.message);
  process.exit(1);
}

// Forward Python output.
if (result.stdout) console.log(result.stdout.trimEnd());
if (result.stderr) console.error(result.stderr.trimEnd());

// If Python exited non-zero, the test already printed [FAIL] lines.
process.exit(result.status || 0);