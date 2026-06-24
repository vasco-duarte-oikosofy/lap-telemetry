#!/usr/bin/env python3
"""
Refresh a track's coaching model from its fastest reference lap while
preserving curated turn names/IDs/apex sides — and, when a session contains a
faster lap, update the reference lap first.

The reference export is delegated to export_fastest_reference_laps.py
(bug 23): this script no longer extracts laps itself, so it inherits the
segment-slice extraction, authoritative timing, abandoned-lap rejection,
faster-only replacement, and the mandatory single-change audit.

All checks run BEFORE any write. In particular, if any corner of the existing
(curated) coaching model has no matching braking event on the new lap, the
script aborts without touching anything — curated models must never silently
lose hand-tuned detail (Bahrain Outer rule). Pass --allow-unmatched to keep
the old geometry for unmatched corners and proceed anyway.

Usage:
    # normal: scan session(s) of ONE (track, vehicle), update ref if faster,
    # then refresh the model from the current reference
    python dev/scripts/update_reference_and_coaching_model.py \
        --session sessions/session_20260529T180345Z_paul-ricard---3a_lmu.parquet \
        --track-id paul-ricard---3a

    # refresh the model from an explicit existing reference parquet
    python dev/scripts/update_reference_and_coaching_model.py \
        --ref product/data/reference-laps/paul-ricard---3a_..._time_01.17.166.parquet \
        --track-id paul-ricard---3a
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "product" / "python"))
sys.path.insert(0, str(ROOT / "dev" / "scripts"))

import pyarrow.parquet as pq

from lap_telemetry.coach.lap_comparator import resample_column

from export_fastest_reference_laps import (
    existing_refs,
    find_complete_laps,
    parse_lap_time_from_name,
    read_vehicle_name,
    vehicle_slug,
)
from generate_track_coaching_model_from_reference import (
    detect_corners_from_signals,
    detect_apex_candidates,
    finite_pairs,
    diagnostics_text,
    DETECTION_METHOD_V1,
    DETECTION_METHOD_V2,
)

EXPORT_SCRIPT = ROOT / "dev" / "scripts" / "export_fastest_reference_laps.py"
REF_LAP_DIR = ROOT / "product" / "data" / "reference-laps"
COACHING_DIR = ROOT / "product" / "data" / "track-coaching"
MAX_APEX_DELTA_M = 150


def detect_corners(ref_parquet: Path) -> tuple[list, str]:
    table = pq.read_table(ref_parquet)
    distances, speeds = finite_pairs(
        table.column("lap_distance_m").to_pylist(),
        table.column("speed_kph").to_pylist(),
    )
    lap_length = int(max(distances))
    resampled_speed = resample_column(distances, speeds, lap_length)

    has_signals = (
        "throttle_norm" in table.column_names
        and "brake_norm" in table.column_names
    )

    if has_signals:
        _, throttles = finite_pairs(
            table.column("lap_distance_m").to_pylist(),
            table.column("throttle_norm").to_pylist(),
        )
        _, brakes = finite_pairs(
            table.column("lap_distance_m").to_pylist(),
            table.column("brake_norm").to_pylist(),
        )
        resampled_throttle = resample_column(distances, throttles, lap_length)
        resampled_brake = resample_column(distances, brakes, lap_length)
        candidates = detect_corners_from_signals(resampled_speed, resampled_throttle, resampled_brake)
        return candidates, DETECTION_METHOD_V2
    else:
        print("Warning: throttle_norm/brake_norm absent, falling back to speed_local_minimum_v1", file=sys.stderr)
        candidates, _ = detect_apex_candidates(resampled_speed)
        return candidates, DETECTION_METHOD_V1


def match_corners(existing_corners: list[dict], candidates: list) -> tuple[list[tuple[dict, object | None]], list]:
    """Nearest-apex matching (each old corner claims the closest unclaimed
    candidate within MAX_APEX_DELTA_M). Returns [(old_corner, match_or_None)]
    plus the unclaimed candidates."""
    apexes = [float(c.apex_m) for c in candidates]
    claimed = [False] * len(candidates)

    def nearest(old_apex: float) -> int | None:
        best_idx, best_dist = None, float("inf")
        for i, apex in enumerate(apexes):
            if claimed[i]:
                continue
            dist = abs(apex - old_apex)
            if dist < best_dist:
                best_dist, best_idx = dist, i
        if best_idx is not None and best_dist <= MAX_APEX_DELTA_M:
            return best_idx
        return None

    pairs: list[tuple[dict, object | None]] = []
    for old_c in existing_corners:
        idx = nearest(float(old_c["apex_s_m"]))
        if idx is not None:
            claimed[idx] = True
            pairs.append((old_c, candidates[idx]))
        else:
            pairs.append((old_c, None))
    leftover = [candidates[i] for i, used in enumerate(claimed) if not used]
    return pairs, leftover


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--session", type=Path, nargs="+",
        help="session parquet file(s), all of the same (track, vehicle)",
    )
    src.add_argument(
        "--ref", type=Path,
        help="existing reference-lap parquet to refresh the model from (skips export)",
    )
    p.add_argument("--track-id", required=True, help="track slug, e.g. paul-ricard---3a")
    p.add_argument(
        "--layout-id", default=None,
        help="accepted for backwards compatibility; the layout is read from the existing model",
    )
    p.add_argument(
        "--allow-unmatched", action="store_true",
        help="proceed even if curated corners have no match on the new lap "
             "(their old geometry is kept); default is to abort with no changes",
    )
    p.add_argument(
        "--max-geometry-delta-m", type=float, default=None,
        help="abort (no writes) if any matched corner's entry/apex/exit would "
             "move more than this many metres from the existing model, and print "
             "the flagged corners for manual review. The reference lap is still "
             "exported only when this check passes.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()

    # --- 1. Resolve vehicle and the lap that will back the model -----------
    export_needed = False
    candidate_time: float | None = None
    tmp_lap: Path | None = None

    if args.ref is not None:
        if not args.ref.exists():
            print(f"ERROR: reference not found: {args.ref}", file=sys.stderr)
            return 1
        ref_time = parse_lap_time_from_name(args.ref)
        if ref_time is None:
            print(f"ERROR: cannot parse lap time from {args.ref.name}", file=sys.stderr)
            return 1
        name_no_time = args.ref.name.split("_time_")[0]
        if not name_no_time.startswith(f"{args.track_id}_"):
            print(f"ERROR: {args.ref.name} is not a {args.track_id} reference", file=sys.stderr)
            return 1
        vslug = name_no_time[len(args.track_id) + 1:]
        backing_lap = args.ref
        backing_time = ref_time
        print(f"Mode: --ref  ({args.ref.name}, {ref_time:.3f}s, vehicle {vslug})")
    else:
        vnames = {read_vehicle_name(s) for s in args.session}
        if len(vnames) != 1 or "" in vnames:
            print(f"ERROR: sessions span vehicles {sorted(vnames)!r} - pass ONE (track, vehicle)",
                  file=sys.stderr)
            return 1
        vslug = vehicle_slug(vnames.pop())

        best = None
        for s in args.session:
            table = pq.read_table(s)
            for lap_num, lap_time, seg_start, seg_end in find_complete_laps(table):
                if best is None or lap_time < best[1]:
                    best = (lap_num, lap_time, seg_start, seg_end, s, table)
        if best is None:
            print("ERROR: no complete laps found in the given session(s).", file=sys.stderr)
            return 1
        lap_num, candidate_time, seg_start, seg_end, best_session, best_table = best
        print(f"Fastest lap in session(s): lap {lap_num} @ {candidate_time:.3f}s "
              f"({best_session.name}, vehicle {vslug})")

        existing = existing_refs(args.track_id, vslug)
        existing_best = min((t for _, t in existing), default=None)
        if existing_best is not None and candidate_time > existing_best - 0.001:
            ref_path = min(existing, key=lambda x: x[1])[0]
            backing_lap, backing_time = ref_path, existing_best
            print(f"Not faster than existing reference {existing_best:.3f}s - "
                  f"reference stays; model will be checked against {ref_path.name}")
        else:
            export_needed = True
            tmp_lap = Path(tempfile.gettempdir()) / "ref_model_update_candidate.parquet"
            pq.write_table(best_table.slice(seg_start, seg_end - seg_start), tmp_lap)
            backing_lap, backing_time = tmp_lap, candidate_time
            print(f"Faster than existing reference - will export after corner check")

    # --- 2. Load the existing coaching model -------------------------------
    coaching_path = COACHING_DIR / f"{args.track_id}_{vslug}.json"
    if not coaching_path.exists():
        print(f"ERROR: coaching model not found: {coaching_path}\n"
              f"Use generate_track_coaching_model_from_reference.py to create one.",
              file=sys.stderr)
        return 1
    existing_model = json.loads(coaching_path.read_text())
    existing_corners = existing_model["corners"]

    # --- 3. Corner dry-check BEFORE any write (bug 23) ---------------------
    candidates, detection_method = detect_corners(backing_lap)
    pairs, leftover = match_corners(existing_corners, candidates)
    unmatched = [old_c["name"] for old_c, m in pairs if m is None]
    print(f"Corner check: model has {len(existing_corners)}, lap yields {len(candidates)} "
          f"({len(existing_corners) - len(unmatched)} matched)")
    if unmatched and not args.allow_unmatched:
        print(f"\nABORTED - curated corners not reproduced on this lap: {', '.join(unmatched)}\n"
              f"No files were changed. Re-run with --allow-unmatched to keep their old\n"
              f"geometry, or leave the reference and model as they are.", file=sys.stderr)
        if tmp_lap is not None:
            tmp_lap.unlink(missing_ok=True)
        return 2
    for name in unmatched:
        print(f"  WARNING: {name} keeps old geometry (--allow-unmatched)")
    for c in leftover:
        print(f"  INFO: new corner at apex={c.apex_m}m not in the model - ignored")

    # --- 3b. Geometry-delta guard BEFORE any write -------------------------
    if args.max_geometry_delta_m is not None:
        threshold = args.max_geometry_delta_m
        flagged = []
        for old_c, m in pairs:
            if m is None:
                continue
            d_entry = abs(float(m.s_start_m) - float(old_c["s_start_m"]))
            d_apex = abs(float(m.apex_m) - float(old_c["apex_s_m"]))
            d_exit = abs(float(m.s_end_m) - float(old_c["s_end_m"]))
            if max(d_entry, d_apex, d_exit) > threshold:
                flagged.append((old_c, m, d_entry, d_apex, d_exit))
        if flagged:
            print(f"\nFLAGGED - {len(flagged)} corner(s) would move > {threshold:g} m "
                  f"(entry/apex/exit). Model NOT overwritten; review manually.")
            print(f"  {'Turn':<25} {'dEntry':>8} {'dApex':>8} {'dExit':>8}  "
                  f"-> new Entry/Apex/Exit (was ...)")
            for old_c, m, de, da, dx in flagged:
                print(
                    f"  {old_c['name']:<25} {de:>8.1f} {da:>8.1f} {dx:>8.1f}  "
                    f"-> {m.s_start_m:.1f}/{m.apex_m:.1f}/{m.s_end_m:.1f} "
                    f"(was {old_c['s_start_m']:.1f}/{old_c['apex_s_m']:.1f}/{old_c['s_end_m']:.1f})"
                )
            print("\nABORTED - no files were changed (reference not exported, "
                  "model not overwritten).", file=sys.stderr)
            if tmp_lap is not None:
                tmp_lap.unlink(missing_ok=True)
            return 2
        else:
            print(f"Geometry guard: all matched corners within {threshold:g} m - OK")

    # --- 4. Export the reference (delegated, guarded, audited) -------------
    if export_needed:
        cmd = [sys.executable, str(EXPORT_SCRIPT)] + [str(s) for s in args.session]
        print(f"\nExporting reference via export_fastest_reference_laps.py ...")
        result = subprocess.run(cmd, cwd=ROOT)
        if tmp_lap is not None:
            tmp_lap.unlink(missing_ok=True)
        if result.returncode != 0:
            print("ERROR: reference export failed - coaching model NOT touched.", file=sys.stderr)
            return result.returncode
        refs = existing_refs(args.track_id, vslug)
        backing_lap = min(refs, key=lambda x: x[1])[0]
        backing_time = min(refs, key=lambda x: x[1])[1]

    # --- 5. Write the refreshed model (names/IDs/apex sides preserved) -----
    updated_corners = []
    for old_c, m in pairs:
        if m is None:
            updated_corners.append(dict(old_c))
        else:
            updated_corners.append({
                "id": old_c["id"],
                "name": old_c["name"],
                "s_start_m": round(m.s_start_m, 1),
                "apex_s_m": round(float(m.apex_m), 1),
                "s_end_m": round(m.s_end_m, 1),
                "apex_side": old_c["apex_side"],
                "apex_side_source": old_c["apex_side_source"],
            })

    backing_rel = backing_lap if not backing_lap.is_absolute() else backing_lap.relative_to(ROOT)
    updated_model = {
        "schema_version": existing_model["schema_version"],
        "track_id": existing_model["track_id"],
        "layout_id": existing_model["layout_id"],
        "reference_lap": {
            "path": str(backing_rel),
            "car_id": vslug,
            "lap_time_s": round(backing_time, 3),
            "detection_method": detection_method,
        },
        "lap_length_m": existing_model["lap_length_m"],
        "corners": updated_corners,
        "straight_zones": existing_model.get("straight_zones", []),
    }

    new_text = json.dumps(updated_model, indent=2) + "\n"
    if new_text == coaching_path.read_text():
        print(f"\nCoaching model already up to date ({coaching_path.name}) - nothing written.")
        return 0

    coaching_path.write_text(new_text, encoding="utf-8")
    diag_path = coaching_path.with_suffix(".diagnostics.txt")
    diag_path.write_text(diagnostics_text(candidates, detection_method), encoding="utf-8")
    print(f"\nUpdated coaching model -> {coaching_path}")
    print(f"Updated diagnostics -> {diag_path}")

    print("\nCorner geometry changes:")
    print(f"  {'Turn':<25} {'Entry':>8} {'Apex':>8} {'Exit':>8}  (was Entry/Apex/Exit)")
    for old_c, updated in zip(existing_corners, updated_corners):
        print(
            f"  {updated['name']:<25} "
            f"{updated['s_start_m']:>8.1f} {updated['apex_s_m']:>8.1f} {updated['s_end_m']:>8.1f}"
            f"  (was {old_c['s_start_m']:.1f} / {old_c['apex_s_m']:.1f} / {old_c['s_end_m']:.1f})"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
