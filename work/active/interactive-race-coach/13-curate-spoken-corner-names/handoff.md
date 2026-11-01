# Handoff — Slice 13: corpus-wide spoken names

## Delivered

- Audited all **33 models / 453 corners**, adding **340 aliases** (153 distinct
  official names) under `product/data/track-coaching/`.
- Every multiword official name now has a nonblank `short_name`.
- Examples: Farm Curve → Farm, Curva Grande → Grande, Turn 10A → Ten A,
  Turn 10B → Ten B, Turn 12 → Twelve. Fuji 100R → One Hundred R.
- Numbers below ten remain digits; Lesmo 1/2, Roggia 1/2, Ascari 1/2/3 retain
  their subdivisions. Kink 2/4 and Becketts Entry/Exit remain distinguishable.
- Existing curated aliases are unchanged and reused consistently across cars.
  Recognizable proper names such as Eau Rouge and La Source stay intact;
  Netz Hairpin stays distinct from Netz rather than being shortened blindly.
- All IDs, official names, geometry, reference metadata, throttle targets,
  ordering, apex sides and straight zones are unchanged. See `artifacts/` for
  independent parsed-JSON audit against baseline `a39f21f` and reviewed aliases.
- No runtime coach code, map data or reference laps changed. No new flags.

## Guarded curation tool

`dev/scripts/curate_short_names.py`:

```bash
export PATH="$PWD/.venv/Scripts:$PATH" PYTHONUTF8=1
python dev/scripts/curate_short_names.py          # preview; no writes
python dev/scripts/curate_short_names.py --check  # exit 0 when up to date
python dev/scripts/curate_short_names.py --write  # changes only short_name
```

The writer uses stable corner IDs, checks stale previews, preserves existing
formatting/newlines/Unicode escapes, stages and validates all candidate files
before writing, and compares parsed models with aliases stripped. Re-running is
byte-idempotent. The legacy 636-line Spa model was compacted to 84 lines in a
separate formatting-only commit (`bd32dbb`) to meet the 437-line ceiling.
New aliases require review: extend the explicit `REVIEWED` mapping instead of
adding a blanket word-stripper. The tool otherwise retains unknown proper names.

## Tests and build

- Red first: new corpus test failed for missing aliases and digit-by-digit 10+.
- `--feature coach-short-corner-names`: **695 assertions, 14 scripts, pass**.
- `--feature interactive-race-coach`: **1019 assertions, 29 scripts, pass**.
- Full `--pw`, with temporary Windows import adapter: **1652 assertions across
  69 scripts, pass**. Stock full command still encounters the six known bug-20
  Windows `ERR_UNSUPPORTED_ESM_URL_SCHEME` failures (not caused/fixed here).
- `npm run build`: passes; `product/dist/compare.html` regenerated.
- `git diff --check`: clean.

`test_curated_short_names.py` + Node wrapper cover the complete corpus, critical
aliases, number spelling, real model → template text, writer persistence,
metadata/geometry preservation, CRLF/Unicode handling, idempotence and stale
preview rejection. Registered in the full and both coach feature test lists.

Slice-12 fallback coverage now uses synthetic uncurated input, rather than
assuming a real model is still uncurated. Map tests pin baked display labels
separately from spoken aliases, retaining official-name/geometry parity checks.

## Windows full-suite adapter (temporary, not shipped)

The six existing tests import `C:\\...` paths as ES module specifiers instead of
`file://` URLs. To verify the whole suite without changing unrelated tests, a
local Node loader at `%TEMP%/lt-windows-esm-loader.mjs` adapts those specifiers
only (preserving query/hash suffixes). Recreate it with:

```javascript
import { pathToFileURL } from 'node:url';
export async function resolve(specifier, context, nextResolve) {
  if (/^[A-Za-z]:[\\/]/.test(specifier)) {
    const suffix = specifier.search(/[?#]/);
    specifier = suffix < 0 ? pathToFileURL(specifier).href
      : pathToFileURL(specifier.slice(0, suffix)).href + specifier.slice(suffix);
  }
  return nextResolve(specifier, context);
}
```

Then, on this Windows checkout:

```bash
NODE_OPTIONS='--experimental-loader=file:///C:/Users/duart/AppData/Local/Temp/lt-windows-esm-loader.mjs --disable-warning=ExperimentalWarning' \
  bash scripts/test-summary.sh --pw
```

This is an environment workaround, not a committed bug-20 fix. No ordinary
feature test needs it. Do not mistake the stock full suite for green on Windows.

## Deferred (not this slice)

Map `short_name` values are baked display data; they intentionally retain their
pre-slice labels. A future map rebake currently reads coaching aliases and could
pull speech-only spellings into map labels. Review that separately; do not
blindly rebake all outlines to match this speech curation.
