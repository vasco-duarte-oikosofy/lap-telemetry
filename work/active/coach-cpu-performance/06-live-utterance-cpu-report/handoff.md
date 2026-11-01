# Handoff — Slice 06: live utterance CPU-s

## Delivered

After every live SpeechQueue speech attempt, including failures, one flushed
stderr line prints without --debug:

```text
lap-telemetry: [coach] speech-cpu utterance=1 status=ok cpu_s=14.200 wall_s=23.100 synthesis_cpu_s=14.000 synthesis_wall_s=14.050 scope=process text="..."
```

Example numbers illustrate the format. IDs are sequential per queue/run; actual
spoken text is JSON-escaped onto one line. Stale pending drops produce no record.

- `cpu_s`: process CPU during speak(), including playback handling/wait interval.
- `wall_s`: total elapsed speak() time, including audible playback waiting.
- `synthesis_cpu_s` / `synthesis_wall_s`: Kokoro lazy load + synthesis, ending
  before playback. Includes cold load; reports fresh partial timing on failures.
  Other engines report na, not a misleading zero.
- `status=error` means speech failed, not successful delivery. Later attempts
  still work. Closed metrics pipes cannot kill the speech worker.

**Interpretation:** process_time counts native ONNX threads, but also concurrent
recorder/analysis work in the same process. It excludes simulator/child/external
LLM-server CPU and analysis before speech starts. This is cheap live evidence,
NOT exact per-job attribution or the controlled benchmark's full child-inclusive
lap CPU total. Wall playback waiting is not CPU work. Compare synthesis fields
rather than treating the whole speech wall interval as inference cost.

## Files and behavior

- `product/python/lap_telemetry/coach/speech_queue.py`: both initial and chained
  pending speech use the same reporting path. Existing stale-drop, nonblocking
  enqueue, error handling and queue shutdown behavior remain.
- `product/python/lap_telemetry/coach/tts_adapter.py`: optional last_synthesis_timing
  snapshot on the adapter; Kokoro records its own before-playback boundary.
  Existing speak() return stays None. Model/voice/speed/audio and bounded thread
  policy are unchanged. Direct standalone speak CLI does not use SpeechQueue;
  the always-visible report is for live-coach queue delivery.
- No polling, profiler, child-accounting hooks or new dependency. Only a few
  clock reads and one text line per attempted utterance. No new feature flag.
- `dev/scripts/test_live_utterance_cpu.py` + JS wrapper registered in the main
  suite and coach-cpu-performance feature suite.
- `docs/TTS_SETUP.md`: fields/scope and capturing race logs; stable spec updated.

## Evidence / verification

- Red first: artifacts/test-first-red.txt.
- Feature suite: **398 assertions / 12 scripts pass**.
- Full --pw: **1797 assertions / 74 scripts pass** using the existing temporary
  Windows ESM-path loader (pre-existing bug 20 is not modified).
- npm run build succeeds; product/dist/compare.html current and byte-unchanged.
- Real queued Kokoro cold/warm synthesis: artifacts/real-model-smoke.txt. Audible
  playback was replaced only by waveform capture for this hardware-safe smoke.
  Both outputs match slice 01's waveform exactly; hashes in audio-parity.json.
  This smoke is NOT a live race or audible-playback measurement.
- Deterministic tests cover CPU-vs-wall math, default visibility, both queue paths,
  stale drop, failure/retry, fresh stage boundaries, newline escaping, unchanged
  audio and closed output pipes. No precise timing assertions in parallel CI.

## User action

Restart the coach. Append to the user's normal PowerShell launch command:
`2>&1 | Tee-Object -FilePath coach-race.log`.
Bash equivalent: `2>&1 | tee coach-race.log`.
Keep the full log for lap/analysis context; CPU-only extraction in PowerShell:
`Select-String -Path coach-race.log -Pattern '\[coach\] speech-cpu'`.

Race evidence is still pending from the user. Slices 02–05 remain unimplemented.
No track/reference/session data or other performance option was changed. Commits
stay local on main, avoiding publication of pre-existing unrelated local commits.
