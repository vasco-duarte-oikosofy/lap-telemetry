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

   **Current implementation details** (slice 01, `lap_comparator.py`):

   The `compare_laps()` function in `lap_telemetry.coach.lap_comparator` produces `LapComparisonFacts`. Key design decisions:

   - **Per-corner, per-phase analysis.** Each corner is analyzed for up to four phases: `minimum_speed`, `entry`, `exit_brake` / `exit_throttle` (merged into single `exit` when within 3 m). Each phase that exceeds its threshold produces a separate `CornerLoss` item. A single corner can appear with multiple phases.
   - **Capped output.** Only the top 3 losses and top 3 gains are reported (`losses[:3]` / `gains[:3]`), aligned with the LLM contract's `max_words: 35` constraint.
   - **Rough time proxy for losses only.** `loss_s` for losses is computed as `speed_delta_kph / 100.0`, a ranking heuristic — not a true time-loss calculation. **Gains** use real delta-time from the JS pipeline (see below).
   - **Corners only, no straights.** Time lost on straights (e.g. lower top speed, later throttle application) is not reported because the analysis iterates only over `track_model.corners`.
   - **Confidence levels.** `minimum_speed` phase gets `"high"` confidence when `speed_delta > 2.0 kph`, otherwise `"medium"`. `entry` and `exit` phases always get `"medium"`.
   - **Thresholds.** `minimum_speed` losses are reported when `speed_delta > 0.5 kph`; `entry`/`exit` losses when `speed_delta > 1.0 kph`.
   - **Phase detection algorithm (slice 01c):** Entry, exit, and minimum speed are detected per corner using the driver's throttle, brake, and speed traces. All thresholds are configurable via `PhaseDetectionThresholds` with sensible defaults.
     - **Entry:** Searches from `(s_start_m − 200 m)` toward `apex_s_m`. Prefers `throttle_lift` (first drop below 0.9 after sustained ≥ 0.9). Falls back to `speed_peak` (fastest speed in the search range). The 200 m look-back is essential because braking zones regularly start well before the formal corner zone boundary.
     - **Minimum speed:** Unchanged — minimum of `speed_kph` within `[s_start_m, s_end_m]`. Now also reports `driver_apex_distance_m` and `reference_apex_distance_m` (the positions where each lap hits minimum speed).
     - **Exit:** Searches from `apex_s_m` toward `s_end_m`. Detects `exit_brake` (first brake-off below 0.01 after sustained > 0.05) and `exit_throttle` (first full throttle ≥ 0.95 after sustained < 0.95). When within 3 m, merged into a single `exit`. Falls back to zone boundary when neither channel is available.
     - **Look-back:** `find_entry_point()` and `find_brake_point()` search 200 m before `s_start_m` by default, because throttle lift and braking for corners regularly start 50–100 m before the zone boundary.

   **Known simplifications to address in later slices:**
   - **Entry/exit phase detection (slice 01c — done):** Fixed 30 m offsets are no longer used. Entry is detected at the throttle lift point (or speed local maximum as fallback), searching up to 200 m before the corner zone. Exit has two sub-phases: `exit_brake` (brake fully released) and `exit_throttle` (back to full throttle); when within 3 m of each other they are merged into a single `exit` phase. Speed local maximum is not used for exit. All thresholds are configurable via `PhaseDetectionThresholds`. The `minimum_speed` phase reports both `driver_apex_distance_m` and `reference_apex_distance_m` so the LLM can surface apex offsets (late/early apex). Multi-apex corners remain an open question.
   - **Multi-apex corners:** Need definition. A single `Corner` zone with multiple local speed minima (e.g. a chicane or double-apex sweeper) is currently treated as one corner with one apex. The entry/exit detection algorithm may misidentify the throttle/brake transitions in these cases. A later slice should define whether multi-apex corners are split into separate zones, merged with a dominant apex, or handled with a sub-phase structure. Imola's Variante Alta / Variante Bassa are good test cases.
   - **Apex offset (open question):** The `minimum_speed` phase now reports `driver_apex_distance_m` and `reference_apex_distance_m` — the distances at which each lap hits its minimum speed within the corner zone. When these differ, the driver apexed early or late. A large offset (e.g. 9 m late) is coaching-meaningful on its own ("you missed the apex"). Whether to surface this as a separate `apex_offset` phase, as metadata on `minimum_speed`, or leave it for the LLM prompt to interpret is still open. The current implementation (slice 01c) delivers both raw distances on `minimum_speed`; the LLM prompt contract decides how to present it. On multi-apex corners (chicanes), both driver and reference minima may be ambiguous — testing with Imola is needed before committing to a final design.
   - **Gain time measurement (slice 01c.2 — done for minimum_speed, exit, and entry):** All gain phases now use real delta-time from the JS telemetry pipeline (`product/web/js/pipeline.js`) instead of the `speed_delta / 100.0` heuristic. Each phase measures delta-time over its **own phase boundary**, avoiding double-counting between phases:
     - **minimum_speed gain:** `delta_t[straight_end] - delta_t[apex]`
     - **exit gain:** `delta_t[straight_end] - delta_t[exit_point]`
     - **entry gain:** `delta_t[apex] - delta_t[entry_point]`

     The JS pipeline (steps 1–6: computeKeepIndices, smoothLapTime, resample, forward-clamp, computeDeltaT, smoothDt) guarantees that the delta-t values match the web UI exactly. Contract tests verify against user-confirmed Barcelona fixture values (+436 ms at 2158 m, +331 ms at 2439 m).

     Key design principle: **each phase measures within its own boundary.** Entry ends at apex (minimum_speed takes over). Exit ends at the straight end (next corner's entry). This prevents the same advantage from being counted in two phases.

   - **Gain distance deltas (slice 01c.2 — partially done):** `minimum_speed` and `exit` gains now report `gain_end_distance_m` (the straight-end distance where the gain measurement stops). **Still deferred:** `entry_distance_delta_m` and `exit_distance_delta_m` (comparing driver vs reference phase distances) require resampling the reference lap's pedal channels and running phase detection on them. Three spec documents define the algorithms:
     - [`[work folder]/interactive-race-coach/01c-determine-entry-exit-phase-algorithm/01c.2_exit_gains_improvements/apex_min_speed_gain_algorithm.md`](apex_min_speed_gain_algorithm.md) — `apex_offset_m`, delta-time gains for minimum_speed + exit, `gain_end_distance_m`. **Done.**
     - [`[work folder]/interactive-race-coach/01c-determine-entry-exit-phase-algorithm/01c.2_exit_gains_improvements/entry_gain_algorithm.md`](entry_gain_algorithm.md) — entry gains now use `delta_t[apex] - delta_t[entry]` (revised). `entry_distance_delta_m` still deferred.
     - [`[work folder]/interactive-race-coach/01c-determine-entry-exit-phase-algorithm/01c.2_exit_gains_improvements/exit_gain_algorithm.md`](exit_gain_algorithm.md) — `exit_distance_delta_m` (deferred).
   - Replace `speed_delta / 100.0` with actual integrated time loss (gains are done; losses still use heuristic).
   - **Connected corners / chicanes:** Two corners that share a single throttle-lift point (e.g. t2/t3 at Barcelona) need investigation. The entry detection currently finds the same entry distance for both, which is correct (one lift for a chicane), but the entry→apex delta_t can give opposite signs for each corner because the delta_t window is different. Imola's Variante Alta / Variante Bassa are good test cases for deciding whether to merge connected corners or report them separately.
   - Decide whether each corner should appear at most once (picking worst phase) or keep the current per-phase detail.
   - Add straight-zone time-loss analysis.
   - Add throttle/brake/gear delta facts.

**Future coaching fact candidates** (available Parquet channels not yet used for coaching, prioritized by coaching value):

| Priority | Fact | Why it matters | Required data |
|----------|------|----------------|---------------|
| 🔴 Highest | Integrated time loss per phase | Replace the `speed_delta / 100.0` heuristic; sum across phases should approximate the real lap time delta | `speed_kph`, `lap_distance_m` |
| 🔴 Highest | Brake point distance comparison | Most actionable coaching input: "you braked 20 m later than reference into turn 3" | `brake_norm`, `lap_distance_m` |
| 🟡 High | Throttle lift / full-throttle distance comparison | "you lifted 15 m later" / "you got back on power 25 m later" — comparing driver vs reference at the same phase transitions. **In progress (slice 01c.2):** `entry_distance_delta_m` and `exit_distance_delta_m` will provide this for gains; losses will follow the same pattern. | `throttle_norm`, `lap_distance_m` |
| 🟡 High | Cumulative carry-over flag | Slow exit from turn 3 causes slow entry into turn 4; coach should say "carry-over from turn 3" rather than blaming turn 4 | `speed_kph` (cross-corner dependency) |
| 🟢 Medium | Gear selection at apex | "You were in 3rd where the reference used 2nd" — wrong gear = slower exit or less engine braking | `gear` |
| 🟢 Medium | Peak brake intensity | Distinguish late-but-hard braking from early-but-soft braking; area under brake curve between entry and apex | `brake_norm` |
| 🟢 Medium | Trail braking depth | How far past the apex brake pressure persists; directly relates to car balance and exit speed | `brake_norm` |
| 🔵 Lower | Track position / racing line | Compare driver's line through a corner vs reference using lateral path data | `path_lateral_m` |
| 🔵 Lower | Steering smoothness | Oscillation or mid-corner corrections suggest understeer/oversteer | `steering_norm` |
| 🔵 Lower | Slip angle / TC / ABS activation | Oversteer indication, traction control interventions, ABS triggering | `slip_angle_*`, `tc_active`, `abs_active` |

6. **LLM coach adapter**
   - Takes structured facts plus a strict prompt contract and returns one concise utterance.
   - Provider/model configured locally, similar in spirit to pi: e.g. config file/env vars with provider, model, base URL, API key source, temperature, max tokens.
   - The LLM must not read raw telemetry directly in MVP; it summarizes ranked facts.

7. **Local TTS service**
   - Adds local text-to-speech to this repo.
   - MVP can call a Windows-compatible installed engine or run a small local HTTP service, but the repo should own the adapter and queueing policy.
   - External process calls must use `subprocess` with argument arrays and timeouts, not shell-specific command strings.
   - Requirements: non-blocking, interrupt/skip stale utterances, volume/output-device configurable later.

   **TTS engine research and selection:**

   The TTS adapter must run locally on the same Windows machine running LMU, without internet, without contending for CPU/GPU with the sim. Engine selection must support cross-platform development (macOS) and production deployment (Windows) with identical voice output.

   | Engine | Type | Latency (short utterance) | Voice quality | macOS | Windows | Same voice same output | Notes |
   |--------|------|---------------------------|---------------|-------|---------|----------------------|-------|
   | **Piper** | Neural VITS (ONNX) | ~100-200 ms | Good, natural | ✅ | ✅ | ✅ bit-identical | Pre-built binary, ~30 MB per voice, runs on CPU. Used by Home Assistant, Rhasspy, Wyoming ecosystem. |
   | **Sherpa-ONNX** | Neural runtime (loads Piper models + others) | ~50-100 ms first chunk | Good | ✅ | ✅ | ✅ | Python + C++, can load Piper `.onnx` models. More setup than standalone Piper. |
   | **Kokoro TTS** | StyleTTS variant | ~200 ms GPU, slower CPU | Very good | ✅ | ✅ | ✅ | Small model (~80 MB), gaining community traction. Slower than Piper on CPU. |
   | **F5-TTS** | Flow-matching | ~300 ms GPU | Near-human | ✅ | ✅ | ✅ | Excellent voice cloning from 5-second clip. Needs GPU for real-time. |
   | **Coqui TTS / XTTSv2** | VITS, multi-arch | ~1-2 s CPU | Very good | ✅ | ✅ | ✅ | Heavy ML stack (torch), GPU preferred. Voice cloning from 3 s clip. |
   | **pyttsx3 / SAPI** | Windows system voice | ~10 ms | Robotic | ⚠️ uses `say` | ✅ uses SAPI | ❌ different voices | Zero-install fallback only. macOS voice != Windows voice. |
   | **Edge TTS** | Cloud (Microsoft) | ~200 ms | Excellent | ✅ | ✅ | ✅ | Requires internet. Fragile during race sessions. |
   | **OpenAI TTS API** | Cloud | ~500 ms | Excellent | ✅ | ✅ | N/A | Paid, requires internet + API key per utterance. |

   **Primary: Piper.** Rationale:
   - Runs entirely offline on CPU alongside LMU without stealing resources.
   - Same `.onnx` voice model produces identical audio on macOS and Windows — dev on Mac, ship on Windows, same result.
   - ~30+ pre-trained English voices in the Piper voice catalog; pick one, download the model file, point config at it.
   - Sub-200 ms latency for ≤35 word utterances, fast enough to speak during a straight.
   - Home Assistant chose Piper specifically because it runs on a Raspberry Pi alongside other work — our constraint (gaming PC running LMU) is less demanding.
   - Simple invocation: `echo "text" | piper --model voice.onnx --output_file out.wav`

   **Fallback: pyttsx3/SAPI.** Zero-install Windows fallback if Piper is not installed. Sounds robotic but will always produce audio. Only used on Windows (macOS uses a different engine). Not suitable for cross-platform dev/test.

   **Future upgrade path: Kokoro or F5-TTS.** The adapter interface should abstract the engine so Kokoro (for better quality on GPU machines) or F5-TTS (for voice cloning from a real race engineer) can be swapped in later. The adapter owns the synthesis call; the engine is a plugin, not the core.

   **Voice catalog workflow:**
   1. Browse voices at [piper.voice.vvoice](https://piper.voice.vvoice/).
   2. Pick a calm, clear English voice (e.g., `en_US-lessac-medium`).
   3. Download the `.onnx` + `.json` model files to `product/data/tts-voices/`.
   4. Point config at the model file path.
   5. Switch voices by changing the config path — no code changes.

   **Voice cloning consideration:** F5-TTS and Coqui XTTSv2 can clone a voice from a 3-5 second reference clip. This would allow recording a real race engineer and using their voice. Requires GPU for real-time and is deferred to a later slice.

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
