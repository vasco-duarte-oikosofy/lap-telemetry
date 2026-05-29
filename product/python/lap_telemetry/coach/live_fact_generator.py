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
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from lap_telemetry.coach.facts import LapComparisonFacts, PartialLapError
from lap_telemetry.coach.frames_to_parquet import frames_to_parquet
from lap_telemetry.coach.lap_detector import LapCompleted
from lap_telemetry.coach.reference_resolver import resolve_reference_lap
from lap_telemetry.coach.track_model_resolver import resolve_track_model

log = logging.getLogger(__name__)

# Minimum frame count for a lap to be worth analysing.
_MIN_VALID_FRAMES = 50

# Phrases that indicate the LLM leaked reasoning instead of producing an utterance.
_META_PREFIXES = ("let me", "i will", "as a rule", "as a race engineer", "sure,",
                  "sure.", "here is", "coaching note:", "this seems", "below is")


def _is_meta_output(utterance: str) -> bool:
    """Return True when the LLM output looks like leaked reasoning, not an utterance."""
    text = utterance.strip()
    if not text:
        return True
    lower = text.lower()
    if text.startswith("-") or text.startswith("–"):
        return True
    if text.endswith(":"):
        return True
    for phrase in _META_PREFIXES:
        if lower.startswith(phrase):
            return True
    return False


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

    def generate(self, event: LapCompleted, top: int = 3) -> str | None:
        """Generate a coaching utterance from a LapCompleted event.

        Args:
            event: The lap-completed event.
            top: Number of coaching items per call (1 or 3). Truncates
                facts and adjusts the LLM's word limit.

        Returns the utterance string, or ``None`` if any step fails.
        """
        track_name = event.track_name
        frames = event.frames
        t_start = time.monotonic()

        # Guard: skip ghost laps produced at session end.
        if event.frame_count < _MIN_VALID_FRAMES or event.lap_time_s <= 0:
            log.debug(
                "Skipping ghost lap %d (frames=%d, lap_time=%.2fs)",
                event.lap_number, event.frame_count, event.lap_time_s,
            )
            return None

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

        # 5. Apply top-N filtering.
        if top < len(facts.top_losses):
            facts.top_losses = facts.top_losses[:top]
        if top < len(facts.top_gains):
            facts.top_gains = facts.top_gains[:top]
        # Adjust word limit in constraints based on top.
        facts.constraints["max_words"] = 20 if top == 1 else 35

        # 6. Generate utterance.
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
        t_total = time.monotonic() - t_start

        print(
            f"lap-telemetry: [coach] timing lap={event.lap_number} "
            f"convert={t_convert * 1000:.0f}ms "
            f"compare={t_compare * 1000:.0f}ms "
            f"llm={t_llm * 1000:.0f}ms "
            f"total={t_total * 1000:.0f}ms",
            file=sys.stderr,
            flush=True,
        )

        if utterance is not None and _is_meta_output(utterance):
            print(
                f"lap-telemetry: [coach] dropped meta-output for lap {event.lap_number}: "
                f"{utterance[:120]!r}",
                file=sys.stderr,
                flush=True,
            )
            return None

        return utterance

    def generate_from_parquet(
        self,
        parquet_path: Path,
        lap_number: int,
        track_name: str,
        top: int = 3,
    ) -> str | None:
        """Generate a coaching utterance from a session Parquet file.

        This is the Parquet-based path used by the dual-path coach (Option C).
        Instead of converting event.frames (which may have dropped data),
        it reads the complete data from the session Parquet written by
        SessionWriter.

        Args:
            parquet_path: Path to the session Parquet file (shard or merged).
            lap_number: Which lap to filter for comparison.
            track_name: Track name for resolving reference/model.
            top: Number of coaching items per call.

        Returns the utterance string, or ``None`` if any step fails.
        """
        t_start = time.monotonic()

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

        # 3. Load track model and compare laps (filtering to lap_number).
        #    No frames_to_parquet step — we read directly from the session file.
        t0 = time.monotonic()
        try:
            from lap_telemetry.coach.track_model import load_track_coaching_model
            from lap_telemetry.coach.lap_comparator import compare_laps
            model = load_track_coaching_model(model_path)
            t1 = time.monotonic()
            facts = compare_laps(parquet_path, ref_path, model, lap_number=lap_number)
            t_compare = time.monotonic() - t1
        except PartialLapError as exc:
            log.warning(
                "Skipping coaching for partial lap %d (track=%s): %s",
                lap_number, track_name, exc,
            )
            return None
        except Exception:
            log.exception(
                "compare_laps() from Parquet failed for track=%s lap=%d",
                track_name, lap_number,
            )
            return None

        t_parquet = time.monotonic() - t0

        # 4. Apply top-N filtering.
        if top < len(facts.top_losses):
            facts.top_losses = facts.top_losses[:top]
        if top < len(facts.top_gains):
            facts.top_gains = facts.top_gains[:top]
        # Adjust word limit in constraints based on top.
        facts.constraints["max_words"] = 20 if top == 1 else 35

        # 5. Generate utterance.
        if self._utterance_fn is None:
            log.warning("No utterance function configured — skipping LLM call")
            log.info(
                "Facts from Parquet (no utterance fn): track=%s lap=%d delta=%.3fs losses=%d gains=%d",
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
        t_total = time.monotonic() - t_start

        print(
            f"lap-telemetry: [coach] timing-from-parquet lap={lap_number} "
            f"parquet_read={t_parquet * 1000:.0f}ms "
            f"compare={t_compare * 1000:.0f}ms "
            f"llm={t_llm * 1000:.0f}ms "
            f"total={t_total * 1000:.0f}ms",
            file=sys.stderr,
            flush=True,
        )

        if utterance is not None and _is_meta_output(utterance):
            print(
                f"lap-telemetry: [coach] dropped meta-output for lap {lap_number}: "
                f"{utterance[:120]!r}",
                file=sys.stderr,
                flush=True,
            )
            return None

        return utterance