# Slice 01: Architecture and Code Review

**Outcome.** A single findings document, `20260617_architecture_code_review_glm5.2.md`,
capturing a thorough architecture and code review of the repo as of the review date,
placed under this slice folder.

## Steps

1. Read `AGENTS.md`, `docs/ARCHITECTURE.md`, `docs/DESIGN.md`, and `work/README.md`
   to understand intended architecture and standing rules.
2. Inventory the codebase: line counts per file, file architecture, layer boundaries
   (recorder / coach / web / dev-tooling).
3. Read every production module under `product/python/lap_telemetry/` (recorder + coach)
   and `product/web/js/` (non-data modules), plus the runtime-critical
   `dev/scripts/compute_delta_t.mjs` bridge.
4. Characterise current repository health:
   - `npm run build` → must succeed and refresh `product/dist/compare.html`.
   - `bash scripts/test-summary.sh` → record pass/fail state (do not fix; this is a
     read-only review).
5. Compile findings, prioritised:
   - **P0** — correctness/health risks or hard-rule violations that should be addressed
     soon.
   - **P1** — maintainability / DRY / architecture concerns worth a dedicated slice.
   - **P2** — minor cleanups and tech debt.
   Each finding: location (`file:line`), evidence, impact, recommendation.
6. Record strengths so the review is balanced.
7. Write `20260617_architecture_code_review_glm5.2.md` (the deliverable, using the
   requested slug), `handoff.md`, and `learnings.md`.
8. Mark the slice ✅ in `PLAN.md`. Commit. **Stop** — do not start any follow-up slice.

## Non-goals

- Do not modify any file outside `work/active/architecture-code-review/`.
- Do not "fix" anything found; findings are recommendations for future slices.
- Do not run the Playwright suite (no UI code is touched; the review is documentation).