# Learnings — Phase 05 Apex Metrics UI

- Importing `validateApexAnnotations()` into the browser bundle also pulled in `apexAnnotations.js`; its Node-only loader needed an indirect dynamic import for `node:fs/promises` so esbuild can still bundle the browser app.
- Existing recorder sidecars expose `track`, not `track_id`; the UI matches annotation `track_id` to sidecar track metadata by slug-normalizing both values and defaults missing layout metadata to `default`.
- Reusing the existing `.json` load path was enough: apex annotation JSON is recognized by the contract shape (`track_id`, `layout_id`, `corners`) and is not attached as ordinary session metadata.
