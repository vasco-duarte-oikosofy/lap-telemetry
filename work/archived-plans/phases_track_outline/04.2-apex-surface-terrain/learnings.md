# Learnings — Phase 04.2 Apex Surface/Terrain

- The loaded telemetry already carries the four wheel surface and terrain arrays, and the Phase 04.1 session slicing keeps those arrays aligned with each lap segment without extra aggregator code.
- Surface values are numeric recorder channel values today, even though the apex metric contract names the field generically as `surface_type`; the metric preserves the raw channel value instead of inventing labels.
- Treating `null`/`undefined`/empty string as missing keeps front-to-rear fallback deterministic while preserving valid numeric surface value `0`.
