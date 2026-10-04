#!/usr/bin/env python3
"""Tests for the guarded coaching-model updater's corner merge.

`update_reference_and_coaching_model.py` refreshes corner geometry from a new
faster reference lap. It must never lose curated content: names, IDs, apex
sides, and especially `target_throttle_pct` (which marks flat-out corners such
as Road Atlanta's T4 Esses) must survive an update. Flat corners produce no
braking event, so the detector usually leaves them unmatched; they are kept
via --allow-unmatched and must not be dropped or stripped.

Protocol: prints [PASS]/[FAIL] lines and exits non-zero on any failure.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dev" / "scripts"))

from update_reference_and_coaching_model import refresh_corners  # noqa: E402

_passed = 0
_failed = 0


def check(condition: bool, name: str, detail: str = "") -> None:
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  [PASS] {name}{' — ' + detail if detail else ''}")
    else:
        _failed += 1
        print(f"  [FAIL] {name}{' — ' + detail if detail else ''}")


def flat_corner() -> dict:
    return {
        "id": "t4",
        "name": "Turn 4 (The Esses)",
        "s_start_m": 880.0,
        "apex_s_m": 1120.0,
        "s_end_m": 1300.0,
        "apex_side": "right",
        "apex_side_source": "manual",
        "target_throttle_pct": 100,
    }


def test_matched_corner_keeps_curated_fields_and_takes_new_geometry() -> None:
    old = flat_corner()
    match = SimpleNamespace(s_start_m=875.0, apex_m=1115, s_end_m=1298.0)
    out = refresh_corners([(old, match)])[0]

    check(out["target_throttle_pct"] == 100, "matched flat corner keeps target_throttle_pct")
    check(out["id"] == "t4" and out["name"] == old["name"], "matched corner keeps id + name")
    check(out["apex_side"] == "right" and out["apex_side_source"] == "manual",
          "matched corner keeps apex side metadata")
    check(out["s_start_m"] == 875.0 and out["apex_s_m"] == 1115.0 and out["s_end_m"] == 1298.0,
          "matched corner takes the new lap geometry",
          f"{out['s_start_m']}/{out['apex_s_m']}/{out['s_end_m']}")


def test_unmatched_corner_is_kept_verbatim() -> None:
    old = flat_corner()
    out = refresh_corners([(old, None)])[0]
    check(out == old, "unmatched corner (--allow-unmatched) kept verbatim")
    check(out is not old, "unmatched corner is a copy, not the same object")


def test_inputs_are_not_mutated() -> None:
    old = flat_corner()
    before = dict(old)
    refresh_corners([(old, SimpleNamespace(s_start_m=1.0, apex_m=2, s_end_m=3.0))])
    check(old == before, "existing corner dict is never mutated in place")


def test_mixed_pairs_preserve_order() -> None:
    a = {"id": "t1", "name": "Turn 1", "s_start_m": 1.0, "apex_s_m": 2.0, "s_end_m": 3.0,
         "apex_side": "right", "apex_side_source": "manual"}
    b = flat_corner()
    m = SimpleNamespace(s_start_m=10.0, apex_m=20, s_end_m=30.0)
    out = refresh_corners([(a, m), (b, None)])
    check([c["id"] for c in out] == ["t1", "t4"], "corner order preserved")
    check(out[0]["s_start_m"] == 10.0 and out[1]["s_start_m"] == 880.0,
          "each corner uses its own match")


def main() -> int:
    print("═══ Coaching-model updater merge tests ═══\n")
    test_matched_corner_keeps_curated_fields_and_takes_new_geometry()
    test_unmatched_corner_is_kept_verbatim()
    test_inputs_are_not_mutated()
    test_mixed_pairs_preserve_order()
    print(f"\n{_passed}/{_passed + _failed} assertions passed")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
