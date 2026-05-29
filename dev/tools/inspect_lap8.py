"""
Reproduction script for bug 12 — partial-lap coaching investigation.
Covers lap 8 (session-end partial) AND laps 4/7 (shard-cut partial).

Run: python dev/tools/inspect_lap8.py
"""
import pyarrow as pa
import pyarrow.parquet as pq
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "product" / "python"))

SESS  = ROOT / "sessions" / "session_20260529T092852Z_bahrain-outer-circuit_lmu.parquet"
REF   = ROOT / "product" / "data" / "reference-laps" / "bahrain-outer-circuit_dkr-engineering-4-elms25_time_01.11.380.parquet"
MODEL = ROOT / "product" / "data" / "track-coaching" / "bahrain-outer-circuit_dkr-engineering-4-elms25.json"

from lap_telemetry.coach.track_model import load_track_coaching_model
from lap_telemetry.coach.lap_comparator import compare_laps

model = load_track_coaching_model(MODEL)

# ── Helper ─────────────────────────────────────────────────────────────────────

def run_compare(label, table, note=""):
    """Write table to a temp parquet and run compare_laps (no lap_number filter)."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
        tmp = Path(f.name)
    pq.write_table(table, tmp, compression="snappy")
    try:
        facts = compare_laps(tmp, REF, model)
        print(f"\n=== {label} {note} ===")
        print(f"  rows={len(table)}, lap_time_delta_s={facts.lap_time_delta_s:.3f}s")
        dist = table.column("lap_distance_m").to_pylist()
        lt   = table.column("lap_time_s").to_pylist()
        print(f"  dist=[{min(dist):.0f}..{max(dist):.0f}]  lap_time_s=[{min(lt):.2f}..{max(lt):.2f}]")
        all_items = [("GAIN", g) for g in facts.top_gains] + [("LOSS", l) for l in facts.top_losses]
        for kind, c in all_items:
            print(f"  {kind}: {c.corner_id} {c.phase}: loss_s={c.loss_s:.3f}  apex_m={c.apex_distance_m:.0f}  driver={c.driver_value:.1f}  ref={c.reference_value:.1f}")
    except Exception as e:
        print(f"\n=== {label} === ERROR: {e}")
        import traceback; traceback.print_exc()
    finally:
        tmp.unlink(missing_ok=True)


# ── Load session ───────────────────────────────────────────────────────────────
sess_table = pq.read_table(SESS)
d = {c: sess_table.column(c).to_pylist() for c in sess_table.schema.names}

# ── Section 1: lap 8 (head-partial — session ended at 1046m) ──────────────────
print("\n" + "="*70)
print("SECTION 1: Lap 8 — head-partial (session ended at 1046 m)")
print("="*70)

lap8_mask = [ln == 8 for ln in d["lap_number"]]
lap8_table = sess_table.filter(lap8_mask)
run_compare("lap 8 from merged file", lap8_table, "(all frames incl stale frame)")

# Also test without the stale frame (lap_time_s < 0 at high distance)
lt8  = lap8_table.column("lap_time_s").to_pylist()
lap8_clean_mask = [t >= 0 for t in lt8]
lap8_clean = lap8_table.filter(lap8_clean_mask)
run_compare("lap 8 clean (stale frame stripped)", lap8_clean)

# ── Section 2: laps 4 and 7 — shard-cut partial simulation ────────────────────
print("\n" + "="*70)
print("SECTION 2: Laps 4 and 7 — shard-cut simulation")
print("Hypothesis: flush every 30s clears the buffer mid-lap (71s lap).")
print("The shard used by the coach only contains the TAIL of the lap.")
print("="*70)

FLUSH_S = 30.0  # _FLUSH_INTERVAL_S from record.py

for lap_n in [4, 7]:
    mask = [ln == lap_n for ln in d["lap_number"]]
    full_table = sess_table.filter(mask)
    lt_col = full_table.column("lap_time_s").to_pylist()
    dist_col = full_table.column("lap_distance_m").to_pylist()

    run_compare(f"lap {lap_n} FULL (from merged file — baseline)", full_table)

    # Simulate shard cut: keep only frames with lap_time_s >= FLUSH_S
    # (approximates "buffer was cleared when car was ~30s into the lap")
    shard_mask = [t >= FLUSH_S for t in lt_col]
    shard_tail = full_table.filter(shard_mask)
    run_compare(
        f"lap {lap_n} TAIL (simulate shard cut at lap_time_s >= {FLUSH_S:.0f}s)",
        shard_tail,
        f"<-- what the coach actually received"
    )

# ── Section 3: all laps from merged file for comparison ───────────────────────
print("\n" + "="*70)
print("SECTION 3: All laps from merged file (should all be sensible)")
print("="*70)

for lap_n in [4, 5, 6, 7, 8]:
    mask_n = [ln == lap_n for ln in d["lap_number"]]
    t = sess_table.filter(mask_n)
    facts = compare_laps(SESS, REF, model, lap_number=lap_n)
    lt_c = t.column("lap_time_s").to_pylist()
    dist_c = t.column("lap_distance_m").to_pylist()
    gains  = [(g.corner_id, g.phase, g.loss_s) for g in facts.top_gains]
    losses = [(l.corner_id, l.phase, l.loss_s) for l in facts.top_losses]
    print(f"  lap {lap_n}: rows={len(t)}, delta={facts.lap_time_delta_s:.3f}s, "
          f"dist=[{min(dist_c):.0f}..{max(dist_c):.0f}], "
          f"gains={[(c,p,f'{v:.3f}') for c,p,v in gains]}, "
          f"losses={[(c,p,f'{v:.3f}') for c,p,v in losses]}")
