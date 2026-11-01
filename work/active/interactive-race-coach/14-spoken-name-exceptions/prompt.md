# Slice 14 — Preserve user-selected full spoken corner names

**Status:** ✅ Complete in `093c04a`.
**Feature tests:** `bash scripts/test-summary.sh --feature coach-short-corner-names`

## Acceptance

- Explicit exceptions to short-name curation: Curva Grande must be spoken as
  Curva Grande, not Grande. Descida do Lago must retain the full name, including
  the current Descida do Lago 1/2 subdivision suffixes.
- Apply to all matching coaching models (both Monza cars and Interlagos).
- Exceptions override earlier curated aliases in the guarded writer; reruns
  must not revert them. Other curated names and number spelling stay unchanged.
- No runtime algorithm, official-name, geometry, reference or map-label changes.

## Steps

1. Extend corpus tests and add exception-writer coverage; observe red.
2. Add a small explicit exception allowlist in the curation tool; run its
   preview, guarded writer and idempotence audit.
3. Adjust the prior Monza naming expectation. Run feature tests, full --pw
   (document existing Windows ESM workaround) and build.
4. Commit on main, record hash/status in PLAN and handoff/learnings, stop.
