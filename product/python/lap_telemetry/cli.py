"""lap-telemetry CLI entrypoint."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
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
        default=0.0,
        help=(
            "Seconds to wait for an active sim. 0 (default) = wait forever; "
            "Ctrl+C to abort. With --once, an unset value defaults to 3 s "
            "so smoke tests fail fast."
        ),
    )
    rec.add_argument(
        "--out-dir",
        type=Path,
        default=Path("sessions"),
        help="Directory to write session files (default: ./sessions).",
    )

    summ = sub.add_parser("summary", help="Print per-lap overview of a recorded session.")
    summ.add_argument("file", type=Path, help="Path to a .parquet session file.")

    compare = sub.add_parser(
        "compare-laps",
        help="Compare a current lap against a reference lap and print coaching facts.",
    )
    compare.add_argument(
        "--current-lap",
        type=Path,
        required=True,
        help="Path to current lap Parquet file.",
    )
    compare.add_argument(
        "--reference-lap",
        type=Path,
        required=True,
        help="Path to reference lap Parquet file.",
    )
    compare.add_argument(
        "--track-model",
        type=Path,
        required=True,
        help="Path to track coaching model JSON.",
    )

    debrief = sub.add_parser(
        "debrief",
        help="Analyse a whole recorded session and coach the driver through it.",
    )
    debrief.add_argument(
        "file",
        type=Path,
        help="Session Parquet, or one of its .partN.parquet shards.",
    )
    debrief.add_argument(
        "--list",
        action="store_true",
        help="Print the lap inventory (which laps are real flying laps) and exit.",
    )
    debrief.add_argument(
        "--json",
        action="store_true",
        help="Print the session facts as JSON and exit.",
    )
    debrief.add_argument(
        "--report-only",
        action="store_true",
        help="Write the Markdown report and exit (no conversation).",
    )
    debrief.add_argument(
        "--out",
        type=Path,
        help="Directory for the report (default: next to the session).",
    )
    debrief.add_argument(
        "--reference",
        type=Path,
        help="Reference lap Parquet (default: resolve by track and car).",
    )
    debrief.add_argument(
        "--track-model",
        type=Path,
        help="Coaching model JSON (default: resolve by track and car).",
    )
    debrief.add_argument("--track", help="Override the track name from the sidecar.")
    debrief.add_argument("--car", dest="vehicle_name", help="Override the vehicle name.")

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
            out_dir=args.out_dir,
        )
    if args.cmd == "summary":
        from .summary import run as summary_run
        return summary_run(args.file)
    if args.cmd == "compare-laps":
        from .coach.cli import run as compare_run
        return compare_run(args.current_lap, args.reference_lap, args.track_model)
    if args.cmd == "debrief":
        from .debrief import run as debrief_run
        return debrief_run(
            args.file,
            list_only=args.list,
            json_only=args.json,
            report_only=args.report_only,
            out_dir=args.out,
            reference=args.reference,
            track_model_path=args.track_model,
            track=args.track,
            vehicle_name=args.vehicle_name,
        )
    parser.error(f"unknown command: {args.cmd}")
    return 2  # unreachable


if __name__ == "__main__":
    sys.exit(main())
