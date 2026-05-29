"""Evaluate bug 10b scoring columns from today's live session."""
import pyarrow.parquet as pq
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent.parent
SESS = ROOT / "sessions" / "session_20260529T092852Z_bahrain-outer-circuit_lmu.parquet"

needed = ["lap_number", "lap_time_s",
          "scoring_last_lap_time_s", "scoring_time_into_lap_s",
          "scoring_lap_start_et_s", "scoring_total_laps"]

schema = pq.read_metadata(SESS).schema.to_arrow_schema()
have = [c for c in needed if c in schema.names]
missing = [c for c in needed if c not in schema.names]

if missing:
    print(f"MISSING columns (session recorded before 10b): {missing}")
    raise SystemExit(1)

f = pq.read_table(SESS, columns=have)
d = {c: f.column(c).to_pylist() for c in have}

laps = defaultdict(list)
for i, ln in enumerate(d["lap_number"]):
    laps[ln].append(i)

print(f"{'lap':>4}  {'max(lap_time_s)':>16}  {'scoring_last_lap':>16}  {'delta':>8}  {'max(time_into_lap)':>18}  {'total_laps':>10}")
print("-" * 82)

for ln in sorted(laps.keys()):
    if ln not in (1, 2, 3, 4, 5, 6, 7):
        continue
    idxs = laps[ln]
    lt   = [d["lap_time_s"][i] for i in idxs]
    slt  = [d["scoring_last_lap_time_s"][i] for i in idxs if d["scoring_last_lap_time_s"][i] is not None]
    sit  = [d["scoring_time_into_lap_s"][i] for i in idxs if d["scoring_time_into_lap_s"][i] is not None]
    stl  = [d["scoring_total_laps"][i] for i in idxs if d["scoring_total_laps"][i] is not None]

    max_lt  = max(lt)
    max_slt = max(slt) if slt else None
    max_sit = max(sit) if sit else None
    tl_val  = stl[-1] if stl else None
    delta   = round(max_slt - max_lt, 3) if max_slt else None

    print(f"  {ln:>2}  {max_lt:>16.3f}  {str(round(max_slt,3)) if max_slt else 'None':>16}  "
          f"{str('+'+str(delta)) if delta is not None else 'n/a':>8}  "
          f"{str(round(max_sit,3)) if max_sit else 'None':>18}  "
          f"{str(tl_val) if tl_val else 'None':>10}")

# How often is scoring_last_lap_time_s populated vs None?
total = len(d["lap_number"])
populated = sum(1 for v in d["scoring_last_lap_time_s"] if v is not None)
print(f"\nscoring_last_lap_time_s: {populated}/{total} rows populated ({100*populated//total}%)")
sit_pop = sum(1 for v in d["scoring_time_into_lap_s"] if v is not None)
print(f"scoring_time_into_lap_s: {sit_pop}/{total} rows populated ({100*sit_pop//total}%)")
