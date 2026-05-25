# AGENTS.md — standing rules for every slice of this project

These rules apply to every commit you make, on every slice. They override
convenience. Pi loads this file automatically at startup; you do not need
to be reminded of these rules in each prompt.

## ⛔ UNSKIPPABLE: One slice at a time — no exceptions

You are **only allowed to work on one slice at a time**. This rule is
non-negotiable and overrides every other consideration:

- **One slice.** You must identify exactly one slice from a `prompt.md` in
  the current mission's slice folder. That is the only work you may do.
- **If you are unsure which slice to work on**, you **must stop immediately**
  and ask the user: *"Which slice should I work on?"* Do not guess. Do not
  pick one yourself. Do not continue until you have explicit confirmation.
- **No scope creep.** You may not touch files, add features, or refactor
  anything outside the scope of the single confirmed slice.
- **When the slice is done, stop.** Do not start the next slice. Do not
  "clean up" neighboring code. Commit, write your handoff, and exit.

If you ever find yourself editing files that are not required by the current
slice's `prompt.md`, you are breaking this rule. Stop and reconfirm.

## XP working agreements

1. **One slice at a time.** Never bundle two slices into one delivery.
2. **Test-first.** Write the failing test before the code that makes it pass.
3. **Commit cadence: small and green.** Many small commits per slice, each
   one passing the existing test suite. No "WIP" commits.
4. **Refactor commits are separate from behavior commits.** Refactor commits
   start with `refactor:` and must not change rendered output.
5. **YAGNI is an active veto.** Develop only what is needed to complete the slice you are on, nothing else. Keep it focused and simple. 
6. **The simplest thing that could possibly work.** Optimize only when a
   later slice reveals a real problem.
7. **Spike, then stabilize.** For unknowns, write a throwaway spike, learn,
   throw it away, then implement properly with tests. Do not ship the spike.
8. **Stop at green.** When this slice's acceptance passes, commit, write
   your handoff, exit. Do not start the next slice.
9. **When in doubt, ask.** If anything is ambiguous, STOP and ask.
10. **Narrate decisions in commit messages.** Explain *why*, not just *what*.

## File architecture

- Follow the existing file architecture. Read three nearby files before
  adding a new one.
- Files should be small and coherent. Default ceiling: 200 lines per file.
- **Hard ceiling: 437 lines per file. No file may exceed this, ever.**
- One file, one job.

## Required artifacts at end of every slice

You are not done until all of these exist:

1. `bash scripts/test-summary.sh --feature <feature>` exits 0 (feature tests pass). Full suite must also pass at feature completion and every 3rd slice.
2. `npm run build` succeeds and `dist/compare.html` is current (no stale bundle).
3. The current mission slice has `learnings.md` — what surprised you, anything
   the next agent needs to know that is not in the spec.
4. The current mission slice has `handoff.md` — concrete state: what is on disk
   now, what feature flags are live, new helpers worth knowing about, deferred
   TODOs.
5. Commits directly on `main`, with `refactor:` prefixes where appropriate.

## Work missions

Ongoing and completed work is tracked under `work/`. Follow the mission-folder
convention documented in [`work/README.md`](work/README.md): each mission has a
`PLAN.md`, and each vertical slice has `prompt.md`, `artifacts/`, `handoff.md`,
and `learnings.md`.

For the full step-by-step process of starting a new feature, see
[`docs/HOW_TO_START_A_NEW_FEATURE.md`](docs/HOW_TO_START_A_NEW_FEATURE.md).

## Build instructions

To build the distribution bundle:

```bash
npm run build
```

This creates `dist/compare.html` — a standalone single file that works via `file://`.
The build script (`scripts/bundle.js`) inlines CSS from `web/css/styles.css` and
bundles `web/js/main.js` (with its module dependencies) via esbuild.

## Testing

Before writing a new test or fixing a failing test, **read
[TESTING_LESSONS.md](docs/TESTING_LESSONS.md)**. It documents hard-won rules
about Playwright and headless Chromium that prevent silent, layout-dependent
failures — and how to wire Python test scripts into the Node-based parallel
runner (lesson L12: Python tests need a thin `.js` wrapper).

### Running tests

Always use `bash scripts/test-summary.sh` to run the test suite. It runs every
script individually, reports only failures with the exact script path to
re-run, and prints a concise one-line summary on success:

```bash
bash scripts/test-summary.sh                                       # fast suite (no Playwright)
bash scripts/test-summary.sh --pw                                  # full suite including Playwright
bash scripts/test-summary.sh --feature interactive-race-coach     # feature-specific
bash scripts/test-summary.sh scripts/test_f1f2.js                  # single failing script
```

Playwright (browser) tests are **excluded by default** because each one
launches a Chromium process (~1–2 s overhead per test). Only include them
when your slice changes the UI layer (`web/`, `dist/`), or when told to
by a specific `--feature` list that includes them. Use `--pw` to force
the full suite including Playwright tests.

Do **not** use raw `npm test` — its voluminous output pollutes context and
makes it hard to spot failures.

**Run the full suite (with `--pw`) before completing every slice.** This
catches cross-layer regressions that feature-specific runs miss.

### Test cadence: feature-specific during development, full suite at milestones

During active development on a mission, run **only the feature-specific tests**
using `--feature <name>`. This keeps feedback fast (under 5 seconds).

