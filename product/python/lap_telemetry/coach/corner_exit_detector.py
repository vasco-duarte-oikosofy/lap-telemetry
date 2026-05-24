"""Corner-exit detector — detects when the car leaves a corner zone.

Receives Frame objects via ``feed()`` (called by CoachTap on the bus worker
thread). Maintains current ``lap_distance_m`` and ``lap_number``. Uses the
``TrackCoachingModel`` to determine when the car transitions from inside a
corner zone to outside all corners (or inside a StraightZone).

Emits a ``CornerExited`` event when ``lap_distance_m`` crosses from inside a
corner to outside all corners. Anti-chatter: enforces a minimum cooldown
(default 8 seconds of ``session_time_s``) between events.

Does NOT emit for corner exits on the first lap (no reference data yet)
or before the first LapCompleted for a track.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

from lap_telemetry.coach.track_model import TrackCoachingModel
from lap_telemetry.recorder.connect import Frame

log = logging.getLogger(__name__)

# Default cooldown between corner-exit events (seconds of session_time_s).
DEFAULT_COOLDOWN_S = 8.0


@dataclass
class CornerExited:
    """Emitted when the car exits a corner zone onto a straight."""
    corner_id: str
    corner_name: str
    exit_distance_m: float
    lap_number: int
    track_name: str


class CornerExitDetector:
    """Detects corner exits from frame stream.

    Usage::

        model = load_track_coaching_model(path)
        det = CornerExitDetector(track_model=model)
        det.on_corner_exited = lambda e: ...
        det.feed(frame)
    """

    def __init__(
        self,
        track_model: Optional[TrackCoachingModel] = None,
        cooldown_s: float = DEFAULT_COOLDOWN_S,
    ) -> None:
        self.track_model = track_model
        self.cooldown_s = cooldown_s
        self.on_corner_exited: Optional[Callable[[CornerExited], None]] = None

        self._current_corner_id: Optional[str] = None
        self._prev_lap_number: Optional[int] = None
        self._prev_track_name: Optional[str] = None
        self._last_exit_session_time: float = -float("inf")
        self._laps_seen: int = 0

    def set_track_model(self, model: TrackCoachingModel) -> None:
        """Update the track model (e.g. when a new track is detected)."""
        self.track_model = model
        self._current_corner_id = None

    def notify_lap_completed(self) -> None:
        """Mark that a lap has been completed. Enables corner-exit detection."""
        self._laps_seen += 1

    def feed(self, frame: Frame) -> None:
        """Process a single frame for corner-exit detection."""
        if self.track_model is None:
            return

        # Reset state on track change
        if self._prev_track_name is not None and frame.track_name != self._prev_track_name:
            self._current_corner_id = None
            self._laps_seen = 0
            self._last_exit_session_time = -float("inf")

        # Skip first lap — no reference data yet
        if self._laps_seen < 1:
            self._prev_lap_number = frame.lap_number
            self._prev_track_name = frame.track_name
            return

        # Reset on lap change (cooldown resets)
        if self._prev_lap_number is not None and frame.lap_number != self._prev_lap_number:
            self._current_corner_id = None

        distance = frame.lap_distance_m
        corner = self.track_model.get_corner_at(distance)

        if corner is not None:
            # Inside a corner zone
            self._current_corner_id = corner.id
        else:
            # Outside all corners — check if we just exited a corner
            if self._current_corner_id is not None:
                exited_id = self._current_corner_id
                self._current_corner_id = None

                # Cooldown check
                elapsed = frame.session_time_s - self._last_exit_session_time
                if elapsed < self.cooldown_s:
                    log.debug(
                        "Corner exit cooldown: %.1fs < %.1fs, skipping %s",
                        elapsed, self.cooldown_s, exited_id,
                    )
                else:
                    # Find the corner name
                    corner_name = exited_id
                    for c in self.track_model.corners:
                        if c.id == exited_id:
                            corner_name = c.name
                            break

                    self._last_exit_session_time = frame.session_time_s

                    event = CornerExited(
                        corner_id=exited_id,
                        corner_name=corner_name,
                        exit_distance_m=distance,
                        lap_number=frame.lap_number,
                        track_name=frame.track_name,
                    )

                    if self.on_corner_exited is not None:
                        self.on_corner_exited(event)

        self._prev_lap_number = frame.lap_number
        self._prev_track_name = frame.track_name