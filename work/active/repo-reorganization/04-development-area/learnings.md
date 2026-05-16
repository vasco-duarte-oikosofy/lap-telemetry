# Learnings: 04-development-area

## Notes

- Moving `scripts/` affects test code in two ways: package script paths and each script's notion of repo root via `__dirname`.
- Keeping `bash scripts/test-summary.sh` as a wrapper avoids changing the standing agent command while still moving implementations to `dev/scripts/`.
- Some tests spawn helper scripts by path; those helper paths must use `dev/scripts/` after the move.
- `dev/tools/README-GENERATE-OUTLINE.md` is an important workflow guide, not a generic folder README. It is preserved and linked from both `dev/tools/README.md` and `dev/scripts/README.md`.
- `README-GENERATE-OUTLINE.md` had to stay under the 437-line file ceiling after edits.
