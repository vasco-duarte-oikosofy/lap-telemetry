# Architecture & Code Review — lap-telemetry

**Reviewer:** Claude (Opus 4.8)
**Date:** 2026-06-17
**Scope:** Read-only review of `product/` (recorder + coach + comparison app),
`product/web/js/`, and the `dev/scripts/` tooling the coach depends on at
runtime. No production code changed; findings only.
**Repo state:** branch `main`, HEAD `1ac6107`.

---

## Method

1. Read `AGENTS.md`, `docs/ARCHITECTURE.md`, and `work/README.md` for the
   intended architecture and standing rules.
2. Inventoried every production module under `product/python/lap_telemetry/`
   and `product/web/js/` (line counts, layer boundaries, import graph).
3. Read the runtime-critical modules in full: `recorder/connect.py`,
   `recorder/writer.py`, `coach/template_adapter.py`, `coach/live_coach.py`,
   `coach/coach_tap.py`, `coach/llm_adapter.py`, `coach/resample.py`,
   `coach/js_pipeline.py`, and `web/js/{main,pipeline}.js`, plus the
   `dev/scripts/compute_delta_t.mjs` bridge.
4. Characterised repository health (build + fast test suite).
5. Compiled findings P0 → P2 with `file:line` evidence, impact, and a
   recommendation. Recorded strengths.

---

## Repository health

| Check | Result |
|---|---|
| `npm run build` | ✅ Succeeds; refreshes `product/dist/compare.html` (1.9 MB single file). |
| `bash scripts/test-summary.sh` (fast) | ✅ `ALL PASS — 889 assertions across 30 test scripts` in ~2.3 s. |
| Playwright suite | Not run (25 PW tests skipped; no UI changed by this review). |
| Files over the **437-line hard ceiling** | ⚠️ 4 in `product/`: `coach/template_adapter.py` (652), `recorder/connect.py` (494), `web/js/pipeline.js` (448), `web/js/main.js` (446). |
| Uncommitted working-tree noise | `dev/scripts/test_repo_reorg_root_cleanup.js` had a pre-existing un-staged edit (adding `.pi` to allowed root dirs); restored during review, not committed. |

**Note for the next agent:** `npm run build` itself is clean and deterministic;
it does not touch test files. The `test_repo_reorg_root_cleanup.js` change was
already present in the working tree before this review began.

---

## Strengths (the review is balanced)

- **Clean layer separation in intent.** `recorder/` (sim → Frame → Parquet),
  `coach/` (facts → utterance → TTS), and `web/js/` (load → resample → render)
  are conceptually distinct and each have a single clear job, matching
  `docs/ARCHITECTURE.md`.
- **Sim-agnostic `Frame` dataclass** (`connect.py:32`) is the right seam: the
  rest of the system never sees LMU/rF2 differences.
- **Schema is single-sourced where it matters.** `frames_to_parquet.py:17`
  imports `_SCHEMA` from `writer.py` and *derives* its columns from it
  (`frames_to_parquet.py:35`) precisely so it "never drifts when new fields
  are added." This is exemplary DRY discipline — and makes the violations
  below (which ignore the same pattern) more glaring.
- **Pure, well-documented data transforms** in `pipeline.js`. Functions like
  `smoothLapTime`, `smoothDt`, and `computeKeepIndices` carry long, specific
  comments explaining *why* (the Δt saw-tooth, the SHM boundary artifact) —
  exactly the "narrate decisions" rule from AGENTS.md, applied in code.
- **Defence-in-depth on the Δt path.** `main.js` forward-clamps `lap_time_s` to
  a physical invariant before subtracting, with a comment naming the failure
  mode it guards. The history of the phantom-error RCA is preserved in code.
- **Crash-safety designed in.** Shard + sidecar written from session start;
  `recover_orphaned_shards()` exists; the sidecar is refreshed on every flush.
- **Zero `TODO`/`FIXME`/`HACK` markers** across `product/python` and
  `product/web/js` — debt is tracked in `work/`, not littered in code.
- **Config never stores secrets** (`coach_config.py` docstring + `api_key`
  property reads from env only) — a deliberate, correct security choice.

---

## P0 — Correctness / health risks & hard-rule violations

### P0-1 — Production coach has a **runtime dependency on `dev/` via a Node subprocess**

**Evidence:**
- `product/python/lap_telemetry/coach/lap_comparator.py:13` →
  `from .js_pipeline import run_js_pipeline`
- `js_pipeline.py:20` → `_JS_SCRIPT = _REPO_ROOT / "dev" / "scripts" / "compute_delta_t.mjs"`
- `js_pipeline.py` spawns `subprocess.run(["node", str(_JS_SCRIPT)], …, timeout=30)`
- `lap_comparator.py:225` calls `run_js_pipeline(...)`.

