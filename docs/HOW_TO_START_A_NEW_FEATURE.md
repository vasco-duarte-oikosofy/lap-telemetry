# How to Start a New Feature

This is the step-by-step process for starting a new feature in this repository.

## 1. Write (or reference) a stable spec

Create a spec document under `docs/specs/<feature-name>.md` that describes *what* the feature should do in stable terms. This spec is the single source of truth — the mission's `PLAN.md` links to it.

## 2. Create the mission folder

```
work/active/<feature-name>/
```

## 3. Write `PLAN.md`

Place it at `work/active/<feature-name>/PLAN.md`. It must contain:

- A link to the stable spec (`docs/specs/<feature-name>.md`)
- A **status table** of vertical slices, for example:

```markdown
| Slice | Status | Vertical outcome |
|---|---|---|
| `01-<slice-name>` | 🔲 Not started | <brief outcome> |
| `02-<slice-name>` | 🔲 Not started | <brief outcome> |
```

## 4. Define the feature test suite

Add a feature key to `testFeatures` in `package.json`. The key must match
the mission folder name. Include:

1. `test_runner_self_test.js` and `test_protocol_enforcement.js` (infrastructure guards).
2. All test scripts that directly test the feature's code.
3. Any test scripts that exercise shared code paths the feature touches.

Then add the `--feature` command to the mission's `PLAN.md` (next to the Goal).

See [AGENTS.md](../AGENTS.md) for full details on feature test cadence.

## 5. Create the first vertical slice folder

```
work/active/<feature-name>/01-<slice-name>/
```

Each slice folder must contain these four artifacts:

| File | Purpose |
|---|---|
| `prompt.md` | Execution order for this slice — numbered steps, goal, and non-goals |
| `artifacts/` | Temporary/reference files for completing the slice (not production code) |
| `handoff.md` | Concrete state at handoff: what changed, what remains, commands/results worth knowing |
| `learnings.md` | Surprises and context not in the spec |

## 6. Implement one slice at a time

Within a slice, follow this cycle:

1. **Write the failing test first** (test-first)
2. **Write the minimal code** to make it pass (simplest thing that could possibly work)
3. **Run** `bash scripts/test-summary.sh --feature <feature>` — must exit 0
4. **Run** `npm run build` — must succeed with current `dist/compare.html`
5. **Commit** — small, green, on `main`. Use `refactor:` prefix for refactor-only commits
6. Repeat until the slice's acceptance criteria pass

## 7. Finish the slice

When acceptance passes:

1. Ensure `bash scripts/test-summary.sh --feature <feature>` exits 0 (feature tests).
   Run the full suite (no `--feature`) at feature completion and every 3rd slice — **no failing tests may remain**. If a test was passing before your slice and is now failing, you must fix it before finishing. You may not leave failing tests "for the next slice" or skip them.
2. Update `handoff.md` — what's on disk, feature flags, helpers, deferred TODOs
3. Update `learnings.md` — what surprised you, context for the next agent
4. Update the slice status in `PLAN.md` (✅ Complete)
5. Ensure all required artifacts exist (see [AGENTS.md](../AGENTS.md))
6. Commit and **stop** — do not start the next slice

## 8. Proceed to the next slice

Create the next slice folder (`02-<next-slice>/`) with its own `prompt.md`, `artifacts/`, `handoff.md`, and `learnings.md`, then repeat from step 5.

## Key guardrails

- **One slice at a time.** Never bundle slices.
- **YAGNI.** Only build what the current slice needs.
- **200-line default ceiling, 437-line hard ceiling** per file. One file, one job.
- **Read three nearby files** before adding a new one, to follow existing patterns.
- **No failing tests left behind.** At the end of every slice, the full test suite must pass. You may not leave failing tests "for the next slice" or skip them.
- **When in doubt, stop and ask.** If anything is ambiguous, STOP and ask.