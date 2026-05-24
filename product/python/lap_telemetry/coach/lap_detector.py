"""Lap boundary detector — receives frames, detects lap transitions.

Detects two events:

- ``NewLap`` — a new lap has started (lap_number changed or first frame).
- ``LapCompleted`` — the previous lap finished when a new lap starts.

Maintains ``current_lap_frames`` — the rolling buffer of frames for the
lap in progress. On ``LapCompleted``, the completed lap's frames are
frozen into the event and the buffer is reset for the next lap.

Edge cases:

- First frame ever: emits ``NewLap``, no ``LapCompleted``.
- Lap number goes backward (session restart): emits ``NewLap`` for the
  new lap, discards the in-progress lap without ``LapCompleted``.
- Track name changes: treat as a new session; discard in-progress lap
  without ``LapCompleted``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from lap_telemetry.recorder.connect import Frame


@dataclass
class LapCompleted:
    """Emitted when a lap is completed (new lap boundary detected)."""
    lap_number: int
    track_name: str
    lap_time_s: float
    frame_count: int
    frames: list[Frame] = field(default_factory=list)


@dataclass
class NewLap:
    """Emitted when a new lap starts."""
    lap_number: int
    track_name: str


class LapDetector:
    """Detects lap boundaries from frame lap_number changes.

    Usage::

        det = LapDetector()
        det.on_lap_completed = lambda e: ...
        det.on_new_lap = lambda e: ...
        det.feed(frame)
    """

    def __init__(self) -> None:
        self.on_lap_completed: Optional[Callable[[LapCompleted], None]] = None
        self.on_new_lap: Optional[Callable[[NewLap], None]] = None
        self.current_lap_frames: list[Frame] = []
        self._prev_lap_number: Optional[int] = None
        self._prev_track_name: Optional[str] = None

    def feed(self, frame: Frame) -> None:
        """Process a single frame for lap boundary detection."""
        lap_changed = self._prev_lap_number is not None and frame.lap_number != self._prev_lap_number
        track_changed = self._prev_track_name is not None and frame.track_name != self._prev_track_name

        if track_changed:
            # Track change = new session. Discard in-progress lap.
            self.current_lap_frames = []
            self._emit_new_lap(frame)
        elif lap_changed:
            # Lap boundary. If lap number went backward, discard without
            # completion. If it went forward (or changed unpredictably),
            # complete the previous lap.
            if frame.lap_number < (self._prev_lap_number or 0):
                # Backward jump — session restart. Discard.
                self.current_lap_frames = []
                self._emit_new_lap(frame)
            else:
                # Normal forward lap boundary.
                self._emit_lap_completed(frame)
                self.current_lap_frames = []
                self._emit_new_lap(frame)
        elif self._prev_lap_number is None:
            # Very first frame.
            self._emit_new_lap(frame)

        self.current_lap_frames.append(frame)
        self._prev_lap_number = frame.lap_number
        self._prev_track_name = frame.track_name

    def _emit_new_lap(self, frame: Frame) -> None:
        if self.on_new_lap is not None:
            self.on_new_lap(NewLap(lap_number=frame.lap_number, track_name=frame.track_name))

    def _emit_lap_completed(self, first_frame_of_new_lap: Frame) -> None:
        if self.on_lap_completed is None or self._prev_lap_number is None:
            return
        frames = list(self.current_lap_frames)
        lap_time = frames[-1].lap_time_s if frames else 0.0
        self.on_lap_completed(LapCompleted(
            lap_number=self._prev_lap_number,
            track_name=self._prev_track_name or "",
            lap_time_s=lap_time,
            frame_count=len(frames),
            frames=frames,
        ))