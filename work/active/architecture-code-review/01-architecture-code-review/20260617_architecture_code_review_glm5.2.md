# Architecture & Code Review — lap-telemetry

**Review date:** 2026-06-17
**Reviewer:** GLM 5.2 (via pi)
**Scope:** `product/python/lap_telemetry/` (recorder + coach), `product/web/js/`
(comparison app), and the runtime-critical `dev/scripts/compute_delta_t.mjs` bridge.
Read-only review — no production code was modified.
**Method:** Read `AGENTS.md`, `docs/ARCHITECTURE.md`, `docs/DESIGN.md`; walked every
production module; characterised repo health (`npm run build`, fast test suite);
compiled findings with `file:line` evidence.

---

## 1. Executive summary

The codebase is in good shape. It has a clear three-layer architecture (recorder →
coach → web), strong defensive engineering with documented rationale, and a serious
testing culture. Most files respect the 200-line default ceiling, and nearly every
non-obvious decision carries a "why" comment.

The review surfaced **two standing-rule violations** that should be addressed soon, a
**central architectural tradeoff** that deserves to be made explicit, and a
**handful of DRY/duplication clusters** that are good candidates for focused
refactor slices. None of the findings are correctness emergencies; the product works
and ships (build green).

**Top items at a glance**

| # | Severity | Finding |
|---|---|---|
| 1 | P0 | Repository is **red**: `test_repo_reorg_root_cleanup.js` fails — `.pi/` is git-tracked but neither allow-listed nor gitignored |
| 2 | P0 | **4 production files exceed the 437-line hard ceiling** (worst: `template_adapter.py` @ 652) |
| 3 | P1 | Live coach **shells out to Node per lap** for Δt (`js_pipeline.py`); hard runtime dependency on Node + brittle path resolution |
| 4 | P1 | **Utterance-mode dispatch duplicated 3×**; local Ollama config inlined 3× |
| 5 | P1 | `LiveFactGenerator.generate()` ≈ `generate_from_parquet()` (~80% duplicated) |
| 6 | P1 | `connect.py` `LMUConnection.read_frame` ≈ `RF2Connection.read_frame` (~80-line near-duplicate) |
| 7 | P1 | Recorder **three-way schema sync** (`Frame` ↔ `_SCHEMA` ↔ `append`) — drift = silent data bug |
| 8 | P1 | Per-lap snapshot is **O(n²) in shard reads**; `.snap*` files orphaned on hard kill |
| 9 | P1 | `compare_laps` is a ~150-line function with 3 repeated phase blocks + magic-number fallback |
| 10 | P2 | Dead/duplicate hyparquet imports in `main.js`; dynamic `import()` in `ui.js` handlers |
| 11 | P2 | `format_time` dead branches; stale `_backup.js`; slice demo scripts in `product/python/` |

---

## 2. Repository health (as measured during review)

| Check | Result |
|---|---|
| `npm run build` | ✅ Succeeds; `product/dist/compare.html` refreshed (1.9 MB) |
| `bash scripts/test-summary.sh` (fast, no `--pw`) | ❌ **882 passed, 1 script failed** — see P0-1 |
| Root-level `tests/` dir (forbidden by AGENTS) | ✅ Absent |
| `product/data/` curation | ✅ 18 reference laps, 37 coaching-model files across many tracks |

> Note: the Playwright suite was **not** run (no UI code was touched; this is a
> documentation-only review). The single fast-suite failure is pre-existing and
> unrelated to any change made for this review (this review changed only files under
> `work/active/architecture-code-review/`).

---

## 3. Architecture assessment

### 3.1 Layer map (actual vs documented)

`docs/ARCHITECTURE.md` describes a recorder → analysis → web flow. The shipped code
matches it and adds a substantial **coach** layer not in that doc:

