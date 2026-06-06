#!/usr/bin/env python3
"""
Bug 23 repro: update_reference_and_coaching_model.py's legacy extraction
(groupby lap_number + global mask) corrupts laps from restarted sessions.

Run from the repo root:
    .venv/Scripts/python.exe work/active/bugs/23-updater-legacy-extraction/repro.py

The legacy logic below is a verbatim copy of the script's original
find_fastest_lap + step-3 mask extraction (kept here so the repro stays
valid after the script is fixed).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "product" / "python"))
sys.path.insert(0, str(ROOT / "dev" / "scripts"))

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

SESSION = Path("sessions/session_20260520T180234Z_autodromo-nazionale-monza_lmu.parquet")
MIN_LAP_TIME_S = 60.0
MIN_LAP_POINTS = 100


def legacy_find_fastest_lap(table: pa.Table):
    """Verbatim copy of the pre-fix find_fastest_lap (groupby lap number)."""
    lap_numbers = table.column("lap_number").to_pylist()
    lap_times_col = table.column("lap_time_s").to_pylist()

    lap_time_map = {}
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

    row_counts = sorted(c[2] for c in candidates)
    median_rows = row_counts[len(row_counts) // 2]
    threshold = median_rows * 0.95
    valid = [(n, t) for n, t, rc in candidates if rc >= threshold]
    return min(valid, key=lambda x: x[1])


def main() -> int:
    table = pq.read_table(SESSION)
    print(f"Session: {SESSION.name} ({table.num_rows} rows, 3 stints, repeated lap numbers)\n")

    # --- fixed path (segment-based, shared with export script) ---
    from export_fastest_reference_laps import find_complete_laps
    ln, lt, s, e = min(find_complete_laps(table), key=lambda c: c[1])
    print(f"FIXED   : fastest lap is lap {ln} @ {lt:.3f}s (authoritative), "
          f"segment slice -> {e - s} rows")

    # --- legacy flaw 1: groupby-lap-number picks the wrong lap ---
    lap_num, lap_time = legacy_find_fastest_lap(table)
    print(f"LEGACY 1: groupby-lap-number picks lap {lap_num} @ {lap_time:.3f}s "
          f"(wrong lap and/or undercounted time)")

    # --- legacy flaw 2: mask extraction of the true fastest lap merges stints ---
    mask_rows = table.filter(pc.equal(table.column("lap_number"), ln)).num_rows
    print(f"LEGACY 2: lap_number == {ln} mask extraction -> {mask_rows} rows "
          f"(real lap is {e - s} rows)")

    wrong_lap = lap_num != ln or abs(lap_time - lt) > 0.001
    merged = mask_rows != e - s
    if wrong_lap or merged:
        print("\nBUG REPRODUCED:")
        if wrong_lap:
            print(f"  - legacy selects lap {lap_num} @ {lap_time:.3f}s instead of "
                  f"lap {ln} @ {lt:.3f}s")
        if merged:
            print(f"  - mask extraction merges {mask_rows - (e - s)} rows from "
                  f"another stint into the exported 'lap'")
        return 0
    print("\nBug NOT reproduced (legacy and fixed agree).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
