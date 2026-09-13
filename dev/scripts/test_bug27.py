#!/usr/bin/env python3
"""Test bug 27 — car-blind coaching resolution.

Verifies that the live coach resolves the reference lap and coaching model
for the **correct car**, using product/data/vehicle_catalog.json to group
liveries of the same car model (e.g. all Ferrari 296 GT3 entries). Also
verifies the coaching model is loaded once per session (cached), not re-parsed
every lap.

Run: python dev/scripts/test_bug27.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "product" / "python"))

from lap_telemetry.coach.reference_resolver import resolve_reference_lap
from lap_telemetry.coach.track_model_resolver import resolve_track_model
from lap_telemetry.coach import car_catalog
from lap_telemetry.coach.live_fact_generator import LiveFactGenerator

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
TRACK = "Lusail International Circuit"

# == Car catalog canonicalization ============================================

print("-- car_catalog: canonical car slug from vehicle name --")

ok(car_catalog.canonical_car_slug("Vista AF Corse 2026 #54:WEC") == "ferrari-296-gt3",
   "T1: 'Vista AF Corse 2026 #54:WEC' -> ferrari-296-gt3",
   f"got {car_catalog.canonical_car_slug('Vista AF Corse 2026 #54:WEC')!r}")
ok(car_catalog.canonical_car_slug("Vista AF Corsa 2026 #54:WEC") == "ferrari-296-gt3",
   "T2: 'Vista AF Corsa 2026 #54:WEC' (alt spelling) -> ferrari-296-gt3")
ok(car_catalog.canonical_car_slug("GR Racing 2025 #86:ELMS") == "ferrari-296-gt3",
   "T3: 'GR Racing 2025 #86:ELMS' (different livery) -> ferrari-296-gt3")
ok(car_catalog.canonical_car_slug("DKR Engineering #4:ELMS25") == "ginetta-lmp3",
   "T4: 'DKR Engineering #4:ELMS25' -> ginetta-lmp3")
ok(car_catalog.canonical_car_slug("Nonexistent Car #99:X") is None,
   "T5: unknown vehicle -> None")

ok(car_catalog.car_id_canonical_slug("vista-af-corse-2026-54-wec") == "ferrari-296-gt3",
   "T6: car-id 'vista-af-corse-2026-54-wec' -> ferrari-296-gt3",
   f"got {car_catalog.car_id_canonical_slug('vista-af-corse-2026-54-wec')!r}")
ok(car_catalog.car_id_canonical_slug("dkr-engineering-4-elms25") == "ginetta-lmp3",
   "T7: car-id 'dkr-engineering-4-elms25' -> ginetta-lmp3")
ok(car_catalog.car_id_canonical_slug("some-unknown-car-id") is None,
   "T8: unknown car-id -> None")

# == Reference resolver — car-aware (the core bug) ===========================

print("\n-- reference_resolver: picks the right car for Lusail --")

legacy = resolve_reference_lap(TRACK, search_dir=REF_DIR)
ok(legacy is not None and "dkr-engineering" in legacy.stem,
   "T9 (legacy, no vehicle): Lusail -> fastest (LMP3) — backward compat",
   f"got {legacy}")

ferrari_ref = resolve_reference_lap(TRACK, search_dir=REF_DIR,
                                    vehicle_name="Vista AF Corse 2026 #54:WEC")
ok(ferrari_ref is not None, "T10a: Ferrari vehicle resolves to a reference")
ok(ferrari_ref is not None and "vista-af-corse" in ferrari_ref.stem,
   "T10b: Ferrari reference is the vista-af-corse file (not the LMP3)",
   f"got {ferrari_ref}")
ok(ferrari_ref is not None and "dkr-engineering" not in ferrari_ref.stem,
   "T10c: Ferrari reference is NOT the DKR LMP3 file",
   f"got {ferrari_ref}")

gr_ref = resolve_reference_lap(TRACK, search_dir=REF_DIR,
                               vehicle_name="GR Racing 2025 #86:ELMS")
ok(gr_ref is not None and "vista-af-corse" in gr_ref.stem,
   "T11: different Ferrari livery (GR Racing) -> same Ferrari reference",
   f"got {gr_ref}")

lmp3_ref = resolve_reference_lap(TRACK, search_dir=REF_DIR,
                                 vehicle_name="DKR Engineering #4:ELMS25")
ok(lmp3_ref is not None and "dkr-engineering" in lmp3_ref.stem,
   "T12: LMP3 vehicle -> LMP3 reference",
   f"got {lmp3_ref}")

porsche_ref = resolve_reference_lap(TRACK, search_dir=REF_DIR,
                                    vehicle_name="Some Porsche #7:WEC")
ok(porsche_ref is None,
   "T13: vehicle with no matching reference for track -> None",
   f"got {porsche_ref}")

# == Track model resolver — car-aware ========================================

print("\n-- track_model_resolver: picks the right car for Lusail --")

ferrari_model = resolve_track_model(TRACK, search_dir=MODEL_DIR,
                                    vehicle_name="Vista AF Corse 2026 #54:WEC")
ok(ferrari_model is not None and "vista-af-corse" in ferrari_model.stem,
   "T14: Ferrari vehicle -> Ferrari coaching model (not LMP3)",
   f"got {ferrari_model}")
ok(ferrari_model is not None and "dkr-engineering" not in ferrari_model.stem,
   "T15: Ferrari model is NOT the DKR LMP3 model",
   f"got {ferrari_model}")

lmp3_model = resolve_track_model(TRACK, search_dir=MODEL_DIR,
                                 vehicle_name="DKR Engineering #4:ELMS25")
ok(lmp3_model is not None and "dkr-engineering" in lmp3_model.stem,
   "T16: LMP3 vehicle -> LMP3 coaching model",
   f"got {lmp3_model}")

# == Per-session model caching (load once) ===================================

print("\n-- LiveFactGenerator: coaching model loaded once per session --")

import lap_telemetry.coach.track_model as tm_mod
import lap_telemetry.coach.lap_comparator as cmp_mod
from lap_telemetry.coach.facts import LapComparisonFacts

calls = {"load": 0}
real_load = tm_mod.load_track_coaching_model


def counting_load(path):
    calls["load"] += 1
    return real_load(path)


def stub_compare(current_lap, ref_path, model, lap_number=None):
    return LapComparisonFacts(
        type="lap_coaching_summary", track_id="circuit-de-barcelona",
        lap_number=lap_number or 0, lap_time_delta_s=0.0,
        top_losses=[], top_gains=[],
        constraints={"max_words": 35, "style": "calm_concise_engineer"},
    )


cur_lap = ROOT / "dev" / "fixtures" / "coach" / "barcelona_lap15_current.parquet"
gen = LiveFactGenerator(utterance_fn=None)

orig_load = tm_mod.load_track_coaching_model
orig_compare = cmp_mod.compare_laps
tm_mod.load_track_coaching_model = counting_load
cmp_mod.compare_laps = stub_compare
try:
    gen.generate_from_parquet(
        parquet_path=cur_lap, lap_number=15,
        track_name="Circuit de Barcelona",
        vehicle_name="DKR Engineering #4:ELMS25",
        top=3,
    )
    after_first = calls["load"]
    gen.generate_from_parquet(
        parquet_path=cur_lap, lap_number=15,
        track_name="Circuit de Barcelona",
        vehicle_name="DKR Engineering #4:ELMS25",
        top=3,
    )
    after_second = calls["load"]
finally:
    tm_mod.load_track_coaching_model = orig_load
    cmp_mod.compare_laps = orig_compare

ok(after_first == 1, "T17: model loaded once on first lap", f"load count after first = {after_first}")
ok(after_second == 1, "T18: model NOT reloaded on second lap (cached)", f"load count after second = {after_second}")

# == Summary =================================================================

print(f"\n{'-' * 60}")
if fail_count:
    print(f"  FAIL: {fail_count} FAILURES")
    sys.exit(1)
else:
    print(f"  PASS: {pass_count} assertions passed")