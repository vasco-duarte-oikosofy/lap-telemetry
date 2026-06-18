# Mission: Architecture and Code Review

**Goal:** Produce a thorough, evidence-based architecture and code review of the
current codebase (`product/`, `dev/`, `web/`, recorder + coach + comparison app) and
capture the findings as a single living document under this mission folder.

**Spec / scope:** No stable spec under `docs/specs/` — this is an *analysis* mission,
not a feature mission. It reads the code as-is and reports findings. It changes **no
production code**; the only artifacts are documentation under this folder.

**Feature tests:** Not applicable. This mission writes no product code, so it adds no
`testFeatures` entry and has no test-first cycle. Repository health (build + existing
suite) is verified only to characterise current state, not to gate a code change.

---

## Vertical slices

| Slice | Status | Vertical outcome |
|---|---|---|
| `01-architecture-code-review` | ✅ Complete | Read-only review of recorder, coach, and web layers; independent findings written by multiple models: `20260617_architecture_code_review_glm5.2.md`, `…_gpt-5.5.md`, `…_kimi2.7.md`, `…_opus4.8.md` |

---

## Method

1. Read the architecture docs (`docs/ARCHITECTURE.md`, `docs/DESIGN.md`) and the
   standing rules (`AGENTS.md`).
2. Walk every production module under `product/python/` and `product/web/js/`,
   plus the `dev/scripts/` tooling that the coach depends on at runtime
   (`compute_delta_t.mjs`).
3. Characterise repository health: `npm run build`, `bash scripts/test-summary.sh`.
4. Record findings prioritised P0 → P2 with concrete `file:line` evidence, impact,
   and a recommendation. Record strengths too.
5. Write `handoff.md` and `learnings.md`; mark the slice ✅.

## Non-goals

- No code changes, no refactors, no test additions. Findings only.
- No edits to `AGENTS.md` or `track-heatmap-spec.md` (standing-order protected).
- No new mission folders for follow-up work — those are proposed inside the findings
  document as recommendations, to be picked up later by the user.