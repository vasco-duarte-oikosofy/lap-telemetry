# Handoff: 05-product-subtree

## State

Complete. Product-owned source, data, Python package code, and generated bundle now live under `product/`.

## Changed files

- Moved browser app source from `web/` to `product/web/`.
- Moved Python package from `lap_telemetry/` to `product/python/lap_telemetry/`.
- Moved product-owned data from `data/` to `product/data/`.
- Moved generated bundle from `dist/` to `product/dist/`.
- Added orientation files:
  - `product/web/README.md`
  - `product/python/README.md`
  - `product/data/README.md`
  - `product/dist/README.md`
- Updated `pyproject.toml` so setuptools finds packages under `product/python` while keeping the import/package name `lap_telemetry`.
- Updated development scripts and tests to reference `product/web`, `product/data`, and `product/dist`.
- Updated `dev/scripts/test-summary.sh` to set `PYTHONPATH` for `product/python` during test runs.
- Updated README quick-start/layout references for the new product paths.
- Updated `work/active/repo-reorganization/PLAN.md` to mark this slice complete.

## Validation

- `bash scripts/test-summary.sh` passed: 714 assertions across 33 test scripts.
- `npm run build` passed and wrote `product/dist/compare.html`.

## Important context

- Stable root command `bash scripts/test-summary.sh` still works.
- Stable root command `npm run build` still works.
- `scripts/bundle.js` remains a compatibility wrapper; implementation is `dev/scripts/bundle.js`.
- `product/dist/compare.html` is now the standalone viewer path.
- `NEXT_STEPS.md` still has unrelated local modifications and was not part of this slice.
- `AGENTS.md` still mentions `dist/compare.html`; it was not edited because the standing rule requires explicit approval before modifying `AGENTS.md`.

## Next slice

`06-docs-and-work-archive` should move stable docs into `docs/` and historical root planning files into `work/archived-plans/`.
