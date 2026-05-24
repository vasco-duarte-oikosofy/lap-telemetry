#!/usr/bin/env python3
"""
Demo script for Interactive Race Coach — Slice 05: Live Bus Tap

Runs the recorder with a live bus tap. Since we cannot connect to a
real sim in CI, the demo script uses the ``--once`` flag for a quick
smoke test.

Usage (with sim running)::

    python3 product/python/demo_coach_slice05.py --out-dir sessions

Smoke test (no sim)::

    python3 product/python/demo_coach_slice05.py --out-dir sessions --once
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from lap_telemetry.coach.live_coach import main


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Demo: recorder with live coach bus tap (slice 05).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("sessions"),
        help="Parquet session output directory.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Smoke-test: record one frame and exit.",
    )
    parser.add_argument(
        "--probe-timeout",
        type=float,
        default=0.0,
        help="Seconds to wait for a sim (0 = wait forever).",
    )
    args = parser.parse_args()
    sys.argv = [
        "demo_coach_slice05",
        "--out-dir", str(args.out_dir),
        "--probe-timeout", str(args.probe_timeout),
    ]
    if args.once:
        sys.argv.append("--once")
    sys.exit(main())