"""Live fuel fact generator — computes FuelFacts and emits a spoken fuel update."""
from __future__ import annotations

import logging
from typing import Callable

from lap_telemetry.coach.fuel_facts import FuelFacts, compute_fuel_facts
from lap_telemetry.recorder.connect import Frame

log = logging.getLogger(__name__)


class LiveFuelFactGenerator:
    """Compute FuelFacts from live frames and generate a spoken fuel update.

    Speaks only during race sessions, and only when the situation warrants
    it: WARNING/CRITICAL status, or a ≤ 3-lap margin between fuel remaining
    and race laps remaining.
    """

    def __init__(self, utterance_fn: Callable[[FuelFacts], str | None]) -> None:
        self._utterance_fn = utterance_fn

    def generate(self, frames: list[Frame]) -> str | None:
        """Return a spoken utterance or None if no call is warranted.

        Args:
            frames: Frames from the completed lap.

        Returns:
            Utterance string, or None if the call should be skipped.
        """
        if not frames:
            return None

        try:
            facts = compute_fuel_facts(frames)
        except Exception:
            log.exception("compute_fuel_facts() failed")
            return None

        if facts.session_type != "race":
            return None

        if not self._should_speak(facts):
            return None

        try:
            return self._utterance_fn(facts)
        except Exception:
            log.exception("Fuel utterance_fn failed")
            return None

    @staticmethod
    def _should_speak(facts: FuelFacts) -> bool:
        """Return True when the fuel situation is worth reporting."""
        if facts.fuel_status in ("WARNING", "CRITICAL"):
            return True
        if (
            facts.laps_of_fuel_remaining is not None
            and facts.race_laps_remaining is not None
            and (facts.race_laps_remaining - facts.laps_of_fuel_remaining) <= 3
        ):
            return True
        return False
