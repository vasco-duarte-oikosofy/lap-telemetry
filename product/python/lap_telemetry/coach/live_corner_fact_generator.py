"""Live corner fact generator — produces a coaching utterance for a single corner exit.

Receives a ``CornerExited`` event plus the current lap's frames, resolves the
reference lap and track model, runs ``compare_laps()`` on the partial lap data
(up to a short window past the corner exit), filters facts to only the exited
corner, and calls the LLM for a short coaching note.

If the corner has no significant loss (loss_s < threshold for all phases),
returns ``None`` — don't coach gains on corner exit; save them for the lap summary.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from lap_telemetry.coach.corner_exit_detector import CornerExited
from lap_telemetry.coach.corner_exit_prompt import build_corner_exit_messages
from lap_telemetry.coach.facts import CornerLoss, LapComparisonFacts
from lap_telemetry.coach.frames_to_parquet import frames_to_parquet
from lap_telemetry.coach.lap_detector import LapDetector, LapCompleted
from lap_telemetry.coach.reference_resolver import resolve_reference_lap
from lap_telemetry.coach.track_model import TrackCoachingModel
from lap_telemetry.coach.track_model_resolver import resolve_track_model
from lap_telemetry.coach.track_model import load_track_coaching_model
from lap_telemetry.coach.lap_comparator import compare_laps

log = logging.getLogger(__name__)

# Loss thresholds for corner-exit coaching.
# Only emit if at least one phase exceeds these thresholds.
MIN_LOSS_S_MINIMUM_SPEED = 0.1
MIN_LOSS_S_ENTRY_EXIT = 0.05

# How far past the corner exit to include in the partial lap (metres).
EXIT_WINDOW_M = 150.0


@dataclass
class LiveCornerFactGeneratorConfig:
    """Configuration for the live corner fact generator."""
    reference_search_dir: Path | None = None
    track_model_search_dir: Path | None = None
    enable_cache: bool = True


# Type alias for the LLM utterance generator function.
UtteranceFn = Callable[[LapComparisonFacts, str, int], Optional[str]]


class LiveCornerFactGenerator:
    """Generates coaching utterances from corner exits.

    Usage::

        gen = LiveCornerFactGenerator(utterance_fn=my_llm_fn)
        text = gen.generate(event, lap_detector)
        if text:
            speech_queue.enqueue(text)
    """

    def __init__(
        self,
        utterance_fn: UtteranceFn | None = None,
        config: LiveCornerFactGeneratorConfig | None = None,
    ) -> None:
        self._utterance_fn = utterance_fn
        self._config = config or LiveCornerFactGeneratorConfig()
        self._ref_cache: dict[str, Path | None] = {}
        self._model_cache: dict[str, Path | None] = {}
        self._loaded_models: dict[str, TrackCoachingModel] = {}

    def generate(
        self,
        event: CornerExited,
        current_lap_frames: list,
        lap_detector: LapDetector | None = None,
        top: int = 1,
    ) -> str | None:
        """Generate a coaching utterance from a CornerExited event.

        Args:
            event: The corner-exit event.
            current_lap_frames: The frames from the lap in progress (from
                the LapDetector).
            lap_detector: Optional LapDetector (unused, kept for API compat).
            top: Number of coaching items (1 or 3).

        Returns:
            Utterance string, or ``None`` if skipped.
        """
        track_name = event.track_name

        # 1. Resolve reference lap.
        ref_path = resolve_reference_lap(
            track_name,
            search_dir=self._config.reference_search_dir,
            _cache=self._ref_cache if self._config.enable_cache else None,
        )
        if ref_path is None:
            log.warning("No reference lap for track=%s — skipping corner exit", track_name)
            return None

        # 2. Resolve track model.
        model_path = resolve_track_model(
            track_name,
            search_dir=self._config.track_model_search_dir,
            _cache=self._model_cache if self._config.enable_cache else None,
        )
        if model_path is None:
            log.warning("No track model for track=%s — skipping corner exit", track_name)
            return None

        # 3. Load the track model.
        if track_name not in self._loaded_models:
            try:
                self._loaded_models[track_name] = load_track_coaching_model(model_path)
            except Exception:
                log.exception("Failed to load track model for track=%s", track_name)
                return None
        model = self._loaded_models[track_name]

        # 4. Find the corner that was exited.
        corner = None
        for c in model.corners:
            if c.id == event.corner_id:
                corner = c
                break
        if corner is None:
            log.warning("Corner %s not found in model — skipping", event.corner_id)
            return None

        # 5. Filter current lap frames to up to EXIT_WINDOW_M past the corner exit.
        exit_dist = event.exit_distance_m
        max_dist = exit_dist + EXIT_WINDOW_M
        partial_frames = [
            f for f in current_lap_frames
            if f.lap_distance_m <= max_dist
        ]
        if len(partial_frames) < 10:
            log.debug("Too few partial frames (%d) for corner exit — skipping", len(partial_frames))
            return None

        # 6. Convert partial frames to temp Parquet.
        t0 = time.monotonic()
        try:
            tmp_path = frames_to_parquet(partial_frames)
        except Exception:
            log.exception("Failed to convert partial frames to Parquet for track=%s", track_name)
            return None

        # 7. Compare laps.
        try:
            facts = compare_laps(tmp_path, ref_path, model)
        except Exception:
            log.exception("compare_laps() failed for corner exit track=%s", track_name)
            return None
        finally:
            try:
                tmp_path.unlink()
            except OSError:
                pass

        t_compare = time.monotonic() - t0

        # 8. Filter facts to only the exited corner.
        corner_losses = [
            loss for loss in facts.top_losses
            if loss.corner_id == event.corner_id
        ]

        # 9. Check if any phase has a significant loss.
        has_significant_loss = False
        for loss in corner_losses:
            if loss.phase == "minimum_speed" and loss.loss_s >= MIN_LOSS_S_MINIMUM_SPEED:
                has_significant_loss = True
                break
            elif loss.phase in ("entry", "exit", "exit_brake", "exit_throttle") and loss.loss_s >= MIN_LOSS_S_ENTRY_EXIT:
                has_significant_loss = True
                break

        if not has_significant_loss:
            log.debug(
                "No significant loss in corner %s (losses=%s) — skipping utterance",
                event.corner_id,
                [(l.phase, l.loss_s) for l in corner_losses],
            )
            return None

        # 10. Truncate to top N.
        corner_losses = corner_losses[:top]

        # 11. Build a facts object for the prompt.
        corner_facts = LapComparisonFacts(
            type=facts.type,
            track_id=facts.track_id,
            lap_number=facts.lap_number,
            lap_time_delta_s=facts.lap_time_delta_s,
            top_losses=corner_losses,
            top_gains=[],
            constraints={"max_words": 20 if top == 1 else 30},
        )

        # 12. Generate utterance.
        if self._utterance_fn is None:
            log.warning("No utterance function configured — skipping corner exit LLM call")
            return None

        try:
            utterance = self._utterance_fn(corner_facts, event.corner_name, top)
        except Exception:
            log.exception("LLM utterance generation failed for corner %s", event.corner_id)
            return None

        log.info(
            "Corner exit coaching: track=%s corner=%s compare=%.1fms → %s",
            track_name,
            event.corner_id,
            t_compare * 1000,
            utterance[:80] if utterance else "(none)",
        )

        return utterance