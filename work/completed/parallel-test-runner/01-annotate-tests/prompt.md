# Slice 01 — Annotate tests with `// @parallel` header

## Goal

Add a `// @parallel true` or `// @parallel false` comment to every test script in the suite, so the parallel runner (slice 02) can classify them without guessing.

## Steps

1. Determine the classification for each of the 36 test scripts.
2. Add `// @parallel true` as the second line (after the shebang or `'use strict'`) to every parallel-safe script, or `// @parallel false` to any that must stay serial.
3. Run `bash scripts/test-summary.sh` — must still pass with all 36 scripts green.
4. Verify the annotations are parseable: write a tiny one-liner that greps for the annotation and confirms every test script has one.
5. Commit.

## Acceptance

- Every test script in `package.json`'s test command has a `// @parallel` comment.
- The existing sequential suite passes unchanged.
- A grep confirms no script is missing the annotation.

## Non-goals

- Do not write the parallel runner yet.
- Do not change how tests run or report.