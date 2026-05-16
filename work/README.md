# work/

Mission planning and execution history lives here.

Use `work/` for active, completed, and archived implementation work. Stable project documentation belongs in `docs/`; production code belongs in `product/`; development tooling belongs in `dev/`.

## Mission structure

Each mission folder must use this structure:

```text
<mission>/
  PLAN.md
  <slice-name>/
    prompt.md
    artifacts/
    handoff.md
    learnings.md
```

## Required files

- `PLAN.md` links to the stable spec under `docs/` and contains only a status table for clear, incremental, vertical slices.
- `<slice-name>/prompt.md` gives the execution order for that slice.
- `<slice-name>/artifacts/` holds temporary or historical reference artifacts for completing the slice. These artifacts are not production code.
- `<slice-name>/handoff.md` records the concrete state for the next agent: what changed, what remains, and any commands/results worth knowing.
- `<slice-name>/learnings.md` records surprises and context that are not already in the spec.

## State folders

- `active/` contains missions currently being worked.
- `completed/` contains completed mission folders.
- `archived-plans/` contains historical planning and handoff documents that predate this convention.

Do not add loose mission files directly under `work/`; create or use a mission folder.
