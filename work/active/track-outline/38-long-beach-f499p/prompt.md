# Slice 38 — Long Beach / Ferrari 499P practice combo

**Status:** ✅ Delivered in `90c6e6e`; automated standalone rendering passes.
User live/by-eye outline approval remains pending. User confirmed this one combo.
**Feature tests:** `bash scripts/test-summary.sh --feature long-beach-f499p`

## Deliverables

1. From `sessions/session_20261101T114510Z_grand-prix-of-long-beach_lmu_practice.parquet`,
   export the fastest guarded, valid complete Ferrari 499P lap. Use contiguous
   segments and telemetry-clock timing; do not trust an abandoned lap's displayed
   time or filter raw rows by lap_number. Validate the reference folder.
2. Create a car-specific coaching model for Grand Prix of Long Beach with
   official turn numbering/names and correct apex sides. Include detector-missed
   flat turns with full real zones and throttle targets; do not collapse them
   to points or attach them to a neighbour's braking geometry.
3. Generate a trajectory outline from this reference (unless an appropriate
   external width source exists), preserving actual flat-turn shape. State that
   constant-width boundaries are synthetic, not physical walls/track limits.
4. Register the generated module/manifest, bake correct turn markers, build,
   update coverage, and verify coach resolution/facts and browser rendering.

## Process

- Read coaching/reference/outline pipeline guides and nearby track slices.
- Verify exact vehicle catalog entry resolves to ferrari-499p.
- Review official circuit map and telemetry together; document sources and
  per-turn geometry so later refreshes can preserve flat turns.
- Test first: reference timing/provenance, complete official turn list, real
  flat zones, position/steering plausibility, runtime outline registration.
- Use guarded scripts for product data, one combo only. Do not alter unrelated
  models or refresh their references. Run feature tests, full --pw, and build.
- Commit on main, record handoff/learnings and plan status/hash, stop. Separate
  future by-eye live QA from automated render evidence.
