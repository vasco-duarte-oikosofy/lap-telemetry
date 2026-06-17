# Architecture and Code Review — GPT-5.5 — 2026-06-17

## Scope and method

This is an independent read-only review. Per request, I did **not** read the existing review document already present in this mission folder. I read the mission plan/prompt, `AGENTS.md`, `docs/ARCHITECTURE.md`, `docs/DESIGN.md`, `work/README.md`, production code under `product/python/lap_telemetry/` and `product/web/js/`, and the runtime-critical `dev/scripts/compute_delta_t.mjs` bridge.

Repository health checked during review:

- `npm run build` — **passed**, wrote `product/dist/compare.html`; git remained clean afterward.
- `bash scripts/test-summary.sh` — **failed**: `dev/scripts/test_repo_reorg_root_cleanup.js` reports unexpected tracked root directory `.pi`.

## Executive summary

The codebase has strong separation between recorder, analysis/coach, and browser comparison app, and the recent coach pipeline shows good fault-tolerance instincts: bounded queues, after-lap Parquet authority, explicit partial-lap guards, and deterministic template fallback. The largest risks are not design intent but architectural drift: hard file-size rule violations, duplicated schema definitions, production runtime dependence on a script living under `dev/`, and a few correctness/security edges around nullable booleans, HTML construction, and cross-thread live coach state.

## Findings

### P0 — Hard file-size rule violations in production modules

**Evidence:** `AGENTS.md` sets a hard ceiling of 437 lines per file. Current production files exceed it:

- `product/python/lap_telemetry/coach/template_adapter.py` — 653 lines
- `product/python/lap_telemetry/recorder/connect.py` — 494 lines
- `product/web/js/pipeline.js` — 448 lines
- `product/web/js/main.js` — 446 lines

**Impact:** This is a standing-rule violation and also reflects real cohesion pressure: `connect.py` holds frame schema, two sim adapters, probe logic, and distance integration; `main.js` still owns a large render orchestration path; `template_adapter.py` mixes phrase formatting, deduplication, and fuel phrasing.

**Recommendation:** Schedule a pure refactor slice before adding more behavior in these areas. Split along existing seams without rendered-output changes: recorder frame schema/helpers vs LMU/rF2 adapters; web render orchestration vs bin preparation; template phrase formatters vs selection/dedup logic.

### P0 — Fast suite currently fails because tracked `.pi/` conflicts with root cleanup guard

**Evidence:** `bash scripts/test-summary.sh` failed with `dev/scripts/test_repo_reorg_root_cleanup.js`. The guard permits only `dev`, `docs`, `product`, `scripts`, `var`, `vendor`, and `work` as tracked root directories (`dev/scripts/test_repo_reorg_root_cleanup.js:21-29`) and asserts no others (`dev/scripts/test_repo_reorg_root_cleanup.js:38-39`). `git ls-files .pi` shows `.pi/skills/session-compare/SKILL.md` and `.pi/skills/session-compare/scripts/compare_session.py` are tracked.

**Impact:** Every normal fast-suite run is red before product tests are considered, so agents may normalize failures or skip the suite. This also creates ambiguity about whether `.pi` is project-owned source, harness config, or local agent metadata.

**Recommendation:** Decide whether `.pi/` is now an allowed L1 folder and update the guard/docs accordingly, or move the tracked skill under an allowed tree. Do this as a focused repo-organization slice.

### P0 — ABS/TC false samples are recorded as null, not false

**Evidence:** LMU frames set `abs_active=True if tele_v.mABSActive else None` and `tc_active=True if tele_v.mTCActive else None` (`product/python/lap_telemetry/recorder/connect.py:310-311`). The schema declares nullable booleans (`product/python/lap_telemetry/recorder/writer.py:38-39`), while the UI treats these as binary panels/strips (`product/web/js/panelConfig.js:31-49`).

**Impact:** For LMU sessions, inactive ABS/TC is indistinguishable from missing/unknown data at the file-format boundary. That contradicts the intended binary channel semantics and can leak into analytics, resampling, and future consumers that distinguish `false` from `null`.

**Recommendation:** Record `bool(tele_v.mABSActive)` / `bool(tele_v.mTCActive)` for LMU and reserve `None` for sims or legacy files where the channel is absent/unknown. Add a regression around null counts for a synthetic inactive LMU frame.

### P1 — Production coach depends on a `dev/scripts` Node bridge at runtime

**Evidence:** `product/python/lap_telemetry/coach/js_pipeline.py` documents that it calls `dev/scripts/compute_delta_t.mjs` (`js_pipeline.py:7-8`), resolves repo root, and hardcodes `_JS_SCRIPT = _REPO_ROOT / "dev" / "scripts" / "compute_delta_t.mjs"` (`js_pipeline.py:18-20`). It launches `node` with that script (`js_pipeline.py:88-93`). `lap_comparator.py` imports and uses this path for normal comparison (`product/python/lap_telemetry/coach/lap_comparator.py:13`, `:225-236`).

**Impact:** The coach cannot be packaged or run as a product subtree without `dev/` and Node. This also blurs the repository boundary described by `work/README.md`: production code belongs in `product/`, development tooling in `dev/`.

**Recommendation:** Move the bridge into product code (for example `product/js/` or package data under `product/python/lap_telemetry/coach/`) or port the shared resampling contract to a packaged library. Keep `dev/scripts` wrappers only as test/CLI entry points.

