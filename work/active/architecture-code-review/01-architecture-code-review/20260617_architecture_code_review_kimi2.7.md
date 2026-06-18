# Architecture & Code Review — 2026-06-18

**Reviewer:** Kimi K2.7 Code (cloud) via pi  
**Scope:** `product/python/lap_telemetry/` (recorder + coach), `product/web/js/` (non-data modules), `dev/scripts/compute_delta_t.mjs`.  
**Out of scope:** data files under `product/data/`, vendored submodules, existing review documents in this folder.  

---

## 1. Executive summary

The codebase is a coherent, working telemetry recorder + lap-comparison + live-coaching stack. Architecture docs (`ARCHITECTURE.md`, `DESIGN.md`) accurately describe the recorder and web analyzer, but they are silent about the now-largest subsystem: the live race coach. The build is green, but the fast test suite is red on a pre-existing repo-hygiene guard.

The most important new finding is a **correctness bug in fuel-status classification** (`fuel_facts.py`) that will mis-classify practice/qualifying/race sessions, breaking fuel-engineer calls. Several other issues are maintainability / DRY / hard-ceiling violations; none break functionality today but they accumulate risk as the coach layer grows.

| Priority | Count | Themes |
|----------|-------|--------|
| P0 | 3 | test-suite health, fuel session-type bug, Node-runtime dependency for core coach analysis |
| P1 | 9 | duplicated helpers, dead imports, over-size files, fragile full-track detection, LLM/TTS config gaps |
| P2 | 7 | naming inconsistencies, dead code, comment drift, minor edge cases |

---

## 2. Repository health

```text
$ npm run build
✓ Build complete — product/dist/compare.html refreshed

$ bash scripts/test-summary.sh
FAILED — 882 passed, 1 of 30 scripts failed in 4.6s
dev/scripts/test_repo_reorg_root_cleanup.js: unexpected tracked root directories: .pi
```

The single failure is unrelated to product code; see **P0-1**.

**Line-count inventory (production code only):**

| Layer | Files | Lines |
|-------|-------|-------|
| `product/python/lap_telemetry/recorder/` | 5 | ~1,500 |
| `product/python/lap_telemetry/coach/` | 30 | ~7,100 |
| `product/python/lap_telemetry/` shared | 4 | ~500 |
| `product/web/js/` (non-data modules) | ~45 | ~4,900 |
| `dev/scripts/compute_delta_t.mjs` | 1 | ~180 |
| **Total** | | **~14,200** |

Four production files exceed the 437-line hard ceiling from `AGENTS.md`:

1. `product/python/lap_telemetry/recorder/connect.py` — ~494 lines
2. `product/python/lap_telemetry/recorder/writer.py` — ~410 lines (close, but under)
3. `product/python/lap_telemetry/coach/template_adapter.py` — ~652 lines
4. `product/python/lap_telemetry/coach/lap_comparator.py` — ~396 lines (under)
5. `product/web/js/main.js` — ~446 lines
6. `product/web/js/pipeline.js` — ~448 lines
7. `product/web/js/ui.js` — ~404 lines

The ceiling is genuinely violated by `connect.py`, `template_adapter.py`, `main.js`, `pipeline.js`, and `ui.js`.

---

## 3. Strengths

