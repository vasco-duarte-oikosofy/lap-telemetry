#!/usr/bin/env python3
"""Slice 12 — the coach speaks curated short corner names.

``short_name`` has always been in the coaching models (``"Variante della
Roggia 1"`` → ``"Roggia 1"``), but only the map code read it. The coach's
``Corner`` dropped it, so a driver heard the full official name after every
corner.

The naming rule is one property: ``Corner.display_name`` → ``short_name`` if
curated, else ``name``. These tests pin that rule and the two places it has to
reach the driver: the facts (``CornerLoss.corner_name``) and the corner-exit
event (``CornerExited.corner_name``).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "product" / "python"))

from lap_telemetry.coach.corner_exit_detector import CornerExitDetector
from lap_telemetry.coach.lap_comparator import compare_laps
from lap_telemetry.coach.track_model import (
    Corner,
    TrackCoachingModel,
    load_track_coaching_model,
)

MONZA_MODEL = (ROOT / "product" / "data" / "track-coaching"
               / "monza-curva-grande-circuit_dkr-engineering-4-elms25.json")
BARCELONA_MODEL = (ROOT / "product" / "data" / "track-coaching"
                   / "circuit-de-barcelona_dkr-engineering-4-elms25.json")
BARCELONA_CURRENT = ROOT / "dev" / "fixtures" / "coach" / "barcelona_lap15_current.parquet"
BARCELONA_REF = (ROOT / "product" / "data" / "reference-laps"
                 / "circuit-de-barcelona_dkr-engineering-4-elms25_time_01.36.456.parquet")


pass_count = 0
fail_count = 0


def ok(condition: bool, label: str) -> None:
    global pass_count, fail_count
    if condition:
        pass_count += 1
        print(f"  [PASS] {label}")
    else:
        fail_count += 1
        print(f"  [FAIL] {label}")


# ── 1. Loader surfaces short_name; display_name applies the rule ─────────────


def test_loader_reads_short_name() -> None:
    model = load_track_coaching_model(MONZA_MODEL)
    by_id = {c.id: c for c in model.corners}

    ok(by_id["t2"].short_name == "Roggia 1",
       f"t2 short_name = {by_id['t2'].short_name!r}, expected 'Roggia 1'")
    ok(by_id["t10"].short_name == "Parabolica",
       f"t10 short_name = {by_id['t10'].short_name!r}, expected 'Parabolica'")
    ok(by_id["t4"].short_name == "Lesmo 1",
       f"t4 preserves the numbered turn (short_name = {by_id['t4'].short_name!r})")

    ok(by_id["t2"].name == "Variante della Roggia 1",
       f"t2 keeps its official name for identity ({by_id['t2'].name!r})")


def test_display_name_prefers_short() -> None:
    model = load_track_coaching_model(MONZA_MODEL)
    by_id = {c.id: c for c in model.corners}

    expected = {
        "t1": "Curva Grande",
        "t2": "Roggia 1",
        "t3": "Roggia 2",
        "t4": "Lesmo 1",
        "t6": "Serraglio",
        "t9": "Ascari 3",
        "t10": "Parabolica",
    }
    for corner_id, want in expected.items():
        got = by_id[corner_id].display_name
        ok(got == want, f"{corner_id} display_name = {got!r}, expected {want!r}")


def test_display_name_falls_back_for_models_without_short_names() -> None:
    # Use an uncurated synthetic corner: the real corpus is now curated.
    from lap_telemetry.coach.track_model import validate_corner
    corner = validate_corner(dict(id="legacy", name="Turn 1", s_start_m=10,
                                  apex_s_m=20, s_end_m=30, apex_side="right"), 0)
    ok(corner.short_name is None, "legacy input without short_name still loads")
    ok(corner.display_name == corner.name,
       f"display_name falls back to name ({corner.display_name!r})")


def test_empty_short_name_is_ignored() -> None:
    model = TrackCoachingModel(
        schema_version="1", track_id="t", layout_id="t", lap_length_m=1000.0,
        corners=[Corner(id="c1", name="Turn 1", s_start_m=10.0, apex_s_m=20.0,
                        s_end_m=30.0, apex_side="right", short_name="")],
    )
    ok(model.corners[0].display_name == "Turn 1",
       f"empty short_name falls back to name ({model.corners[0].display_name!r})")


# ── 2. Facts spoken by the coach use the short name ──────────────────────────


def test_comparison_facts_use_short_name() -> None:
    if not BARCELONA_CURRENT.exists():
        print("  SKIP: comparison facts short name (fixture not found)")
        return

    model = load_track_coaching_model(BARCELONA_MODEL)
    # Curate a short name on every corner the way the Monza model does.
    for index, corner in enumerate(model.corners):
        corner.short_name = f"S{index + 1}"
    expected = {c.id: c.short_name for c in model.corners}
    long_names = {c.id: c.name for c in model.corners}

    facts = compare_laps(BARCELONA_CURRENT, BARCELONA_REF, model, top_n=60)
    all_facts = facts.top_losses + facts.top_gains
    ok(len(all_facts) > 0, f"comparison produced facts (got {len(all_facts)})")

    for fact in all_facts:
        ok(fact.corner_name == expected[fact.corner_id],
           f"{fact.corner_id} {fact.phase} corner_name = {fact.corner_name!r}, "
           f"expected short name {expected[fact.corner_id]!r}")

    used_short = [f for f in all_facts if f.corner_name != long_names[f.corner_id]]
    ok(len(used_short) == len(all_facts),
       f"every fact uses the curated short name (got {len(used_short)}/{len(all_facts)})")


# ── 3. Corner-exit events use the short name ──────────────────────────────────


def test_corner_exit_event_ues_short_name() -> None:
    model = TrackCoachingModel(
        schema_version="1", track_id="t", layout_id="t", lap_length_m=5000.0,
        corners=[Corner(id="c1", name="Variante della Roggia 2", s_start_m=100.0,
                        apex_s_m=150.0, s_end_m=200.0, apex_side="right",
                        short_name="Roggia 2")],
    )
    detector = CornerExitDetector(track_model=model)
    events: list = []
    detector.on_corner_exited = events.append
    detector.notify_lap_completed()

    for dist in (150, 199, 205):
        detector.feed(_frame(dist, dist * 0.05))

    ok(len(events) == 1, f"one corner exit emitted (got {len(events)})")
    if events:
        ok(events[0].corner_name == "Roggia 2",
           f"event corner_name = {events[0].corner_name!r}, expected 'Roggia 2'")
        ok(events[0].corner_id == "c1", "event keeps the canonical corner_id")


def _frame(distance_m: float, session_time_s: float):
    from types import SimpleNamespace
    return SimpleNamespace(
        lap_distance_m=float(distance_m), lap_number=1,
        session_time_s=float(session_time_s), track_name="Test", vehicle_name="Car",
    )


def main() -> int:
    print("═══ Coach short corner names ═══\n")

    test_loader_reads_short_name()
    test_display_name_prefers_short()
    test_display_name_falls_back_for_models_without_short_names()
    test_empty_short_name_is_ignored()
    test_comparison_facts_use_short_name()
    test_corner_exit_event_ues_short_name()

    total = pass_count + fail_count
    print(f"\n  {pass_count}/{total} assertions passed")
    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
