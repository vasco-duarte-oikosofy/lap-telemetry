"""Reference-lap resolver — maps a track name to the fastest reference lap file.

Looks for reference lap Parquet files in ``product/data/reference-laps/``
that match the track slug. If multiple references exist for a track, picks
the one with the smallest lap time (``_time_`` suffix in the filename).

Caches the resolved path so disk scanning happens once per track.

Uses exact slug matching only. Prefix matching was removed because it
caused false positives between layout variants (e.g. "fuji-speedway-classic"
incorrectly matching "fuji-speedway" data — a different circuit layout).
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

log = logging.getLogger(__name__)

# Default search directory — can be overridden for testing.
_DEFAULT_DIR = Path(__file__).resolve().parents[3] / "data" / "reference-laps"


def _track_slug(track_name: str) -> str:
    """Slugify a track name the same way SessionWriter does.

    Example: ``""Circuit de Barcelona""`` → ``"circuit-de-barcelona"``.
    """
    slug = track_name.lower().replace(" ", "-")
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    return slug or "unknown"


def _extract_prefix(slug: str) -> str:
    """Extract the track prefix from a slug (everything before the first ``_``)."""
    return slug.split("_")[0] if "_" in slug else slug


def resolve_reference_lap(
    track_name: str,
    search_dir: Path | None = None,
    _cache: dict[str, Path | None] | None = None,
) -> Path | None:
    """Find the fastest reference lap Parquet for a track.

    Matching is exact: the file's track prefix (part before the first ``_``)
    must equal the live slug. Prefix matching was removed because it caused
    false positives between layout variants.

    Args:
        track_name: Track name from LMU (e.g. ``"Fuji Speedway"``).
        search_dir: Directory containing reference lap files.
            Defaults to ``product/data/reference-laps/``.
        _cache: Optional mutable cache dict for avoiding repeated disk scans.
            Pass ``{}`` to enable caching across calls.

    Returns:
        Path to the reference lap Parquet file, or ``None`` if no match found.
    """
    if search_dir is None:
        search_dir = _DEFAULT_DIR

    slug = _track_slug(track_name)

    # Check cache first.
    if _cache is not None and slug in _cache:
        cached = _cache[slug]
        if cached is not None and not cached.exists():
            # Cache entry is stale — file was removed.
            del _cache[slug]
        else:
            return cached

    # Glob for all reference lap files.
    candidates = list(search_dir.glob("*_time_*.parquet"))
    if not candidates:
        log.debug("No reference laps found in %s", search_dir)
        result = None
    else:
        # Filter: match files whose track prefix equals the slug.
        # We use exact slug matching only — prefix matching (slug.startswith(track_part))
        # was removed because it caused false positives between layout variants
        # (e.g. "fuji-speedway-classic" incorrectly matching "fuji-speedway" data,
        # which is a different circuit layout, not a name variation).
        matching = []
        for p in candidates:
            stem = p.stem  # e.g. "circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.456"
            # Split on "_time_" to get the prefix (track + vehicle)
            if "_time_" not in stem:
                continue
            prefix = stem.split("_time_")[0]  # e.g. "circuit-de-barcelona_dkr-engineering-4-elms25"
            track_part = prefix.split("_")[0]  # e.g. "circuit-de-barcelona"
            if track_part == slug:
                matching.append(p)

        if not matching:
            log.debug("No reference lap match for track=%s (slug=%s)", track_name, slug)
            result = None
        elif len(matching) == 1:
            result = matching[0]
        else:
            # Pick the fastest — smallest _time_ value in the filename.
            def _parse_time(p: Path) -> float:
                m = re.search(r"_time_(\d+\.\d+)", p.name)
                return float(m.group(1)) if m else float("inf")

            matching.sort(key=_parse_time)
            result = matching[0]

    if _cache is not None:
        _cache[slug] = result

    if result is not None:
        log.info("Resolved reference lap for track=%s → %s", track_name, result.name)

    return result