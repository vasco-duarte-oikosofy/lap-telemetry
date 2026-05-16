"""
Record loop: probe sim, poll frames, write Parquet shards via SessionWriter.

Designed to be left running across a whole driving evening: the probe retries
until a sim appears, the frame gate ignores `mInRealtime` (which is False in
LMU's pit garage / menus), and one recorder run produces a separate session
file per (track, vehicle) combo. See `work/archived-plans/m3-plan.md` §D for rationale.
"""
from __future__ import annotations

import signal
import sys
import time
from pathlib import Path
from typing import Optional

from .connect import ConnectError, Frame, _BaseConnection, probe_and_connect
from .writer import SessionWriter, recover_orphaned_shards

_FLUSH_INTERVAL_S = 30.0
_PROBE_RETRY_INTERVAL_S = 3.0
_PROBE_STATUS_INTERVAL_S = 30.0
# How long to wait without a recordable frame before declaring the session
# over (sim quit to main menu, loading screen overshoot, etc.).
_SESSION_IDLE_TIMEOUT_S = 5.0


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


def _is_recordable(frame: Optional[Frame]) -> bool:
    """The "in session, driving (or in pits)" predicate.

    `mInRealtime` is False in LMU's pit-garage UI and menu screens, so we don't
    use it. A non-None frame with non-empty track + vehicle and not paused is
    the reliable "record this row" signal.
    """
    if frame is None or frame.paused:
        return False
    return bool(frame.track_name) and bool(frame.vehicle_name)


def _wait_for_sim(
    probe_timeout_s: float,
    is_stopping,
) -> Optional[_BaseConnection]:
    """Probe for an active sim. `probe_timeout_s == 0` means wait forever.

    Returns the connection, or None if the user interrupted before a sim was
    found. Raises `ConnectError` only if the bounded timeout elapsed without
    a sim appearing.
    """
    print("lap-telemetry: waiting for active sim (LMU or rF2)...", flush=True)
    started = time.monotonic()
    last_status = started
    last_error: Optional[str] = None
    while not is_stopping():
        try:
            return probe_and_connect(timeout_s=_PROBE_RETRY_INTERVAL_S)
        except ConnectError as exc:
            last_error = str(exc)
            now = time.monotonic()
            if probe_timeout_s > 0 and (now - started) >= probe_timeout_s:
                raise
            if now - last_status >= _PROBE_STATUS_INTERVAL_S:
                print("lap-telemetry: still waiting for sim...", flush=True)
                last_status = now
            # Sleep in small increments so SIGINT is responsive.
            sleep_until = now + 1.0
            while time.monotonic() < sleep_until and not is_stopping():
                time.sleep(0.1)
    return None


def run(
    rate_hz: float = 50.0,
    once: bool = False,
    probe_timeout_s: float = 0.0,
    out_dir: Path = Path("sessions"),
) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    recover_orphaned_shards(out_dir)
    period = 1.0 / max(rate_hz, 1.0)

    stopping = False

    def _stop(*_args) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, _stop)
    if hasattr(signal, "SIGBREAK"):  # Windows
        signal.signal(signal.SIGBREAK, _stop)

    # `--once` is a smoke test: bound the probe so it fails fast.
    effective_probe_timeout = probe_timeout_s
    if once and probe_timeout_s == 0.0:
        effective_probe_timeout = 3.0

    try:
        conn = _wait_for_sim(effective_probe_timeout, lambda: stopping)
    except ConnectError as exc:
        print(f"lap-telemetry: {exc}", file=sys.stderr)
        print(
            "lap-telemetry: hint — start LMU or rF2 first (with the rF2 SHM plugin loaded), "
            "then re-run.",
            file=sys.stderr,
        )
        return 2

    if conn is None:
        # Ctrl+C during the probe wait.
        print("lap-telemetry: aborted before any sim was detected.", flush=True)
        return 0

    print(f"lap-telemetry: connected to {conn.sim} (Ctrl+C to stop)", flush=True)
    print(f"lap-telemetry: writing sessions to {out_dir.resolve()}", flush=True)

    last_lap = -1
    last_track = ""
    last_vehicle = ""
    n_frames = 0
    n_skipped = 0
    writer: Optional[SessionWriter] = None
    last_flush_time = time.monotonic()
    last_recordable_time = time.monotonic()
    next_tick = time.monotonic()

    def _close_writer(reason: str) -> None:
        nonlocal writer, last_track, last_vehicle, last_lap
        if writer is None:
            return
        parquet_path, json_path = writer.close()
        print(f"lap-telemetry: session closed ({reason}) -> {parquet_path}", flush=True)
        print(f"lap-telemetry:                          {json_path}", flush=True)
        writer = None
        last_track = ""
        last_vehicle = ""
        last_lap = -1

    try:
        while not stopping:
            conn.update()
            frame: Optional[Frame] = conn.read_frame()

            if once:
                # Smoke-test path: print one frame (recordable or not) and exit.
                if frame is not None:
                    print(_format_frame(frame), flush=True)
                    n_frames += 1
                else:
                    n_skipped += 1
                break

            if not _is_recordable(frame):
                n_skipped += 1
                # Idle for too long → close any open writer cleanly.
                if (
                    writer is not None
                    and time.monotonic() - last_recordable_time >= _SESSION_IDLE_TIMEOUT_S
                ):
                    _close_writer("idle")
            else:
                # frame is non-None per _is_recordable
                assert frame is not None
                last_recordable_time = time.monotonic()

                # Track or vehicle change → rotate session file.
                if writer is not None and (
                    frame.track_name != last_track or frame.vehicle_name != last_vehicle
                ):
                    _close_writer("session changed")

                if writer is None:
                    print(
                        f"lap-telemetry: track={frame.track_name} "
                        f"vehicle={frame.vehicle_name}",
                        flush=True,
                    )
                    writer = SessionWriter(out_dir, conn.sim, frame.track_name, rate_hz)
                    last_track = frame.track_name
                    last_vehicle = frame.vehicle_name
                    last_flush_time = time.monotonic()

                if frame.lap_number != last_lap:
                    print(
                        f"lap-telemetry: lap boundary -> lap {frame.lap_number}",
                        flush=True,
                    )
                    last_lap = frame.lap_number

                writer.append(frame)
                n_frames += 1

                now = time.monotonic()
                if now - last_flush_time >= _FLUSH_INTERVAL_S:
                    writer.flush_shard()
                    last_flush_time = now

            next_tick += period
            sleep_for = next_tick - time.monotonic()
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                next_tick = time.monotonic()
    finally:
        conn.stop()
        if writer is not None:
            parquet_path, json_path = writer.close()
            print(f"lap-telemetry: session saved  -> {parquet_path}", flush=True)
            print(f"lap-telemetry:                   {json_path}", flush=True)
        print(
            f"lap-telemetry: stopped. frames={n_frames} skipped={n_skipped}",
            flush=True,
        )
    return 0
