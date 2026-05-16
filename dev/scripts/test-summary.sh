#!/usr/bin/env bash
# test-summary.sh — Delegate to the Node parallel runner.
#
# Usage:
#   bash scripts/test-summary.sh          # run full suite (parallel)
#   bash scripts/test-summary.sh <file>   # re-run a single failing test script
#   bash scripts/test-summary.sh --concurrency 4  # custom concurrency
set -euo pipefail

export PYTHONPATH="$(pwd)/product/python${PYTHONPATH:+:$PYTHONPATH}"
exec node dev/scripts/run-tests-parallel.js "$@"