Run the **full suite with `--pw`** at two points:
1. After completing the feature (before the final commit).
2. After every 3rd slice within a mission, to catch cross-feature regressions.

During development, run without `--pw` for fast feedback (~10 s instead of ~20 s).
Include `--pw` only when the slice touches UI code, or at the milestone points above.

Feature test lists are defined in `package.json` under `testFeatures`.
Each key is a feature name (matching the mission folder name) and its value
is an array of test script paths.

**Creating a feature test suite:**

1. Add a key to `testFeatures` in `package.json` with the feature name
   and an array of test script paths.
2. Add the `--feature` command to the mission's `PLAN.md` (next to the Goal).
3. Include the two infrastructure guards:
   `test_runner_self_test.js` and `test_protocol_enforcement.js`.
4. Include all test scripts that directly test the feature's code.
5. Include any test scripts that exercise shared code paths the feature
   touches (e.g., if the feature modifies `pipeline.js`, include web UI
   tests that use the resampler).
6. Re-evaluate the list at each new slice — dependencies can grow.

**This is required when starting a new mission**, not optional. Every
mission must have a feature test suite before the first slice begins.

**When defining a feature's test list, always include:**
1. The feature's own test scripts.
2. `test_runner_self_test.js` and `test_protocol_enforcement.js` — these
   guard test infrastructure and must pass regardless of which feature you're
   working on. If you add a new test script and forget the `[PASS]`/`[FAIL]`
   protocol, `test_protocol_enforcement.js` catches it immediately.
3. Any tests that exercise **shared code paths** your feature touches. For
   example, if your feature modifies `product/web/js/pipeline.js`, include the
   web UI tests that exercise the resampler. If your feature only adds new
   Python modules under `product/python/lap_telemetry/coach/`, the web UI
   tests are unlikely to be affected.
4. Re-evaluate the list when starting each new slice — dependencies can
   grow as the feature evolves.

## Standing orders

- Start only the slice named in your current prompt.
- Ask before modifying `AGENTS.md` or `track-heatmap-spec.md`.
- Start with a specific and focused implementation, refactor only as needed to respect SOLID rules and YAGNI.

## Coach LLM setup (slice 03+)

The coach LLM adapter requires Python packages not installed by default. On a new machine:

```bash
pip3 install openai litellm
```

- `openai` — required for all providers; used directly for Ollama, DeepSeek, Google, and as fallback.
- `litellm` — optional but recommended; provides a unified interface for Anthropic/OpenAI-native endpoints.

Provider and model are configured in `coach_config.toml` (project root). API keys are **never** stored in files — set them as environment variables:

```bash
export OLLAMA_API_KEY=your-key        # for Ollama cloud
export ANTHROPIC_API_KEY=your-key     # for Anthropic
export OPENAI_API_KEY=your-key        # for OpenAI
```

## Coach TTS setup (slice 04+)

The coach TTS adapter requires Kokoro. On a new machine:

```bash
pip3 install kokoro-onnx sounddevice
```

Then download the Kokoro model and voices (~115 MB total):

```bash
mkdir -p product/data/tts-voices
curl -SL "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx" \
  -o product/data/tts-voices/kokoro-v1.0.int8.onnx
curl -SL "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin" \
  -o product/data/tts-voices/kokoro-voices-v1.0.bin
```

Full setup guide: [`docs/TTS_SETUP.md`](docs/TTS_SETUP.md).

The CLI must be run from the **project root** (so `coach_config.toml` is found), or set `COACH_CONFIG` to the config file path:

```bash
# From project root
cd /path/to/lap-telemetry
python3 -m lap_telemetry.coach.generate_utterance --facts dev/fixtures/coach/barcelona_lap15_facts.json

# Or from anywhere with COACH_CONFIG
export COACH_CONFIG=/path/to/lap-telemetry/coach_config.toml
```

## Reference-lap extraction and storage

To extract the fastest lap from a session file and store it as the reference lap for a circuit, follow the procedure in [`dev/scripts/EXTRACT_AND_STORE_REFERENCE_LAP.md`](dev/scripts/EXTRACT_AND_STORE_REFERENCE_LAP.md).

For sessions recorded as many `.part*.parquet` shards, see the **Multi-shard sessions** pitfall section in that doc — merge shards to a single file before running the extraction scripts.

## Generating a track coaching model

To generate a corner-detection coaching model from a reference lap, follow the procedure in [`dev/scripts/GENERATE_TRACK_COACHING_MODEL.md`](dev/scripts/GENERATE_TRACK_COACHING_MODEL.md).

## Generating a track outline

For circuits with TUMFTM data (Spa, Bahrain, COTA, Monza, etc.), follow [`docs/specs/MULTI_TRACK_TUMFTM_OUTLINE_PIPELINE.md`](docs/specs/MULTI_TRACK_TUMFTM_OUTLINE_PIPELINE.md).

For circuits with no external boundary data (Lusail, Fuji, Le Mans, etc.), generate a trajectory-based outline from the reference lap — follow [`dev/scripts/GENERATE_TRAJECTORY_OUTLINE.md`](dev/scripts/GENERATE_TRAJECTORY_OUTLINE.md).

See [`docs/TRACK_OUTLINE_COVERAGE.md`](docs/TRACK_OUTLINE_COVERAGE.md) for which tracks are covered and at what quality.
