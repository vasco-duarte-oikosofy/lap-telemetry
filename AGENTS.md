# AGENTS.md — standing rules for every phase of this project

These rules apply to every commit you make, on every phase. They override
convenience. Pi loads this file automatically at startup; you do not need
to be reminded of these rules in each prompt.

## XP working agreements

1. **One subphase at a time.** Never bundle two subphases into one delivery.
2. **Test-first.** Write the failing test before the code that makes it pass.
3. **Commit cadence: small and green.** Many small commits per subphase, each
   one passing the existing test suite. No "WIP" commits.
4. **Refactor commits are separate from behavior commits.** Refactor commits
   start with `refactor:` and must not change rendered output.
5. **YAGNI is an active veto.** Develop only what is needed to complete the sub-phase you are on, nothing else. Keep it focused and simple. 
6. **The simplest thing that could possibly work.** Optimize only when a
   later subphase reveals a real problem.
7. **Spike, then stabilize.** For unknowns, write a throwaway spike, learn,
   throw it away, then implement properly with tests. Do not ship the spike.
8. **Stop at green.** When this subphase's acceptance passes, commit, write
   your handoff, exit. Do not start the next subphase.
9. **When in doubt, ask.** If anything is ambiguous, STOP and ask.
10. **Narrate decisions in commit messages.** Explain *why*, not just *what*.

## File architecture

- Follow the existing file architecture. Read three nearby files before
  adding a new one.
- Files should be small and coherent. Default ceiling: 200 lines per file.
- **Hard ceiling: 437 lines per file. No file may exceed this, ever.**
- One file, one job.

## Required artifacts at end of every phase

You are not done until all of these exist:

1. `bash scripts/test-summary.sh` exits 0 (runs full suite, all pass).
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
bash scripts/test-summary.sh                        # full suite
bash scripts/test-summary.sh scripts/test_f1f2.js   # single failing script
```

Do **not** use raw `npm test` — its voluminous output pollutes context and
makes it hard to spot failures.

## Standing orders

- Start only the subphase named in your current prompt.
- Ask before modifying `AGENTS.md` or `track-heatmap-spec.md`.
- Start with a specific and focused implementation, refactor only as needed to respect SOLID rules and YAGNI.
