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

    Accented characters are transliterated (e.g. \u00f3\u2192o, \u00e9\u2192e)
    via NFKD normalization, not stripped. This ensures "Aut\u00f3dromo Jos\u00e9 Carlos
    Pace" becomes "autodromo-jose-carlos-pace" (readable) instead of
    "autdromo-jos-carlos-pace" (broken).

    Example: ``""Circuit de Barcelona""`` \u2192 ``"circuit-de-barcelona"``.
    """
    import unicodedata

    # Decompose accented chars into base + combining, then strip combining marks.
    # e.g. "\u00f3" (\u00f3 with accent) \u2192 "o" + "\u0301" (combining acute) \u2192 "o"
    slug = unicodedata.normalize("NFKD", track_name)
    slug = "".join(c for c in slug if not unicodedata.combining(c))
    slug = slug.lower().replace(" ", "-")
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    return slug or "unknown"


def _extract_prefix(slug: str) -> str:
    """Extract the track prefix from a slug (everything before the first ``_``)."""
    return slug.split("_")[0] if "_" in slug else slug


def _ref_car_id(path: Path, track_slug: str) -> str:
    """Extract the car-id slug from a reference-lap filename.

    ``lusail-..._vista-af-corse-2026-54-wec_time_01.58.640`` →
    ``"vista-af-corse-2026-54-wec"``. Returns ``""`` for a car-agnostic file.
    """
    stem = path.stem
    if "_time_" not in stem:
        return ""
    prefix = stem.split("_time_")[0]
    if prefix == track_slug:
        return ""
    if prefix.startswith(track_slug + "_"):
        return prefix[len(track_slug) + 1:]
    return ""


def resolve_reference_lap(
    track_name: str,
    search_dir: Path | None = None,
    vehicle_name: str | None = None,
    _cache: dict[str, Path | None] | None = None,
) -> Path | None:
    """Find the fastest reference lap Parquet for a track.

    Matching is exact: the file's track prefix (part before the first ``_``)
    must equal the live slug. Prefix matching was removed because it caused
    false positives between layout variants.

    When ``vehicle_name`` is given, candidates are narrowed to the live
    vehicle's car via ``product/data/vehicle_catalog.json`` (liveries of the
    same car model are grouped). When the vehicle has no matching reference
    for this track, ``None`` is returned — another car's reference is never
    used. When ``vehicle_name`` is None, the fastest match is returned
    regardless of car (legacy behaviour).

    Args:
        track_name: Track name from LMU (e.g. ``"Fuji Speedway"``).
        search_dir: Directory containing reference lap files.
            Defaults to ``product/data/reference-laps/``.
        vehicle_name: Live LMU vehicle name (e.g. ``"Vista AF Corse 2026 #54:WEC"``).
            When given, restricts the match to the same canonical car.
        _cache: Optional mutable cache dict for avoiding repeated disk scans.
            Pass ``{}`` to enable caching across calls.

    Returns:
        Path to the reference lap Parquet file, or ``None`` if no match found.
    """
    if search_dir is None:
        search_dir = _DEFAULT_DIR

    slug = _track_slug(track_name)
    cache_key = f"{slug}|{vehicle_name or ''}"

    # Check cache first.
    if _cache is not None and cache_key in _cache:
        cached = _cache[cache_key]
        if cached is not None and not cached.exists():
            # Cache entry is stale — file was removed.
            del _cache[cache_key]
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
        else:
            # Sort by fastest (smallest _time_ value) — stable base order.
            def _parse_time(p: Path) -> float:
                m = re.search(r"_time_(\d+\.\d+)", p.name)
                return float(m.group(1)) if m else float("inf")

            matching.sort(key=_parse_time)
            # Narrow to the live vehicle's car when a vehicle is given.
            from lap_telemetry.coach.car_catalog import prioritize_for_car

            matching = prioritize_for_car(
                matching, vehicle_name, lambda p: _ref_car_id(p, slug)
            )
            result = matching[0] if matching else None

    if _cache is not None:
        _cache[cache_key] = result

    if result is not None:
        log.info("Resolved reference lap for track=%s → %s", track_name, result.name)

    return result