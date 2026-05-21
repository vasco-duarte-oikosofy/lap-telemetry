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
[TESTING_LESSONS.md](TESTING_LESSONS.md)**. It documents hard-won rules
about Playwright and headless Chromium that prevent silent, layout-dependent
failures.

### Running tests

Always use `bash scripts/test-summary.sh` to run the test suite. It runs every
script individually, reports only failures with the exact script path to
re-run, and prints a concise one-line summary on success:

```bash
bash scripts/test-summary.sh                                       # full suite
bash scripts/test-summary.sh --feature interactive-race-coach     # feature-specific
bash scripts/test-summary.sh scripts/test_f1f2.js                  # single failing script
```

Do **not** use raw `npm test` — its voluminous output pollutes context and
makes it hard to spot failures.

### Test cadence: feature-specific during development, full suite at milestones

During active development on a mission, run **only the feature-specific tests**
using `--feature <name>`. This keeps feedback fast (under 5 seconds).

Run the **full suite** (no `--feature`) at two points:
1. After completing the feature (before the final commit).
2. After every 3rd slice within a mission, to catch cross-feature regressions.

Feature test lists are defined in `package.json` under `testFeatures`.
When starting a new mission, add a feature key with the relevant test scripts
and update the mission's `PLAN.md` to reference it.

## Standing orders

- Start only the slice named in your current prompt.
- Ask before modifying `AGENTS.md` or `track-heatmap-spec.md`.
- Start with a specific and focused implementation, refactor only as needed to respect SOLID rules and YAGNI.

## Reference-lap extraction and storage

To extract the fastest lap from a session file and store it as the reference lap for a circuit, follow the procedure in [`dev/scripts/EXTRACT_AND_STORE_REFERENCE_LAP.md`](dev/scripts/EXTRACT_AND_STORE_REFERENCE_LAP.md).
