# Handoff — Slice 14: explicit full-name exceptions

## State

- Curva Grande is spoken in full in both Monza Curva Grande models.
- Interlagos retains Descida do Lago 1 and Descida do Lago 2 in full, preserving
  the subdivision suffixes. Bare Descida do Lago is protected for future data.
- `FULL_NAME_EXCEPTIONS` in `dev/scripts/curate_short_names.py` takes precedence
  over pre-existing aliases. This prevents a rerun from reinstating Grande or
  Lago 1/2. Other existing aliases retain their ordinary precedence.
- Corpus tests pin all affected real models. A synthetic writer test covers
  shortened legacy aliases, bare names, numbered names and repeat runs.
- No flags, runtime coach code, geometry, reference exports or map changes.

## Verification

- Feature: `bash scripts/test-summary.sh --feature coach-short-corner-names`
  passes (702 assertions, 14 scripts).
- Full --pw passes (1659 assertions, 69 scripts), with the temporary Windows
  ESM adapter from slice 13's handoff. Stock bug-20 Windows imports are not fixed
  by this slice; the adapter remains uncommitted environment tooling.
- Build passes and `product/dist/compare.html` is current.
- Guarded writer --check reports no pending changes.
- `artifacts/audit.md`: exactly four alias changes; every non-alias field and
  all other aliases match pre-slice `e624f7a`.

## Future exceptions

Only add full proper names explicitly requested/reviewed. Add corresponding
corpus/writer expectations before updating the allowlist and running --write.
This does not introduce a general rule to keep every Curva or Descida prefix.
