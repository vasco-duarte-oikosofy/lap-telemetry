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
from generate_track_coaching_model_from_reference import Candidate
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


def test_nearest_corner_claims_the_event_not_the_earlier_listed_one() -> None:
    """Bug 29: Fuji's 'Netz' (3310 m) is listed before 'Netz Hairpin' (3404 m).

    Model-order claiming handed the hairpin's braking event (3385 m on the
    2026-11-07 quali lap) to Netz -- 75 m away, legal under the 150 m tolerance
    -- and then reported the hairpin (19 m away) as unmatched. Ownership must be
    decided by distance, not by list position.
    """
    netz = {"id": "netz", "name": "Netz", "s_start_m": 3284.0, "apex_s_m": 3310.0,
            "s_end_m": 3310.0, "apex_side": "left", "apex_side_source": "manual",
            "target_throttle_pct": 100}
    hairpin = {"id": "netz_hairpin", "name": "Netz Hairpin", "s_start_m": 3291.0,
               "apex_s_m": 3404.0, "s_end_m": 3439.0, "apex_side": "left",
               "apex_side_source": "manual"}
    event = SimpleNamespace(s_start_m=3360.0, apex_m=3385, s_end_m=3446.0)
    before = [dict(netz), dict(hairpin)]

    pairs, leftover = match_corners([netz, hairpin], [event])
    check(pairs[0][1] is None,
          'earlier-listed flat corner does not steal its neighbour event')
    check(pairs[1][1] is event, 'the corner sitting on the event claims it')
    check(leftover == [], 'the claimed event is no longer offered as leftover')

    updated = refresh_corners(pairs)
    check(updated[0] == netz,
          'unmatched flat corner keeps geometry and target_throttle_pct verbatim')
    check(updated[1]['s_start_m'] == 3360.0 and updated[1]['apex_s_m'] == 3385.0
          and updated[1]['s_end_m'] == 3446.0,
          'the real corner takes the new lap geometry')
    check([netz, hairpin] == before, 'matching never mutates the model corners')


def test_matching_is_deterministic_and_respects_the_distance_cap() -> None:
    """Equal distances resolve to the earlier corner; far events stay unclaimed."""
    early = {"id": "a", "name": "A", "s_start_m": 0.0, "apex_s_m": 100.0, "s_end_m": 0.0,
             "apex_side": "right", "apex_side_source": "manual"}
    late = {**early, "id": "b", "name": "B", "apex_s_m": 140.0}
    event = SimpleNamespace(s_start_m=90.0, apex_m=120, s_end_m=130.0)
    pairs, _ = match_corners([early, late], [event])
    check(pairs[0][1] is event and pairs[1][1] is None,
          'a tie resolves to the earlier corner, deterministically')

    far = SimpleNamespace(s_start_m=400.0, apex_m=420, s_end_m=430.0)
    pairs, leftover = match_corners([early], [event, far])
    check(pairs[0][1] is event and leftover == [far],
          'candidates beyond MAX_APEX_DELTA_M stay unclaimed')


def test_preservation_and_geometry_guards_precede_export() -> None:
    model_path = ROOT / 'product/data/track-coaching/grand-prix-of-long-beach_ferrari-af-corse-2026-50-lm.json'
    model = json.loads(model_path.read_text(encoding='utf-8'))
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
                                   preserve_geometry=sorted(ids), max_geometry_delta_m=25,
                                   min_lap_time_s=updater.MIN_LAP_TIME_S)
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



