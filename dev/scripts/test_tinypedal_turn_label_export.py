#!/usr/bin/env python3
"""Tests for the TinyPedal turn-label exporter.

Run through the Node wrapper (dev/scripts/test_tinypedal_turn_label_export.js),
which prints the [PASS]/[FAIL] protocol lines.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dev" / "scripts"))

import export_turn_labels_for_tinypedal as exporter  # noqa: E402

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if condition else 'FAIL'}] {name}{' — ' + detail if detail else ''}")
    if not condition:
        FAILURES.append(name)


def outline(track_name: str, turn_distances: list[float]) -> dict:
    """Minimal outline: a 1000 m straight-ish square with turns on it."""
    centerline = [
        {"x": 0.0, "y": 0.0}, {"x": 250.0, "y": 0.0},
        {"x": 500.0, "y": 0.0}, {"x": 500.0, "y": 250.0},
        {"x": 500.0, "y": 500.0}, {"x": 0.0, "y": 500.0},
    ]
    turns = [
        {"id": str(i + 1), "number": i + 1, "name": f"Corner {i + 1}",
         "short_name": None, "apex_s_m": distance}
        for i, distance in enumerate(turn_distances)
    ]
    return {"track_name": track_name, "sim_track_name": track_name,
            "centerline": centerline, "turns": turns}


def main() -> int:
    print("\n-- centreline length --")
    length = exporter.centerline_length_m(outline("X", [])["centerline"])
    check("closed polyline length includes the closing segment",
          abs(length - 2000.0) < 1e-6, f"{length:.1f} m")

    print("\n-- fractions --")
    check("half way round is 0.5", abs(exporter.turn_fraction(1000, 2000) - 0.5) < 1e-9)
    check("a fraction never exceeds 1", exporter.turn_fraction(9999, 2000) == 1.0)
    check("a negative distance clamps to 0", exporter.turn_fraction(-5, 2000) == 0.0)

    print("\n-- payload --")
    data = exporter.build_payload(outline("Test Track", [100.0, 1500.0]), "Test Track")
    check("schema version", data["schema_version"] == exporter.SCHEMA_VERSION)
    check("track name is the TinyPedal name", data["track_name"] == "Test Track")
    check("lap length is exported", abs(data["lap_length_m"] - 2000.0) < 1e-6,
          f"{data['lap_length_m']}")
    check("every turn is exported", len(data["turns"]) == 2)
    check("fractions are relative to the lap",
          abs(data["turns"][0]["s_frac"] - 0.05) < 1e-6 and abs(data["turns"][1]["s_frac"] - 0.75) < 1e-6,
          f"{data['turns'][0]['s_frac']}, {data['turns'][1]['s_frac']}")
    check("names survive", data["turns"][0]["name"] == "Corner 1")

    print("\n-- name matching --")
    keys = {exporter.normalize_name("Autódromo José Carlos Pace"): "Autódromo José Carlos Pace"}
    check("accents and case are ignored",
          exporter.match_trackmap({"sim_track_name": "Autodromo Jose Carlos Pace"}, keys)
          == "Autódromo José Carlos Pace")
    check("an unknown track matches nothing",
          exporter.match_trackmap({"sim_track_name": "Nowhere"}, keys) is None)

    print("\n-- serialised file --")
    text = exporter.render(data)
    parsed = json.loads(text)
    check("output is valid JSON", parsed["track_name"] == "Test Track")
    check("one turn per line keeps diffs readable", text.count("\n    {") == 2)
    check("round trips unchanged", parsed["turns"] == data["turns"])

    print("\n-- real outlines against a temporary trackmap folder --")
    with tempfile.TemporaryDirectory() as folder:
        # The exporter is driven by our outlines, so the folder has to hold the
        # map names of real outlined tracks.
        (Path(folder) / "Silverstone International Circuit.svg").write_text("<svg/>", encoding="utf-8")
        (Path(folder) / "Circuit de Barcelona.svg").write_text("<svg/>", encoding="utf-8")
        code = exporter.main(["--trackmap", folder, "--out", folder])
        exported = sorted(path.name for path in Path(folder).glob("*.turns.json"))
        check("tracks with a map are exported", code == 0 and len(exported) == 2,
              ", ".join(exported))
        check("outlines without a map are skipped, not invented",
              not (Path(folder) / "Circuit de la Sarthe.turns.json").exists())
        shipped = json.loads((Path(folder) / "Silverstone International Circuit.turns.json")
                             .read_text(encoding="utf-8"))
        check("a real track exports every turn", len(shipped["turns"]) == 8,
              f"{len(shipped['turns'])} turns")
        check("fractions stay inside the lap",
              all(0 < turn["s_frac"] < 1 for turn in shipped["turns"]))
        check("fractions follow the driving direction",
              all(a["s_frac"] <= b["s_frac"]
                  for a, b in zip(shipped["turns"], shipped["turns"][1:])))
        check("re-running --check finds nothing stale",
              exporter.main(["--trackmap", folder, "--out", folder, "--check"]) == 0)
        (Path(folder) / "Silverstone International Circuit.turns.json").write_text(
            "{}", encoding="utf-8")
        check("a stale file fails --check",
              exporter.main(["--trackmap", folder, "--out", folder, "--check"]) == 1)
    # A folder with no track maps exits rather than silently writing nothing.
    try:
        exporter.main(["--trackmap", tempfile.mkdtemp()])
        empty_folder_error = False
    except SystemExit:
        empty_folder_error = True
    check("a folder with no track maps is an error", empty_folder_error)

    print(f"\n{'RESULT: PASS' if not FAILURES else 'RESULT: FAIL (' + str(len(FAILURES)) + ')'}")
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())
