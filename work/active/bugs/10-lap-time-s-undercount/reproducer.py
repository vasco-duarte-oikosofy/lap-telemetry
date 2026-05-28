"""Reproducer for bug 10: lap_time_s underestimates lap time at crossing boundary.

Run from project root:
    python work/active/bugs/10-lap-time-s-undercount/reproducer.py
"""
import pyarrow.parquet as pq
from pathlib import Path

SESSION = Path("sessions/session_20260528T174221Z_bahrain-outer-circuit_lmu.parquet")


def build_segments(lap_col):
    segs = []
    prev, start = lap_col[0], 0
    for i in range(1, len(lap_col)):
        if lap_col[i] != prev:
            segs.append((prev, start, i))
            prev, start = lap_col[i], i
    segs.append((prev, start, len(lap_col)))
    return segs


def main():
    t = pq.read_table(SESSION, columns=["lap_number", "lap_time_s", "session_time_s"])
    laps  = t.column("lap_number").to_pylist()
    times = t.column("lap_time_s").to_pylist()

    segs = build_segments(laps)

    print(f"{'lap':>3}  {'frames':>6}  {'max_t':>9}  {'first_next':>10}  {'offset':>7}  {'corrected':>9}  {'frames/50Hz':>11}")
    for i, (lap_num, start, end) in enumerate(segs):
        max_t      = max(times[start:end])
        first_next = times[end] if end < len(times) else None
        offset     = abs(first_next) if (first_next is not None and first_next < 0) else 0.0
        corrected  = max_t + offset
        frame_dur  = (end - start) / 50.0
        m, s = divmod(corrected, 60)
        mf, sf = divmod(frame_dur, 60)
        fn_str = f"{first_next:.3f}" if first_next is not None else "  n/a"
        print(
            f"{lap_num:3d}  {end-start:6d}  {max_t:9.3f}  {fn_str:>10}  {offset:7.3f}  "
            f"{int(m)}:{s:06.3f}   {int(mf)}:{sf:06.3f}"
        )


if __name__ == "__main__":
    main()
