#!/usr/bin/env python3
"""Re-start a TinyPedal recorded track map at the simulator's start/finish line.

TinyPedal draws the start/finish line between the first two points of a map's
`map` polyline and anchors turn labels by arc length from that first point. A
recording that began a few dozen metres past the line (an older game build, a
pit-exit start, an interrupted recording) therefore draws its start line in the
wrong place AND shifts every turn label by the same offset, while the shape of
the lap is perfectly fine.

This tool rotates `map` and `dist` so index 0 is the point the outline says is
lap distance 0 (the simulator's timing line), re-zeroes the recorded distance
axis, and rotates the sector indices in `desc` with it. Nothing else changes:
the point set, the coordinates and the drawn shape stay byte-identical.

Usage:
    py dev/scripts/align_tinypedal_map_start_line.py --track "Paul Ricard - ELMS" --check
    py dev/scripts/align_tinypedal_map_start_line.py --track "Paul Ricard - ELMS"

Verification (refuses to write on any failure): the rotated point set equals the
original, the re-zeroed distance axis is monotonic, and every turn anchor of the
outline lands within `--tolerance-m` of its recorded position.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRACKMAP = ROOT.parent / "tinypedal" / "trackmap"
DEFAULT_OUTLINES = ROOT / "product" / "data" / "track-outlines"
MAP_RE = re.compile(r'(<polyline id="map"[^>]*points=")([^"]*)(")')
DIST_RE = re.compile(r'(<polyline id="dist"[^>]*points=")([^"]*)(")')
DESC_RE = re.compile(r"<desc>\s*([0-9,\s]*?)\s*</desc>")


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def parse_points(text: str) -> list[tuple[float, float]]:
    return [tuple(float(v) for v in pair.split(",")) for pair in text.split()]


def format_points(points: list[tuple[float, float]]) -> str:
    return " ".join(f"{x:.4f},{y:.4f}" for x, y in points)


def outline_for(outlines_dir: Path, track_name: str) -> dict:
    for path in sorted(outlines_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for field in ("sim_track_name", "track_name"):
            if data.get(field) and normalize_name(data[field]) == normalize_name(track_name):
                return data
    raise SystemExit(f"no outline found for {track_name!r}")


def start_index(map_points, outline) -> int:
    """Index of the recorded point closest to the outline's lap-distance 0.

    TinyPedal records map y with the opposite sign to the simulator's pos_z.
    """
    start = outline["centerline"][0]
    best, best_index = float("inf"), 0
    for index, (x, y) in enumerate(map_points):
        distance = math.hypot(x - start["x"], y + start["y"])
        if distance < best:
            best, best_index = distance, index
    return best_index


def rotate_sector_indices(desc: str | None, count: int, shift: int) -> str | None:
    if desc is None:
        return None
    indices = [int(part) for part in desc.split(",")]
    return ",".join(str((index - shift) % count) for index in indices)


def lap_length(outline: dict) -> float:
    """Same axis rule as the turn-label exporter: explicit sim axis, else geometry."""
    if "lap_length_m" in outline:
        return float(outline["lap_length_m"])
    points = [(p["x"], p["y"]) for p in outline["centerline"]] + [
        (outline["centerline"][0]["x"], outline["centerline"][0]["y"])]
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def read_polylines(svg: str) -> tuple[re.Match, re.Match, list, list]:
    map_match, dist_match = MAP_RE.search(svg), DIST_RE.search(svg)
    if not map_match or not dist_match:
        raise ValueError("map has no `map`/`dist` polylines")
    map_points = parse_points(map_match[2])
    dist_points = parse_points(dist_match[2])
    if len(map_points) != len(dist_points) or len(map_points) < 10:
        raise ValueError("map and dist polylines disagree in length")
    return map_match, dist_match, map_points, dist_points


def measure(svg: str, outline: dict) -> dict:
    """How far this recording's start sits from the simulator's timing line."""
    _, _, map_points, dist_points = read_polylines(svg)
    shift = start_index(map_points, outline)
    distances = [pair[0] for pair in dist_points]
    recorded_length = max(distances)
    along = (distances[shift] - distances[0]) % recorded_length
    return {
        "shift": shift,
        "points": len(map_points),
        "axis_offset_m": round(min(along, recorded_length - along), 2),
        "start_offset_m": round(math.dist(map_points[shift], (
            outline["centerline"][0]["x"], -outline["centerline"][0]["y"])), 2),
        "point_spacing_m": round(recorded_length / len(map_points), 2),
    }


def align(svg: str, outline: dict, tolerance_m: float) -> tuple[str, dict]:
    """Return (new svg text, report). Raises ValueError when verification fails."""
    report = measure(svg, outline)
    map_match, dist_match, map_points, dist_points = read_polylines(svg)
    count, shift = report["points"], report["shift"]
    rotated = map_points[shift:] + map_points[:shift]

    distances = [pair[0] for pair in dist_points]
    recorded_length = max(distances)
    base = distances[shift]
    base = distances[shift]
    distances = distances[shift:] + distances[:shift]
    elevations = [pair[1] for pair in dist_points]
    elevations = elevations[shift:] + elevations[:shift]
    rezeroed = [round((value - base) % recorded_length, 4) for value in distances]
    if any(b < a - 1e-6 for a, b in zip(rezeroed, rezeroed[1:])):
        raise ValueError("re-zeroed distance axis is not monotonic")

    # Verify the resulting anchors before writing anything.
    lengths = [0.0]
    closed = rotated + [rotated[0]]
    for first, second in zip(closed, closed[1:]):
        lengths.append(lengths[-1] + math.dist(first, second))
    worst = 0.0
    axis = lap_length(outline)
    for turn in outline["turns"]:
        target = lengths[-1] * (turn["apex_s_m"] / axis)
        index = max(0, min(len(lengths) - 2, next(
            i for i in range(len(lengths) - 1) if lengths[i + 1] >= target)))
        span = lengths[index + 1] - lengths[index]
        ratio = 0.0 if span <= 0 else (target - lengths[index]) / span
        anchor = (rotated[index][0] + (rotated[index + 1][0] - rotated[index][0]) * ratio,
                  rotated[index][1] + (rotated[index + 1][1] - rotated[index][1]) * ratio)
        worst = max(worst, math.dist(anchor, (turn["x"], -turn["y"])))
    report["worst_anchor_m"] = round(worst, 2)
    if worst > tolerance_m:
        raise ValueError(f"turn anchors would move {worst:.1f} m (> {tolerance_m} m)")

    new_map = format_points(rotated)
    new_dist = format_points(list(zip(rezeroed, elevations)))
    text = svg[:map_match.start(2)] + new_map + svg[map_match.end(2):]
    text = DIST_RE.sub(lambda m: m.group(1) + new_dist + m.group(3), text, count=1)
    desc = DESC_RE.search(text)
    if desc:
        rotated_desc = rotate_sector_indices(desc[1], count, shift)
        text = text[:desc.start(1)] + rotated_desc + text[desc.end(1):]
        report["sector_indices"] = rotated_desc
    if sorted(rotated) != sorted(map_points):
        raise ValueError("rotation changed the recorded point set")
    return text, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--track", required=True, help="TinyPedal track map name")
    parser.add_argument("--trackmap", type=Path, default=DEFAULT_TRACKMAP)
    parser.add_argument("--outlines", type=Path, default=DEFAULT_OUTLINES)
    parser.add_argument("--tolerance-m", type=float, default=25.0)
    parser.add_argument("--min-offset-m", type=float, default=30.0,
                        help="below this the map already starts at the timing line "
                             "(default 30 m = a few recorded point spacings)")
    parser.add_argument("--check", action="store_true", help="verify only, write nothing")
    args = parser.parse_args(argv)
    path = args.trackmap / f"{args.track}.svg"
    if not path.exists():
        raise SystemExit(f"no track map at {path}")
    outline = outline_for(args.outlines, args.track)
    original = path.read_text(encoding="utf-8")
    measured = measure(original, outline)
    if measured["axis_offset_m"] < args.min_offset_m:
        print(f"{args.track}: already starts at the timing line "
              f"(axis {measured['axis_offset_m']:.1f} m, position "
              f"{measured['start_offset_m']:.1f} m) - nothing to do")
        return 0
    try:
        aligned, report = align(original, outline, args.tolerance_m)
    except ValueError as error:
        print(f"FAIL: {args.track}: {error}", file=sys.stderr)
        return 2
    print(f"{args.track}: rotating {report['points']} points by {report['shift']} "
          f"(recording began {report['axis_offset_m']:.1f} m past the timing line); "
          f"worst anchor {report['worst_anchor_m']:.1f} m")
    if args.check:
        print(f"STALE: {path.name} is not aligned with the simulator timing line",
              file=sys.stderr)
        return 1
    path.write_text(aligned, encoding="utf-8")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
