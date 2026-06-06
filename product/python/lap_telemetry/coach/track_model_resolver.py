"""Track coaching model resolver — maps a track name to a model JSON file.

Looks for track coaching model JSON files in ``product/data/track-coaching/``
that match the track slug. If multiple models exist (e.g. different vehicle
suffixes), picks the first match.

Caches the resolved path so disk scanning happens once per track.

Uses exact slug matching only. Prefix matching was removed because it
caused false positives between layout variants (e.g. "fuji-speedway-classic"
incorrectly matching "fuji-speedway" data — a different circuit layout).
"""
from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)

# Default search directory — can be overridden for testing.
_DEFAULT_DIR = Path(__file__).resolve().parents[3] / "data" / "track-coaching"


def _track_slug(track_name: str) -> str:
    """Slugify a track name the same way SessionWriter does.

    Accented characters are transliterated (ó→o, é→e)
    via NFKD normalization, not stripped. This ensures "Autódromo José Carlos
    Pace" becomes "autodromo-jose-carlos-pace" (readable) instead of
    "autdromo-jos-carlos-pace" (broken).

    Example: ``""Circuit de Barcelona""`` → ``"circuit-de-barcelona"``.
    """
    import re
    import unicodedata

    # Decompose accented chars into base + combining, then strip combining marks.
    # e.g. "ó" (o with accent) → "o" + "\u0301" (combining acute) → "o"
    slug = unicodedata.normalize("NFKD", track_name)
    slug = "".join(c for c in slug if not unicodedata.combining(c))
    slug = slug.lower().replace(" ", "-")
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    return slug or "unknown"


def resolve_track_model(
    track_name: str,
    search_dir: Path | None = None,
    _cache: dict[str, Path | None] | None = None,
) -> Path | None:
    """Find a track coaching model JSON for a track.

    Matching is exact: the file's stem prefix (before the first ``_``
    or the entire stem) must equal the live slug.

    Args:
        track_name: Track name from LMU (e.g. ``"Fuji Speedway"``).
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

    # Filter: match files whose track prefix equals the slug.
    # We use exact slug matching only — prefix matching (slug.startswith(track_part))
    # was removed because it caused false positives between layout variants
    # (e.g. "fuji-speedway-classic" incorrectly matching "fuji-speedway" data,
    # which is a different circuit layout, not a name variation).
    matching = []
    for p in candidates:
        stem = p.stem  # e.g. "circuit-de-barcelona_dkr-engineering-4-elms25" or "circuit-de-barcelona"
        # The track part is the first segment before any "_"
        track_part = stem.split("_")[0]
        if track_part == slug:
            matching.append(p)

    if not matching:
        log.debug("No track model found for track=%s (slug=%s)", track_name, slug)
        result = None
    else:
        result = matching[0]

    if _cache is not None:
        _cache[slug] = result

    if result is not None:
        log.info("Resolved track model for track=%s → %s", track_name, result.name)

    return result