"""lap-telemetry CLI entrypoint."""
from __future__ import annotations

import argparse
import sys
from typing import Sequence

from . import __version__


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lap-telemetry",
        description="Telemetry recorder + lap-comparison tool for rFactor 2 / Le Mans Ultimate.",
    )
    parser.add_argument("--version", action="version", version=f"lap-telemetry {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    rec = sub.add_parser("record", help="Connect to active sim and stream telemetry frames.")
    rec.add_argument(
        "--rate",
        type=float,
        default=50.0,
        help="Poll rate in Hz (default: 50).",
    )
    rec.add_argument(
        "--once",
        action="store_true",
        help="Print exactly one frame, then exit.",
    )
    rec.add_argument(
        "--probe-timeout",
        type=float,
        default=3.0,
        help="Seconds to wait for an active sim before giving up (default: 3.0).",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "record":
        from .recorder.record import run
        return run(
            rate_hz=args.rate,
            once=args.once,
            probe_timeout_s=args.probe_timeout,
        )
    parser.error(f"unknown command: {args.cmd}")
    return 2  # unreachable


if __name__ == "__main__":
    sys.exit(main())
