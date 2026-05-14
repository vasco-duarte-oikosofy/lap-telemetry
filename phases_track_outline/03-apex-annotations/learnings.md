# Learnings — Phase 03 Apex Annotations

- A pure browser-side validator is enough for the annotation contract; the file loader can stay Node-only for tests/CLI-style consumers by dynamically importing `node:fs/promises`.
- Missing annotation files are best represented as a status result (`not_configured`) rather than an exception so later metric/UI phases can branch without try/catch.
- The existing feature flag dropdown automatically lists new entries added to `features`, so adding `apexAnnotations` exposes the delivery switch without extra UI code.
