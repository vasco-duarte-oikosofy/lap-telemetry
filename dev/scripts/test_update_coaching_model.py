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

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pyarrow as pa

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "dev" / "scripts"))

import update_reference_and_coaching_model as updater  # noqa: E402
from update_reference_and_coaching_model import refresh_corners, match_corners

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


def test_explicit_geometry_preservation_does_not_steal_events() -> None:
    flat = {**flat_corner(), 'id': 'flat', 'apex_s_m': 100.0}
    brake = {**flat_corner(), 'id': 'brake', 'apex_s_m': 145.0}
    first = SimpleNamespace(s_start_m=130.0, apex_m=145, s_end_m=155.0)
    extra = SimpleNamespace(s_start_m=290.0, apex_m=300, s_end_m=310.0)
    before = [dict(flat), dict(brake)]
    pairs, leftover = match_corners([flat, brake], [first, extra], preserve_geometry={'flat'})
    check(pairs[0][1] is None and pairs[1][1] is first,
          'explicitly preserved corner does not claim its neighbour braking event')
    check(leftover == [extra], 'unclaimed events remain available for review')
    updated = refresh_corners(pairs)
    check(updated[0] == flat and updated[1]['apex_s_m'] == 145,
          'preserved geometry/curation exact; other matched corners still refresh')
    check([flat, brake] == before, 'preserving/matching never mutates inputs')
    normal, _ = match_corners([brake], [first])
    check(normal[0][1] is first, 'no-flag matching retains its original behavior')
    rejected = False
    try:
        match_corners([flat], [first], preserve_geometry={'typo'})
    except ValueError:
        rejected = True
    check(rejected, 'unknown preserved corner ID fails safely')


def test_preservation_and_geometry_guards_precede_export() -> None:
    model_path = ROOT / 'product/data/track-coaching/grand-prix-of-long-beach_ferrari-af-corse-2026-50-lm.json'
    model = json.loads(model_path.read_text())
    preserved = {'t3', 't7', 't10', 't11'}
    candidates = [SimpleNamespace(s_start_m=c['s_start_m'] + (100 if c['id'] == 't1' else 0),
                                 apex_m=c['apex_s_m'], s_end_m=c['s_end_m'])
                  for c in model['corners'] if c['id'] not in preserved]
    table = pa.table({'dummy': [1, 2, 3, 4]})
    for ids, expected_message in [(preserved, 'FLAGGED'), ({'typo'}, 'unknown')]:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / model_path.name
            path.write_text(json.dumps(model))
            before = path.read_bytes()
            args = SimpleNamespace(ref=None, session=[Path('source.parquet')],
                                   track_id=model['track_id'], allow_unmatched=False,
                                   preserve_geometry=sorted(ids), max_geometry_delta_m=25)
            output = io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output), \
                 patch.object(updater, 'parse_args', return_value=args), \
                 patch.object(updater, 'COACHING_DIR', Path(folder)), \
                 patch.object(updater, 'read_vehicle_name', return_value='Ferrari AF Corse 2026 #50:LM'), \
                 patch.object(updater, 'existing_refs', return_value=[(Path('old.parquet'), 75.889)]), \
                 patch.object(updater, 'find_complete_laps', return_value=[(7, 74.87109375, 0, 4)]), \
                 patch.object(updater.pq, 'read_table', return_value=table), \
                 patch.object(updater, 'detect_corners', return_value=(candidates, 'throttle_brake_v1')), \
                 patch.object(updater.tempfile, 'gettempdir', return_value=folder), \
                 patch.object(updater.subprocess, 'run') as export:
                code = updater.main()
            check(code == 2 and expected_message.lower() in output.getvalue().lower(),
                  f'{expected_message}: unsafe refresh aborts before paired write')
            check(not export.called and path.read_bytes() == before,
                  f'{expected_message}: reference exporter not called and model bytes untouched')


def main() -> int:
    print("═══ Coaching-model updater merge tests ═══\n")
    test_matched_corner_keeps_curated_fields_and_takes_new_geometry()
    test_unmatched_corner_is_kept_verbatim()
    test_inputs_are_not_mutated()
    test_mixed_pairs_preserve_order()
    for test in [test_explicit_geometry_preservation_does_not_steal_events,
                 test_preservation_and_geometry_guards_precede_export]:
        try:
            test()
        except Exception as error:
            check(False, f'{test.__name__}: {error}')
    print(f"\n{_passed}/{_passed + _failed} assertions passed")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
