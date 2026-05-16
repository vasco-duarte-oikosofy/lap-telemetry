# dev/

Development-only tooling and tracked development inputs will live here.

This folder is for things needed to build, test, inspect, or evolve the product, but not shipped as the product boundary itself.

## Belongs here

- `scripts/` — test runners, build implementation scripts, and development automation.
- `tools/` — one-off or reusable development tools.
- `sessions/` — tracked development session data used by tests and exploration.
- Test fixtures.

## Does not belong here

- Production/final code intended for extraction.
- Stable documentation that belongs in `docs/`.
- Mission execution history that belongs in `work/`.
- Generated local output that belongs in untracked `var/`.

No existing development files are moved into this folder in the current slice.
