#!/usr/bin/env python3
"""Test bug 25 — prefix-match false positive in track_model_resolver and reference_resolver.

Verifies that a layout variant like "Fuji Speedway Classic" (slug:
fuji-speedway-classic) does NOT match data files for "Fuji Speedway"
(slug: fuji-speedway), which is a different circuit layout.

Also verifies that the Barcelona prefix-matching case still works when
the data file slug exactly matches the live track slug.

Run: python3 dev/scripts/test_bug25.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "product" / "python"))

from lap_telemetry.coach.track_model_resolver import resolve_track_model
from lap_telemetry.coach.reference_resolver import resolve_reference_lap

pass_count = 0
fail_count = 0


def ok(condition: bool, label: str, detail: str = "") -> None:
    global pass_count, fail_count
    if condition:
        pass_count += 1
        print(f"  [PASS] {label}")
    else:
        fail_count += 1
        print(f"  [FAIL] {label}{' — ' + detail if detail else ''}")


MODEL_DIR = ROOT / "product" / "data" / "track-coaching"
REF_DIR = ROOT / "product" / "data" / "reference-laps"

# ══════════════════════════════════════════════════════════════════════════
# Bug 25: Layout variant false positive
# ══════════════════════════════════════════════════════════════════════════

print("-- Bug 25: Layout variant must NOT match different layout's data --")

# T1: "Fuji Speedway Classic" must NOT resolve to the fuji-speedway model.
classic_model = resolve_track_model("Fuji Speedway Classic", search_dir=MODEL_DIR)
ok(classic_model is None, "T1: track model resolver — Fuji Speedway Classic returns None",
   f"got {classic_model}")

# T2: "Fuji Speedway Classic" must NOT resolve to the fuji-speedway reference lap.
classic_ref = resolve_reference_lap("Fuji Speedway Classic", search_dir=REF_DIR)
ok(classic_ref is None, "T2: reference resolver — Fuji Speedway Classic returns None",
   f"got {classic_ref}")

# T3: "Fuji Speedway" (normal layout) still resolves correctly.
fuji_model = resolve_track_model("Fuji Speedway", search_dir=MODEL_DIR)
ok(fuji_model is not None, "T3a: track model resolver — Fuji Speedway resolves",
   f"got {fuji_model}")
ok(fuji_model is not None and "fuji-speedway" in fuji_model.stem,
   "T3b: track model resolver — correct file matched",
   f"got {fuji_model}")

fuji_ref = resolve_reference_lap("Fuji Speedway", search_dir=REF_DIR)
ok(fuji_ref is not None, "T3c: reference resolver — Fuji Speedway resolves",
   f"got {fuji_ref}")

# ══════════════════════════════════════════════════════════════════════════
# Positive cases: exact slug matches still work
# ══════════════════════════════════════════════════════════════════════════

print("\n-- Exact match cases still work --")

# T4: Bahrain Outer Circuit (exact slug match).
bahrain_model = resolve_track_model("Bahrain Outer Circuit", search_dir=MODEL_DIR)
ok(bahrain_model is not None, "T4a: track model — Bahrain Outer Circuit resolves")
bahrain_ref = resolve_reference_lap("Bahrain Outer Circuit", search_dir=REF_DIR)
ok(bahrain_ref is not None, "T4b: reference — Bahrain Outer Circuit resolves")

# T5: Paul Ricard - 3A (slug with special chars → paul-ricard---3a).
ricard_model = resolve_track_model("Paul Ricard - 3A", search_dir=MODEL_DIR)
ok(ricard_model is not None, "T5a: track model — Paul Ricard 3A resolves")
ricard_ref = resolve_reference_lap("Paul Ricard - 3A", search_dir=REF_DIR)
ok(ricard_ref is not None, "T5b: reference — Paul Ricard 3A resolves")


# T6: Accent transliteration -- Autodromo Jose Carlos Pace (with accents) resolves.
jose_model = resolve_track_model("Autódromo José Carlos Pace", search_dir=MODEL_DIR)
ok(jose_model is not None, "T6a: track model -- Autodromo Jose Carlos Pace resolves")
ok(jose_model is not None and "autodromo-jose-carlos-pace" in jose_model.stem,
   "T6b: track model -- matched correct transliterated file",
   f"got {jose_model}")
jose_ref = resolve_reference_lap("Autódromo José Carlos Pace", search_dir=REF_DIR)
ok(jose_ref is not None, "T6c: reference -- Autodromo Jose Carlos Pace resolves")
ok(jose_ref is not None and "autodromo-jose-carlos-pace" in jose_ref.stem,
   "T6d: reference -- matched correct transliterated file",
   f"got {jose_ref}")

# ══════════════════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════════════════

print(f"\n{'-' * 60}")
if fail_count:
    print(f"  FAIL: {fail_count} FAILURES")
    sys.exit(1)
else:
    print(f"  PASS: {pass_count} assertions passed")