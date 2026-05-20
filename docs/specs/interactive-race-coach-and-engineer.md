# Interactive Race Coach and Engineer

## Purpose

Build a local, live coaching and engineering companion for Le Mans Ultimate (LMU) using this repo's telemetry stack. The first useful product is a calm, concise voice that speaks during straights after a lap or corner group and explains where lap time is being gained or lost against a reference lap.

Example MVP call:

> "You lost three tenths mostly in turns 4 and 5. Minimum speed was 7 km/h lower through 4, and exit throttle was later in 5. Next lap, protect entry speed there."

Longer-term, the same system should also make race-engineer calls such as fuel-to-end, stint strategy, tire/weather implications, traffic gaps, and pit-window advice.

## Goals

- Live practice coaching first; post-session review and race strategy next.
- LMU first, using the existing recorder and shared-memory scaffolding.
- Speak only; no two-way voice in the initial architecture.
- Speak during straights, not mid-corner.
- Use cloud/online LLMs for reasoning/text generation, with provider/model configuration through a local harness-style adapter.
- Use local TTS added to this repo so the audio path is dependable during driving.
- Start LLM-first but keep deterministic analysis primitives so the LLM explains facts rather than inventing telemetry.
- Slice vertically so each slice validates one architecture risk with something usable on track.

## Windows runtime constraints

The target runtime is the same Windows machine that runs LMU. Every implementation slice must preserve these constraints:

- Product CLIs must run from PowerShell/CMD as normal Python commands; do not require Bash, WSL, Unix signals, `fork`, or POSIX-only paths.
- Use `pathlib.Path`, config files, and environment variables for paths/secrets. Do not hard-code `/tmp`, shell quoting assumptions, or case-sensitive path behavior.
- The live bus should start in-process with Python `queue.Queue`/threads so Windows firewall, port binding, and native extension installation do not block the MVP. If split-process streaming is later needed, prefer localhost HTTP/WebSocket with a pure-Python dependency and an explicit port/config.
- TTS must have a Windows-compatible backend. Candidate adapters should be wrapped behind one repo interface; acceptable MVP options include a Windows Piper executable, Windows SAPI/`pyttsx3`, or another locally installed Windows engine. Invoke external tools with `subprocess` argument lists, not `shell=True`.
- Audio queueing must not block the 50 Hz recorder loop; use a worker thread/process that can drop stale utterances.
- Any cloud model adapter must work behind normal Windows TLS/proxy settings and avoid Unix credential helpers as a required path.
- CI/dev tests may still use existing repo scripts, but each feature slice needs at least one documented Windows manual smoke command.

## Non-goals for the first MVP

- No speech recognition or driver questions.
- No fully autonomous setup engineering.
- No multi-sim abstraction beyond not blocking future rF2 support.
- No configurable personality/modes until the core loop is validated.
- No attempt to detect every driving mistake at once.

## Existing technology to reuse

| Existing asset | Reuse |
| --- | --- |
| `product/python/lap_telemetry/recorder/connect.py` | LMU/rF2 shared-memory connection, player selection, sim-agnostic `Frame`, 50 Hz estimated lap distance, track/vehicle names, throttle/brake/steering/speed/RPM, path lateral/track edge, surfaces, ABS/TC. |
| `record.py` | Long-running probe/poll loop, recordable-frame gate, lap-boundary awareness, track/vehicle session rotation. |
| `writer.py` | Parquet schema and sidecar format for durable session storage. |
| `product/data/reference-laps/*.parquet` | Baseline reference laps by track for live comparison. |
| `product/web/js/pipeline.js` | Segment building, partial/rolling lap rules, distance resampling, lap-time smoothing, delta-time lessons. Port the pure parts to Python for live use rather than importing browser JS. |
| `product/web/js/sLookup.js` | Distance-indexed lookup concept for comparing current samples against reference at the same `s`. |
| `product/web/js/apexAnnotations.js` and `apexMetrics.js` | Corner metadata shape and apex/track-edge analysis precedent. Extend this idea from apex distance to coaching zones. |
| `product/data/track-outlines/` | Track identity and geometry inputs; useful later for generating/validating corner zones. |
| `docs/ARCHITECTURE.md` | Current recorder/browser pipeline context. |

## Gaps / new components needed

1. **Live telemetry bus**
   - Add a second sink beside `SessionWriter`: each accepted `Frame` is also published to a live in-process stream.
   - The first implementation should be an in-process callback backed by a bounded `queue.Queue`; later it can become localhost HTTP/WebSocket if another process needs it.
   - Must not delay recorder polling or Parquet writes.

2. **Reference lap loader**
   - Resolve the active track to `product/data/reference-laps/<track>_time_*.parquet`.
   - Load required columns into memory at coach startup.
   - Produce a distance-indexed reference model: speed, lap time, throttle, brake, steering, gear, and optional position/edge channels.

