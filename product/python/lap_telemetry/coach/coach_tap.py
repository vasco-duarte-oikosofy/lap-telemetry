"""Coach tap orchestrator — wires QueuedBus → detectors → generators → SpeechQueue.

Supports three ``CoachMode`` values:

- ``LAP`` (default) — only after-lap summaries via ``LapDetector`` →
  ``LiveFactGenerator``. Reproduces slice-06 behavior exactly.
- ``TURN`` — only turn-by-turn coaching via ``CornerExitDetector`` →
  ``LiveCornerFactGenerator``. No lap-summary utterances.
- ``ALL`` — both channels. ``LapCompleted`` events trigger after-lap
  summaries; ``CornerExited`` events trigger mid-lap notes. Lap-completed
  utterances take priority over pending corner-exit utterances (stale-drop
  in ``SpeechQueue``).

Architecture (Option C — dual-path):

After-lap summaries read from the session Parquet written by SessionWriter
(authoritative). Corner-exit notes use the live frame buffer from LapDetector
(fast, low-latency, small window). Both analysis paths run on a
ThreadPoolExecutor(max_workers=1) so the bus worker thread never blocks.

The bus worker thread only does lightweight work: feeding detectors,
submitting analysis jobs to the pool, and checking speech windows. All
heavy work (compare_laps, LLM calls) runs on the pool thread.
"""
from __future__ import annotations

import logging
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional

from lap_telemetry.coach.coach_config import CoachMode, CoachRunConfig
from lap_telemetry.coach.corner_exit_detector import CornerExitDetector, CornerExited
from lap_telemetry.coach.live_corner_fact_generator import LiveCornerFactGenerator
from lap_telemetry.coach.live_fact_generator import LiveFactGenerator
from lap_telemetry.coach.live_fuel_fact_generator import LiveFuelFactGenerator
from lap_telemetry.coach.lap_detector import LapCompleted, LapDetector, NewLap
from lap_telemetry.coach.speech_window import is_speech_window
from lap_telemetry.coach.speech_queue import SpeechQueue
from lap_telemetry.recorder.bus import QueuedBus

log = logging.getLogger(__name__)

# Max time to wait for the session Parquet to be flushed for a given lap
# before falling back to event.frames (the old path). This covers the gap
# between the LapCompleted event and the SessionWriter's flush_shard().
_PARQUET_FLUSH_TIMEOUT_S = 10.0

# Shorter timeout for tests — avoids 10s waits in test scenarios.
# Set via environment variable COACH_PARQUET_TIMEOUT_S.
def _get_parquet_timeout() -> float:
    import os
    try:
        return float(os.environ.get("COACH_PARQUET_TIMEOUT_S", _PARQUET_FLUSH_TIMEOUT_S))
    except (ValueError, TypeError):
        return _PARQUET_FLUSH_TIMEOUT_S