**Impact.** The shipping product (`product/python`) cannot compute a lap
comparison without (a) a Node.js runtime on PATH, and (b) a file that lives in
`dev/` — the development-tooling tree that `AGENTS.md` explicitly separates from
production code ("development tooling belongs in `dev/`"). Any packaging,
relocation, or `dev/` cleanup silently breaks the live coach. It also crosses a
process boundary (fork + JSON serialise/deserialise of full lap arrays, 30 s
timeout) on the latency-sensitive after-lap path.

The motivation is sound — "use the *same* JS code the user sees on screen so the
coach can't drift from the chart" (`js_pipeline.py` docstring). But the
mechanism inverts the dependency arrows: `product/` now depends on `dev/`.

**Recommendation (future slice).** Either (a) move `compute_delta_t.mjs` and the
needed `pipeline.js` functions into `product/` (e.g. `product/web/js` is already
product; depend on *that*, not `dev/`), or (b) port the 6-step pipeline to pure
Python and pin parity with a golden-vector test. Option (a) is the smaller
change and preserves the single-source-of-truth goal; the key is that
`product → product`, never `product → dev`.

### P0-2 — Four production files exceed the **437-line hard ceiling**

`AGENTS.md`: *"Hard ceiling: 437 lines per file. No file may exceed this, ever."*

| File | Lines | Over by |
|---|---:|---:|
| `product/python/lap_telemetry/coach/template_adapter.py` | 652 | +215 |
| `product/python/lap_telemetry/recorder/connect.py` | 494 | +57 |
| `product/web/js/pipeline.js` | 448 | +11 |
| `product/web/js/main.js` | 446 | +9 |

**Impact.** Direct, current violations of a hard, "ever" rule. `template_adapter.py`
is the worst offender at 1.5× the ceiling.

**Recommendation.**
- `template_adapter.py` — the file is a flat list of ~30 near-identical
  single-phrase / detail-clause builders (`_loss_*`, `_gain_*`,
  `_loss_detail_*`, `_gain_detail_*`). Split into `template_phrases.py`
  (builders) + `template_adapter.py` (orchestration: dedup, ordering,
  truncation, public API). This also exposes the loss/gain symmetry (see P1-3).
- `connect.py` — extract the per-sim `read_frame` bodies (see P1-1); the two
  `Frame(...)` constructions are ~70 lines each and nearly identical.
- `main.js` / `pipeline.js` — borderline (+9/+11). The cheapest legal fix is to
  extract the geometry/track-transform helpers from `pipeline.js`
  (`buildTrackTransform`, `buildTrackPolylinePts`, `computeTrackBounds`) into a
  `trackGeometry.js`, and the `getMapState`/`getRenderState`/debug-window glue
  from `main.js` into a small `renderState.js`.

### P0-3 — `_distance_to_track_edge` is **copy-pasted three times** with two signatures

**Evidence:**
- `recorder/connect.py:211` — `def _distance_to_track_edge(track_edge, path_lateral)`
- `recorder/writer.py:66` — `def _distance_to_track_edge(frame)` (re-derives `frame.track_edge_m - abs(frame.path_lateral_m)`)
- `coach/frames_to_parquet.py:58` — identical body to `writer.py`.

**Impact.** The same physical formula (`track_edge − |path_lateral|`) is
maintained in three places. `connect.py` already computes
`distance_to_track_edge_m` and stores it on the `Frame`
(`connect.py:308`/`406`), so the `writer.py` and `frames_to_parquet.py` copies
re-derive a value the `Frame` already carries — a latent inconsistency risk if
the formula ever changes (e.g. clamping, sign convention). This sits in the
recorder write path, so drift would silently corrupt a stored column.

**Recommendation.** Keep one definition (the `Frame`-level one in `connect.py`),
have `writer.py`/`frames_to_parquet.py` read `frame.distance_to_track_edge_m`
directly, or import a single shared helper. Given `frames_to_parquet.py` already
imports `_SCHEMA` from `writer.py`, the same import discipline applies here.

---

## P1 — Maintainability / DRY / architecture (worth dedicated slices)

### P1-1 — `LMUConnection.read_frame` and `RF2Connection.read_frame` are ~70 lines of near-duplicate `Frame(...)`

**Evidence:** `connect.py:282–339` (LMU) vs `connect.py:378–435` (rF2). The two
`Frame(...)` literals differ only in: `abs_active`/`tc_active` (LMU reads,
rF2 `None`), `fuel_l`/`fuel_capacity_l` (LMU only), and the SHM accessor objects.
Every other field — slip angles, surfaces, terrain, sectors, scoring timing,
position — is constructed identically.

