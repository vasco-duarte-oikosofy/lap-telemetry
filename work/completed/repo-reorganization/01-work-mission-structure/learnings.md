# Learnings: 01-work-mission-structure

## Notes

- `sessions/` is tracked development data, not local output. The future migration should move it to `dev/sessions/`, not `var/sessions/`.
- `.claude/` had one tracked local settings file. This slice removed it from Git tracking and ignores the folder going forward.
- The repo already had many unrelated working-tree changes before this slice. Future agents should inspect `git status` carefully before staging.
