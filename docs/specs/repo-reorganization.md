# Spec: Repository Reorganization

## Goal

Reorganize the repository so agents and humans can quickly distinguish production code, development tooling, stable documentation, ongoing work, third-party/vendor code, and generated local outputs.

## Desired top-level shape

```text
/
  CATALOG_INDEX.md
  product/
  dev/
  docs/
  work/
  vendor/
  var/
```

## Requirements

- Production/final code must be grouped so it can later become a standalone GitHub project or submodule.
- Development tools must be clearly separate from production/in-development code.
- Test outputs and local generated output must be isolated in an untracked folder.
- `sessions/` is tracked development data and must move under `dev/`, not `var/`.
- `.claude/` must not be tracked.
- Every L1 folder must have a `README.md` for orientation.
- Root must have `CATALOG_INDEX.md` that progressively discloses all L1 folders.
- Ongoing and completed implementation work must live under `work/` as mission folders.
- Historical root-level plans and handoffs should be archived under `work/archived-plans/`.

## Proposed ownership

| Area | Purpose | Examples |
|---|---|---|
| `product/` | Production/final code and product-owned assets | web app, Python package, product data, releasable bundle |
| `dev/` | Development-only tools and tracked development inputs | scripts, tools, tests, fixtures, `sessions/` |
| `docs/` | Stable docs and specs | architecture, design, testing lessons, specs |
| `work/` | Active/completed/archive mission history | mission plans, prompts, handoffs, learnings |
| `vendor/` | External/submodule code | shared-memory dependencies |
| `var/` | Untracked generated local output | test reports, screenshots, temp files |

## Migration policy

Move files in small vertical slices. Each slice must leave the suite green and update references needed by that slice. Do not bundle unrelated moves.
