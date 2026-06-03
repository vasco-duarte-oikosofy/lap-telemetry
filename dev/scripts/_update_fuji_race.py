#!/usr/bin/env python3
"""Update Fuji reference lap and coaching model from today's race session (sharded)."""
from __future__ import annotations

import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "product" / "python"))
sys.path.insert(0, str(ROOT / "dev" / "scripts"))

import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.compute as pc

from generate_track_coaching_model_from_reference import (
    detect_corners_from_signals,
    detect_apex_candidates,
    finite_pairs,
    diagnostics_text,
    DETECTION_METHOD_V1,
    DETECTION_METHOD_V2,
)
from lap_telemetry.coach.lap_comparator import resample_column

SESSIONS_DIR = ROOT / "sessions"
REF_LAP_DIR = ROOT / "product" / "data" / "reference-laps"
COACHING_DIR = ROOT / "product" / "data" / "track-coaching"

TRACK_ID = "fuji-speedway"
VSLUG = "dkr-engineering-4-elms25"
SESSION_PREFIX = "session_20260603T170236Z_fuji-speedway_lmu_race"
BEST_LAP_NUM = 16


def format_lap_time(seconds: float) -> str:
    minutes = int(seconds // 60)
    remaining = seconds - minutes * 60
    secs = int(remaining)
    millis = int(round((remaining - secs) * 1000))
    if millis == 1000:
        secs += 1
        millis = 0
    return f"{minutes:02d}.{secs:02d}.{millis:03d}"


def main() -> int:
    # 1. Read all shards
    shards = sorted(SESSIONS_DIR.glob(f"{SESSION_PREFIX}.part*.parquet"))
    print(f"Reading {len(shards)} shards...", flush=True)
    tables = [pq.read_table(s) for s in shards]
    table = pa.concat_tables(tables)
    print(f"Total rows: {table.num_rows}", flush=True)

    # 2. Get best lap time from data
    lap_time_map: dict[int, float] = {}
    for ln, lt in zip(
        table.column("lap_number").to_pylist(),
        table.column("lap_time_s").to_pylist(),
    ):
        if ln is None or ln < 1:
            continue
        if lt is not None and lt == lt:
            cur = lap_time_map.get(int(ln), 0.0)
            lap_time_map[int(ln)] = max(cur, float(lt))

    best_time = lap_time_map[BEST_LAP_NUM]
    time_str = format_lap_time(best_time)
    print(f"Fastest lap: #{BEST_LAP_NUM} -> {time_str} ({best_time:.3f}s)", flush=True)

    # 3. Extract lap and write reference
    mask = pc.equal(table.column("lap_number"), BEST_LAP_NUM)
    lap_table = table.filter(mask)
    print(f"Lap rows: {lap_table.num_rows}", flush=True)

    new_ref_name = f"{TRACK_ID}_{VSLUG}_time_{time_str}.parquet"
    new_ref_path = REF_LAP_DIR / new_ref_name

    # Remove old reference laps
    for old in REF_LAP_DIR.glob(f"{TRACK_ID}_{VSLUG}_time_*.parquet"):
        if old != new_ref_path:
            print(f"Removing old reference: {old.name}")
            old.unlink()

    REF_LAP_DIR.mkdir(parents=True, exist_ok=True)
    pq.write_table(lap_table, new_ref_path)
    print(f"Written reference lap: {new_ref_path}", flush=True)

    # 4. Corner detection
    ref_table = pq.read_table(new_ref_path)
    distances, speeds = finite_pairs(
        ref_table.column("lap_distance_m").to_pylist(),
        ref_table.column("speed_kph").to_pylist(),
    )
    lap_length = int(max(distances))
    resampled_speed = resample_column(distances, speeds, lap_length)

    has_signals = (
        "throttle_norm" in ref_table.column_names
        and "brake_norm" in ref_table.column_names
    )
    if has_signals:
        _, throttles = finite_pairs(
            ref_table.column("lap_distance_m").to_pylist(),
            ref_table.column("throttle_norm").to_pylist(),
        )
        _, brakes = finite_pairs(
            ref_table.column("lap_distance_m").to_pylist(),
            ref_table.column("brake_norm").to_pylist(),
        )
        resampled_throttle = resample_column(distances, throttles, lap_length)
        resampled_brake = resample_column(distances, brakes, lap_length)
        new_candidates = detect_corners_from_signals(
            resampled_speed, resampled_throttle, resampled_brake
        )
        detection_method = DETECTION_METHOD_V2
        print(f"Detection method: {detection_method} (brake/throttle signals present)")
    else:
        new_candidates, _ = detect_apex_candidates(resampled_speed)
        detection_method = DETECTION_METHOD_V1
        print(f"Warning: falling back to {detection_method}", file=sys.stderr)

    print(f"Detected {len(new_candidates)} corners", flush=True)

    # 5. Load existing coaching model
    coaching_path = COACHING_DIR / f"{TRACK_ID}_{VSLUG}.json"
    existing_model = json.loads(coaching_path.read_text())
    existing_corners = existing_model["corners"]
    print(f"Existing model has {len(existing_corners)} corners", flush=True)

    # 6. Match new corners to existing by nearest apex (preserve names/IDs)
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
                f"  WARNING: no match for {old_c['name']} (apex {old_apex}m) "
                f"within {MAX_APEX_DELTA_M}m -- keeping old geometry",
                file=sys.stderr,
            )
            updated_corners.append(dict(old_c))

    for i, used in enumerate(claimed):
        if not used:
            c = new_candidates[i]
            print(f"  INFO: new corner at apex={c.apex_m}m not matched -- ignored")

    # 7. Write updated coaching model
    ref_rel_path = str(new_ref_path.relative_to(ROOT)).replace("\\", "/")
    updated_model = {
        "schema_version": existing_model["schema_version"],
        "track_id": existing_model["track_id"],
        "layout_id": existing_model["layout_id"],
        "reference_lap": {
            "path": ref_rel_path,
            "car_id": VSLUG,
            "lap_time_s": round(best_time, 3),
            "detection_method": detection_method,
        },
        "lap_length_m": existing_model["lap_length_m"],
        "corners": updated_corners,
        "straight_zones": existing_model.get("straight_zones", []),
    }

    coaching_path.write_text(json.dumps(updated_model, indent=2) + "\n", encoding="utf-8")
    print(f"\nUpdated coaching model: {coaching_path}", flush=True)

    diag_path = coaching_path.with_suffix(".diagnostics.txt")
    diag_path.write_text(diagnostics_text(new_candidates, detection_method), encoding="utf-8")
    print(f"Updated diagnostics: {diag_path}", flush=True)

    # 8. Print corner diff
    print("\nCorner geometry (entry / apex / exit):")
    print(f"  {'Turn':<25} {'Entry':>8} {'Apex':>8} {'Exit':>8}  delta")
    for old_c, upd in zip(existing_corners, updated_corners):
        delta = upd["apex_s_m"] - old_c["apex_s_m"]
        print(
            f"  {upd['name']:<25} {upd['s_start_m']:>8.1f} {upd['apex_s_m']:>8.1f} "
            f"{upd['s_end_m']:>8.1f}  ({delta:+.1f}m)"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
