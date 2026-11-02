#!/usr/bin/env bash
# Run the demo coach script with a single command.
# Usage:  bash scripts/run_coach_demo.sh
#         bash scripts/run_coach_demo.sh --verbose
set -euo pipefail
cd "$(dirname "$0")/.."
# Resolve Python through the shared helper: on Windows `python3` is often the
# Microsoft Store stub, and macOS has no plain `python`. See docs/TESTING_LESSONS.md L16.
PYTHON="$(node dev/scripts/python.js)"
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
export PYTHONPATH="$PWD/product/python${PYTHONPATH:+:$PYTHONPATH}"
# shellcheck disable=SC2086  # the resolver prints "py -3" style command + prefix
$PYTHON product/python/demo_coach_slice01.py "$@"