- **Single-source Δt truth.** The coaching pipeline deliberately shells out to `dev/scripts/compute_delta_t.mjs`, which imports the web's `pipeline.js`. This guarantees that the spoken lap summary and the web UI see identical Δt traces. The decision is well documented in `js_pipeline.py`, `DESIGN.md`, and the RCA documents.
- **Defensive recorder design.** `SessionWriter` writes the sidecar from session start and refreshes it on every shard flush, so a hard kill still leaves recoverable metadata. `recover_orphaned_shards()` handles `.partN.parquet` leftovers.
- **Clean feature-flag discipline.** `appState.js` keeps every map/heatmap/apex feature behind an explicit flag, with `mapWalkingSkeleton` the only on-by-default one. Completed slices can be left off until acceptance is signed off.
- **Good failure isolation in live coach.** `QueuedBus` drops oldest frames rather than blocking the recorder; `SpeechQueue` drops stale utterances; `CoachTap` runs heavy analysis (`compare_laps`, LLM, TTS) on a `ThreadPoolExecutor(max_workers=1)` so the bus worker never blocks.
- **Prompt engineering is explicit and versioned.** `prompt_templates.py`, `short_prompt.py`, and `corner_exit_prompt.py` encode TTS rules, same-corner deduplication, gain-first ordering, and distance-delta interpretation. The deterministic `template_adapter.py` mirrors those rules.

---

## 4. Findings

### P0 — Correctness / health risks

#### P0-1. Fast test suite is red: `.pi/` is tracked but not allow-listed

- **Location:** root `.gitignore`, `dev/scripts/test_repo_reorg_root_cleanup.js`
- **Evidence:** `bash scripts/test-summary.sh` fails with `AssertionError: unexpected tracked root directories: .pi`. The directory contains `skills/session-compare/SKILL.md` and `scripts/compare_session.py` — a legitimate pi-harness skill, but neither in the test's `allowedRootDirs` nor in `.gitignore`.
- **Impact:** Every agent that runs the fast suite sees a red result, which erodes trust and can mask real regressions. It also violates the AGENTS.md "commit cadence: small and green" rule.
- **Recommendation:** Either add `.pi/` to the test allow-list (if project-level skills are intentional) or move the skill to `~/.pi/agent/skills/` and remove the tracked directory. Do not leave the suite red.

#### P0-2. Fuel session-type mapping is wrong

- **Location:** `product/python/lap_telemetry/coach/fuel_facts.py:14-24`
- **Evidence:**
  ```python
  SESSION_TYPE_MAP = {
      0: "practice",
      1: "test",
      2: "qualifying",
      3: "race",
      4: "other",
      5: "other",
      6: "other",
      7: "other",
      8: "other",
  }
  ```
  This contradicts both `DESIGN.md` §3 / `ARCHITECTURE.md` and `writer.py:_session_type_slug`:
  - documented values: `0=test day, 1-4=practice, 5-8=qualifying, 9=warmup, 10-13=race`
  - `_session_type_slug`: `10-13 → race`, `5-8 → quali`, `0-4 or 9 → practice`
- **Impact:** `LiveFuelFactGenerator._should_speak()` returns `false` for most real race sessions because `facts.session_type` will be `"practice"` or `"other"` instead of `"race"`. Fuel-engineer calls (slice 08) will be silently suppressed in the wrong sessions.
- **Recommendation:** Replace `SESSION_TYPE_MAP` with the documented mapping, or reuse `_session_type_slug` if the dependency direction can be made sensible. Add a unit test that exercises every `mSession` value 0-13.

#### P0-3. Core coach analysis depends on Node.js at runtime

- **Location:** `product/python/lap_telemetry/coach/lap_comparator.py:170-190`, `product/python/lap_telemetry/coach/js_pipeline.py:53-60`
- **Evidence:** `compare_laps()` calls `run_js_pipeline()`, which spawns `node dev/scripts/compute_delta_t.mjs`. The Node script imports `../../product/web/js/pipeline.js` and runs the full 6-step Δt pipeline.
- **Impact:** The offline/CLI coaching path (`lap-telemetry compare-laps`, `generate_utterance`, `live_coach`) silently requires Node.js. A user who installs only the Python package cannot run lap comparison or live coaching. This is an architecture-level deployment constraint that is not surfaced in `README.md` or `ARCHITECTURE.md`.
- **Recommendation:** Document the Node dependency prominently. Consider packaging the pipeline logic as a small bundled JS file (`dev/scripts/compute_delta_t.mjs` already exists; it could be distributed with the package) and validating `node` availability at coach startup with a clear error message.

