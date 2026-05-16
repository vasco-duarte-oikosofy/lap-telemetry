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

## 4. Create the first vertical slice folder

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

## 5. Implement one slice at a time

Within a slice, follow this cycle:

1. **Write the failing test first** (test-first)
2. **Write the minimal code** to make it pass (simplest thing that could possibly work)
3. **Run** `bash scripts/test-summary.sh` — must exit 0
4. **Run** `npm run build` — must succeed with current `dist/compare.html`
5. **Commit** — small, green, on `main`. Use `refactor:` prefix for refactor-only commits
6. Repeat until the slice's acceptance criteria pass

## 6. Finish the slice

When acceptance passes:

1. Ensure `bash scripts/test-summary.sh` exits 0 — **no failing tests may remain**. If a test was passing before your slice and is now failing, you must fix it before finishing. You may not leave failing tests "for the next slice" or skip them.
2. Update `handoff.md` — what's on disk, feature flags, helpers, deferred TODOs
3. Update `learnings.md` — what surprised you, context for the next agent
4. Update the slice status in `PLAN.md` (✅ Complete)
5. Ensure all required artifacts exist (see [AGENTS.md](../AGENTS.md))
6. Commit and **stop** — do not start the next slice

## 7. Proceed to the next slice

Create the next slice folder (`02-<next-slice>/`) with its own `prompt.md`, `artifacts/`, `handoff.md`, and `learnings.md`, then repeat from step 5.

## Key guardrails

- **One slice at a time.** Never bundle slices.
- **YAGNI.** Only build what the current slice needs.
- **200-line default ceiling, 437-line hard ceiling** per file. One file, one job.
- **Read three nearby files** before adding a new one, to follow existing patterns.
- **No failing tests left behind.** At the end of every slice, the full test suite must pass. You may not leave failing tests "for the next slice" or skip them.
- **When in doubt, stop and ask.** If anything is ambiguous, STOP and ask.