def test_curated_unicode_names_round_trip_through_the_updater() -> None:
    """Windows cp1252 must never mangle names like Junção/Hôtel.

    The updater used to call read_text() without an encoding: on Windows that
    decodes the UTF-8 model as cp1252, so a refresh wrote back mojibake
    ("JunÃ§Ã£o"). Curated names must survive byte-identical.
    """
    model = {
        "schema_version": 1,
        "track_id": "autodromo-jose-carlos-pace",
        "layout_id": "default",
        "reference_lap": {"path": "product/data/reference-laps/old_time_01.30.354.parquet",
                          "car_id": "dkr-engineering-4-elms25", "lap_time_s": 90.354,
                          "detection_method": "throttle_brake_v1"},
        "lap_length_m": 4271.98,
        "corners": [{
            "id": "t12", "name": "Junção", "short_name": "Junção",
            "s_start_m": 3134.0, "apex_s_m": 3255.0, "s_end_m": 3284.0,
            "apex_side": "left", "apex_side_source": "manual", "target_throttle_pct": 51,
        }, {
            "id": "t13", "name": "Café", "s_start_m": 3391.0, "apex_s_m": 3391.0,
            "s_end_m": 3391.0, "apex_side": "left", "apex_side_source": "manual",
            "target_throttle_pct": 100,
        }],
        "straight_zones": [],
    }
    candidates = [Candidate(apex_m=3255, min_speed_kph=82.0, prominence_kph=18.0,
                            left_peak_kph=100.0, right_peak_kph=95.0,
                            s_start_m=3134.0, s_end_m=3284.0)]
    table = pa.table({'dummy': [1, 2, 3, 4]})
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / 'autodromo-jose-carlos-pace_dkr-engineering-4-elms25.json'
        path.write_text(json.dumps(model, ensure_ascii=False), encoding='utf-8')
        args = SimpleNamespace(ref=None, session=[Path('source.parquet')],
                               track_id='autodromo-jose-carlos-pace', allow_unmatched=False,
                               preserve_geometry=['t13'], max_geometry_delta_m=None,
                               min_lap_time_s=updater.MIN_LAP_TIME_S)
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output),              patch.object(updater, 'parse_args', return_value=args),              patch.object(updater, 'COACHING_DIR', Path(folder)),              patch.object(updater, 'read_vehicle_name', return_value='DKR Engineering #4:ELMS25'),              patch.object(updater, 'existing_refs', return_value=[(Path('old.parquet'), 90.354)]),              patch.object(updater, 'find_complete_laps', return_value=[(10, 90.062, 0, 4)]),              patch.object(updater.pq, 'read_table', return_value=table),              patch.object(updater, 'detect_corners', return_value=(candidates, 'throttle_brake_v1')),              patch.object(updater.tempfile, 'gettempdir', return_value=folder),              patch.object(updater.subprocess, 'run') as export:
            export.return_value.returncode = 0
            code = updater.main()
        raw = path.read_bytes()
        written = json.loads(raw.decode('utf-8'))
        names = [c['name'] for c in written['corners']]
        check(code == 0 and export.called, 'updater ran the guarded export path')
        check(names == ['Junção', 'Café'],
              'curated Unicode names round-trip unchanged', repr(names))
        check('Ã' not in raw.decode('utf-8'),
              'no double-encoded UTF-8 is written back to a curated model')
        check(written['corners'][1]['target_throttle_pct'] == 100,
              'flat marker still preserved through the same run')


def main() -> int:
    print("═══ Coaching-model updater merge tests ═══\n")
    test_matched_corner_keeps_curated_fields_and_takes_new_geometry()
    test_unmatched_corner_is_kept_verbatim()
    test_inputs_are_not_mutated()
    test_mixed_pairs_preserve_order()
    for test in [test_explicit_geometry_preservation_does_not_steal_events,
                 test_nearest_corner_claims_the_event_not_the_earlier_listed_one,
                 test_matching_is_deterministic_and_respects_the_distance_cap,
                 test_preservation_and_geometry_guards_precede_export,
                 test_curated_unicode_names_round_trip_through_the_updater]:
        try:
            test()
        except Exception as error:
            check(False, f'{test.__name__}: {error}')
    print(f"\n{_passed}/{_passed + _failed} assertions passed")
    return 1 if _failed else 0


if __name__ == "__main__":
    sys.exit(main())
