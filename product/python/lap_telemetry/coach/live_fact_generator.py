"""Live fact generator — analyzes a completed lap and produces a coaching utterance.

Receives a ``LapCompleted`` event, resolves the reference lap and track model,
converts frames to a temporary Parquet file, calls ``compare_laps()`` to
produce facts, then passes facts to ``generate_utterance()`` for a text
string suitable for TTS.

Every step after the event publish can fail without crashing the recorder:
missing reference/model → skip with warning, comparison error → log and skip,
LLM failure → log and skip. The caller (coach_tap) never sees an exception.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from lap_telemetry.coach.facts import LapComparisonFacts
from lap_telemetry.coach.frames_to_parquet import frames_to_parquet
from lap_telemetry.coach.lap_detector import LapCompleted
from lap_telemetry.coach.reference_resolver import resolve_reference_lap
from lap_telemetry.coach.track_model_resolver import resolve_track_model

log = logging.getLogger(__name__)


# Type alias for the LLM utterance generator function.
UtteranceFn = Callable[[LapComparisonFacts], Optional[str]]


@dataclass
class LiveFactGeneratorConfig:
    """Configuration for the live fact generator."""
    reference_search_dir: Path | None = None
    track_model_search_dir: Path | None = None
    # Enable caching for reference/model resolution.
    enable_cache: bool = True


class LiveFactGenerator:
    """Generates coaching utterances from completed laps.

    Usage::

        gen = LiveFactGenerator(utterance_fn=my_llm_fn)
        text = gen.generate(event)
        if text:
            speech_queue.enqueue(text)
    """

    def __init__(
        self,
        utterance_fn: UtteranceFn | None = None,
        config: LiveFactGeneratorConfig | None = None,
    ) -> None:
        self._utterance_fn = utterance_fn
        self._config = config or LiveFactGeneratorConfig()
        self._ref_cache: dict[str, Path | None] = {}
        self._model_cache: dict[str, Path | None] = {}

    def generate(self, event: LapCompleted) -> str | None:
        """Generate a coaching utterance from a LapCompleted event.

        Returns the utterance string, or ``None`` if any step fails.
        """
        track_name = event.track_name
        frames = event.frames

        # 1. Resolve reference lap.
        ref_path = resolve_reference_lap(
            track_name,
            search_dir=self._config.reference_search_dir,
            _cache=self._ref_cache if self._config.enable_cache else None,
        )
        if ref_path is None:
            log.warning(
                "No reference lap for track=%s — skipping utterance",
                track_name,
            )
            return None

        # 2. Resolve track model.
        model_path = resolve_track_model(
            track_name,
            search_dir=self._config.track_model_search_dir,
            _cache=self._model_cache if self._config.enable_cache else None,
        )
        if model_path is None:
            log.warning(
                "No track model for track=%s — skipping utterance",
                track_name,
            )
            return None

        # 3. Convert frames to temporary Parquet.
        t0 = time.monotonic()
        try:
            tmp_path = frames_to_parquet(frames)
        except Exception:
            log.exception("Failed to convert frames to Parquet for track=%s", track_name)
            return None
        t_convert = time.monotonic() - t0

        # 4. Load track model and compare laps.
        try:
            from lap_telemetry.coach.track_model import load_track_coaching_model
            from lap_telemetry.coach.lap_comparator import compare_laps
            model = load_track_coaching_model(model_path)
            t1 = time.monotonic()
            facts = compare_laps(tmp_path, ref_path, model)
            t_compare = time.monotonic() - t1
        except Exception:
            log.exception(
                "compare_laps() failed for track=%s — skipping utterance",
                track_name,
            )
            return None
        finally:
            # Clean up the temp file.
            try:
                tmp_path.unlink()
            except OSError:
                pass

        # 5. Generate utterance.
        if self._utterance_fn is None:
            log.warning("No utterance function configured — skipping LLM call")
            # Still output facts for debugging.
            log.info(
                "Facts generated (no utterance fn): track=%s lap=%d delta=%.3fs losses=%d gains=%d",
                facts.track_id,
                facts.lap_number,
                facts.lap_time_delta_s,
                len(facts.top_losses),
                len(facts.top_gains),
            )
            return None

        t2 = time.monotonic()
        try:
            utterance = self._utterance_fn(facts)
        except Exception:
            log.exception("LLM utterance generation failed for track=%s", track_name)
            return None
        t_llm = time.monotonic() - t2

        log.info(
            "Coaching: track=%s lap=%d convert=%.1fms compare=%.1fms llm=%.1fms → %s",
            track_name,
            event.lap_number,
            t_convert * 1000,
            t_compare * 1000,
            t_llm * 1000,
            utterance[:80] if utterance else "(none)",
        )

        return utterance