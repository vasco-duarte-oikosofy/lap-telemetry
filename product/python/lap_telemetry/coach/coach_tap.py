"""Coach tap orchestrator — wires a QueuedBus to a LapDetector.

Prints debug events to stderr. Provides ``shutdown()`` for clean teardown.
Knows nothing about recording, Parquet, or sessions — it only sees Frames.
"""
from __future__ import annotations

import sys
from typing import Optional

from lap_telemetry.recorder.bus import QueuedBus
from lap_telemetry.coach.lap_detector import LapCompleted, LapDetector, NewLap


class CoachTap:
    """Wires ``QueuedBus`` → ``LapDetector`` and prints debug events.

    Usage::

        bus = QueuedBus(maxsize=256)
        tap = CoachTap(bus)
        tap.start()
        # ... publish frames to bus ...
        tap.shutdown()
    """

    def __init__(self, bus: QueuedBus) -> None:
        self._bus = bus
        self._detector = LapDetector()
        self._detector.on_lap_completed = self._on_lap_completed
        self._detector.on_new_lap = self._on_new_lap

    def start(self) -> None:
        """Subscribe the detector to the bus and start the bus worker."""
        self._bus.subscribe(self._detector.feed)
        self._bus.start()

    def shutdown(self) -> None:
        """Shut down the bus worker thread."""
        self._bus.shutdown()

    def _on_lap_completed(self, event: LapCompleted) -> None:
        print(
            f"lap-telemetry: [coach] lap completed: lap {event.lap_number}, "
            f"track={event.track_name}, frames={event.frame_count}, "
            f"lap_time={event.lap_time_s:.2f}s",
            file=sys.stderr,
            flush=True,
        )

    def _on_new_lap(self, event: NewLap) -> None:
        print(
            f"lap-telemetry: [coach] new lap: lap {event.lap_number}, "
            f"track={event.track_name}",
            file=sys.stderr,
            flush=True,
        )