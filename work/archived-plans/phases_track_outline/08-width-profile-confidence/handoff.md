# Handoff — Phase 08 Width Profile Confidence

State on disk:

- `scripts/export_width_profile.js`
  - `buildProfileFromRows(rows, binSizeM)` now:
    - Uses `Math.abs(track_edge_m)` for width values (fixes negative left-side encoding in LMU data).
    - Fills gap bins between min and max `s_m` — missing positions are explicitly present with `status: "missing"`.
    - Adds `status` and `confidence` fields to every sample bin.
    - Returns `{ samples, skipped, missing_bins, one_sided_bins, low_sample_bins, complete_bins }`.
  - New exported function: `classifyBin(bin)` — pure function returning `{ status, confidence }`.
  - New constant: `MIN_SAMPLES = 3` — minimum sample count per side for "complete" status.
  - `exportWidthProfile` summary now includes `missing_bins`, `one_sided_bins`, `low_sample_bins`, `complete_bins`.
  - CLI stdout prints confidence breakdown after export line.

- `scripts/test_width_profile_confidence.js`
  - 54 assertions covering all Phase 08 acceptance criteria.
  - Tests: complete bins, one-sided bins, low-sample bins, gap bins explicit, negative track_edge_m, confidence ordering, CLI summary counts, CLI stdout output, mixed fixture with all statuses, Parquet round-trip with abs, both-sides-under-MIN, Phase 07 smoke.

- `scripts/test_width_profile_export.js`
  - Updated 2 assertions in Test 3: gap bins at s=1 and s=2 are now present (status="missing") instead of absent.

- `package.json`
  - Added `node scripts/test_width_profile_confidence.js` to `npm test`.

Confidence rule (documented in code):

| Status      | Condition                                       | Confidence |
|-------------|-------------------------------------------------|------------|
| complete    | both sides have >= MIN_SAMPLES (3) samples      | 1.0        |
| low-sample  | both sides present, but one side < MIN_SAMPLES  | 0.75       |
| one-sided   | exactly one side has samples                    | 0.5        |
| missing     | gap bin, no data at this s_m                    | 0          |

Feature flags live:

- No new feature flags. Width profile CLI remains command-driven.

Verification:

- `npm test` passed (all prior + 54 new assertions).
- `npm run build` passed; `dist/compare.html` unchanged (no frontend changes).

Deferred:

- Interpolation/smoothing of gaps → Phase 08.1.
- Center path polyline → Phase 09.
- Boundary polylines → Phase 09.1.
- Browser UI changes.
- More nuanced confidence (e.g., weighted by sample count) → Phase 12 diagnostics if needed.