class CoachTap:
    """Wires ``QueuedBus`` → detectors → generators → ``SpeechQueue``.

    Usage::

        bus = QueuedBus(maxsize=256)
        config = CoachRunConfig(mode=CoachMode.ALL, top=3)
        tap = CoachTap(
            bus,
            fact_generator=gen,
            corner_fact_generator=cgen,
            speech_queue=sq,
            config=config,
        )
        tap.start()
        # ... publish frames to bus ...
        tap.shutdown()
    """

    def __init__(
        self,
        bus: QueuedBus,
        fact_generator: LiveFactGenerator | None = None,
        corner_fact_generator: LiveCornerFactGenerator | None = None,
        fuel_fact_generator: LiveFuelFactGenerator | None = None,
        speech_queue: SpeechQueue | None = None,
        config: CoachRunConfig | None = None,
    ) -> None:
        self._bus = bus
        self._fact_generator = fact_generator
        self._corner_fact_generator = corner_fact_generator
        self._fuel_fact_generator = fuel_fact_generator
        self._speech_queue = speech_queue
        self._config = config or CoachRunConfig()

        self._detector = LapDetector()
        self._corner_exit_detector = CornerExitDetector()

        # Wire lap detector callbacks
        self._detector.on_lap_completed = self._on_lap_completed
        self._detector.on_new_lap = self._on_new_lap

        # Wire corner-exit detector callback
        self._corner_exit_detector.on_corner_exited = self._on_corner_exited

        # Pending corner-exit utterance (held if not in a speech window)
        self._pending_corner_utterance: str | None = None

        # Thread pool for analysis (max_workers=1 for serialization)
        self._pool: ThreadPoolExecutor | None = None
        if self._config.mode != CoachMode.OFF:
            self._pool = ThreadPoolExecutor(max_workers=1)

        # Parquet flush signaling: when SessionWriter flushes a shard containing
        # a completed lap, it fires on_lap_flushed(path, lap_number). We store
        # the path so the pool thread can wait for it.
        self._parquet_events: dict[int, Path] = {}
        self._parquet_events_lock = threading.Lock()
        self._parquet_events_cond = threading.Condition(self._parquet_events_lock)

    def notify_parquet_flushed(self, parquet_path: Path, lap_number: int) -> None:
        """Called by SessionWriter when a shard containing a completed lap is flushed.

        This is the signalling mechanism for the dual-path: the after-lap
        analysis waits for this notification before reading from the Parquet.
        """
        with self._parquet_events_cond:
            self._parquet_events[lap_number] = parquet_path
            self._parquet_events_cond.notify_all()

    def _wait_for_parquet(self, lap_number: int, timeout_s: float | None = None) -> Path | None:
        """Wait for the session Parquet to be flushed for a given lap number.

        Returns the Parquet path if available within the timeout, otherwise None.
        On timeout, falls back to None (caller should use event.frames instead).
        """
        if timeout_s is None:
            timeout_s = _get_parquet_timeout()
        deadline = time.monotonic() + timeout_s
        with self._parquet_events_cond:
            while lap_number not in self._parquet_events:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._parquet_events_cond.wait(timeout=remaining)
            return self._parquet_events.get(lap_number)

    def start(self) -> None:
        """Subscribe detectors to the bus and start the bus worker."""
        self._bus.subscribe(self._on_frame)
        if hasattr(self._bus, 'start'):
            self._bus.start()

    def shutdown(self) -> None:
        """Shut down the thread pool, bus worker thread, and speech queue."""
        if self._pool is not None:
            self._pool.shutdown(wait=True)
            self._pool = None
        if hasattr(self._bus, 'shutdown'):
            self._bus.shutdown()
        if self._speech_queue is not None:
            self._speech_queue.shutdown()

    def _on_frame(self, frame) -> None:
        """Process a single frame from the bus (runs on bus worker thread)."""
        # Always feed the lap detector (it tracks state for all modes)
        self._detector.feed(frame)

        # Feed the corner-exit detector only if mode includes turn-by-turn
        if self._config.mode in (CoachMode.TURN, CoachMode.ALL):
            self._corner_exit_detector.feed(frame)

            # Check if a pending corner utterance can now be spoken
            if self._pending_corner_utterance is not None:
                model = self._corner_exit_detector.track_model
                if model is not None and is_speech_window(frame.lap_distance_m, model):
                    if self._speech_queue is not None:
                        self._speech_queue.enqueue(self._pending_corner_utterance)
                    self._pending_corner_utterance = None

    def _on_lap_completed(self, event: LapCompleted) -> None:
        """Handle lap completion — submit analysis to thread pool."""
        # Notify corner-exit detector that a lap was completed
        self._corner_exit_detector.notify_lap_completed()

        # Generate after-lap summary only in LAP or ALL mode
        if self._config.mode not in (CoachMode.LAP, CoachMode.ALL):
            return

        if self._fact_generator is None:
            return

        # Submit to the thread pool — non-blocking for the bus worker
        if self._pool is not None:
            future = self._pool.submit(self._analyze_lap, event)
            future.add_done_callback(self._on_lap_analysis_done)
        else:
            # Fallback: run inline (should not happen if mode != OFF)
            self._analyze_lap(event)

    def _analyze_lap(self, event: LapCompleted) -> tuple[str | None, str | None]:
        """Heavy work: fact generation + utterance (runs on pool thread).

        Uses the dual-path: waits for Parquet flush first (authoritative data),
        falls back to event.frames if Parquet is not available within timeout.

        Returns (utterance, fuel_utterance) tuple.
        """
        # Clear any pending corner utterance — lap summary takes priority
        self._pending_corner_utterance = None

        t_lap_done = time.monotonic()
        print(
            f"lap-telemetry: [coach] lap completed: lap {event.lap_number}, "
            f"track={event.track_name}, frames={event.frame_count}, "
            f"lap_time={event.lap_time_s:.2f}s",
            file=sys.stderr,
            flush=True,
        )

        # Dual-path: try to read from session Parquet first
        parquet_path = self._wait_for_parquet(event.lap_number)

        utterance = None
        if parquet_path is not None:
            # Path C: read from session Parquet (authoritative, complete data)
            try:
                utterance = self._fact_generator.generate_from_parquet(
                    parquet_path=parquet_path,
                    lap_number=event.lap_number,
                    track_name=event.track_name,
                    top=self._config.top,
                )
            except Exception:
                log.exception("Parquet-based fact generation failed for lap %d", event.lap_number)
        else:
            # Timeout fallback: use event.frames (old path, may have dropped frames)
            log.warning(
                "Parquet flush timeout for lap %d — falling back to event.frames (%d frames)",
                event.lap_number, event.frame_count,
            )
            try:
                utterance = self._fact_generator.generate(event, top=self._config.top)
            except Exception:
                log.exception("Fact generation failed for lap %d", event.lap_number)

        if utterance is not None and self._speech_queue is not None:
            t_enqueue = time.monotonic()
            print(
                f"lap-telemetry: [coach] utterance (enqueue +{(t_enqueue - t_lap_done) * 1000:.0f}ms): {utterance}",
                file=sys.stderr,
                flush=True,
            )

        # Fuel engineer call — only when enabled and generator is wired
        fuel_utterance = None
        if self._config.fuel_calls and self._fuel_fact_generator is not None:
            try:
                fuel_utterance = self._fuel_fact_generator.generate(event.frames)
            except Exception:
                log.exception("Fuel fact generation failed for lap %d", event.lap_number)
                fuel_utterance = None

        return (utterance, fuel_utterance)

    def _on_lap_analysis_done(self, future) -> None:
        """Callback: enqueue utterance and fuel utterance to speech queue."""
        utterance_and_fuel = None
        try:
            utterance_and_fuel = future.result()
        except Exception:
            log.exception("Lap analysis failed")
            return
        if utterance_and_fuel is None:
            return
        utterance, fuel_utterance = utterance_and_fuel
        if utterance is not None and self._speech_queue is not None:
            self._speech_queue.enqueue(utterance)
        if fuel_utterance is not None and self._speech_queue is not None:
            print(
                f"lap-telemetry: [coach] fuel utterance: {fuel_utterance}",
                file=sys.stderr,
                flush=True,
            )
            self._speech_queue.enqueue(fuel_utterance)

    def _on_new_lap(self, event: NewLap) -> None:
        """Handle new lap — debug output."""
        print(
            f"lap-telemetry: [coach] new lap: lap {event.lap_number}, "
            f"track={event.track_name}",
            file=sys.stderr,
            flush=True,
        )

    def _on_corner_exited(self, event: CornerExited) -> None:
        """Handle corner exit — submit analysis to thread pool."""
        if self._corner_fact_generator is None:
            return

        # Submit to the thread pool — non-blocking for the bus worker
        if self._pool is not None:
            self._pool.submit(self._analyze_corner, event)
        else:
            # Fallback: run inline (should not happen if mode != OFF)
            self._analyze_corner(event)

    def _analyze_corner(self, event: CornerExited) -> None:
        """Corner-exit analysis (runs on pool thread).

        Uses live frames from LapDetector (fast, small window, low-latency).
        This is the corner-exit path of the dual-path architecture.
        """
        print(
            f"lap-telemetry: [coach] corner exit: {event.corner_name} "
            f"at {event.exit_distance_m:.0f}m lap {event.lap_number}",
            file=sys.stderr,
            flush=True,
        )

        # Generate utterance for this corner exit
        try:
            utterance = self._corner_fact_generator.generate(
                event,
                current_lap_frames=self._detector.current_lap_frames,
                top=self._config.top,
            )
        except Exception:
            log.exception("Corner fact generation failed for %s", event.corner_id)
            return

        if utterance is None:
            log.debug("No utterance for corner %s — skipping", event.corner_id)
            return

        # Check speech window before enqueuing
        model = self._corner_exit_detector.track_model
        if model is not None and self._speech_queue is not None:
            # Find current distance from the latest frame in the current lap
            current_frames = self._detector.current_lap_frames
            if current_frames:
                current_dist = current_frames[-1].lap_distance_m
                if is_speech_window(current_dist, model):
                    print(
                        f"lap-telemetry: [coach] corner utterance: {utterance}",
                        file=sys.stderr,
                        flush=True,
                    )
                    self._speech_queue.enqueue(utterance)
                else:
                    # Hold utterance until we're in a speech window
                    log.debug("Not in speech window, holding corner utterance")
                    self._pending_corner_utterance = utterance
            else:
                # No frames — just enqueue immediately
                if self._speech_queue is not None:
                    self._speech_queue.enqueue(utterance)
        elif self._speech_queue is not None:
            # No model — just enqueue
            self._speech_queue.enqueue(utterance)