#!/usr/bin/env node
// Wrapper for test_bug27.py — runs the Python test and translates output
// to the [PASS]/[FAIL] protocol expected by test-summary.sh.
const { spawnSync } = require("child_process");
const path = require("path");

const script = path.resolve(__dirname, "test_bug27.py");
const result = spawnSync("python", [script], { encoding: "utf-8" });

if (result.error) {
  console.error(result.error.message);
  process.exit(1);
}

if (result.stdout) console.log(result.stdout.trimEnd());
if (result.stderr) console.error(result.stderr.trimEnd());

process.exit(result.status || 0);