---

### P1 — Maintainability / architecture concerns

#### P1-1. Three-way schema sync is untested and undocumented

- **Location:** `product/python/lap_telemetry/recorder/connect.py:Frame`, `product/python/lap_telemetry/recorder/writer.py:_SCHEMA`, `SessionWriter.append()`
- **Evidence:** `Frame` has ~40 fields; `_SCHEMA` lists the same ~40 columns in the same order; `append()` has a 43-line field list. There is no test or generated code that ensures they stay in sync. Adding a new field requires editing three places plus `frames_to_parquet.py`.
- **Impact:** Low-probability, high-cost silent failure: a drift means a column is written as empty or with the wrong data type.
- **Recommendation:** Generate `Frame`, `_SCHEMA`, and the append block from one canonical column table, or add a unit test that reflects on `Frame`, `_SCHEMA`, and `writer.py` to confirm every `Frame` field has a matching schema field and append line.

#### P1-2. `template_adapter.py` exceeds the hard ceiling and is highly repetitive

- **Location:** `product/python/lap_telemetry/coach/template_adapter.py` — ~652 lines
- **Evidence:** The file contains ~20 near-mirror functions (`_loss_minimum_speed` / `_gain_minimum_speed`, `_loss_entry` / `_gain_entry`, etc.) plus detail-clause builders. The loss/gain logic is identical except for sign and a few directional words.
- **Impact:** Hard-ceiling violation; any coaching-rule change must be applied twice; easy to introduce loss/gain asymmetry bugs.
- **Recommendation:** Parameterise the phrase table by `(phase, is_gain)` and consolidate detail-clause builders. A targeted refactor should bring the file well under 437 lines.

#### P1-3. `connect.py` exceeds the hard ceiling

- **Location:** `product/python/lap_telemetry/recorder/connect.py` — ~494 lines
- **Evidence:** Contains `_BaseConnection`, `LMUConnection`, `RF2Connection`, helpers, and a large `Frame` dataclass. The `read_frame()` methods in LMU/rF2 are ~70-line near-duplicates.
- **Impact:** Hard-ceiling violation; the sim-specific `read_frame` methods are hard to keep in parity.
- **Recommendation:** Extract a shared `_build_frame()` helper that takes a generic scoring/telemetry/vehicle struct and returns a `Frame`. Move the `Frame` dataclass to its own module. Both moves should bring `connect.py` under 437 lines.

#### P1-4. `_track_slug` is implemented in at least three places

- **Location:** `product/python/lap_telemetry/recorder/writer.py`, `product/python/lap_telemetry/coach/reference_resolver.py`, `product/python/lap_telemetry/coach/track_model_resolver.py`
- **Evidence:** Each file has its own `unicodedata.normalize("NFKD", ...)` slugify implementation.
- **Impact:** Divergence risk: a track-name edge case fixed in one place will not propagate to the others, causing reference/model lookup to fail for a track that the recorder can write.
- **Recommendation:** Move `_track_slug` to a shared module (e.g., `lap_telemetry/names.py`) and import it everywhere.

#### P1-5. `main.js`, `ui.js`, and `pipeline.js` exceed the hard ceiling

- **Location:** `product/web/js/main.js` (~446), `product/web/js/pipeline.js` (~448), `product/web/js/ui.js` (~404)
- **Evidence:** `main.js` contains render orchestration, map-state helpers, and debug hooks. `pipeline.js` mixes resampling, Δt, geometry helpers, and nice-tick logic. `ui.js` mixes file loading, sidecar handling, drag-reorder, and event wiring.
- **Impact:** Files doing multiple jobs; harder to test and reason about.
- **Recommendation:** Split `main.js` into `render.js` and `debug.js`; split `pipeline.js` into `resample.js` + `geometry.js`; split `ui.js` into `fileLoader.js` + `panelDrag.js`. This is mostly file moves, not rewrites.

