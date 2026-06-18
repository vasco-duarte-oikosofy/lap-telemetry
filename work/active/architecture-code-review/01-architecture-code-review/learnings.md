# Learnings — Slice 01: Architecture and Code Review

Surprises and context not already in the spec/docs.

- **The repo is currently red on the fast suite** — and not because of anything
  obvious in `product/`. The single failure is a repo-hygiene guard
  (`test_repo_reorg_root_cleanup.js`) complaining that `.pi/` is a tracked root
  directory. `.pi/` is the pi agent-harness skills folder (2 tracked files:
  `session-compare/SKILL.md`, `session-compare/scripts/compare_session.py`). It is
  neither in `allowedRootDirs` nor in `.gitignore`. Easy to miss because the failure
  is buried among 882 passing tests and the summary line just says "1 of 30 scripts
  failed". Lesson: when the suite is "almost green", read the actual failing script
  name, don't assume it's flaky.

- **`docs/ARCHITECTURE.md` under-describes the system.** It covers recorder + summary
  + web but **not the coach layer**, which is now the largest part of the codebase
  (~30 modules under `coach/`, including a dual-path live pipeline, LLM/TTS adapters,
  speech queue, fuel engineer). Anyone reading ARCHITECTURE.md to orient themselves
  will miss the coach entirely.

- **The headline metric (Δt) is computed in Node, not Python.** `lap_comparator.py`
  shells out to `node dev/scripts/compute_delta_t.mjs` for every lap, importing the
  web's `pipeline.js` to guarantee parity. This is a deliberate single-source-of-truth
  decision (the Δt RCA in `work/archived-plans/` shows the metric was painful), but it
  makes the Python coach depend on Node at runtime — easy to miss because the offline
  CLI and tests paper over it. The pure-Python `resample.py` exists but is explicitly
  "test-only", which can mislead a reader into thinking Python has a real Δt path.

- **Three-way schema sync in the recorder is undocumented and untested.** `Frame`
  dataclass (`connect.py`), `_SCHEMA` (`writer.py`), and `SessionWriter.append`'s
  43-line field list must agree field-for-field. A drift = silent column-data bug
  (column written empty or schema mismatch). No test guards this. This is the
  highest-hidden-risk finding: low probability, high silent-failure cost.

- **The 437-line hard ceiling is genuinely exceeded in 4 production files**, the
  worst being `template_adapter.py` at 652 — and that file is mostly *mirror-image*
  loss/gain phrase builders that a parameterised table would roughly halve. So the
  biggest ceiling violator is also the one with the cleanest refactor path.

- **`main.js` carries dead imports.** `parquetRead`/`parquetMetadataAsync`/
  `compressors` (and `readColumns`/`buildSegments`/`interpAt`) appear only in the
  import statements and are never used in `main.js` — they're used by `ui.js`/
  `pipeline.js`, which import them themselves. Harmless (esbuild tree-shakes) but
  misleading about ownership.

- **Test cadence note for doc-only slices:** the AGENTS rule "run the full suite with
  `--pw` before completing every slice" assumes a code-changing slice. For a
  read-only documentation slice, running `--pw` adds ~20 s and regressions nothing.
  I ran the fast suite (to characterise state) and skipped `--pw`, documenting the
  deviation in `handoff.md`. If a future agent treats this as a rule violation, note
  the slice changed zero files outside `work/`.

- **Git activity is curation-heavy, not feature-heavy.** The last ~25 commits are
  almost all reference-lap / coaching-model / track-outline curation (Silverstone,
  Fuji, Sebring, Le Mans). The interactive-race-coach PLAN shows slices 01-11 all
  ✅, but most web `features.*` flags in `appState.js` default to `false` — completed
  features remain behind feature flags. Worth knowing if someone wonders why "done"
  features aren't visible by default.

## Addendum — Kimi K2.7 review run (2026-06-18)

- **Independent review surfaced a real correctness bug the first review missed.**
  The fuel-engineer module (`fuel_facts.py`) maps `mSession` values to session-type
  strings using a table that contradicts both the design docs and the recorder's own
  `_session_type_slug`. Consequence: race sessions will often be classified as
  "practice"/"other", and the fuel-engineer call (slice 08) will be silently
  skipped. This was not in the earlier glm5.2 / gpt-5.5 reviews, showing the value
  of running multiple models.

- **The Node.js dependency of the coach is still invisible in architecture docs.**
  Both reviews flagged it, but it remains undocumented in `README.md` and
  `ARCHITECTURE.md`. Any packaging or distribution work will hit this first.

- **Dead code is easy to spot when reading fresh.** The broken first loop in
  `panels.js:40-52` (`for (const { key } of Object.values(bins))`) is a
  straightforward mistake that multiple passes found. It does not affect rendering
  today because a later loop recomputes the same thing, but it is misleading and
  should be removed.

- **Approximate constants in feature flags are fragile.** The
  `rangeKey === '0:4650'` heuristic in `trackHeatmapController.js` works only for
  ~4.65 km tracks and is already technical debt before the feature ships. Numeric
  comparisons against `currentMaxDist` are safer.

- **Multiple-model review is cheap and high-value for analysis missions.** Two
  reviews agreed on the big rocks (`.pi/` suite failure, template/connector size,
  schema-sync risk, Node dependency) while each found distinct details (fuel map bug,
  dead imports, Ollama URL, activity-strip off-by-one). The overlap increases
  confidence; the differences expand coverage.
