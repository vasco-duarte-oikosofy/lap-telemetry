#!/usr/bin/env python3
"""
Extract the fastest lap from a session, install it as the new reference lap,
and update the coaching model's corner geometry while preserving turn names/IDs.

Usage:
    python dev/scripts/update_reference_and_coaching_model.py \
        --session sessions/session_20260529T174714Z_paul-ricard---3a_lmu.parquet \
        --track-id paul-ricard---3a \
        --layout-id 3a
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "product" / "python"))

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from lap_telemetry.coach.lap_comparator import resample_column

# Reuse detection logic from the generation script
sys.path.insert(0, str(ROOT / "dev" / "scripts"))
from generate_track_coaching_model_from_reference import (
    detect_corners_from_signals,
    detect_apex_candidates,
    finite_pairs,
    diagnostics_text,
    DETECTION_METHOD_V1,
    DETECTION_METHOD_V2,
)

MIN_LAP_TIME_S = 60.0
MIN_LAP_POINTS = 100
REF_LAP_DIR = ROOT / "product" / "data" / "reference-laps"
COACHING_DIR = ROOT / "product" / "data" / "track-coaching"


def format_lap_time(seconds: float) -> str:
    minutes = int(seconds // 60)
    remaining = seconds - minutes * 60
    secs = int(remaining)
    millis = int(round((remaining - secs) * 1000))
    if millis == 1000:
        secs += 1
        millis = 0
    return f"{minutes:02d}.{secs:02d}.{millis:03d}"


def vehicle_slug(vehicle_name: str) -> str:
    s = vehicle_name.lower()
    s = re.sub(r"#", "", s)
    s = re.sub(r"[:/]", "-", s)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


def find_fastest_lap(table: pa.Table) -> tuple[int, float] | None:
    if "lap_number" not in table.schema.names or "lap_time_s" not in table.schema.names:
        return None

    lap_numbers = table.column("lap_number").to_pylist()
    lap_times_col = table.column("lap_time_s").to_pylist()

    lap_time_map: dict[int, float] = {}
    for ln, lt in zip(lap_numbers, lap_times_col):
        if ln is None or ln < 1:
            continue
        if lt is not None and not (lt != lt):
            cur = lap_time_map.get(int(ln), 0.0)
            lap_time_map[int(ln)] = max(cur, float(lt))

    candidates = []
    for lap_num, lap_time in lap_time_map.items():
        if lap_time <= MIN_LAP_TIME_S:
            continue
        mask = pc.equal(table.column("lap_number"), lap_num)
        row_count = pc.sum(mask.cast(pa.int32())).as_py()
        if row_count < MIN_LAP_POINTS:
            continue
        candidates.append((lap_num, lap_time, row_count))

    if not candidates:
        return None

    row_counts = sorted(c[2] for c in candidates)
    median_rows = row_counts[len(row_counts) // 2]
    threshold = median_rows * 0.95
    valid = [(lap_num, lap_time) for lap_num, lap_time, rc in candidates if rc >= threshold]
    if not valid:
        return None
    return min(valid, key=lambda x: x[1])


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


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--session", type=Path, required=True)
    p.add_argument("--track-id", required=True)
    p.add_argument("--layout-id", required=True)
    return p.parse_args()


def main() -> int:
    args = parse_args()

    # --- 1. Read session and find fastest lap ---
    print(f"Reading {args.session} ...")
    table = pq.read_table(args.session)
    result = find_fastest_lap(table)
    if result is None:
        print("ERROR: No complete laps found in session.", file=sys.stderr)
        return 1
    best_lap_num, best_time = result
    print(f"Fastest lap: #{best_lap_num} in {best_time:.3f}s ({format_lap_time(best_time)})")

    # --- 2. Read vehicle info from sidecar ---
    sidecar = args.session.with_suffix(".json")
    vehicle_name = ""
    if sidecar.exists():
        vehicle_name = json.loads(sidecar.read_text()).get("vehicle_name", "")
    vslug = vehicle_slug(vehicle_name) if vehicle_name else "unknown"
    print(f"Vehicle: {vehicle_name!r} -> slug: {vslug}")

    # --- 3. Export new reference lap parquet ---
    time_str = format_lap_time(best_time)
    new_ref_name = f"{args.track_id}_{vslug}_time_{time_str}.parquet"
    new_ref_path = REF_LAP_DIR / new_ref_name

    mask = pc.equal(table.column("lap_number"), best_lap_num)
    lap_table = table.filter(mask)
    print(f"Exporting {lap_table.num_rows} rows -> {new_ref_path}")

    # Remove any existing reference lap for this track+vehicle
    pattern = f"{args.track_id}_{vslug}_time_*.parquet"
    old_refs = list(REF_LAP_DIR.glob(pattern))
    for old in old_refs:
        if old != new_ref_path:
            print(f"Removing old reference lap: {old.name}")
            old.unlink()

    REF_LAP_DIR.mkdir(parents=True, exist_ok=True)
    pq.write_table(lap_table, new_ref_path)

    # --- 4. Run corner detection on new reference lap ---
    print("Running corner detection ...")
    new_candidates, detection_method = detect_corners(new_ref_path)
    print(f"Detected {len(new_candidates)} corners via {detection_method}")

    # --- 5. Load existing coaching model to preserve turn names ---
    coaching_pattern = f"{args.track_id}_{vslug}.json"
    coaching_path = COACHING_DIR / coaching_pattern
    if not coaching_path.exists():
        print(f"ERROR: Coaching model not found: {coaching_path}", file=sys.stderr)
        return 1

    existing_model = json.loads(coaching_path.read_text())
    existing_corners = existing_model["corners"]
    print(f"Existing coaching model has {len(existing_corners)} corners, new detection has {len(new_candidates)}")

    # --- 6. Merge: match old corners to new candidates by nearest apex ---
    # Each old corner claims the closest unmatched new candidate within MAX_APEX_DELTA_M.
    # Old corners with no match keep their existing geometry (with a warning).
    MAX_APEX_DELTA_M = 150

    new_apex_positions = [float(c.apex_m) for c in new_candidates]
    claimed = [False] * len(new_candidates)

    def find_nearest_unclaimed(old_apex_m: float) -> int | None:
        best_idx = None
        best_dist = float("inf")
        for i, apex in enumerate(new_apex_positions):
            if claimed[i]:
                continue
            dist = abs(apex - old_apex_m)
            if dist < best_dist:
                best_dist = dist
                best_idx = i
        if best_idx is not None and best_dist <= MAX_APEX_DELTA_M:
            return best_idx
        return None

    updated_corners = []
    for old_c in existing_corners:
        old_apex = old_c["apex_s_m"]
        match_idx = find_nearest_unclaimed(old_apex)
        if match_idx is not None:
            new_c = new_candidates[match_idx]
            claimed[match_idx] = True
            updated_corners.append({
                "id": old_c["id"],
                "name": old_c["name"],
                "s_start_m": round(new_c.s_start_m, 1),
                "apex_s_m": round(float(new_c.apex_m), 1),
                "s_end_m": round(new_c.s_end_m, 1),
                "apex_side": old_c["apex_side"],
                "apex_side_source": old_c["apex_side_source"],
            })
        else:
            print(
                f"  WARNING: no match for {old_c['name']} (apex {old_apex}m) within {MAX_APEX_DELTA_M}m "
                f"-- keeping old geometry",
                file=sys.stderr,
            )
            updated_corners.append(dict(old_c))

    unmatched_new = [new_candidates[i] for i, used in enumerate(claimed) if not used]
    if unmatched_new:
        for c in unmatched_new:
            print(
                f"  INFO: new corner at apex={c.apex_m}m not matched to any existing turn -- ignored",
                file=sys.stderr,
            )

    # Rebuild model with updated reference and corner geometry
    ref_rel_path = str(new_ref_path.relative_to(ROOT))
    updated_model = {
        "schema_version": existing_model["schema_version"],
        "track_id": existing_model["track_id"],
        "layout_id": existing_model["layout_id"],
        "reference_lap": {
            "path": ref_rel_path,
            "car_id": vslug,
            "lap_time_s": round(best_time, 3),
            "detection_method": detection_method,
        },
        "lap_length_m": existing_model["lap_length_m"],
        "corners": updated_corners,
        "straight_zones": existing_model.get("straight_zones", []),
    }

    coaching_path.write_text(json.dumps(updated_model, indent=2) + "\n", encoding="utf-8")
    print(f"Updated coaching model -> {coaching_path}")

    # Write diagnostics
    diag_path = coaching_path.with_suffix(".diagnostics.txt")
    diag_path.write_text(diagnostics_text(new_candidates, detection_method), encoding="utf-8")
    print(f"Updated diagnostics -> {diag_path}")

    # Print corner-by-corner diff
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
