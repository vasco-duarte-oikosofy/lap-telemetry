#!/usr/bin/env python3
"""SLICE-01 SPIKE (throwaway) — bake turn-label anchors for the circuit map.

Prototype of the `turns` block described in docs/specs/MAP_TURN_NAMES.md.

For every corner of a curated coaching model:
  apex_s_m -> world x,y on the reference lap
           -> outward normal (pointing away from the outline polygon interior)
           -> offset by a world distance equivalent to `gap_px` at a 250 px map

Output JSON is intentionally the shape the spec proposes, so slice 02 can copy
it. Nothing here is production code.

Usage:
  python3 bake_anchors.py <track-slug>
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pyarrow.parquet as pq

def _project_root(start: Path) -> Path:
    for parent in start.parents:
        if (parent / "product" / "data").is_dir():
            return parent
    raise RuntimeError("project root not found")


ROOT = _project_root(Path(__file__).resolve())
MAP_SIZE = 250.0          # canonical compare-app map (pipeline.js buildTrackTransform)
MAP_PAD = 20.0            # pipeline.js PAD
FONT_RATIO = 0.023        # fontSize = clamp(map_size * FONT_RATIO, 5, 8)
FONT_MIN, FONT_MAX = 5.0, 8.0
GAP_RATIO = 0.75          # gap_px = fontSize * GAP_RATIO (adjacency)

# Spike-only: short display names for official names too long to fit on a
# 250 px map. The real fix is a curated `short_name` field (slice 02 proposal);
# this dict just proves the effect. Keys are (track slug, corner name).
SHORT_NAMES = {
    ("monza-curva-grande-circuit", "Curva Grande"): "Curva Grande",
    ("monza-curva-grande-circuit", "Variante della Roggia 1"): "Roggia 1",
    ("monza-curva-grande-circuit", "Variante della Roggia 2"): "Roggia 2",
    ("monza-curva-grande-circuit", "Lesmo 1"): "Lesmo 1",
    ("monza-curva-grande-circuit", "Lesmo 2"): "Lesmo 2",
    ("monza-curva-grande-circuit", "Curva del Serraglio"): "Serraglio",
    ("monza-curva-grande-circuit", "Variante Ascari 1"): "Ascari 1",
    ("monza-curva-grande-circuit", "Variante Ascari 2"): "Ascari 2",
    ("monza-curva-grande-circuit", "Variante Ascari 3"): "Ascari 3",
    ("monza-curva-grande-circuit", "Curva Alboreto (Parabolica)"): "Parabolica",
}


def font_px(map_size: float, floor: bool = True) -> float:
    raw = map_size * FONT_RATIO
    return max(FONT_MIN, min(FONT_MAX, raw)) if floor else raw


def map_scale(bbox: dict, map_size: float) -> float:
    """px per world unit for a square map with the pipeline's padding."""
    inner = map_size - 2 * MAP_PAD
    w = bbox["maxX"] - bbox["minX"] or 1.0
    h = bbox["maxY"] - bbox["minY"] or 1.0
    return min(inner / w, inner / h)


def bbox_of(points: list[dict]) -> dict:
    xs = [p["x"] for p in points]
    ys = [p["y"] for p in points]
    return {"minX": min(xs), "maxX": max(xs), "minY": min(ys), "maxY": max(ys)}


def unwrap_lap(lap_s, lap_x, lap_y):
    """Roll the lap so distance is monotonically increasing from ~0.

    Spike finding: `lap_distance_m` in an exported reference parquet WRAPS at
    the start/finish line (e.g. 2960.6, ..., 0.1, ..., 2960.5) — the first row
    is not s=0, so a plain binary search on the raw column silently returns a
    bogus bracket. Roll at the single wrap point instead.
    """
    wrap = None
    for i in range(1, len(lap_s)):
        if lap_s[i] < lap_s[i - 1]:
            wrap = i
            break
    if wrap is None:
        return lap_s, lap_x, lap_y
    return (lap_s[wrap:] + lap_s[:wrap],
            lap_x[wrap:] + lap_x[:wrap],
            lap_y[wrap:] + lap_y[:wrap])


def interpolate_lap(lap_s, lap_x, lap_y, s: float):
    """Linear interpolation of the reference lap position at distance s."""
    if s <= lap_s[0]:
        return lap_x[0], lap_y[0]
    if s >= lap_s[-1]:
        return lap_x[-1], lap_y[-1]
    lo, hi = 0, len(lap_s) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if lap_s[mid] <= s:
            lo = mid
        else:
            hi = mid
    span = lap_s[hi] - lap_s[lo]
    t = (s - lap_s[lo]) / span if span > 0 else 0.0
    return (lap_x[lo] + t * (lap_x[hi] - lap_x[lo]),
            lap_y[lo] + t * (lap_y[hi] - lap_y[lo]))