#### P1-6. `renderPanel` has a dead / broken first loop

- **Location:** `product/web/js/panels.js:40-52`
- **Evidence:**
  ```javascript
  for (const { key } of Object.values(bins)) {
    if (key) { ... }
  }
  ```
  `Object.values(bins)` returns `Float64Array`s, which have no `.key` property, so `key` is always `undefined` and the loop does nothing. A second per-channel loop later in the function does the real work.
- **Impact:** Dead code; misleading about how y-range is computed; could hide a real bug if someone later tries to rely on the first loop.
- **Recommendation:** Remove the loop or change it to `Object.keys(bins)` if the intent was to compute a global y-range.

#### P1-7. `trackHeatmapController.js` hard-codes an approximate full-track check

- **Location:** `product/web/js/trackHeatmapController.js:160`
- **Evidence:** `const isNowFullTrack = rangeKey === null || rangeKey === '0:4650'; // approximate`
- **Impact:** Any track whose length is not ~4,650 m will fail this heuristic, so auto-zoom reset behavior will be inconsistent.
- **Recommendation:** Compare numeric `start === 0 && end >= maxDist` (or `end === currentMaxDist`) instead of string-matching an approximate literal.

#### P1-8. `live_coach.py` and `generate_utterance.py` duplicate utterance-mode dispatch

- **Location:** `product/python/lap_telemetry/coach/live_coach.py`, `product/python/lap_telemetry/coach/generate_utterance.py`
- **Evidence:** Both files contain near-identical `if utterance_mode == TEMPLATE / LOCAL_LLM / CLOUD_LLM` blocks that build `LLMConfig`, call `_call_llm`, and handle errors.
- **Impact:** A change to local-LLM wiring (e.g., custom base URL, model name) must be made in both places.
- **Recommendation:** Extract a `build_utterance_fn(config, mode, local_model)` factory that returns the right callable; use it in both CLIs.

#### P1-9. `llm_adapter.py` default Ollama base URL is misleading

- **Location:** `product/python/lap_telemetry/coach/llm_adapter.py:190-195`
- **Evidence:** `_provider_base_url("ollama")` returns `https://ollama.com/v1`. Local Ollama typically runs at `http://localhost:11434/v1`.
- **Impact:** A user who selects provider `ollama` without setting `base_url` will get network errors against a non-existent cloud endpoint.
- **Recommendation:** Return `None` for Ollama and emit a clear error telling the user to set `base_url` (or use `http://localhost:11434/v1` as a sensible default and document it).

---

### P2 — Minor cleanups and tech debt

#### P2-1. `main.js` carries several dead imports

- **Location:** `product/web/js/main.js`
- **Evidence:** `parquetRead`, `parquetMetadataAsync`, `compressors`, `renderHeatmapSegments`, `renderMapLegend` are imported but never used in `main.js`.
- **Impact:** Misleading about ownership; no runtime cost (esbuild tree-shakes).
- **Recommendation:** Remove unused imports.

#### P2-2. `ui.js` imports `pickers.js` twice

- **Location:** `product/web/js/ui.js:8-13`, `product/web/js/ui.js:18-20`
- **Evidence:** The same symbols are re-exported at the top and then imported again later.
- **Impact:** Minor clutter.
- **Recommendation:** Keep one import block.

#### P2-3. `panelConfig.js` `COLUMNS` comment is misleading

- **Location:** `product/web/js/panelConfig.js:4-17`
- **Evidence:** Comment says "Any column needed by a panel or tooltip MUST be listed here", but `scoring_last_lap_time_s`, `pos_x_m`, `pos_z_m`, `abs_active`, `tc_active`, and outline channels are needed but absent. They are loaded separately in `ui.js`.
- **Impact:** The comment implies COLUMNS is the single source of truth, but it is not.
- **Recommendation:** Update the comment to say COLUMNS is the default panel set, and all additional columns are requested in `ui.js:loadFile`.

