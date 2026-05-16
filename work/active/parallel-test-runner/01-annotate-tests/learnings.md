# Slice 01 — Learnings

## What surprised us

1. **Two comment styles to handle.** Test files have two header patterns:
   - `#!/usr/bin/env node` + `'use strict'` (7 files) — annotation goes after `'use strict'`
   - `/** ... */` block comment (27 files) — annotation goes after the closing `*/`
   - `// ...` line-comment files (2 files: `test_m6.js`, `test_m6_extras.js`) — annotation goes before the first existing comment line

   The `sed` insertion for block-comment files used `*/` matching which missed the 2 line-comment-only files. Had to add those manually.

2. **All tests are parallel-safe.** No test shares ports, files, or global state. Every Playwright test starts its own Chromium instance and HTTP server on port 0 (random). Every test writes reports to its own unique `var/test-output/<test>-report/` directory.

## What the next agent needs

- The `// @parallel true` annotation is on the line immediately after `'use strict'` or after the header comment block — parseable as `'// @parallel (true|false)'` anchored to line start.
- A missing `@parallel` annotation should default to `false` (serial) per the spec.
- The 18 pure-Node tests each complete in <0.5s; the 18 Playwright tests each take ~2-3s (browser startup dominates).