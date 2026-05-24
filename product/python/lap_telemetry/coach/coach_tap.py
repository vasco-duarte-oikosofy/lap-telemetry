"""Coach tap orchestrator — wires QueuedBus → LapDetector → LiveFactGenerator → SpeechQueue.

On ``LapCompleted``: calls ``LiveFactGenerator``, feeds utterance text to
``SpeechQueue``. On ``NewLap``: no action (the previous lap's utterance
is already queued).

Prints debug info to stderr (fact generation timing, utterance text, skip
reasons). Manages ``SpeechQueue`` lifecycle (shutdown on Ctrl+C).
"""
from __future__ import annotations

import logging
import sys
from typing import Optional

from lap_telemetry.coach.lap_detector import LapCompleted, LapDetector, NewLap
from lap_telemetry.coach.live_fact_generator import LiveFactGenerator
from lap_telemetry.coach.speech_queue import SpeechQueue
from lap_telemetry.recorder.bus import QueuedBus

log = logging.getLogger(__name__)


class CoachTap:
    """Wires ``QueuedBus`` → ``LapDetector`` → ``LiveFactGenerator`` → ``SpeechQueue``.

    Usage::

        bus = QueuedBus(maxsize=256)
        tap = CoachTap(bus, fact_generator=gen, speech_queue=sq)
        tap.start()
        # ... publish frames to bus ...
        tap.shutdown()
    """

    def __init__(
        self,
        bus: QueuedBus,
        fact_generator: LiveFactGenerator | None = None,
        speech_queue: SpeechQueue | None = None,
    ) -> None:
        self._bus = bus
        self._detector = LapDetector()
        self._fact_generator = fact_generator
        self._speech_queue = speech_queue
        self._detector.on_lap_completed = self._on_lap_completed
        self._detector.on_new_lap = self._on_new_lap

    def start(self) -> None:
        """Subscribe the detector to the bus and start the bus worker."""
        self._bus.subscribe(self._detector.feed)
        self._bus.start()

    def shutdown(self) -> None:
        """Shut down the bus worker thread and speech queue."""
        self._bus.shutdown()
        if self._speech_queue is not None:
            self._speech_queue.shutdown()

    def _on_lap_completed(self, event: LapCompleted) -> None:
        print(
            f"lap-telemetry: [coach] lap completed: lap {event.lap_number}, "
            f"track={event.track_name}, frames={event.frame_count}, "
            f"lap_time={event.lap_time_s:.2f}s",
            file=sys.stderr,
            flush=True,
        )

        if self._fact_generator is None:
            return

        try:
            utterance = self._fact_generator.generate(event)
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
        print(
            f"lap-telemetry: [coach] new lap: lap {event.lap_number}, "
            f"track={event.track_name}",
            file=sys.stderr,
            flush=True,
        )