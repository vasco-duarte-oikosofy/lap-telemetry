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

All steps after the bus publish happen on the ``QueuedBus`` worker thread —
never on the 50 Hz recorder thread.
"""
from __future__ import annotations

import logging
import sys
from typing import Optional

from lap_telemetry.coach.coach_config import CoachMode, CoachRunConfig
from lap_telemetry.coach.corner_exit_detector import CornerExitDetector, CornerExited
from lap_telemetry.coach.live_corner_fact_generator import LiveCornerFactGenerator
from lap_telemetry.coach.live_fact_generator import LiveFactGenerator
from lap_telemetry.coach.lap_detector import LapCompleted, LapDetector, NewLap
from lap_telemetry.coach.speech_window import is_speech_window
from lap_telemetry.coach.speech_queue import SpeechQueue
from lap_telemetry.recorder.bus import QueuedBus

log = logging.getLogger(__name__)


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
        speech_queue: SpeechQueue | None = None,
        config: CoachRunConfig | None = None,
    ) -> None:
        self._bus = bus
        self._fact_generator = fact_generator
        self._corner_fact_generator = corner_fact_generator
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

    def start(self) -> None:
        """Subscribe detectors to the bus and start the bus worker."""
        self._bus.subscribe(self._on_frame)

    def shutdown(self) -> None:
        """Shut down the bus worker thread and speech queue."""
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
        """Handle lap completion — notify detectors and generate summary."""
        # Notify corner-exit detector that a lap was completed
        self._corner_exit_detector.notify_lap_completed()

        # Generate after-lap summary only in LAP or ALL mode
        if self._config.mode not in (CoachMode.LAP, CoachMode.ALL):
            return

        if self._fact_generator is None:
            return

        # Clear any pending corner utterance — lap summary takes priority
        self._pending_corner_utterance = None

        print(
            f"lap-telemetry: [coach] lap completed: lap {event.lap_number}, "
            f"track={event.track_name}, frames={event.frame_count}, "
            f"lap_time={event.lap_time_s:.2f}s",
            file=sys.stderr,
            flush=True,
        )

        try:
            utterance = self._fact_generator.generate(event, top=self._config.top)
        except Exception:
            log.exception("Fact generation failed for lap %d", event.lap_number)
            return

        if utterance is not None and self._speech_queue is not None:
            print(
                f"lap-telemetry: [coach] utterance: {utterance}",
                file=sys.stderr,
                flush=True,
            )
            self._speech_queue.enqueue(utterance)

    def _on_new_lap(self, event: NewLap) -> None:
        """Handle new lap — debug output."""
        print(
            f"lap-telemetry: [coach] new lap: lap {event.lap_number}, "
            f"track={event.track_name}",
            file=sys.stderr,
            flush=True,
        )

    def _on_corner_exited(self, event: CornerExited) -> None:
        """Handle corner exit — generate coaching note if applicable."""
        if self._corner_fact_generator is None:
            return

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