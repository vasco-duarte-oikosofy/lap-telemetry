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
| `05-live-bus-tap` | ✅ Complete | Recorder runs normally and a coach tap receives frames, detects lap boundaries, and writes debug events |
| `06-live-after-lap-spoken-summary` | ✅ Complete | At lap end, analyze completed lap, generate one LLM utterance, and speak it on the next straight |
| `07-corner-exit-coaching` | ✅ Complete | Speak one targeted note after selected corner exits when a safe straight is available |
| `08-fuel-fact-recorder-channels` | ✅ Complete | Extend `Frame` with fuel/race-state fields and print deterministic fuel-to-end facts |
| `09-fuel-engineer-call` | ✅ 1ab96b7 | Speak "fuel laps remaining vs race laps remaining" using deterministic strategy facts plus LLM phrasing |
| `10-facts-inspector` | ✅ Complete | Add `--print-facts` flag to `generate_utterance.py` — prints facts JSON to stdout and exits without calling the LLM |
| `11-low-latency-utterance` | ✅ e14d71e | Add `--utterance-mode` options: `local-llm` (small local model, short prompt), `template` (deterministic phrase fill, no LLM), `cloud-llm` (current default). Also `--coach-mode off` for record-only |
| `12-coach-short-corner-names` | ✅ 4968f39 | Coach speaks the curated `short_name` when one exists (`Curva Alboreto (Parabolica)` → `Parabolica`, `Variante della Roggia 1` → `Roggia 1`), else falls back to `name`. `Corner.short_name` + `Corner.display_name` in `track_model.py`, wired into the facts and the corner-exit event. Initially exercised on Monza; corpus-wide curation delivered in slice 13 |
| `13-curate-spoken-corner-names` | ✅ 328f1c2 (refactor bd32dbb) | Added 340 aliases across all 33 models / 453 corners, retaining numbered subdivisions and spelling 10+ for TTS. Guarded writer audits all non-alias fields unchanged. No geometry or map-label changes. |

| `14-spoken-name-exceptions` | ✅ 093c04a | Keep Curva Grande and Descida do Lago (including 1/2) in full as explicit exceptions to shortening. |

**Slices 13–14 tests:** `bash scripts/test-summary.sh --feature coach-short-corner-names`

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
