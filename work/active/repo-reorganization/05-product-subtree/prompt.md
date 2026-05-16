# Slice Prompt: 05-product-subtree

## Goal

Move production/final code and product-owned assets into `product/` so the subtree becomes the future extraction boundary for a standalone repository or submodule.

## Execution order

1. Create this slice folder with `prompt.md`, `artifacts/`, `handoff.md`, and `learnings.md`.
2. Move product-owned source/assets into `product/`:
   - `web/` to `product/web/`
   - `lap_telemetry/` to `product/python/lap_telemetry/`
   - `data/` to `product/data/`
   - `dist/` to `product/dist/`
3. Update build, test, and packaging paths for the new product subtree.
4. Preserve stable root commands where practical.
5. Run `bash scripts/test-summary.sh`.
6. Run `npm run build`.
7. Update mission `PLAN.md`, handoff, and learnings.
8. Commit this slice only.

## Non-goals

- Do not move development scripts or sessions; that was slice 04.
- Do not archive root planning docs; that is slice 06.
- Do not move vendor/submodule code; that is slice 07.
- Do not change product behavior or rendered output intentionally.
