# Bug 26: `.pi/` tracked root directory fails repo-reorganization guard

## Observed

```text
$ bash scripts/test-summary.sh dev/scripts/test_repo_reorg_root_cleanup.js
FAILED
dev/scripts/test_repo_reorg_root_cleanup.js: unexpected tracked root directories: .pi
```

The `.pi/skills/session-compare/` directory is git-tracked but is not one of the allowed root directories listed in the repo-reorganization test.

## Root cause

The `.pi/` directory is a pi coding-agent harness configuration folder. While the `session-compare` skill it contains is useful, it is personal/agent-harness configuration rather than project source code. The repo reorganization acceptance test intentionally limits tracked root directories to `dev`, `docs`, `product`, `scripts`, `var`, `vendor`, `work` to keep the repository structure clean and predictable.

## Fix plan

1. Remove `.pi/` from git tracking while preserving the local files so the user can move the skill to `~/.pi/agent/skills/` if desired.
2. Add `.pi/` to `.gitignore` so it is not accidentally re-tracked.
3. Re-run the failing test and the full fast suite to confirm green.

## Files

- `.gitignore`
- `work/active/bugs/26-pi-tracked-root-directory/bug.md`

## Status

🔧 In progress
