"""Tests for aligning a TinyPedal recorded map to the simulator timing line.

Run through the Node wrapper (dev/scripts/test_tinypedal_map_alignment.js), which
prints the [PASS]/[FAIL] protocol lines.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dev" / "scripts"))

import align_tinypedal_map_start_line as tool  # noqa: E402

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if condition else 'FAIL'}] {name}{' — ' + detail if detail else ''}")
    if not condition:
        FAILURES.append(name)


# A 1000 m square recorded from 100 m *past* the start line, split into 40 points.
SIDE_POINTS = 10
SQUARE = ([(100.0 * i, 0.0) for i in range(SIDE_POINTS)] +
          [(1000.0, 100.0 * i) for i in range(SIDE_POINTS)] +
          [(1000.0 - 100.0 * i, 1000.0) for i in range(SIDE_POINTS)] +
          [(0.0, 1000.0 - 100.0 * i) for i in range(SIDE_POINTS)])


def svg(points, distances=None, desc="5,20") -> str:
    distances = distances or [i * 100.0 for i in range(len(points))]
    map_text = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    dist_text = " ".join(f"{d:.1f},0.0" for d in distances)
    return ('<?xml version="1.0" encoding="utf-8"?>\n<svg><title>T</title>\n'
            f'<desc>{desc}</desc>\n'
            f'<polyline id="map" points="{map_text}" />\n'
            f'<polyline id="dist" points="{dist_text}" />\n</svg>\n')


def outline(start_index: int = 10) -> dict:
    """Outline whose lap distance 0 is the recorded point `start_index`.

    TinyPedal records map y with the opposite sign to the simulator's pos_z.
    """
    ordered = SQUARE[start_index:] + SQUARE[:start_index]
    center = [{"x": x, "y": -y} for x, y in ordered]
    turns = [{"id": f"t{n}", "number": n, "name": f"turn {n}",
              "apex_s_m": 300.0 * n, "x": center[3 * n]["x"], "y": center[3 * n]["y"]}
             for n in (0, 1, 2, 3)]
    return {"track_name": "Square", "sim_track_name": "Square",
            "lap_length_m": 4000.0, "centerline": center, "turns": turns}


def main() -> int:
    text = svg(SQUARE)
    measured = tool.measure(text, outline())
    check("the offset is measured from the recorded distance axis",
          abs(measured["axis_offset_m"] - 1000.0) < 5 or abs(measured["axis_offset_m"] - 3000.0) < 5,
          f"{measured['axis_offset_m']} m")
    check("the rotation index points at the timing line", measured["shift"] == 10,
          f"shift {measured['shift']}")

    aligned, report = tool.align(text, outline(), tolerance_m=25.0)
    new_points = tool.parse_points(tool.MAP_RE.search(aligned)[2])
    new_dists = tool.parse_points(tool.DIST_RE.search(aligned)[2])
    check("rotation starts the map at the timing line",
          new_points[0] == SQUARE[10], f"{new_points[0]}")
    check("the recorded point set is preserved", sorted(new_points) == sorted(SQUARE))
    check("the distance axis is re-zeroed", new_dists[0][0] == 0.0)
    check("the distance axis stays monotonic",
          all(b >= a for a, b in zip(new_dists, new_dists[1:])))
    check("sector indices rotate with the points",
          "<desc>35,10</desc>" in aligned, aligned.split("<desc>")[1].split("</desc>")[0])
    check("anchors are verified before writing", report["worst_anchor_m"] < 25.0,
          f"{report['worst_anchor_m']} m")

    again = tool.measure(aligned, outline())
    check("re-measuring the aligned map finds no offset",
          again["axis_offset_m"] < 30.0, f"{again['axis_offset_m']} m")

    inconsistent = outline()
    inconsistent["turns"] = [
        dict(turn, apex_s_m=turn["apex_s_m"] + 500.0) for turn in inconsistent["turns"]
    ]
    try:
        tool.align(text, inconsistent, tolerance_m=25.0)
        refused = False
    except ValueError:
        refused = True
    check("an outline that disagrees with the map is refused", refused)

    real_map = tool.DEFAULT_TRACKMAP / "Paul Ricard - ELMS.svg"
    if real_map.exists():
        real = tool.measure(real_map.read_text(encoding="utf-8"),
                            tool.outline_for(tool.DEFAULT_OUTLINES, "Paul Ricard - ELMS"))
        check("the curated ELMS map now starts at the timing line",
              real["axis_offset_m"] < 30.0, f"{real['axis_offset_m']} m")
    else:
        print("  [SKIP] sibling TinyPedal map folder unavailable")

    print(f"\n{'RESULT: PASS' if not FAILURES else 'RESULT: FAIL (' + str(len(FAILURES)) + ')'}")
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())
