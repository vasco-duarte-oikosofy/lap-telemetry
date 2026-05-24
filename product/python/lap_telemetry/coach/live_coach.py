"""Live coach CLI — start the recorder with a coach bus tap.

Usage::

    python -m lap_telemetry.coach.live_coach --out-dir sessions

When a lap boundary is detected::

    lap-telemetry: [coach] lap completed: lap 3, track=circuit-de-barcelona, frames=2500, lap_time=89.42s
    lap-telemetry: [coach] new lap: lap 4, track=circuit-de-barcelona
"""
from __future__ import annotations

import argparse
import signal
import sys
from pathlib import Path

# Ensure product/python is in the path for imports.
_SCRIPT_DIR = Path(__file__).resolve().parent
_PRODUCT_PY = _SCRIPT_DIR.parent.parent
if str(_PRODUCT_PY) not in sys.path:
    sys.path.insert(0, str(_PRODUCT_PY))

from lap_telemetry.coach.coach_tap import CoachTap
from lap_telemetry.recorder.bus import QueuedBus
from lap_telemetry.recorder import record


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Start the recorder with a live coach bus tap.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("sessions"),
        help="Directory for Parquet session output (default: sessions).",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Smoke-test mode: record one frame and exit.",
    )
    parser.add_argument(
        "--probe-timeout",
        type=float,
        default=0.0,
        help="Seconds to wait for a sim before giving up (0 = wait forever).",
    )
    args = parser.parse_args()

    bus = QueuedBus(maxsize=256)
    tap = CoachTap(bus)
    tap.start()

    # Ensure clean shutdown on Ctrl+C.
    _shutting_down = False

    def _signal_handler(*_args: object) -> None:
        nonlocal _shutting_down
        if _shutting_down:
            return  # avoid double-shutdown
        _shutting_down = True
        tap.shutdown()

    signal.signal(signal.SIGINT, _signal_handler)
    if hasattr(signal, "SIGBREAK"):  # Windows
        signal.signal(signal.SIGBREAK, _signal_handler)

    try:
        return record.run(
            rate_hz=50.0,
            once=args.once,
            probe_timeout_s=args.probe_timeout,
            out_dir=args.out_dir,
            bus=bus,
        )
    finally:
        tap.shutdown()


if __name__ == "__main__":
    sys.exit(main())