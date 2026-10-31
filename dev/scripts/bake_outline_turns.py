#!/usr/bin/env python3
"""Bake the `turns` block into track outline JSON files.

Turn names are a property of the layout, not of the car, so they live in the
outline (`docs/specs/MAP_TURN_NAMES.md`). This tool reads the curated coaching
model(s) for a track, converts each corner's `apex_s_m` into a map anchor in sim
world coordinates (plus outward/tangent unit vectors), and writes the `turns`
block into `product/data/track-outlines/<slug>.json`. It touches nothing else in
the file.

Usage:
    python3 dev/scripts/bake_outline_turns.py silverstone-international-circuit
    python3 dev/scripts/bake_outline_turns.py --all
    python3 dev/scripts/bake_outline_turns.py --all --check   # verify only

Selection rule: only tracks whose best coaching model has at least one curated
corner name are baked. A model whose corner names are all placeholders
("turn 1", "turn 2", ...) is over-segmented or uncurated, and baking it would
put a wrongly numbered `T1..Tn` on the map. `--all` reports those as skipped.

When several models exist for one track (one per car), the one with the most
curated names wins; ties go to the model with more corners, then to the
alphabetically first file so the choice is deterministic. Disagreement between
the top two is reported.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import pyarrow.parquet as pq
import pyarrow.compute as pc

ROOT = Path(__file__).resolve().parents[2]
OUTLINES_DIR = ROOT / "product" / "data" / "track-outlines"
MODELS_DIR = ROOT / "product" / "data" / "track-coaching"
REFS_DIR = ROOT / "product" / "data" / "reference-laps"

PLACEHOLDER_NAME = re.compile(r"^turn\s*\d+$", re.IGNORECASE)
PROBE_M = 25.0          # distance used to decide which normal points outward
TANGENT_WINDOW_M = 2.0  # half-window for the along-track direction


# ── lap geometry ──────────────────────────────────────────────────────────────


def unwrap_lap(s: list[float], x: list[float], y: list[float]):
    """Roll a lap so `s` increases monotonically.

    `lap_distance_m` in an exported reference parquet starts just before the
    start/finish line and wraps to 0 inside the file, so a binary search on the
    raw column silently returns a bogus bracket.
    """
    for i in range(1, len(s)):
        if s[i] < s[i - 1]:
            return s[i:] + s[:i], x[i:] + x[:i], y[i:] + y[:i]
    return s, x, y


def interpolate(s: list[float], vals: list[float], target: float) -> float:
    if target <= s[0]:
        return vals[0]
    if target >= s[-1]:
        return vals[-1]
    lo, hi = 0, len(s) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if s[mid] <= target:
            lo = mid
        else:
            hi = mid
    span = s[hi] - s[lo]
    t = (target - s[lo]) / span if span else 0.0
    return vals[lo] + t * (vals[hi] - vals[lo])


def point_in_polygon(px: float, py: float, poly: list[tuple[float, float]]) -> bool:
    """Ray casting against a closed ring (the outline centreline)."""
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > py) != (y2 > py):
            x_int = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
            if px < x_int:
                inside = not inside
    return inside


def load_lap(ref_path: Path):
    table = pq.read_table(ref_path)
    s = [float(v) for v in table.column("lap_distance_m").to_pylist()]
    x = [float(v) for v in table.column("pos_x_m").to_pylist()]
    y = [float(v) for v in table.column("pos_z_m").to_pylist()]
    return unwrap_lap(s, x, y)


# ── model discovery ───────────────────────────────────────────────────────────


def model_files(slug: str) -> list[Path]:
    """Coaching models for a track: `<slug>_<car>.json` plus legacy `<slug>.json`."""
    found = [p for p in MODELS_DIR.glob(f"{slug}_*.json") if not p.name.endswith(".diagnostics.txt")]
    legacy = MODELS_DIR / f"{slug}.json"
    if legacy.exists():
        found.append(legacy)
    return sorted(set(found))


def car_id_of(model_path: Path, slug: str) -> str | None:
    """`<slug>_<car>.json` -> `<car>`; legacy `<slug>.json` -> None."""
    stem = model_path.stem
    if stem == slug:
        return None
    if stem.startswith(slug + "_"):
        return stem[len(slug) + 1:]
    return None


def pick_reference(slug: str, car_id: str | None) -> Path | None:
    candidates = sorted(REFS_DIR.glob(f"{slug}_*_time_*.parquet"))
    if car_id:
        exact = [p for p in candidates if p.name.startswith(f"{slug}_{car_id}_time_")]
        if exact:
            return exact[-1]
    return candidates[-1] if candidates else None


def describe_model(model_path: Path, slug: str) -> dict:
    model = json.loads(model_path.read_text(encoding="utf-8"))
    corners = model.get("corners", [])
    named = [c for c in corners if c.get("name") and not PLACEHOLDER_NAME.match(str(c["name"]))]
    return {
        "path": model_path,
        "car_id": car_id_of(model_path, slug),
        "corners": corners,
        "named": len(named),
    }


def choose_model(slug: str) -> tuple[dict | None, str]:
    """Pick the best model for a track. Returns (model_info | None, reason)."""
    described = [describe_model(p, slug) for p in model_files(slug)]
    if not described:
        return None, "no coaching model"
    ranked = sorted(described, key=lambda d: (-d["named"], -len(d["corners"]), str(d["path"])))
    best = ranked[0]
    if best["named"] == 0:
        return None, f"model not curated ({len(best['corners'])} placeholder corners)"
    if len(ranked) > 1 and ranked[1]["named"] == best["named"] and \
            len(ranked[1]["corners"]) == len(best["corners"]):
        a = [c.get("name") for c in best["corners"]]
        b = [c.get("name") for c in ranked[1]["corners"]]
        if a != b:
            print(f"  ! models disagree for {slug}: {best['path'].name} vs {ranked[1]['path'].name}",
                  file=sys.stderr)
    return best, f"{best['path'].name} ({best['named']}/{len(best['corners'])} named)"


# ── baking ────────────────────────────────────────────────────────────────────


def bake_turns(slug: str, outline: dict, model_info: dict, ref_path: Path) -> list[dict]:
    centre = [(float(p["x"]), float(p["y"])) for p in outline["centerline"]]
    lap_s, lap_x, lap_y = load_lap(ref_path)

    turns = []
    for number, corner in enumerate(model_info["corners"], start=1):
        apex = float(corner["apex_s_m"])
        x = interpolate(lap_s, lap_x, apex)
        y = interpolate(lap_s, lap_y, apex)
        x0 = interpolate(lap_s, lap_x, apex - TANGENT_WINDOW_M)
        y0 = interpolate(lap_s, lap_y, apex - TANGENT_WINDOW_M)
        x1 = interpolate(lap_s, lap_x, apex + TANGENT_WINDOW_M)
        y1 = interpolate(lap_s, lap_y, apex + TANGENT_WINDOW_M)
        dx, dy = x1 - x0, y1 - y0
        norm = math.hypot(dx, dy) or 1.0
        tx, ty = dx / norm, dy / norm
        nx, ny = -ty, tx
        for cx, cy in ((-ty, tx), (ty, -tx)):
            if not point_in_polygon(x + cx * PROBE_M, y + cy * PROBE_M, centre):
                nx, ny = cx, cy
                break

        raw_name = corner.get("name")
        name = None if (not raw_name or PLACEHOLDER_NAME.match(str(raw_name))) else str(raw_name)
        short = corner.get("short_name")
        turns.append({
            "id": str(corner.get("id", number)),
            "number": number,
            "name": name,
            "short_name": str(short) if short else None,
            "apex_s_m": round(apex, 1),
            "x": round(x, 3),
            "y": round(y, 3),
            "outward": [round(nx, 4), round(ny, 4)],
            "tangent": [round(tx, 4), round(ty, 4)],
        })
    return turns


def write_turns(outline_path: Path, turns: list[dict]) -> None:
    """Rewrite only the `turns` key, keeping the rest of the file byte-identical."""
    data = json.loads(outline_path.read_text(encoding="utf-8"))
    data["turns"] = turns
    outline_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def process(slug: str, check_only: bool) -> str:
    outline_path = OUTLINES_DIR / f"{slug}.json"
    if not outline_path.exists():
        return f"skip  {slug}: no outline"
    outline = json.loads(outline_path.read_text(encoding="utf-8"))
    if "centerline" not in outline:
        return f"skip  {slug}: not a track outline"

    model_info, reason = choose_model(slug)
    if model_info is None:
        return f"skip  {slug}: {reason}"
    ref_path = pick_reference(slug, model_info["car_id"])
    if ref_path is None:
        return f"skip  {slug}: no reference lap ({reason})"

    turns = bake_turns(slug, outline, model_info, ref_path)
    existing = outline.get("turns")
    changed = existing != turns

    if check_only:
        state = "ok   " if (not changed and existing) else "STALE"
        return f"{state} {slug}: {len(turns)} turns ({reason})"

    if changed:
        write_turns(outline_path, turns)
    return f"{'baked' if changed else 'same '} {slug}: {len(turns)} turns ({reason})"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("slugs", nargs="*", help="outline slugs (default: all outlines)")
    parser.add_argument("--all", action="store_true", help="bake every outline that has a curated model")
    parser.add_argument("--check", action="store_true", help="verify only, write nothing")
    args = parser.parse_args(argv)

    slugs = args.slugs
    if args.all or not slugs:
        slugs = sorted(p.stem for p in OUTLINES_DIR.glob("*.json"))

    baked = skipped = 0
    for slug in slugs:
        line = process(slug, args.check)
        print(line)
        if line.startswith("baked") or line.startswith("ok") or line.startswith("same"):
            baked += 1
        else:
            skipped += 1
    print(f"\n{baked} track(s) with turns, {skipped} skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