3. **Track coaching model**
   - A versioned JSON artifact per track/layout with corner zones and speech-safe names.
   - Initial fields:
     - `track_id`, `layout_id`, `lap_length_m`
     - `corners[]`: `id`, `name`, `s_start_m`, `apex_s_m`, `s_end_m`, `apex_side`
     - optional `straight_zones[]`: where speech is allowed
   - Can initially be generated/edited from existing laps and apex annotations; later automate from repeated laps and track outline data.

4. **Live lap buffer and event detector**
   - Maintain current lap samples in memory.
   - Detect corner entry/apex/exit crossings by `lap_distance_m`.
   - Detect lap boundary and freeze the completed lap for analysis.
   - Detect safe speech windows: speed above threshold, low steering, current `s` inside configured straight zone or inferred post-corner straight.

5. **Deterministic analysis engine**
   - Computes factual observations against the reference lap.
   - MVP metrics:
     - per-corner minimum speed delta;
     - entry loss, apex/min-speed loss, exit loss using `delta_time_s(s)` over configured zones;
     - throttle pickup delay and exit speed delta as secondary facts.
   - Output should be structured JSON, not prose.

6. **LLM coach adapter**
   - Takes structured facts plus a strict prompt contract and returns one concise utterance.
   - Provider/model configured locally, similar in spirit to pi: e.g. config file/env vars with provider, model, base URL, API key source, temperature, max tokens.
   - The LLM must not read raw telemetry directly in MVP; it summarizes ranked facts.

7. **Local TTS service**
   - Adds local text-to-speech to this repo.
   - MVP can call a Windows-compatible installed engine or run a small local HTTP service, but the repo should own the adapter and queueing policy.
   - External process calls must use `subprocess` with argument arrays and timeouts, not shell-specific command strings.
   - Requirements: non-blocking, interrupt/skip stale utterances, volume/output-device configurable later.

8. **Coach orchestrator CLI**
   - New command such as `lap-telemetry coach --out-dir sessions --reference-dir product/data/reference-laps`.
   - Starts recorder polling, live analyzer, model adapter, and TTS queue.
   - For MVP it may also keep writing normal Parquet sessions so post-session debug remains possible.

9. **Race strategy analyzer**
   - Later component for fuel/laps remaining, pit windows, tire/weather, and gap/traffic calls.
   - Needs additional LMU shared-memory channels beyond current `Frame` if not already exposed: fuel remaining/capacity, fuel per lap, race session type, session time remaining, laps remaining, tire state, weather, standings, gaps, pit status.

## Proposed architecture

```text
LMU shared memory
   |
   v
Recorder connection (`Frame` @ 50 Hz)
   |------------------------------|
   v                              v
SessionWriter                 Live telemetry bus
(Parquet + sidecar)              |
                                  v
                         Live lap buffer / events
                                  |
                     |------------|------------|
                     v                         v
              Reference lap model       Track coaching model
                     |                         |
                     |------------|------------|
                                  v
                         Deterministic facts
                                  |
                                  v
                         LLM coach adapter
                                  |
                                  v
                           Local TTS queue
                                  |
                                  v
                              Headphones
```

The key boundary is between deterministic facts and generated speech. Telemetry comparison should be testable without any LLM. The LLM's job is prioritization and phrasing.

## Runtime event pipeline

1. Recorder probes LMU and emits recordable `Frame`s.
2. Session writer persists frames exactly as today.
3. Live bus copies each frame to the coach without blocking the recorder loop.
4. Lap buffer appends frames and indexes them by `lap_distance_m`.
5. Zone detector emits events:
   - `corner_exited(corner_id, lap_number)`
   - `lap_completed(lap_number)`
   - `speech_window_open(start_s, end_s)`
6. Analyzer computes facts for completed zones/laps against the reference.
7. Prioritizer selects the most useful 1-3 facts for the next utterance.
8. LLM adapter turns facts into concise engineer text.
9. TTS queue speaks only if the utterance is still relevant when a speech window is open.
10. Debug artifacts are written for each utterance: input facts, LLM text, timing, and whether audio was spoken/skipped.

## Data contracts

### `Frame` additions likely needed

The existing `Frame` is enough for the first live coaching slice. Race engineer slices likely need new nullable fields:

- `fuel_l`, `fuel_capacity_l`, `fuel_per_lap_l`
- `session_type`, `session_time_remaining_s`, `race_laps_total`, `race_laps_remaining`
- `position_class`, `position_overall`, `gap_ahead_s`, `gap_behind_s`
- `tire_wear_*`, `tire_temp_*`, `track_temp_c`, `rain_intensity`, `wetness`
- `pit_limiter`, `in_pit_lane`, `pit_stop_state`

Add these only when a slice consumes them.

### Track coaching JSON

```json
{
  "schema_version": "1",
  "track_id": "circuit-de-barcelona",
  "layout_id": "lmu-default",
  "lap_length_m": 4657.0,
  "corners": [
    {
      "id": "t4",
      "name": "turn 4",
      "s_start_m": 1320.0,
      "apex_s_m": 1395.0,
      "s_end_m": 1480.0,
      "apex_side": "right"
    }
  ],
  "straight_zones": [
    { "id": "after-t5", "s_start_m": 1600.0, "s_end_m": 1900.0 }
  ]
}
```