def point_in_polygon(px: float, py: float, poly: list[tuple[float, float]]) -> bool:
    """Ray-casting point-in-polygon (centerline treated as a closed ring)."""
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > py) != (y2 > py):
            xint = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
            if px < xint:
                inside = not inside
    return inside


def bake(slug: str, ref_parquet: Path, model_path: Path, outline_path: Path) -> dict:
    outline = json.loads(outline_path.read_text(encoding="utf-8"))
    model = json.loads(model_path.read_text(encoding="utf-8"))
    table = pq.read_table(ref_parquet)
    lap_s = [float(v) for v in table.column("lap_distance_m").to_pylist()]
    lap_x = [float(v) for v in table.column("pos_x_m").to_pylist()]
    lap_y = [float(v) for v in table.column("pos_z_m").to_pylist()]
    lap_s, lap_x, lap_y = unwrap_lap(lap_s, lap_x, lap_y)

    centre = [(float(p["x"]), float(p["y"])) for p in outline["centerline"]]
    bbox = bbox_of(outline["centerline"])
    scale250 = map_scale(bbox, MAP_SIZE)
    gap_world = font_px(MAP_SIZE) * GAP_RATIO / scale250   # world units

    turns = []
    for index, corner in enumerate(model["corners"], start=1):
        apex = float(corner["apex_s_m"])
        x, y = interpolate_lap(lap_s, lap_x, lap_y, apex)
        # Local track direction from the lap, +-2 m around the apex.
        x0, y0 = interpolate_lap(lap_s, lap_x, lap_y, apex - 2.0)
        x1, y1 = interpolate_lap(lap_s, lap_x, lap_y, apex + 2.0)
        dx, dy = x1 - x0, y1 - y0
        norm = math.hypot(dx, dy) or 1.0
        tx, ty = dx / norm, dy / norm
        # Two candidate normals; keep the one whose probe leaves the polygon.
        cand = [(-ty, tx), (ty, -tx)]
        probe = 25.0
        nx, ny = cand[0]
        for cx, cy in cand:
            if not point_in_polygon(x + cx * probe, y + cy * probe, centre):
                nx, ny = cx, cy
                break
        name = corner.get("name")
        if name and name.strip().lower().replace(" ", "") in {
            f"turn{i}" for i in range(1, 40)
        }:
            name = None
        turns.append({
            "id": corner["id"],
            "number": index,
            "name": name,
            "short": SHORT_NAMES.get((slug, name), name),
            "apex_s_m": apex,
            "x": round(x, 3),
            "y": round(y, 3),
            "outward": [round(nx, 4), round(ny, 4)],
            "tangent": [round(tx, 4), round(ty, 4)],
            "label_x": round(x + nx * gap_world, 3),
            "label_y": round(y + ny * gap_world, 3),
        })

    return {
        "_spike": "slice-01 map-turn-names — not production data",
        "track_id": slug,
        "bbox": bbox,
        "map_size_ref": MAP_SIZE,
        "world_per_px_250": round(1.0 / scale250, 4),
        "gap_world": round(gap_world, 3),
        "gap_px_250": round(font_px(MAP_SIZE) * GAP_RATIO, 2),
        "font_px_250": font_px(MAP_SIZE),
        "turns": turns,
    }


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    slug = sys.argv[1]
    refs = sorted((ROOT / "product/data/reference-laps").glob(f"{slug}_*_time_*.parquet"))
    models = sorted((ROOT / "product/data/track-coaching").glob(f"{slug}_*.json"))
    outline_path = ROOT / "product/data/track-outlines" / f"{slug}.json"
    if not refs or not models:
        print(f"missing reference lap or model for {slug}", file=sys.stderr)
        return 1
    out = Path(__file__).parent / f"anchors-{slug}.json"
    data = bake(slug, refs[-1], models[0], outline_path)
    out.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"{out.name}: {len(data['turns'])} turns, gap {data['gap_px_250']}px "
          f"@250 ({data['gap_world']} world units), font {data['font_px_250']}px")
    for t in data["turns"]:
        print(f"  T{t['number']:<2} {str(t['name']):<26} apex={t['apex_s_m']:7.1f} "
              f"outward=({t['outward'][0]:+.2f},{t['outward'][1]:+.2f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