```
SIM SHM → recorder/connect.py (Frame) → record.py → writer.py (Parquet+JSON)
                                          │
                                          └─ bus.py (LiveBus / QueuedBus) ──┐
                                                                              ▼
                                            coach/coach_tap.py (orchestrator, dual-path)
                                              ├─ lap_detector.py        (after-lap)
                                              ├─ corner_exit_detector.py (turn-by-turn)
                                              ├─ live_fact_generator.py  (→ lap_comparator → js_pipeline)
                                              ├─ live_fuel_fact_generator.py
                                              └─ speech_queue.py → tts_adapter.py
                                            coach/live_coach.py (CLI wiring)
                                            coach/generate_utterance.py (offline CLI)

Parquet files → web (main.js + pipeline.js + panels/cursor/circuitMap/…) → dist/compare.html
```

The coach layer is the largest and newest; `docs/ARCHITECTURE.md` predates it and now
under-describes the system. **Recommendation:** refresh ARCHITECTURE.md to include
the coach pipeline and the dual-path (Parquet-authoritative vs bus-buffer) design.

### 3.2 Recorder layer — `recorder/`

Well-factored and robust. `connect.py` (Frame dataclass + sim probe), `record.py`
(poll loop, lap/track/vehicle rotation, idle + sim-restart detection), `writer.py`
(shard + atomic sidecar + orphan recovery), `bus.py` (sync + threaded bounded queue).

Strengths: speed-integrated distance with pause detection (`connect._estimate_dist`),
oldest-first-drop bounded bus (`bus.py`), atomic sidecar writes (`writer._write_sidecar`),
orphan `.partN.parquet` recovery, no `mInRealtime` gate (documented why).

Concerns: see P1-6 (three-way schema sync), P1-8 (snapshot O(n²) + orphan `.snap*`),
P1-6/P1 duplication in `connect.py`.

### 3.3 Coach layer — `coach/`

The most complex layer. The dual-path design (after-lap summaries read the
authoritative session Parquet via a flush callback; corner-exit notes use the live
frame buffer) is sound and well-documented in `coach_tap.py`'s module docstring.
Non-blocking by construction: bus worker thread + `ThreadPoolExecutor(max_workers=1)`.

Concerns: see P1-3 (Node bridge), P1-4 (utterance dispatch dup), P1-5 (generator dup),
P1-9 (`compare_laps` length), P2-7 (reasoning-model extraction fragility), P2-9
(provider set duplicated).

### 3.4 Web layer — `web/js/`

Clean module decomposition: `pipeline.js` (pure transforms), `panels.js`/`cursor.js`/
`circuitMap.js` (render), `appState.js` (state container), `ui.js` (events),
`utils.js`, `constants.js`, `panelConfig.js`, plus the heatmap + outline subsystem.
Most modules are 80–300 lines.

Strengths: Δt by direct `lap_time_s` subtraction with a documented rationale (avoids
the old ∫1/speed phantom error), distance-aligned shared x-axis, CSS-variable lap
colours, persisted zoom/colours/panel-order in `localStorage`, feature-flag gated
rollout.

Concerns: see P0-2 (`main.js`/`pipeline.js` over ceiling), P2-10 (dead imports +
dynamic `import()` in handlers), and a test-coupling comment in `main.js:299`
("don't add DOM nodes so legacy tests counting 8 panels still pass") — a backwards-
compat constraint worth noting as mild tech debt.

### 3.5 Cross-cutting: the JS↔Python Δt bridge (P1-3)

`lap_comparator.compare_laps` does **not** compute Δt in Python. It shells out to
`node dev/scripts/compute_delta_t.mjs` (`js_pipeline.py:run_js_pipeline`), which
imports the *same* `computeKeepIndices → smoothLapTime → resample → forward-clamp →
computeDeltaT → smoothDt` from `product/web/js/pipeline.js`. A pure-Python
`resample.py` exists but is explicitly "for synthetic test data that doesn't need the
full JS pipeline" (`resample.py` module docstring).

This is a deliberate, defensible tradeoff — **single source of truth for the headline
metric** (web UI and coach must agree) — and the project's Δt RCA
(`work/archived-plans/rca-deltat-phantom-error.md`) shows that metric was painful to
get right. The costs, however, are real and should be made explicit:

- The Python coach has a **hard runtime dependency on Node.js** and the ability to
  `subprocess.run(["node", …])` once per analysed lap (30 s timeout).
