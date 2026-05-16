# Learnings — Phase 06 Apex Sidecar Export

- `hyparquet` works in Node via `asyncBufferFromFile()` and the same `parquetRead()` chunk API the browser path uses.
- The export helper only needs the lap number plus apex/track-outline channels; legacy files naturally load missing columns as empty arrays, which lets the existing apex aggregator return `status: "unavailable"`.
- Existing Node tests already produce `MODULE_TYPELESS_PACKAGE_JSON` warnings when dynamically importing browser ES modules; this phase did not change package module type.
