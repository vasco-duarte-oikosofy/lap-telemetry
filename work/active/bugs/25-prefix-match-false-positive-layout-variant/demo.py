#!/usr/bin/env python3
"""Demo for bug 25 — verify the right track (or no track) is recognized.

Usage:
    python work/active/bugs/25-prefix-match-false-positive-layout-variant/demo.py sessions/session_20260606T131054Z_fuji-speedway-classic_lmu_practice.parquet
    python work/active/bugs/25-prefix-match-false-positive-layout-variant/demo.py sessions/session_20260603T164410Z_fuji-speedway_lmu_practice.parquet

Reads the session metadata (.json sidecar next to the .parquet) to get the
track name, then shows what the resolvers find for that track.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "product" / "python"))

from lap_telemetry.coach.track_model_resolver import resolve_track_model, _track_slug
from lap_telemetry.coach.reference_resolver import resolve_reference_lap

MODEL_DIR = ROOT / "product" / "data" / "track-coaching"
REF_DIR = ROOT / "product" / "data" / "reference-laps"


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python demo.py <session.parquet-or.json>")
        print()
        print("Examples:")
        print("  python demo.py sessions/session_20260606T131054Z_fuji-speedway-classic_lmu_practice.parquet")
        print("  python demo.py sessions/session_20260603T164410Z_fuji-speedway_lmu_practice.parquet")
        sys.exit(1)

    session_path = Path(sys.argv[1])

    # Find the .json sidecar
    if session_path.suffix == ".json":
        json_path = session_path
    else:
        # Swap .parquet (or .partN.parquet) for .json
        stem = session_path.name.split(".part")[0] if ".part" in session_path.name else session_path.stem
        json_path = session_path.parent / (stem + ".json")

    if not json_path.exists():
        print(f"No session metadata found at {json_path}")
        sys.exit(1)

    meta = json.loads(json_path.read_text(encoding="utf-8"))
    track_name = meta.get("track", "")
    vehicle_name = meta.get("vehicle_name", "")
    slug = _track_slug(track_name)

    print(f"Session file:  {session_path.name}")
    print(f"LMU track:     {track_name}")
    print(f"Vehicle:       {vehicle_name}")
    print(f"Track slug:    {slug}")
    print()

    model = resolve_track_model(track_name, search_dir=MODEL_DIR)
    ref = resolve_reference_lap(track_name, search_dir=REF_DIR)

    model_label = model.name if model else "None"
    ref_label = ref.name if ref else "None"

    print(f"Track model:   {model_label}")
    print(f"Reference lap: {ref_label}")
    print()

    if model is not None and ref is not None:
        # Check the model's own track_id matches the live slug
        from lap_telemetry.coach.track_model import load_track_coaching_model
        try:
            m = load_track_coaching_model(model)
            layout_match = "YES" if m.track_id == slug else "NO (different layout!)"
            print(f"Model track_id:  {m.track_id}")
            print(f"Layout match:    {layout_match}")
            print(f"Lap length:      {m.lap_length_m:.1f} m")
            print(f"Corners:         {len(m.corners)}")
        except Exception as exc:
            print(f"Model load error: {exc}")

        print()
        print(f"Coaching would FIRE using this data.")

    elif model is None and ref is None:
        print(f"Coaching correctly SUPPRESSED -- no data for this layout.")
    else:
        missing = "track model" if model is None else "reference lap"
        print(f"Coaching SUPPRESSED -- missing {missing} for this layout.")


if __name__ == "__main__":
    main()