# Race log investigation — coach-race.log (2026-11-01 21:38)

## Verdict

**This log cannot answer the CPU question: it contains zero speech attempts.**
`grep -c 'speech-cpu' coach-race.log` → 0, and there is not one
`[coach] speech-cpu ...` record. The reason is in the log itself, 23 times:

```text
lap_telemetry.coach.live_fact_generator: No reference lap for track=Paul Ricard - 1A → skipping utterance
```

Every completed lap was skipped because Paul Ricard 1A had no reference lap at
the time. The 1:46.834 reference was exported later, in slice 24 (`3ef2ef9`) —
this run predates it. So the session measured nothing about coaching cost: the
lap-end work that did run was the comparison/utterance path aborting on a missing
reference, and no Kokoro synthesis or playback happened.

## What the log does contain

- `record_with_coach.py --coach-mode lap --coach-top 1 --utterance template`
  (PowerShell redirect, UTF-16LE with a NativeCommandError banner; decode with
  `iconv -f UTF-16 -t UTF-8 coach-race.log`).
- Two sessions on Paul Ricard 1A / DKR Engineering #4:ELMS25:
  `session_20261101T185113Z_..._practice` and
  `session_20261101T185240Z_..._quali` — exactly the pair that
  `24-paul-ricard-1a/artifacts/earlier-sessions.txt` scanned and rejected as
  slower than the race lap.
- 17 completed laps at ~1:47 (one 106.78 s), all coaching-silent. No frame-time,
  wall-time or CPU figures of any kind.

## Where the CPU target actually stands (committed benchmark, not this log)

| | CPU-s per lap-end event | vs original | vs 10% target (6.01) |
|---|---:|---:|---:|
| Original | 60.14 (warm) | 100% | 10.0× over |
| After slice 01 (`4ffe4b7`) | 14.20 | **23.6%** | 2.36× over |
| Slice-01 goal (≥50% less) | ≤30.07 | ✅ met at 76.4% less | — |
| Mission goal (≤10%) | ≤6.01 | ❌ not met | — |

Remaining work is **97.7% synthesis** (13.89 of 14.20 CPU-s). Reaching 10% means
synthesis must fall to ~5.69 CPU-s, i.e. avoid ~59% of synthesis work on real
utterances. Slice 02 (bounded exact-waveform cache) only helps when wording
repeats; slice 03 (runtime acceleration) is the path that can move the number
regardless of wording. Both are still planning-only.

Rough scaling for races (arithmetic, not measured): the benchmark lap is ~75 s,
so one event per lap is ~19% of a core averaged over a lap at 14.20 CPU-s, ~80%
before slice 01, and ~8% if the 6.01 budget is reached.

## How to collect the missing data

The blocker is gone — Paul Ricard 1A now resolves a reference and model. Re-run
the same command after restarting the coach (it caches reference/model lookups),
and keep the log in UTF-8 so it is greppable:

```bash
# git-bash / macOS / Linux
python record_with_coach.py --coach-mode lap --coach-top 1 > coach-race.log 2>&1
grep 'speech-cpu' coach-race.log
```

```powershell
# PowerShell 5.1 writes UTF-16 with `>`; use Out-File or cmd to keep it UTF-8
python record_with_coach.py --coach-mode lap --coach-top 1 2>&1 |
  Out-File -Encoding utf8 coach-race.log
```

Expected record per spoken lap (slice 06 format):

```text
lap-telemetry: [coach] speech-cpu utterance=1 status=ok cpu_s=... wall_s=... synthesis_cpu_s=... synthesis_wall_s=... scope=process text="..."
```

Interpretation reminder: `cpu_s` is whole-process CPU during speak() (includes
concurrent recorder/analysis work, excludes child processes and the sim), and
`synthesis_cpu_s` is the pre-playback Kokoro segment to compare against the
13.89 CPU-s benchmark figure. This live signal is coarser than the controlled
benchmark — for target claims keep using the benchmark, and use these records to
see whether real race utterances behave like the replay workload.