#### P2-4. `trackOutlineManifest_backup.js` is committed

- **Location:** `product/web/js/trackOutlineManifest_backup.js`
- **Evidence:** A backup file with ~97 lines sits next to the real manifest.
- **Impact:** Clutter; risk of stale data being used by accident.
- **Recommendation:** Remove if no longer needed, or move to a scratch directory outside source control.

#### P2-5. Activity-strip loop reads one index past the array

- **Location:** `product/web/js/panels.js:167-184`
- **Evidence:** The loop condition is `i <= stripBins.length`, which evaluates `stripBins[stripBins.length]` (undefined) on the final iteration. The `on` guard handles it, but the code is fragile.
- **Impact:** No current bug, but easy to break in a refactor.
- **Recommendation:** Iterate `i < stripBins.length` and flush the final run after the loop.

#### P2-6. `coach_config.py` simple TOML fallback is incomplete

- **Location:** `product/python/lap_telemetry/coach/coach_config.py:_parse_simple_toml`
- **Evidence:** The hand-written fallback parser only supports flat sections, strings, ints, floats, and bools. It will silently mangle arrays or tables if a user runs on Python <3.11.
- **Impact:** Python 3.11+ is common, so this is rarely exercised; still a footgun.
- **Recommendation:** Either require Python ≥3.11 and drop the fallback, or raise a clear error when the fallback sees unsupported syntax.

#### P2-7. Static-outline module naming is inconsistent

- **Location:** `product/web/js/static*OutlineData.js`
- **Evidence:** Some files are named `staticCircuitBarcelonaOutlineData.js`, others `staticFujiSpeedway_outlineOutlineData.js` (with an embedded `_outline`).
- **Impact:** Minor friction when adding a new track.
- **Recommendation:** Normalise to one convention, e.g., `static<slug>OutlineData.js`.

---

## 5. Follow-up slice backlog (suggested)

| Slice | Goal | Addresses |
|-------|------|-----------|
| `repo-hygiene-pi` | Resolve `.pi/` tracking so `bash scripts/test-summary.sh` is green. | P0-1 |
| `fuel-session-type-fix` | Correct `SESSION_TYPE_MAP`; add per-value tests. | P0-2 |
| `coach-node-dependency-doc` | Document Node requirement; add startup check with clear error. | P0-3 |
| `refactor-recorder-schema` | Single source of truth for `Frame` / `_SCHEMA` / append list. | P1-1 |
| `refactor-template-adapter` | Parameterise loss/gain phrase builders; file under 437 lines. | P1-2 |
| `refactor-connect` | Extract `_build_frame` + `Frame` module; file under 437 lines. | P1-3, P1-4 |
| `web-js-file-split` | Split `main.js`/`pipeline.js`/`ui.js` into smaller, single-job files. | P1-5, P2-1, P2-2 |
| `web-panels-cleanup` | Fix dead y-range loop and activity-strip off-by-one. | P1-6, P2-5 |
| `heatmap-controller-heuristic` | Replace `rangeKey === '0:4650'` with numeric full-track check. | P1-7 |
| `coach-utterance-factory` | Single factory for TEMPLATE/LOCAL/CLOUD dispatch. | P1-8 |

---

## 6. Method notes

- Reviewed `AGENTS.md`, `docs/ARCHITECTURE.md`, `docs/DESIGN.md`, `work/README.md`.
- Read every production Python module under `product/python/lap_telemetry/` and every non-data JS module under `product/web/js/`, plus `dev/scripts/compute_delta_t.mjs`.
- Did **not** read existing review files in this mission folder, per instruction.
- Ran `npm run build` and `bash scripts/test-summary.sh` (fast suite, no `--pw`) to characterise health.
- Playwright suite was intentionally not run because this slice changes no UI or product code.
