"""Repro for bug 19: session restart duplicates lap-number rows in snapshot.

Run from the repo root:
    python work/active/bugs/19-session-restart-duplicate-lap-snapshot/repro.py

Expected output shows that compare_laps on the corrupted (multi-stint) lap-4
snapshot reports a 1.5+ s loss at turn 9 and a 2.3 s total delta — both much
larger than the true ~0.7 s delta from the second stint alone.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "product/python")

import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.compute as pc

from lap_telemetry.coach.lap_comparator import compare_laps
from lap_telemetry.coach.track_model import load_track_coaching_model
from lap_telemetry.parquet_utils import build_segments, authoritative_duration

SESSION = Path("sessions/session_20260531T173205Z_bahrain-outer-circuit_lmu.parquet")
REFERENCE = Path(
    "product/data/reference-laps/"
    "bahrain-outer-circuit_dkr-engineering-4-elms25_time_01.10.845.parquet"
)
TRACK_MODEL = Path(
    "product/data/track-coaching/"
    "bahrain-outer-circuit_dkr-engineering-4-elms25.json"
)

model = load_track_coaching_model(TRACK_MODEL)
full_table = pq.read_table(SESSION)

lap_numbers = full_table.column("lap_number").to_pylist()
session_times = full_table.column("session_time_s").to_pylist()
segments = build_segments(lap_numbers)

# Identify both occurrences of lap_number=4 in the session.
lap4_segments = [(i, seg) for i, seg in enumerate(segments) if seg[0] == 4]
print("=== Lap-4 segments in session parquet ===")
for seg_idx, (lap_num, start, end) in lap4_segments:
    nxt = segments[seg_idx + 1] if seg_idx + 1 < len(segments) else None
    dur = authoritative_duration(
        full_table, start, end,
        nxt[1] if nxt else None,
        nxt[2] if nxt else None,
    )
    first_t = session_times[start]
    last_t = session_times[end - 1]
    print(
        f"  segment[{seg_idx}]: rows {start}-{end}  "
        f"session_time {first_t:.1f}s–{last_t:.1f}s  "
        f"duration {dur:.2f}s"
    )

# --- Corrupted snapshot: what _write_lap_snapshot(4) actually produced ---
# Filter ALL rows with lap_number=4 (both stints).
corrupted = full_table.filter(pc.equal(full_table.column("lap_number"), 4))
print(f"\nCorrupted snapshot rows: {len(corrupted)}")

with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
    corrupted_path = Path(f.name)
pq.write_table(corrupted, corrupted_path, compression="snappy")

corrupted_facts = compare_laps(corrupted_path, REFERENCE, model)
corrupted_path.unlink(missing_ok=True)

print(f"\n=== compare_laps on CORRUPTED snapshot ===")
print(f"  Total lap delta:  {corrupted_facts.lap_time_delta_s:.3f} s  (WRONG — true ~0.7 s)")
print(f"  Top losses:")
for loss in corrupted_facts.top_losses:
    print(
        f"    {loss.corner_name:8s}  phase={loss.phase:16s}  "
        f"loss={loss.loss_s:.3f} s  "
        f"speed delta {loss.reference_value - loss.driver_value:+.1f} kph"
    )

# --- Clean snapshot: only the second stint's lap 4 ---
# Second stint starts at the segment where session_time_s resets (row 31245).
# Lap-4 second stint is rows 52524–56086.
clean_start, clean_end = 52524, 56086
clean = full_table.slice(clean_start, clean_end - clean_start)
print(f"\nClean snapshot rows (second stint only): {len(clean)}")

with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
    clean_path = Path(f.name)
pq.write_table(clean, clean_path, compression="snappy")

clean_facts = compare_laps(clean_path, REFERENCE, model)
clean_path.unlink(missing_ok=True)

print(f"\n=== compare_laps on CLEAN snapshot (second-stint lap 4 only) ===")
print(f"  Total lap delta:  {clean_facts.lap_time_delta_s:.3f} s  (correct)")
print(f"  Top losses:")
for loss in clean_facts.top_losses:
    print(
        f"    {loss.corner_name:8s}  phase={loss.phase:16s}  "
        f"loss={loss.loss_s:.3f} s  "
        f"speed delta {loss.reference_value - loss.driver_value:+.1f} kph"
    )

# --- Assert the bug ---
print("\n=== Bug assertion ===")
top_corrupted = corrupted_facts.top_losses[0] if corrupted_facts.top_losses else None
top_clean = clean_facts.top_losses[0] if clean_facts.top_losses else None

assert top_corrupted is not None, "No losses in corrupted facts"
assert corrupted_facts.lap_time_delta_s > 2.0, (
    f"Expected corrupted delta > 2 s, got {corrupted_facts.lap_time_delta_s:.3f}s"
)
assert clean_facts.lap_time_delta_s < 1.0, (
    f"Expected clean delta < 1 s, got {clean_facts.lap_time_delta_s:.3f}s"
)
# Turn 9 should appear as the top loss in corrupted data but not in clean data.
corrupted_corners = [c.corner_name for c in corrupted_facts.top_losses]
clean_corners = [c.corner_name for c in clean_facts.top_losses]
assert "turn 9" in corrupted_corners, (
    f"Expected turn 9 in corrupted top losses, got {corrupted_corners}"
)
assert "turn 9" not in clean_corners, (
    f"Expected turn 9 absent from clean top losses, got {clean_corners}"
)

print("  PASS: corrupted snapshot reports inflated delta (>2 s, true: ~0.7 s).")
print("  PASS: clean snapshot reports correct delta (<1 s).")
print("  PASS: turn 9 appears in corrupted losses but not in clean losses.")
print(
    f"\n  Corrupted: delta={corrupted_facts.lap_time_delta_s:.3f}s, "
    f"top loss={top_corrupted.corner_name} {top_corrupted.loss_s:.3f}s"
)
print(
    f"  Clean:     delta={clean_facts.lap_time_delta_s:.3f}s, "
    f"top loss={top_clean.corner_name if top_clean else 'none'} "
    f"{top_clean.loss_s:.3f}s" if top_clean else "  Clean: no losses"
)
