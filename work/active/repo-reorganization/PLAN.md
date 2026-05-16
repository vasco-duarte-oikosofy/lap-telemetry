# Repository Reorganization Mission Plan

Spec: [`docs/specs/repo-reorganization.md`](../../../docs/specs/repo-reorganization.md)

| Slice | Status | Vertical outcome |
|---|---|---|
| `01-work-mission-structure` | Complete | Establish `work/` mission convention, create this mission scaffold, document the repo reorganization spec, and stop before moving production/dev files. |
| `02-root-catalog-and-l1-readmes` | Planned | Add `CATALOG_INDEX.md` and orientation README files for proposed L1 folders. |
| `03-untracked-output-isolation` | Planned | Move/ignore generated test outputs and local temporary files under `var/` without moving tracked development data. |
| `04-development-area` | Planned | Move development-only tooling and tracked development inputs, including `sessions/`, under `dev/` and update references. |
| `05-product-subtree` | Planned | Move production/final code into `product/` and update build/runtime paths so the subtree is extractable. |
| `06-docs-and-work-archive` | Planned | Move stable docs into `docs/` and historical root planning files into `work/archived-plans/`. |
| `07-vendor-boundary` | Planned | Clarify third-party/submodule ownership under `vendor/` and update submodule/docs references. |
