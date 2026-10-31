#!/usr/bin/env python3
"""Export turn labels for the TinyPedal track map widget.

TinyPedal draws its map from `<trackmap>/<Track Name>.svg`, whose `map`
polyline is the car's recorded path and whose `dist` polyline pairs every point
with its **lap distance** in metres.  That makes lap distance the only anchor we
can share between the two code bases: our coordinates are LMU world coordinates,
TinyPedal's are its own recording of the same lap, and nothing but the distance
along the lap is common to both.

So this exporter writes, next to each TinyPedal track map, a `<Track Name>.turns.json`
holding each corner's **normalised distance** (`s_frac`, 0 at the start/finish
line, 1 at the end of the lap).  The widget interpolates that fraction into its
own `dist` polyline at runtime, which keeps working for any recording, any
`display_orientation`, and even if the two laps differ slightly in length.

Only tracks that have BOTH a curated turn list in our outlines and a TinyPedal
track map are exported; everything else is reported and skipped.

Usage:
    py dev/scripts/export_turn_labels_for_tinypedal.py            # write
    py dev/scripts/export_turn_labels_for_tinypedal.py --check    # verify only
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTLINE_DIR = ROOT / "product" / "data" / "track-outlines"
# Turn-label data ships inside the TinyPedal package, not in the user's track
# map folder (which its .gitignore excludes).
DEFAULT_OUT = ROOT.parent / "tinypedal" / "tinypedal" / "data" / "turn_labels"

SCHEMA_VERSION = 1


def normalize_name(name: str) -> str:
    """Name key that ignores accents, case and punctuation ("Autódromo" == "Autodromo")."""
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", ascii_name.lower())


def centerline_length_m(centerline: list[dict]) -> float:
    """Closed polyline length of the outline centreline, in metres."""
    total = 0.0
    for first, second in zip(centerline, centerline[1:]):
        total += math.dist((first["x"], first["y"]), (second["x"], second["y"]))
    total += math.dist(
        (centerline[-1]["x"], centerline[-1]["y"]),
        (centerline[0]["x"], centerline[0]["y"]),
    )
    return total


def turn_fraction(apex_s_m: float, lap_length_m: float) -> float:
    """Turn apex as a fraction of the lap, clamped into (0, 1)."""
    if lap_length_m <= 0:
        raise ValueError("lap length must be positive")
    return min(max(apex_s_m / lap_length_m, 0.0), 1.0)


def build_payload(outline: dict, tiny_track_name: str) -> dict:
    """TinyPedal turn-label payload for one outline."""
    lap_length_m = centerline_length_m(outline["centerline"])
    turns = []
    for turn in outline["turns"]:
        turns.append({
            "number": int(turn["number"]),
            "name": turn.get("name"),
            "short_name": turn.get("short_name"),
            "apex_s_m": round(float(turn["apex_s_m"]), 3),
            "s_frac": round(turn_fraction(float(turn["apex_s_m"]), lap_length_m), 6),
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "track_name": tiny_track_name,
        "lap_length_m": round(lap_length_m, 3),
        "note": (
            "s_frac = apex distance / lap length, 0 at the start/finish line. "
            "The TinyPedal widget interpolates it into its own recorded map so no "
            "coordinate system is shared between the two code bases."
        ),
        "turns": turns,
    }


def load_outlines() -> list[dict]:
    outlines = []
    for path in sorted(OUTLINE_DIR.glob("*.json")):
        outline = json.loads(path.read_text(encoding="utf-8"))
        if outline.get("turns"):
            outline["_path"] = path
            outlines.append(outline)
    return outlines


def match_trackmap(outline: dict, svg_by_key: dict[str, str]) -> str | None:
    """TinyPedal track map whose name matches this outline, if any."""
    for field in ("sim_track_name", "track_name"):
        name = outline.get(field)
        if name and normalize_name(name) in svg_by_key:
            return svg_by_key[normalize_name(name)]
    return None


def collect(trackmap_dir: Path, out_dir: Path) -> tuple[list[tuple[Path, dict]], list[tuple[str, str]]]:
    """(files to write, skipped reasons)."""
    svg_by_key = {normalize_name(path.stem): path.stem for path in trackmap_dir.glob("*.svg")}
    if not svg_by_key:
        raise SystemExit(f"no TinyPedal track maps found in {trackmap_dir}")

    writes: list[tuple[Path, dict]] = []
    skipped: list[tuple[str, str]] = []
    for outline in load_outlines():
        track_name = match_trackmap(outline, svg_by_key)
        if track_name is None:
            skipped.append((outline["track_name"], "no TinyPedal track map"))
            continue
        payload = build_payload(outline, track_name)
        writes.append((out_dir / f"{track_name}.turns.json", payload))
    return writes, skipped


def render(payload: dict) -> str:
    """Serialise, one turn per line so diffs stay readable."""
    head = {key: value for key, value in payload.items() if key != "turns"}
    lines = json.dumps(head, indent=2, ensure_ascii=False).rstrip()
    body = ",\n".join(
        "    " + json.dumps(turn, ensure_ascii=False) for turn in payload["turns"]
    )
    return f"{lines[:-1]},\n  \"turns\": [\n{body}\n  ]\n}}\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help=f"TinyPedal turn-label folder (default: {DEFAULT_OUT})")
    parser.add_argument("--trackmap", type=Path,
                        default=DEFAULT_OUT.parents[2] / "trackmap",
                        help="TinyPedal track map folder, used to match track names")
    parser.add_argument("--check", action="store_true",
                        help="verify the files on disk are current; write nothing")
    args = parser.parse_args(argv)

    writes, skipped = collect(args.trackmap, args.out)
    if not writes:
        print("nothing to export", file=sys.stderr)
        return 1
    args.out.mkdir(parents=True, exist_ok=True)

    stale = []
    for path, payload in writes:
        text = render(payload)
        if args.check:
            current = path.read_text(encoding="utf-8") if path.exists() else None
            if current != text:
                stale.append(path.name)
            continue
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path.name}  ({len(payload['turns'])} turns)")

    for name, reason in skipped:
        print(f"skipped {name}: {reason}")

    if args.check:
        if stale:
            print(f"STALE: {', '.join(stale)}", file=sys.stderr)
            return 1
        print(f"up to date: {len(writes)} turn-label files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