**Impact.** Adding or fixing one telemetry field (the project does this often —
see "slice 08", "bug 10b" comments) means editing two parallel blocks; forgetting
one produces a sim-specific bug. This is exactly the kind of duplication the
`Frame` seam was meant to eliminate.

**Recommendation.** Extract a `_build_frame(sim, scor_v, tele_v, scor_info, …)`
free function that both subclasses call, passing the 3–4 sim-specific values
(abs/tc/fuel) as arguments. Cuts ~70 lines and removes the duplicate-edit hazard.
This also helps `connect.py` back under the 437 ceiling (P0-2).

### P1-2 — `live_coach.main()` (340 lines) hand-rolls a 3×3 utterance-mode matrix

**Evidence:** `live_coach.py` defines `_template_utterance`, `_local_llm_utterance`,
`utterance_fn`, `corner_utterance_fn`, `fuel_utterance_fn` as nested closures,
each repeating the same `if TEMPLATE … if LOCAL_LLM … else CLOUD_LLM` ladder with
near-identical `try/except → log.exception → print → return None` bodies. The
local-LLM `LLMConfig(provider="ollama", …)` block is built **twice**
(`live_coach.py:203` and `:270`).

**Impact.** Three utterance kinds × three modes = nine branches, all in one CLI
`main()`, all with copy-pasted error handling. Adding a fourth mode or a fourth
utterance kind is a combinatorial edit. The function is also doing argparse,
config loading, signal handling, pipeline wiring, *and* utterance strategy — too
many jobs for one function.

**Recommendation.** Introduce an utterance-strategy object (one class per mode,
or a small dispatch table keyed by `UtteranceMode`) that exposes
`after_lap(facts)`, `corner(facts, name, top)`, `fuel(facts)`. Build the Ollama
`LLMConfig` once. `live_coach.main()` then just selects a strategy and wires it
in. Shrinks the file well under the ceiling and isolates the matrix.

### P1-3 — `template_adapter.py` loss/gain symmetry is duplicated, not abstracted

**Evidence:** Every phrase builder exists as a `_loss_*` / `_gain_*` pair
(`_loss_entry`/`_gain_entry`, `_loss_exit_brake`/`_gain_exit_brake`, …) and every
detail clause as `_loss_detail_*` / `_gain_detail_*`. The pairs differ only in
the verb ("lost"/"gained", "less"/"more") and the sign test on the delta.

**Impact.** ~30 functions where ~15 + a polarity parameter would do. This is the
main reason the file is 652 lines (P0-2). Each new coaching phase doubles the
surface area.

**Recommendation.** Parameterise on an `is_gain` flag (the dedup layer already
threads exactly this — `_dedup_corner(items, is_gain)`). The single-phrase
builders can collapse into `_phrase(cl, is_gain)` with a small verb/comparator
lookup. Pair this with the file split from P0-2.

### P1-4 — Two Python resamplers claim to "match" the JS pipeline; the relationship is fragile

**Evidence:** `coach/resample.py` provides `resample_column` + `compute_delta_time_trace`
("Python-only version for synthetic test data"), while `js_pipeline.py` shells
out to JS for "real data." `lap_comparator.py:14` imports *both*.

**Impact.** Two interpolation implementations of the *same* contract now exist
(Python `interp` in `resample.py:28` vs JS `interpAt` in `pipeline.js`). They can
silently diverge; the docstring's "for synthetic test data" carve-out is a
convention, not an enforced boundary. Combined with P0-1, the coach's numeric
core is spread across three languages/files.

**Recommendation.** Once P0-1 is resolved (single pipeline source), delete the
duplicate Python resampler or make it a thin, tested shim with a golden-vector
parity test against the canonical implementation.

### P1-5 — `coach_tap.py` `_analyze_lap` mixes orchestration, I/O waiting, timing logs, and fallback policy

**Evidence:** `coach_tap.py` — `_analyze_lap` waits on a Parquet flush condition,
chooses path C vs the event-frames fallback, runs fact generation, formats
latency `print`s, and runs the fuel path, all in one method on the pool thread.
`_get_parquet_timeout()` reads an env var with a local `import os` inside the
function.

**Impact.** The dual-path policy (authoritative Parquet vs live frames) is
correct and well-commented, but the method is hard to test in isolation and
conflates "decide which data source" with "generate utterance." Latency
`print`s to stderr are interleaved with control flow.

**Recommendation.** Extract `_resolve_lap_source(event) -> (path | frames)` and
keep `_analyze_lap` to "given a source, produce (utterance, fuel_utterance)."
Lift the env read to module load. Lower-priority than the above, but improves
testability of the after-lap path.

---

## P2 — Minor cleanups & tech debt

### P2-1 — Slice-numbered demo scripts live in `product/python/`

