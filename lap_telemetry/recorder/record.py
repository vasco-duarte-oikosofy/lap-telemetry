"""
M1 record loop: probe, poll, print one frame line per tick, exit on Ctrl+C.

Writing Parquet shards is M2.
"""
from __future__ import annotations

import signal
import sys
import time
from typing import Optional

from .connect import ConnectError, Frame, probe_and_connect


def _format_frame(f: Frame) -> str:
    return (
        f"sim={f.sim} t={f.session_time_s:8.2f}s "
        f"lap={f.lap_number:>3} dist={f.lap_distance_m:7.1f}m "
        f"lap_t={f.lap_time_s:6.2f}s "
        f"v={f.speed_kph:6.1f}kph "
        f"thr={f.throttle_norm:.2f} brk={f.brake_norm:.2f} "
        f"str={f.steering_norm:+.2f} gear={f.gear:>2} rpm={f.engine_rpm:6.0f} "
        f"realtime={int(f.in_realtime)} idx={f.player_scor_index}"
    )


def run(
    rate_hz: float = 50.0,
    once: bool = False,
    probe_timeout_s: float = 3.0,
) -> int:
    period = 1.0 / max(rate_hz, 1.0)

    print(f"lap-telemetry: probing for active sim (timeout {probe_timeout_s:.1f}s)...", flush=True)
    try:
        conn = probe_and_connect(timeout_s=probe_timeout_s)
    except ConnectError as exc:
        print(f"lap-telemetry: {exc}", file=sys.stderr)
        print(
            "lap-telemetry: hint — start LMU or rF2 first (with the rF2 SHM plugin loaded), "
            "then re-run.",
            file=sys.stderr,
        )
        return 2

    print(f"lap-telemetry: connected to {conn.sim} (Ctrl+C to stop)", flush=True)

    stopping = False

    def _stop(*_args) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, _stop)
    if hasattr(signal, "SIGBREAK"):  # Windows
        signal.signal(signal.SIGBREAK, _stop)

    last_lap = -1
    last_track = ""
    last_vehicle = ""
    n_frames = 0
    n_skipped = 0
    next_tick = time.monotonic()
    try:
        while not stopping:
            conn.update()
            frame: Optional[Frame] = conn.read_frame()
            if frame is None:
                n_skipped += 1
            else:
                if frame.track_name != last_track or frame.vehicle_name != last_vehicle:
                    print(
                        f"lap-telemetry: track={frame.track_name or '?'} "
                        f"vehicle={frame.vehicle_name or '?'}",
                        flush=True,
                    )
                    last_track = frame.track_name
                    last_vehicle = frame.vehicle_name
                if frame.lap_number != last_lap:
                    print(
                        f"lap-telemetry: lap boundary -> lap {frame.lap_number}",
                        flush=True,
                    )
                    last_lap = frame.lap_number
                print(_format_frame(frame), flush=True)
                n_frames += 1
                if once:
                    break

            next_tick += period
            sleep_for = next_tick - time.monotonic()
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                # Fell behind — re-anchor to now to avoid spiral.
                next_tick = time.monotonic()
    finally:
        conn.stop()
        print(
            f"lap-telemetry: stopped. frames={n_frames} skipped={n_skipped}",
            flush=True,
        )
    return 0
