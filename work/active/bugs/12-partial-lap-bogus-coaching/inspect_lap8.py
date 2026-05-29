"""Temporary inspection script for bug 12 investigation — lap 8 Bahrain Outer."""
import pyarrow.parquet as pq
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "product" / "python"))

SESS = ROOT / "sessions" / "session_20260529T092852Z_bahrain-outer-circuit_lmu.parquet"
REF  = ROOT / "product" / "data" / "reference-laps" / "bahrain-outer-circuit_dkr-engineering-4-elms25_time_01.11.380.parquet"
MODEL = ROOT / "product" / "data" / "track-coaching" / "bahrain-outer-circuit_dkr-engineering-4-elms25.json"

# ── load session ───────────────────────────────────────────────────────────────
sess = pq.read_table(SESS, columns=["lap_number","lap_time_s","lap_distance_m","speed_kph","raw_lap_distance_m"])
d = {c: sess.column(c).to_pylist() for c in sess.schema.names}

lap8 = [i for i, ln in enumerate(d["lap_number"]) if ln == 8]
print(f"Lap 8: {len(lap8)} frames")

def show(label, idxs):
    print(f"\n--- {label} ---")
    print(f"  {'i':>6}  {'lap_time_s':>10}  {'dist_m':>10}  {'raw_dist':>10}  {'kph':>8}")
    for i in idxs:
        raw = d["raw_lap_distance_m"][i]
        raw_s = f"{raw:.1f}" if raw is not None else "None"
        print(f"  {i:>6}  {d['lap_time_s'][i]:>10.3f}  {d['lap_distance_m'][i]:>10.1f}  {raw_s:>10}  {d['speed_kph'][i]:>8.1f}")

show("lap 8 first 30", lap8[:30])
show("lap 8 last 20",  lap8[-20:])

lap7 = [i for i, ln in enumerate(d["lap_number"]) if ln == 7]
show("lap 7 last 10 frames (context)", lap7[-10:])

# ── run compare_laps on lap 8 vs reference and print raw facts ─────────────────
print("\n\n=== compare_laps(lap 8 vs reference) ===")
try:
    from lap_telemetry.coach.track_model import load_track_coaching_model
    from lap_telemetry.coach.lap_comparator import compare_laps
    model = load_track_coaching_model(MODEL)
    facts = compare_laps(SESS, REF, model, lap_number=8)
    print(f"  lap_time_delta_s = {facts.lap_time_delta_s:.3f}s  (driver={facts.lap_time_delta_s + model.lap_length_m/1000:.1f}s ref={model.lap_length_m:.0f}m)")
    print(f"  lap_time_delta_s = {facts.lap_time_delta_s:.3f}s")
    print(f"  top_gains:")
    for g in facts.top_gains:
        print(f"    {g.corner_id} {g.phase}: loss_s={g.loss_s:.3f}  apex_m={g.apex_distance_m:.0f}  driver={g.driver_value:.1f}  ref={g.reference_value:.1f}")
    print(f"  top_losses:")
    for l in facts.top_losses:
        print(f"    {l.corner_id} {l.phase}: loss_s={l.loss_s:.3f}  apex_m={l.apex_distance_m:.0f}  driver={l.driver_value:.1f}  ref={l.reference_value:.1f}")
except Exception as e:
    print(f"  ERROR: {e}")
    import traceback; traceback.print_exc()

# ── also run on a known good lap (lap 5) for comparison ───────────────────────
print("\n\n=== compare_laps(lap 5 vs reference, for comparison) ===")
try:
    facts5 = compare_laps(SESS, REF, model, lap_number=5)
    print(f"  lap_time_delta_s = {facts5.lap_time_delta_s:.3f}s")
    print(f"  top_gains:")
    for g in facts5.top_gains:
        print(f"    {g.corner_id} {g.phase}: loss_s={g.loss_s:.3f}  apex_m={g.apex_distance_m:.0f}  driver={g.driver_value:.1f}  ref={g.reference_value:.1f}")
except Exception as e:
    print(f"  ERROR: {e}")
