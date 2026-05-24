"""Track coaching model resolver — maps a track name to a model JSON file.

Looks for track coaching model JSON files in ``product/data/track-coaching/``
that match the track slug. If multiple models exist (e.g. different vehicle
suffixes), picks the first match.

Caches the resolved path so disk scanning happens once per track.

Uses the same flexible prefix-matching as ``reference_resolver`` to handle
track name variations.
"""
from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)

# Default search directory — can be overridden for testing.
_DEFAULT_DIR = Path(__file__).resolve().parents[3] / "data" / "track-coaching"


def _track_slug(track_name: str) -> str:
    """Slugify a track name the same way SessionWriter does.

    Example: ``"Circuit de Barcelona-Catalunya"`` → ``"circuit-de-barcelona-catalunya"``.
    """
    import re

    slug = track_name.lower().replace(" ", "-")
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    return slug or "unknown"


def resolve_track_model(
    track_name: str,
    search_dir: Path | None = None,
    _cache: dict[str, Path | None] | None = None,
) -> Path | None:
    """Find a track coaching model JSON for a track.

    Matching is flexible: the file's stem prefix (before the first ``_``
    or the entire stem) must either equal the live slug or be a prefix
    of the live slug.

    Args:
        track_name: Track name from LMU (e.g. ``"Circuit de Barcelona-Catalunya"``).
        search_dir: Directory containing track coaching model files.
            Defaults to ``product/data/track-coaching/``.
        _cache: Optional mutable cache dict for avoiding repeated disk scans.
            Pass ``{}`` to enable caching across calls.

    Returns:
        Path to the track coaching model JSON file, or ``None`` if no match found.
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

    # Glob for matching JSON files (exclude .diagnostics.txt).
    candidates = sorted(
        p for p in search_dir.glob(f"*.json")
        if not p.name.endswith(".diagnostics.txt")
    )

    # Filter: match files whose track prefix equals the slug or is a prefix
    # of the slug (handles name variations like "Circuit de Barcelona-Catalunya"
    # matching "circuit-de-barcelona" model).
    matching = []
    for p in candidates:
        stem = p.stem  # e.g. "circuit-de-barcelona_dkr-engineering-4-elms25" or "circuit-de-barcelona"
        # The track part is the first segment before any "_"
        track_part = stem.split("_")[0]
        # Match if track_part == slug, or slug extends track_part (with "-").
        if track_part == slug or slug.startswith(track_part + "-"):
            matching.append(p)

    if not matching:
        log.debug("No track model found for track=%s (slug=%s)", track_name, slug)
        result = None
    else:
        # Prefer an exact slug match, then fall back to the first prefix match.
        exact = [p for p in matching if p.stem.split("_")[0] == slug]
        result = exact[0] if exact else matching[0]

    if _cache is not None:
        _cache[slug] = result

    if result is not None:
        log.info("Resolved track model for track=%s → %s", track_name, result.name)

    return result