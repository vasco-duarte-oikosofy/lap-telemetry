# Learnings: 03-untracked-output-isolation

## Notes

- The test scripts hardcoded root-level report directories; moving generated outputs required updating the scripts, not just `.gitignore`.
- Root-level ignore patterns should be anchored with `/`. A broad `screenshots/` pattern also ignored `var/screenshots/README.md` until it was changed to `/screenshots/`.
- `bash scripts/test-summary.sh` confirms the new `var/test-output/` paths work across the full suite.
- Keep `sessions/` out of this slice. It is tracked development data and belongs in the next `dev/` migration slice.
