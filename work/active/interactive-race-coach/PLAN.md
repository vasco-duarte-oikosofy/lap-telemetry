# Mission: Interactive Race Coach and Engineer

**Spec:** [`docs/specs/interactive-race-coach-and-engineer.md`](../../docs/specs/interactive-race-coach-and-engineer.md)

**Goal:** Build a local, live coaching and engineering companion for Le Mans Ultimate (LMU) using this repo's telemetry stack. The first useful product is a calm, concise voice that speaks during straights after a lap or corner group and explains where lap time is being gained or lost against a reference lap.

**Feature tests:** `bash scripts/test-summary.sh --feature interactive-race-coach`

---

## Vertical slices

| Slice | Status | Vertical outcome |
|---|---|---|
| `01-offline-fact-generator` | ✅ Complete | CLI compares one recorded lap to a reference and prints top corner minimum-speed losses from a hand-authored track model |
| `01b-track-model-from-reference-lap` | ✅ Complete | Generate a reviewable car-specific track coaching model from a valid reference lap using telemetry-derived apex proxies |
| `01c-determine-entry-exit-phase-algorithm` | ✅ Complete | Replace fixed 30 m entry/exit offsets with brake, throttle, and speed-trace detection to determine where corner entry begins and exit ends |
| `02-track-coaching-model-loader` | ✅ Complete | Validate/load one Barcelona LMU coaching JSON and map corner names/zones to telemetry distance (delivered in slice 01 as `track_model.py`) |
| `03-llm-text-adapter` | ✅ Complete | CLI sends sample facts to configured model and records the returned utterance |
| `04-local-tts-smoke-path` | ✅ Complete | CLI speaks a supplied text string through the local TTS adapter with queue semantics |
| `05-live-bus-tap` | 🔲 Not started | Recorder runs normally and a coach tap receives frames, detects lap boundaries, and writes debug events |
| `06-live-after-lap-spoken-summary` | 🔲 Not started | At lap end, analyze completed lap, generate one LLM utterance, and speak it on the next straight |
| `07-corner-exit-coaching` | 🔲 Not started | Speak one targeted note after selected corner exits when a safe straight is available |
| `08-fuel-fact-recorder-channels` | 🔲 Not started | Extend `Frame` with fuel/race-state fields and print deterministic fuel-to-end facts |
| `09-fuel-engineer-call` | 🔲 Not started | Speak "fuel laps remaining vs race laps remaining" using deterministic strategy facts plus LLM phrasing |

---

## Per-slice template

### Slice N: `<slice-name>`

**Outcome.** `<brief outcome>`

**Steps:**
1. Write the failing test first
2. Write the minimal code to make it pass
3. Run `bash scripts/test-summary.sh` — must pass
4. Run `npm run build` — must succeed
5. Commit — small, green, on `main`

---

## MVP acceptance target

At the end of slice 6, a driver can run one command before an LMU practice session. The system records the session as today and, after each completed lap, speaks one concise coaching message during a straight using reference-lap comparison. The message identifies the largest loss by turn and phase, starting with minimum turn speed and entry/exit loss.