`product/python/demo_coach_slice{01,03,04,05,11}.py` + `demo_coach_full_output.py`
(1,062 lines total) sit in the **product** tree. They are development/demo
artifacts (each opens with a slice number and uses `sys.path.insert` hacks —
`demo_coach_slice01.py:36`, etc.). `AGENTS.md`: dev tooling belongs in `dev/`.
`product/python/README.md` documents `demo_coach_slice01.py` as a curated human
smoke test, so it has a defensible reason to exist — but it should live in `dev/`
(or be wired into the suite) rather than shipping in `product/`. The numbered
siblings are pure historical slice demos and are the clearer candidates to move
or retire. **Confirm with the user before moving** — `README.md` references them.

### P2-2 — `trackOutlineManifest_backup.js` is a backup file checked into product source

`product/web/js/trackOutlineManifest_backup.js` (97 lines) is a `_backup` copy of
`trackOutlineManifest.js`. It is **not imported** by any module (only referenced
by `dev/scripts/register_outline.py`) and differs from the live file. A `_backup`
suffix in version-controlled source is dead weight — git *is* the backup.
Recommend deleting it (after confirming `register_outline.py` doesn't require it
as a template).

### P2-3 — `sys.path.insert` hacks inside product modules

`live_coach.py:36` and `connect.py:24` mutate `sys.path` at import time
(plus all 6 demo scripts). `connect.py`'s vendor-path insert is justified for the
"source checkout without pip install" case and documented; `live_coach.py`'s
self-path insert is a smell that a proper package entry point / `python -m`
invocation would remove. Low impact, but it makes import order load-bearing.

### P2-4 — Latency/debug `print(..., file=sys.stderr)` scattered through the coach hot path

`coach_tap.py` and `live_coach.py` emit operational telemetry via raw `print`
rather than the `logging` module they already configure. Mixing `print` and
`log` makes it impossible to silence the coach's stderr chatter via log level.
Consider routing through `log.info` with a dedicated logger so verbosity is
controllable.

### P2-5 — `llm_adapter._call_via_openai` embeds reasoning-model recovery heuristics inline

`llm_adapter.py:160–205` — extracting an utterance from a reasoning model's
`reasoning` field via regex/last-sentence fallback is clever but buried inside the
generic OpenAI call path, with an inline `import re`. It's provider-quirk handling
that would be easier to test and reason about as a named helper
(`_recover_utterance_from_reasoning(message)`).

---

## Architectural observations (no action required, for context)

- **The Δt numeric path is the system's spine and it is triple-implemented:**
  JS (`pipeline.js`, canonical, what the user sees), the Node bridge
  (`compute_delta_t.mjs`, re-orchestrates the JS for Python), and the Python
  shim (`resample.py`, "for synthetic data"). P0-1 and P1-4 both stem from this.
  Consolidating to one source of truth would simplify the largest cross-cutting
  risk in the codebase.
- **The recorder schema is well governed** (single `_SCHEMA`, derived columns)
  — a good model the rest of the codebase doesn't yet follow for *behaviour*
  (formulas, phrase builders, sim frames).
- **The web layer is well-modularised** (20+ small JS files, mostly < 200 lines)
  with only `main.js`/`pipeline.js` slightly over. The Python coach layer is the
  opposite: a few large, branch-heavy files. Effort is best spent on the Python
  coach (P0-2, P1-1/2/3).

---

## Suggested follow-up slices (proposed, not started)

These are recommendations for the user to schedule — this mission starts none of
them.

1. **`product→product` pipeline dependency** (P0-1): relocate the Node bridge out
   of `dev/`, or port to Python with golden-vector parity. *(Highest risk.)*
2. **Split `template_adapter.py`** (P0-2, P1-3): phrases vs orchestration, and
   collapse loss/gain pairs behind an `is_gain` flag.
3. **De-duplicate `connect.py` `read_frame`** (P0-2, P1-1): shared `_build_frame`.
4. **Single-source `_distance_to_track_edge`** (P0-3).
5. **Utterance-strategy refactor in `live_coach.py`** (P1-2).
6. **Housekeeping** (P2-1/2/3): move/retire demo scripts, delete the `_backup`
   JS, drop `sys.path` hacks — *confirm with user first* (README references).

---

## Files read in full during this review

`docs/ARCHITECTURE.md`, `work/README.md`,
`product/python/lap_telemetry/recorder/{connect.py, writer.py (partial)}`,
`product/python/lap_telemetry/coach/{template_adapter.py, live_coach.py,
coach_tap.py, llm_adapter.py, resample.py, js_pipeline.py, coach_config.py
(partial)}`,
`product/web/js/{main.js, pipeline.js}`,
`dev/scripts/compute_delta_t.mjs`. Inventory (line counts, import graph,
grep-based duplication checks) across all of `product/python` and
`product/web/js`.