- Every lap serialises several full column arrays (speed, lap_time, distance,
  throttle, brake × 2) to JSON over stdin and parses JSON over stdout — megabytes
  per lap.
- Repo-root is resolved by counting parents: `_REPO_ROOT = Path(__file__).resolve()
  .parent.parent.parent.parent.parent` (`js_pipeline.py`). Relocating the file
  silently breaks the coach.
- There is **no contract test** asserting `compute_delta_t.mjs` output equals a
  Python reference, so the "parity" guarantee is informal.

**Recommendation (pick one):** (a) keep the bridge but harden it — validate `node` is
present at coach startup, resolve the script via a manifest constant, and add a
contract test that the bridge matches a frozen Python reference fixture; or
(b) port the 6 steps to Python and drive *both* the web and the coach from one
canonical implementation (the web already bundles `pipeline.js`, so the JS stays the
web's source of truth, but the coach stops depending on Node). Option (a) is the
lower-risk incremental path.

---

## 4. Findings — prioritized

### P0 — standing-rule violations / health

#### P0-1  Repository is red on a repo-hygiene guard

- **Location:** `dev/scripts/test_repo_reorg_root_cleanup.js:39`; tracked files
  `.pi/skills/session-compare/SKILL.md`, `.pi/skills/session-compare/scripts/compare_session.py`.
- **Evidence:** `git ls-files .pi` returns 2 files; `.pi` is **not** in
  `allowedRootDirs` (`dev, docs, product, scripts, var, vendor, work`) and **not** in
  `.gitignore`. Fast suite: `FAILED — 882 passed, 1 of 30 scripts failed`;
  `AssertionError: unexpected tracked root directories: .pi`.
- **Impact:** Violates AGENTS.md ("no failing tests may remain"). Any agent running
  the suite sees a red baseline, masking real regressions.
- **Recommendation:** Decide intent for `.pi/` (the agent-harness skills dir). Either
  add `.pi/` to `.gitignore` and `git rm --cached -r .pi`, or add `.pi` to
  `allowedRootDirs` in the guard. This is a one-line decision but it must be made so
  the suite is green again.

#### P0-2  Four production files exceed the 437-line hard ceiling

AGENTS.md: *"Hard ceiling: 437 lines per file. No file may exceed this, ever."*

| File | Lines | Over by |
|---|---|---|
| `product/python/lap_telemetry/coach/template_adapter.py` | 652 | +215 |
| `product/python/lap_telemetry/recorder/connect.py` | 494 | +57 |
| `product/web/js/pipeline.js` | 448 | +11 |
| `product/web/js/main.js` | 446 | +9 |

- **Impact:** Hard-rule violation. `template_adapter.py` is the worst by far.
- **Recommendation:** See P1-2/P1-6 for `template_adapter.py`/`connect.py` (refactor
  also shrinks them). `pipeline.js` (+11) and `main.js` (+9) are just over — extract
  one helper each (e.g. `renderAll`'s resample loop in `main.js`, and the Δt/keep
  block in `pipeline.js`) to get under the ceiling. (Eight `dev/scripts/` test/tool
  files also exceed 437, up to 788; if the rule is meant to apply to `dev/` too, those
  need a separate pass — but test fixtures are a lower priority than production code.)

---

### P1 — maintainability / architecture (good slice candidates)

#### P1-3  Live coach shells out to Node per lap for Δt
See §3.5. `js_pipeline.py` → `subprocess.run(["node", compute_delta_t.mjs])` per lap,
with 5×-`.parent` path resolution and no parity contract test.

#### P1-4  Utterance-mode dispatch duplicated 3×; local Ollama config inlined 3×

- **Locations:**
  - `generate_utterance.py:189-209` — `if UtteranceMode.TEMPLATE / elif LOCAL_LLM / else CLOUD_LLM`.
  - `live_coach.py:225-290` — `utterance_fn`, `corner_utterance_fn`, `fuel_utterance_fn`, each re-implementing the same mode switch.
  - Local Ollama `LLMConfig(provider="ollama", model=…, api_key_env="OLLAMA_API_KEY",
    base_url="http://localhost:11434/v1")` constructed inline at
    `generate_utterance.py:198`, `live_coach.py:202`, `live_coach.py:269`.
- **Impact:** Adding a fourth utterance mode or changing the Ollama base URL requires
  edits in three places. Behaviour can drift between the offline CLI and the live
  coach for the same mode.
- **Recommendation:** A single `make_utterance_fn(mode, llm_config, local_model)`
  factory returning a callable, plus a `local_ollama_config(model)` helper. Each
  caller (`generate_utterance.main`, `live_coach.main`) builds the fn once.

#### P1-5  `LiveFactGenerator.generate()` ≈ `generate_from_parquet()` (~80% duplicated)

- **Location:** `live_fact_generator.py:87` vs `:217`.
- **Evidence:** Both methods do: resolve reference lap → resolve track model →
  `compare_laps` → `top_losses = facts.top_losses[:top]` →
  `facts.constraints["max_words"] = 20 if top==1 else 35` → call utterance fn →
  `_is_meta_output` guard → timing `print(...)`. Only the data source differs
  (frames→temp parquet vs session parquet with `lap_number` filter) plus the
  partial-lap guard.
- **Recommendation:** Extract a shared `_finish(track_name, facts, top,
  utterance_fn, timing_label)` and have both public methods feed it.

#### P1-6  `connect.py` `read_frame` duplication + three-way recorder schema sync

- **Location:** `connect.py` — `LMUConnection.read_frame` (line 267) and
  `RF2Connection.read_frame` (line 380) each build an ~80-line `Frame(...)`,
  differing only in `abs_active`/`tc_active`/`fuel_l*` and the rF2 absence of those.
- **Separate but related — recorder three-way sync:** the `Frame` dataclass
  (`connect.py:24`, ~50 fields), `_SCHEMA` (`writer.py:24`, ~45 fields), and
  `SessionWriter.append` (`writer.py`, 43 `b[col].append(frame.field)` lines) must
  all agree. Adding a `Frame` field without updating `_SCHEMA` **and** `append` =
  a silent column-data bug (column present but empty, or schema mismatch on write).
  There is no test asserting the three agree.
- **Recommendation:** Extract `_build_frame(scor_v, tele_v, sim, *, abs_active, …)`
  so `connect.py` drops under 437 and the two sims share one Frame builder. For the
  schema sync, drive `_SCHEMA`/`append` from the `Frame` dataclass fields, or add a
  test that constructs a `Frame` with every field populated and asserts the written
  Parquet has every column non-null.

#### P1-8  Per-lap snapshot is O(n²) in shard reads; `.snap*` orphaned on hard kill

- **Location:** `writer.py:_write_lap_snapshot` (re-reads + concatenates **all**
  shards for every completed lap); `record.py` calls `writer.flush_shard()` on every
  lap boundary, so every lap triggers a full re-read of all shards so far.
- **Evidence:** snapshots are written to `self._snapshot_paths` and only deleted in
  `close()`. `recover_orphaned_shards` matches only `.partN.parquet`
  (`_SHARD_RE`), so a hard kill leaves `.snap{N}.parquet` files that are never
  recovered or cleaned.
- **Impact:** For a long race (many laps, large shards), per-lap analysis cost grows
  quadratically; orphan `.snap*` files accumulate after crashes.
- **Recommendation:** Maintain a running merged table (append the latest shard once)
  rather than re-reading all shards each lap; and extend `recover_orphaned_shards`
  (or add a separate sweeper) to delete `*.snap*.parquet` on startup.

#### P1-9  `compare_laps` is a ~150-line function with repeated phase blocks

- **Location:** `lap_comparator.py:140` (`def compare_laps`).
- **Evidence:** The per-corner loop runs three near-identical blocks — minimum_speed,
  entry, exit — each doing: detect point → compute speed delta → threshold guard →
  `loss_s = delta_t[end] - delta_t[point]` (with fallback
  `loss_s = speed_delta / 100.0`, a magic-number heuristic) → append `CornerLoss`.
  The exit block also carries nested ref-phase matching fallbacks.
- **Recommendation:** Extract `_phase_loss(delta_t, driver_speed, ref_speed, point,
  end, threshold)` returning a `CornerLoss | None`, called three times per corner.
  Shrinks `compare_laps` and removes the duplicated threshold/fallback logic.

---

### P2 — minor cleanups / tech debt

#### P2-10  Dead/duplicate hyparquet imports; dynamic `import()` in event handlers

- `main.js:55-56` imports `parquetRead, parquetMetadataAsync, compressors` — **never
  used in main.js** (`readColumns` re-imports them dynamically in `pipeline.js:22,35-36`).
  `main.js` also imports `readColumns`, `buildSegments`, `interpAt` (1 occurrence each =
  the import line only — unused in `main.js`; they belong to `ui.js`/`pipeline.js`).
- `pipeline.js:readColumns` does `await import('https://cdn.jsdelivr.net/…')` on
  **every** file load (twice per call).
- `ui.js` uses dynamic `import('./appState.js').then(...)` inside the drop, order-reset
  and map-mode handlers ("to avoid circular ref"), re-fetching `panelOrder`/`setCurrentMapMode`
  that are already statically imported elsewhere — a smell of an appState↔ui cycle and
  of the ESM "import a `let` by value" gotcha.
- **Recommendation:** Import hyparquet once at the top of `pipeline.js` and pass the
  functions through; delete the dead imports from `main.js`; expose
  `setPanelOrder`/`getPanelOrder` (or a small reducer) on `appState.js` to remove the
  dynamic `import()` calls.

#### P2-11  `format_time` dead branches; stale files; demo scripts in `product/`

- `template_adapter.py:format_time` (lines 40-67) has redundant branches: the
  `if t < 0.50 and t % 0.10 == 0` block (lines 49-51) is fully subsumed by the
  following `if t < 0.50` block (lines 52-54, identical body), and the `<0.50`,
  `<0.75`, `<1.00` blocks (lines 52, 57, 62) all return the same
  `f"{_spell_number(tenths)} tenths"` — collapsible to a single `<1.00` branch after
  the exact `0.50`/`0.75`/`1.00` cases. Also `template_adapter.py` (652 lines) has
  mirror-image loss/gain phrase builders and detail clauses — a parameterised
  "gain/loss + phase" table would roughly halve it (and fix P0-2).
- Stale `product/web/js/trackOutlineManifest_backup.js` (97 lines) committed next to
  the real `trackOutlineManifest.js`.
- Slice-specific demo scripts live in **production** code space:
  `product/python/demo_coach_slice{01,03,04,05,11}.py` and `demo_coach_full_output.py`.
  These are slice-spike artifacts that now duplicate the shipped coach CLI /
  `generate_utterance.py`. Per the repo-reorg convention they belong in `dev/`
  (or should be deleted). `demo_coach_slice11.py` (415 lines) was touched recently
  (2026-05-27), so confirm with the owner before removing.

#### P2-12  Other small items

- `llm_adapter._call_via_openai` (~line 130): when `content` is empty, it regex-extracts
  quoted strings / the last sentence from the chain-of-thought `reasoning` field.
  Fragile heuristic that can emit a nonsensical utterance. It does log when fired —
  keep that, and consider a stricter accept/reject guard (e.g. max length + the same
  `_is_meta_output` filter the live path already uses).
- `coach_config._read_toml` reads the file twice (`path.read_text()` then
  `open(path,"rb")` in the tomllib branch) and ships a hand-rolled `_parse_simple_toml`
  fallback for Python 3.10. If/when 3.10 support drops, the fallback can be deleted.
- `_call_llm` keeps the "openai-compatible providers" set in two places
  (`openai_compat = {"ollama","deepseek","google"}` and the `_provider_base_url` dict).
  Adding a provider means editing both — derive the dict from one set.
- Bus interface is duck-typed: `record.py` and `coach_tap.py` guard with
  `hasattr(bus, 'on_lap_flushed'/'start'/'shutdown')` because `LiveBus` lacks them.
  Define a small `Bus` Protocol (flush callback optional) or move `on_lap_flushed`
  onto a shared base.
- `coach_tap._get_parquet_timeout()` does `import os` inside the function body —
  move to module top.
- `main.js:299` comment: panels are intentionally kept DOM-absent "so legacy tests
  counting 8 panels still pass" — a test-coupling constraint on production code;
  mild tech debt worth a note.

---

## 5. Strengths (what to keep doing)

- **Clear layering** that matches the docs, with small mostly-single-purpose modules
  (the median web module is ~130 lines; most coach modules are 80–230).
- **Defensive engineering with documented rationale.** Standouts: speed-integrated
  distance with pause detection (`connect._estimate_dist`), SHM boundary-artifact
  frame filtering (`pipeline.computeKeepIndices` + `lap_comparator` stale-frame strip),
  forward-clamp of `lap_time_s`, dual-path coach (Parquet-authoritative + bus fallback
  with timeout), oldest-first-drop bounded bus, orphan shard recovery, atomic
  sidecar writes, `_is_meta_output` guard against leaked LLM reasoning.
- **Non-blocking coach by construction** (bus worker thread + single-worker pool) —
  the recorder loop never blocks on analysis/LLM/TTS.
- **Strong testing culture:** parallel runner with a concise summary, per-feature
  suites, `test_protocol_enforcement.js`, and `docs/TESTING_LESSONS.md` capturing
  hard-won Playwright/Chromium rules.
- **Honest inline docs** — `smoothDt`, `_estimate_dist`, the "no `mInRealtime` gate"
  decision, and the Δt-by-subtraction decision all explain *why*, not just *what*.
- **Curated, guarded data pipeline** for reference laps and coaching models
  (guarded export/validate scripts, post-run audit) — production data is treated
  carefully.

---

## 6. Suggested follow-up missions / slices

Ordered by leverage. Each is a small, independent slice.

1. **`repo-hygiene-fix`** (P0-1): resolve `.pi/` tracking → green suite. ~15 min.
2. **`refactor-template-adapter`** (P0-2 + P2-11): parameterise the gain/loss × phase
   table, collapse `format_time` branches → drops `template_adapter.py` from 652 to
   well under 437. One behaviour-preserving refactor slice; `test_template_adapter.py`
   guards output.
3. **`refactor-connect-frame-builder`** (P0-2 + P1-6): extract `_build_frame` shared by
   LMU/rF2 → `connect.py` under 437; add a Frame↔schema↔append agreement test.
4. **`refactor-utterance-strategy`** (P1-4): `make_utterance_fn(mode, …)` factory +
   `local_ollama_config(model)`; delete the 3 inline dispatches.
5. **`refactor-live-fact-generator`** (P1-5): shared `_finish` helper.
6. **`harden-js-pipeline-bridge`** (P1-3): node-presence guard at coach startup, robust
   script path, and a contract test asserting `compute_delta_t.mjs` == a frozen
   Python reference fixture.
7. **`fix-per-lap-snapshot`** (P1-8): running-merged-table instead of re-read-all-shards;
   sweep orphan `.snap*.parquet` on startup.
8. **`refactor-compare-laps-phases`** (P1-9): `_phase_loss` helper; shrink `compare_laps`.
9. **`refactor-web-imports`** (P2-10): single hyparquet import in `pipeline.js`; delete
   dead `main.js` imports; remove dynamic `import()` in `ui.js` handlers.
10. **`clean-stale-files`** (P2-11): delete `trackOutlineManifest_backup.js`; relocate
    or remove `demo_coach_slice*.py`.
11. **`refresh-architecture-doc`**: update `docs/ARCHITECTURE.md` to cover the coach
    pipeline and the dual-path design.

---

## 7. Notes for the next agent

- The **only** files changed by this review are under
  `work/active/architecture-code-review/`. No production code was touched.
- The fast-suite failure (P0-1) is **pre-existing** — do not attribute it to this
  review. Confirm with `git status` (clean tree apart from this mission folder).
- All line numbers and counts in this document were measured on 2026-06-17 against
  the current `main`; re-measure before acting, as the codebase is actively curated
  (recent commits curation work on Silverstone/Fuji/Sebring/Le Mans).