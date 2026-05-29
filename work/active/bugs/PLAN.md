# Mission: Bug Investigations

Active bug investigations. Each bug gets its own numbered slice folder.

---

## Bugs

| Slice | Bug | Status |
|---|---|---|
| `01-lusail-loading-error` | Large Lusail sessions throw "Maximum call stack size exceeded" in the loader | ✅ Moved to `work/completed/` |
| `02-ollama-auth` | Ollama cloud auth failure — 401 from `api.ollama.com/v1` with key set | ✅ Moved to `work/completed/` |
| `03-llm-reasoning-leak` | LLM outputs chain-of-thought instead of utterance — prompt guardrails too weak | ✅ Fixed in `50528e5` → moved to completed |
| `04-contradictory-speed-coaching` | LLM coaches "slow down" when driver speed > reference speed at apex | ✅ Fixed in `f38512f` |
| `05-utterance-ordering-lag` | Utterance arrives 1–2 laps late — 53s LLM round-trip is architectural latency, not a queue bug | 📋 Retired → superseded by slice 11 (`low-latency-utterance`), moved to completed |
| `06-ghost-lap-comparator-crash` | 1-frame session-end laps crash compare_laps() with ValueError: max() arg is an empty sequence | ✅ Fixed in `50528e5` → moved to completed |
| `07-coaching-reads-dropped-frames` | Coaching compares against incomplete live frame buffer — should read from the recorded session Parquet instead | ✅ Fixed in `f764b18` → moved to completed |
| `08-coaching-data-source-mismatch` | compare.html reads full recorded Parquet; coaching pipeline reads live bus frames — same JS pipeline code, different (and inferior) data source | ✅ Fixed in `f764b18` (by bug07 option C) → moved to completed |
| `09-utterance-readability` | Utterances hard to parse when spoken: no gain/loss lead-in, gains/losses interleaved, dropped subject | ✅ Fixed in `addb36a` → moved to completed |
| `10-lap-time-s-undercount` | `max(lap_time_s)` per segment underestimates true lap time by 0–180 ms — `lap_time_s` resets to negative at `lap_number` change | ✅ 10b+10c fixed: `scoring_last_lap_time_s` persisted (10b) and `extract_reference_lap.py` updated (10c `43771f7`); remaining consumers tracked as bug 13 |
| `11-schema-column-drift` | Multiple files maintain their own column lists duplicating `_SCHEMA` — adding a column silently breaks any file not updated (crash in `frames_to_parquet.py`, silent miss in JS load gate) | ✅ Fixed in `db81fc6` → moved to completed |
| `12-partial-lap-bogus-coaching` | One stale cross-lap frame inflates `max(current_dist)` to full-track length; session-end frozen frames fill remaining bins at wrong speed → compare_laps produces 15 s phantom gains on partial laps | ✅ Fixed in `1175f88` |
| `13-lap-time-undercount-full-stack` | `max(lap_time_s)` undercount (77–176 ms) still used by `lap_comparator.py`, `summary.py`, and `pipeline.js` `annotateSegments()` — `extract_reference_lap.py` was fixed in 10c but no other consumer was updated | ✅ Fixed in `58f9f8b` → moved to completed |
| `14-on-lap-flushed-wrong-shard` | Bug-12 fix calls `flush_shard()` before `append()` at lap boundaries → `_completed_lap_numbers` is empty at flush time → `on_lap_flushed` fires on the *next* shard (containing the new lap's data, not the completed lap's) → every coached lap either times out or gets "no frames for requested lap" | ✅ Fixed in `ad47c65` → moved to completed |
| `15-gain-first-truncation-ignores-losses` | `TemplateAdapter` (not LLM) uses gain-first ordering; word-limit truncation drops sentences from the end → losses are always the first to be cut → driver hears only gains even on +2 s laps. Also: `_gain_exit()` fallback claims "You carried more speed through" even when driver exit speed was lower. | ✅ Fixed in `f1a83ef` → moved to completed |
| `16-slow-pitstop-lap-passes-guard` | Lap 13 (84.42 s, 18.5% over 71.242 s reference) passes the distance-coverage guard (full lap) but the pitstop causes a 12.5 s phantom Δt at turn 4 → `compare_laps` would coach "You lost twelve seconds at turn 4". Need a duration guard for implausibly slow laps. | ✅ Fixed — pending live confirmation before moving to completed |