### Deterministic facts JSON

```json
{
  "type": "lap_coaching_summary",
  "track_id": "circuit-de-barcelona",
  "lap_number": 7,
  "lap_time_delta_s": 0.82,
  "top_losses": [
    {
      "corner_id": "t4",
      "corner_name": "turn 4",
      "phase": "minimum_speed",
      "loss_s": 0.18,
      "driver_value": 104.2,
      "reference_value": 111.4,
      "unit": "km/h",
      "confidence": "high"
    }
  ],
  "top_gains": [],
  "constraints": {
    "max_words": 35,
    "style": "calm_concise_engineer"
  }
}
```

## LLM behavior contract

- Input: facts JSON only, plus stable instruction prompt.
- Output: one utterance string and optional tags.
- Must mention no more than three coaching points.
- Must not invent corners, lap deltas, fuel values, gaps, or setup advice.
- Prefer actionable language: what happened, where, and what to try next.
- If confidence is low, say less or stay silent.

Example prompt rule:

> You are a calm race engineer. Summarize only the supplied facts. Do not add telemetry values not present in the JSON. Keep it under 35 words. Use turn names from the JSON.

## MVP vertical slice plan

Each slice should be independently useful and test one architecture risk. Stop after each green slice.

| Slice | User-visible result | Architecture risk validated |
| --- | --- | --- |
| 1. Offline fact generator | CLI compares one recorded lap to a reference and prints top corner minimum-speed losses from a hand-authored track model. | Can reproduce useful coaching facts deterministically from existing Parquet/reference data. |
| 2. Track coaching model loader | Validate/load one Barcelona LMU coaching JSON and map corner names/zones to telemetry distance. | The corner/straight data contract is sufficient and testable. |
| 3. LLM text adapter with canned facts | CLI sends sample facts to configured model and records the returned utterance. | Provider configuration and prompt contract work without telemetry complexity. |
| 4. Local TTS smoke path | CLI speaks a supplied text string through the local TTS adapter with queue semantics, with a documented PowerShell smoke command. | Audio can be produced locally on Windows without blocking. |
| 5. Live bus tap | Recorder runs normally and a coach tap receives frames, detects lap boundaries, and writes debug events; no LLM/TTS. | Live streaming does not disturb recording. |
| 6. Live after-lap spoken summary | At lap end, analyze completed lap, generate one LLM utterance, and speak it on the next straight. | End-to-end coaching loop works during practice. |
| 7. Corner-exit coaching | Speak one targeted note after selected corner exits when a safe straight is available. | Low-latency event timing and anti-chatter policies work. |
| 8. Fuel fact recorder channels | Extend `Frame` with fuel/race-state fields and print deterministic fuel-to-end facts. | LMU exposes enough race state through shared memory. |
| 9. Fuel engineer call | Speak "fuel laps remaining vs race laps remaining" using deterministic strategy facts plus LLM phrasing. | Strategy calls share the same fact-to-speech pipeline. |

## MVP acceptance target

At the end of slice 6, a driver can run one command before an LMU practice session. The system records the session as today and, after each completed lap, speaks one concise coaching message during a straight using reference-lap comparison. The message identifies the largest loss by turn and phase, starting with minimum turn speed and entry/exit loss.

## Testing strategy

- Unit-test pure analysis with tiny synthetic laps and real fixture snippets.
- Golden-test facts JSON for a known recorded session/reference pair.
- Contract-test the track coaching JSON validator.
- Mock LLM responses for orchestrator tests; keep live model calls behind explicit smoke scripts.
- Mock TTS in CI; keep real audio as a manual Windows smoke test.
- Add recorder live-bus tests with fake `Frame`s before touching real shared memory.
- Preserve the existing full-suite command for code slices: `bash scripts/test-summary.sh` and `npm run build`.
- For runtime slices, document a PowerShell command that runs on the LMU Windows machine without Bash/WSL.

## Risks and mitigations

- **LLM hallucination:** pass only ranked facts; enforce short output; log every input/output pair.
- **Too chatty while driving:** one utterance per lap first; cooldowns and stale-message dropping before corner-exit coaching.
- **Unsafe speech timing:** require configured/inferred straight windows and skip if the car reaches the next braking zone.
- **Reference mismatch:** include track/layout/vehicle checks where available; warn or stay silent if no reference matches.
- **Recorder timing regression:** live bus must be non-blocking and tested with fake slow subscribers.
- **Track metadata burden:** start with one manually-authored track model, then add generation tools only after the coaching loop proves valuable.
- **TTS installation friction:** isolate the TTS adapter so the engine can be swapped without changing analyzer/orchestrator code.

## Open questions for later slices

- Which local TTS engine is best for the target Windows/LMU machine?
- Should LLM configuration reuse pi auth/model files directly or just copy the provider concepts?
- How should generated track coaching models be reviewed and promoted into `product/data/`?
- What exact LMU shared-memory fields are available for fuel, tire, weather, and gaps?
- Should post-session review use the same facts JSON as live coaching, or a richer report schema?
