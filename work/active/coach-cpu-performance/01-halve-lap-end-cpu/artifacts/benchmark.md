# Before/after benchmark — lap-end local CPU

## Result

| Metric | Original | Bounded session | Reduction |
|---|---:|---:|---:|
| Median cold event CPU (3 fresh processes) | 63.546875 s | 15.328125 s | 75.88% |
| Median warm event CPU (9 events) | 60.140625 s | 14.203125 s | 76.38% |
| Median cold wall time | 18.607 s | 16.476 s | 11.45% |
| Median warm wall time | 15.237 s | 15.202 s | Essentially unchanged |
| Worst sampled synthesis CPU peak (100% = one core) | 848.08% | 104.28% | 87.70% |
| Same peaks as % of this 16-logical-CPU machine | 53.00% | 6.52% | 87.70% |
| Median warm idle-tail CPU, 1 s observation | 0.328125 s | 0 s | No measured spinning tail |

The <=50% CPU-work target passes for **both cold and warm events**, not just
synthesis. Warm cost is **23.62% of the original**, not yet 10%.

## Where the CPU goes

These are medians per stage (so their sum need not equal the event-total median).

| Warm stage | Original CPU | Bounded CPU | Bounded wall |
|---|---:|---:|---:|
| Real Parquet comparison + template text | 0.500000 s | 0.328125 s | 0.312 s |
| Real Kokoro synthesis | 59.265625 s | 13.890625 s | 13.893 s |
| Idle tail | 0.328125 s | 0 s | 1.009 s |

**About 97.7% of remaining event work is synthesis.** Removing all comparison
cost would save only about 2.3% of the remaining budget on this session.
The 10%-of-original budget is about **6.01 CPU-s/event**. With comparison around
0.33 CPU-s, synthesis needs to fall from ~13.89 to ~5.69 CPU-s, or avoid roughly
59% of synthesis work on representative real utterances (not replay duplicates).

## Workload and controls

- Original production code: main at `1bd0890` before any CPU-policy changes.
  Original/new adapter SHA256 and input/model/voice hashes are in the reports.
- Real source: `sessions/session_20261101T114510Z_grand-prix-of-long-beach_lmu_practice.parquet`,
  lap 11, Ferrari AF Corse 2026 #50:LM. The complete session file is read via
  LiveFactGenerator.generate_from_parquet; reference/model resolution is real.
- Each campaign: **3 fresh Python processes**, each performing one cold and
  three warm lap events. Same lap, full facts and utterance every time.
- Same 16-logical-CPU Windows machine; Python 3.10, Kokoro 0.6.1, ORT 1.23.2,
  NumPy 2.2.6, PyArrow 24.0.0 and psutil 7.2.2. Dependencies were installed in
  the local venv BEFORE measuring the original production adapter.
- The existing int8 model and bm_daniel voice at speed 1.05 are unchanged.
- Deterministic TemplateAdapter stands in for a nondeterministic cloud reply.
  No paid/cloud request is made. The live cloud setting is NOT changed.
- Real synthesis is performed, not mocked or disabled. Only audible playback
  is replaced by capture to float32 arrays. Array validation/storage and a 1 s
  idle tail are included in both measured workloads.
- All 12 facts records and utterances match. **All 12 waveforms are exactly
  sample-identical**, 212992 samples at 24000 Hz (8.874667 s). No quality,
  speaking-speed, text-length or content tradeoff. See audio-parity.json.

## Accounting

Primary CPU is time.process_time (Python + all native threads) plus exact
completed-child CPU. Node work is NOT omitted: Windows GetProcessTimes reads
Popen's open process handle after exit; Unix uses reaped-child getrusage.
Timing excludes worker-process startup and report/provenance serialization.
Kokoro remains lazy: cold model/library loading IS inside the cold TTS event.

An external psutil sampler observes the entire process tree in >=200 ms windows
for indicative peaks. Its overhead is outside the measured coach process.
Windows venv launchers create an extra Python process: original max_process_threads
counts only the launcher and is **not used** in any result. The final sampler
reports tree-wide thread counts. CPU peaks already used the whole tree in both.

Simulator/rendering, recorder flush, audible playback and remote/local external
LLM-server work are excluded. These are local coach CPU measurements, **not a
claim of 76% better game FPS**, and are specific to this hardware and workload.

## Evidence and rerun

- `baseline.json`, `optimized.json`: original campaign reports, unedited.
- `baseline/trial-0.json` … `trial-2.json` and optimized equivalents: complete
  per-event CPU/wall samples, facts, text, audio metadata and provenance.
- `comparison.json`: passed CPU/latency/parity gates; `audio-parity.json`: hashes
  of the raw float32 arrays (not the NPY container).
- Raw waveforms and logs remain locally under ignored `var/tmp/coach-cpu/`.
  They were moved there from the reports' original var/coach-cpu paths; the
  comparator resolves supplied campaign directories, not stale provenance paths.

```bash
export PATH="$PWD/.venv/Scripts:$PATH" PYTHONUTF8=1
python -m pip install kokoro-onnx psutil
python dev/scripts/benchmark_coach_cpu.py \
  --out var/tmp/coach-cpu/new-campaign --trials 3 --events 4
python dev/scripts/compare_coach_cpu.py \
  var/tmp/coach-cpu/before var/tmp/coach-cpu/new-campaign \
  --out var/tmp/coach-cpu/new-comparison.json
```

To remeasure original code, use a detached worktree at `1bd0890`, copy these
benchmark helpers into its dev/scripts, and provide the identical source
session and local model/voice files there. Use the SAME venv/dependencies and
explicit --session path. Never restore old production files over live work.

The partial after/ and after-final/ campaigns are excluded entirely: the first
was interrupted by the harness timeout, the second hit a Windows sampler-marker
sharing violation. The final complete campaign is after-verified/. Marker writes
now tolerate concurrent Windows reads. No successful trials were cherry-picked.
