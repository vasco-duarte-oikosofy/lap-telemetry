# Handoff — Slice 12: coach speaks curated short corner names

**Status:** ✅ Done. Feature tests green, full suite unaffected, build current.

## What is on disk now

| File | Change |
|---|---|
| `product/python/lap_telemetry/coach/track_model.py` | `Corner.short_name: str \| None = None` and a `display_name` property (`short_name or name`). `validate_corner()` reads the key (absent → `None`), rejects non-strings with `TrackModelValidationError`, and normalises blank/whitespace-only values to `None`. |
| `product/python/lap_telemetry/coach/lap_comparator.py` | All three `CornerLoss(...)` sites now use `corner_name=corner.display_name`. |
| `product/python/lap_telemetry/coach/corner_exit_detector.py` | `_emit()` builds `CornerExited.corner_name` from `corner.display_name`. |
| `dev/scripts/test_coach_short_names.py` / `.js` | New regression test, 49 assertions. |
| `package.json` | Feature list `coach-short-corner-names` (11 scripts); `test_coach_short_names.js` added to `scripts.test`. |

Nothing else changed: `name` is still the authoritative official name, `corner_id`
is still the stable identity, and the facts JSON shape is unchanged.

## The one rule

```python
Corner.display_name  # -> short_name if curated (non-blank), else name
```

Use it anywhere a corner name is shown **to the driver**. Do not use it for
identity, lookups or matching — use `id` for that.

## Verified end to end

Monza Curva Grande / DKR P3 (`session_20261101T055404Z`), template adapter:

| lap | before | after |
|---|---|---|
| 3 | "…at the apex of Variante della Roggia 2… at the apex of Variante Ascari 2." | "…at the apex of **Roggia 2**… at the apex of **Ascari 2**." |
| 8 | "…the apex of Variante della Roggia 2…" | "…the apex of **Roggia 2**…" |
| 12 | "…at the apex of Curva Alboreto (Parabolica)…" | "…at the apex of **Parabolica**…" |

LLM path checked too: `build_corner_exit_messages(facts, "Roggia 2", 1)` sends
`Corner-exit comparison facts for Roggia 2:` and `"corner_name": "Roggia 2"` in
the JSON payload.

## Test / build state

```
bash scripts/test-summary.sh --feature coach-short-corner-names → ALL PASS (484 assertions, 11 scripts)
bash scripts/test-summary.sh --feature interactive-race-coach    → ALL PASS (806 assertions, 27 scripts)
bash scripts/test-summary.sh --pw                                → 1436 passed, 6 of 68 failed
npm run build                                                    → OK, product/dist/compare.html current
```

The 6 failures are the pre-existing bug 20 Windows ESM issue
(`ERR_UNSUPPORTED_ESM_URL_SCHEME ... protocol 'c:'`), unchanged by this slice.
Run the suite with `export PATH=".venv/Scripts:$PATH" PYTHONUTF8=1` (L16).

## Follow-ups / notes for the next agent

1. **Only the Monza Curva Grande models have `short_name` today** (both the DKR
   and Vista AF Corse files; 6 of 10 corners). Every other track model still
   speaks the long name — curating `short_name` for Barcelona / Silverstone /
   Fuji / … is data work, not code work. `docs/specs/MAP_TURN_NAMES.md` already
   documents the field for the map and is the reference for how to curate it.
2. **The outline/turn-label bake reads `short_name` from the outline JSON**, not
   from the coaching model — the two are curated separately. If a corner is
   renamed for speech, check whether the outline `turns[]` entry needs the same
   value (map labels are a different surface).
3. `update_reference_and_coaching_model.py` **does** preserve `short_name`:
   `refresh_corners()` copies the whole curated corner dict verbatim and only
   replaces `s_start_m`/`apex_s_m`/`s_end_m`, so a refresh cannot strip it.
   `register_outline.py` handles `name`/`short_name` for the *outline* path.
   Covered by `dev/scripts/test_update_coaching_model.py` only insofar as that
   test checks curated fields survive; it does not know about `short_name` yet —
   worth a line there if you touch that script.
