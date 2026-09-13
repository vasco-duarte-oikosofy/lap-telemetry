"""Vehicle catalog — maps LMU vehicle names to a canonical car identity.

Uses ``product/data/vehicle_catalog.json`` to group different team liveries
of the same car model (e.g. all Ferrari 296 GT3 entries) under one canonical
slug. This lets the reference/model resolvers pick the right car's data even
when multiple cars have files for the same track.

Two public functions:

- ``canonical_car_slug(vehicle_name)`` — live LMU vehicle name → canonical slug
  (e.g. "Vista AF Corse 2026 #54:WEC" → "ferrari-296-gt3"). Returns None when
  the vehicle is not in the catalog.

- ``car_id_canonical_slug(car_id_slug)`` — a filename car-id slug → canonical
  slug, via a reverse map built by slugifying each catalog key with
  :func:`vehicle_slug` (the same rule the export script uses to name files).

- ``prioritize_for_car(paths, vehicle_name, car_id_of)`` — stable-sort
  candidate paths by car-match priority for the given vehicle (best first),
  or ``[]`` when the vehicle is given but no candidate is car-compatible.
  When ``vehicle_name`` is None the list is returned unchanged (legacy).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, Optional

_DEFAULT_CATALOG = Path(__file__).resolve().parents[3] / "data" / "vehicle_catalog.json"


def vehicle_slug(vehicle_name: str) -> str:
    """Slugify a vehicle name the same way the export script names files.

    "Vista AF Corse 2026 #54:WEC" → "vista-af-corse-2026-54-wec".
    Mirrors ``dev/scripts/export_fastest_reference_laps.vehicle_slug`` so that
    filename car-ids round-trip through the catalog reverse map.
    """
    s = vehicle_name.lower()
    s = re.sub(r"#", "", s)
    s = re.sub(r"[:/]", "-", s)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


# Module-level cache: catalog path -> (catalog dict, reverse map).
_CATALOG_CACHE: dict[Path, tuple[dict, dict]] = {}


def _load_catalog(catalog_path: Path | None = None) -> tuple[dict, dict]:
    path = Path(catalog_path) if catalog_path else _DEFAULT_CATALOG
    cached = _CATALOG_CACHE.get(path)
    if cached is not None:
        return cached
    with path.open("r", encoding="utf-8") as f:
        catalog = json.load(f)
    reverse: dict[str, str] = {}
    for key, entry in catalog.items():
        if key.startswith("_"):
            continue
        slug = entry.get("slug") if isinstance(entry, dict) else None
        if slug:
            reverse[vehicle_slug(key)] = slug
    _CATALOG_CACHE[path] = (catalog, reverse)
    return catalog, reverse


def canonical_car_slug(vehicle_name: str, catalog_path: Path | None = None) -> Optional[str]:
    """Return the canonical car slug for a live vehicle name, or None."""
    if not vehicle_name:
        return None
    catalog, _ = _load_catalog(catalog_path)
    entry = catalog.get(vehicle_name)
    if isinstance(entry, dict) and entry.get("slug"):
        return entry["slug"]
    return None


def car_id_canonical_slug(car_id_slug: str, catalog_path: Path | None = None) -> Optional[str]:
    """Return the canonical car slug for a filename car-id slug, or None."""
    if not car_id_slug:
        return None
    _, reverse = _load_catalog(catalog_path)
    return reverse.get(car_id_slug)


def prioritize_for_car(
    paths: list[Path],
    vehicle_name: str | None,
    car_id_of: Callable[[Path], str],
    catalog_path: Path | None = None,
) -> list[Path]:
    """Stable-sort candidate paths by car-match priority (best first).

    Priority groups (lower is better):
      0 — exact car-id match (filename car-id == vehicle_slug(vehicle_name))
      1 — same canonical car (both map to the same catalog slug)
      2 — generic / car-agnostic (filename has no car-id)

    When ``vehicle_name`` is given, paths that are not car-compatible are
    dropped; if none remain, returns ``[]``. When ``vehicle_name`` is None,
    the list is returned unchanged (legacy behaviour, no car filtering).

    The sort is stable, so a caller that pre-sorts by its own tie-break
    (fastest time, alphabetical, …) preserves that order within each group.
    """
    if not vehicle_name:
        return list(paths)
    vslug = vehicle_slug(vehicle_name)
    vcanon = canonical_car_slug(vehicle_name, catalog_path)

    def priority(p: Path) -> int | None:
        cid = car_id_of(p) or ""
        if cid and cid == vslug:
            return 0
        if vcanon is not None and cid:
            if car_id_canonical_slug(cid, catalog_path) == vcanon:
                return 1
        if cid == "":
            return 2
        return None

    scored = [(priority(p), p) for p in paths]
    compatible = [(pr, p) for (pr, p) in scored if pr is not None]
    if not compatible:
        return []
    compatible.sort(key=lambda t: t[0])  # stable: preserves caller tie-break
    return [p for (_, p) in compatible]