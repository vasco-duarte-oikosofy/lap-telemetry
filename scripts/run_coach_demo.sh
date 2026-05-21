#!/usr/bin/env bash
# Run the demo coach script with a single command.
# Usage:  bash scripts/run_coach_demo.sh
#         bash scripts/run_coach_demo.sh --verbose
set -euo pipefail
cd "$(dirname "$0")/.."
python3 product/python/demo_coach_slice01.py "$@"