### P1 — Lap snapshot flushing has cumulative I/O cost

**Evidence:** Every completed-lap callback writes a snapshot by reading all shard paths written so far and concatenating them (`product/python/lap_telemetry/recorder/writer.py:328-339`). Normal close/recovery also re-read and concatenate all shards (`writer.py:170`, `writer.py:370`).

**Impact:** During long live-coach stints, each lap snapshot becomes more expensive as the session grows, even though only one completed lap is needed. This can produce latency spikes exactly when after-lap coaching should respond quickly.

**Recommendation:** Keep a per-lap shard index or write lap-complete snapshots incrementally from the just-flushed table plus known lap rows, avoiding full-session re-read on every lap. Preserve the current authoritative-Parquet contract.

### P1 — Live coach shares mutable detector state across threads

**Evidence:** `CoachTap` runs analysis in a `ThreadPoolExecutor` while the bus worker continues feeding detectors. The pool thread reads `self._detector.current_lap_frames` for corner analysis (`product/python/lap_telemetry/coach/coach_tap.py:326`, `:341`) and writes `_pending_corner_utterance` (`coach_tap.py:211`, `:354`), while the bus worker reads/enqueues/clears the same pending field (`coach_tap.py:175-180`). No lock or snapshot boundary is visible.

**Impact:** Corner-exit coaching can analyze a moving list, hold/drop the wrong pending utterance, or race with lap-summary priority. These will be rare, timing-dependent live bugs.

**Recommendation:** Snapshot frame lists before submitting to the executor and protect pending utterance state with a small lock or single-thread ownership rule. Keep heavy compare/LLM work off the bus thread.

### P1 — Browser UI builds HTML from file/sidecar-derived strings without escaping

**Evidence:** Picker optgroups interpolate `entry.fileName`, `vehicleLabel`, and setup text into HTML strings (`product/web/js/pickers.js:21-39`) and then assign `innerHTML` (`pickers.js:44-46`). Session entries interpolate file names/status into an HTML template (`pickers.js:83-89`).

**Impact:** A malicious or malformed local file name/sidecar value can inject markup into a `file://` app. Even if the threat model is local files, this is avoidable and makes future sharing/import features riskier.

**Recommendation:** Build these DOM nodes with `document.createElement`, `.textContent`, and `.setAttribute`, or centralize an HTML escaping helper for any remaining template strings.

### P1 — “Standalone” browser build still has external CDN runtime dependencies

**Evidence:** The build script explicitly leaves `https://*` imports external (`dev/scripts/bundle.js:4-5`, `:70-72`). `pipeline.js` dynamically imports `https://cdn.jsdelivr.net/npm/hyparquet@1/+esm` and `hyparquet-compressors` at runtime (`product/web/js/pipeline.js:22`, `:35-36`). `main.js` also statically imports the same CDN modules (`product/web/js/main.js:55-56`).

**Impact:** `product/dist/compare.html` is a single file, but not fully offline/self-contained for Parquet loading. This conflicts with the practical expectation of a file:// telemetry tool used at a sim rig with unreliable/no internet, and duplicates dependency paths.

**Recommendation:** Bundle npm dependencies from `node_modules` into the dist file, or explicitly document “single file but requires CDN access”. Prefer one import path, not both static and dynamic CDN imports.

### P2 — Telemetry schema is duplicated across recorder, writer, and web loader

**Evidence:** The frame dataclass lists columns (`product/python/lap_telemetry/recorder/connect.py:30-80`), `_SCHEMA` repeats them for Parquet (`product/python/lap_telemetry/recorder/writer.py:17-58`), and web `COLUMNS` repeats the subset used by UI (`product/web/js/panelConfig.js:3-14`). The panel config warns that columns absent from `COLUMNS` are silently never loaded (`panelConfig.js:3-6`).

**Impact:** Adding recorder channels is error-prone: a field can be captured but not written, written but not loaded, or loaded but not shown. The current comments mitigate this socially, not mechanically.

**Recommendation:** Introduce a small schema manifest or code-generated constants for column names and optionality. Keep UI-specific panel definitions separate, but source column names from the shared manifest.

### P2 — Some LLM fallback behavior risks re-exposing reasoning

**Evidence:** When provider content is empty, `_call_via_openai` inspects the provider-specific `reasoning` field and extracts quoted text or the last sentence (`product/python/lap_telemetry/coach/llm_adapter.py:158-181`).

**Impact:** This is a pragmatic fallback, but it couples production behavior to chain-of-thought-ish provider internals. It can produce meta-output that downstream filters only partially catch.

**Recommendation:** Prefer treating empty content as provider failure and retrying with more tokens / a non-reasoning model. If the fallback stays, fence it behind a config flag and test it against explicit non-coaching reasoning examples.

## Strengths observed

- Clear top-level architecture: recorder writes standard Parquet + sidecar; browser and coach consume files rather than SHM directly.
- Segment-based lap handling and partial-lap guards are thoughtful and reflect real sim restart/SHM edge cases.
- The live coach has good isolation instincts: bounded queue, worker thread, executor for heavy work, and graceful skip-on-failure paths.
- Tests are broad and fast when the root-cleanup guard is green; the `[PASS]`/`[FAIL]` protocol and feature lists are valuable.
- The web UI has been progressively modularized (`panelConfig`, `panels`, `cursor`, `circuitMap`, track heatmap modules), making future extraction from `main.js` plausible.
