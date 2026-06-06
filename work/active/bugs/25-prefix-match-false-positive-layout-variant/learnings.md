# Bug 25 learnings

- **Prefix matching was solving a hypothetical problem**: The `slug.startswith(track_part + "-")` heuristic was added for a "Circuit de Barcelona-Catalunya" case that never occurred in any real LMU session. Removing it was safe.

- **Accent stripping broke José Carlos Pace**: The `_track_slug()` function stripped accented characters entirely (ó→nothing, é→nothing) rather than transliterating them (ó→o, é→e). This meant "Autódromo José Carlos Pace" produced `autdromo-jos-carlos-pace` — unreadable and not matching data files that used the transliterated form `autodromo-jose-carlos-pace`. Fixed by using `unicodedata.normalize('NFKD', ...)` + stripping combining marks in all 3 Python copies and the JS slugify.

- **Three copies of `_track_slug()`**: The slug function is duplicated in `track_model_resolver.py`, `reference_resolver.py`, and `writer.py`. Any change must be applied to all three. The JS `slugify()` in `trackOutlineManifest.js` also needs to match.

- **Reference lap file had wrong slug**: `autdromo-jos-carlos-pace_*` (stripped) vs the coaching model `autodromo-jose-carlos-pace_*` (transliterated). Renamed the reference lap to match.

- **NFKD normalization is the standard Python way to transliterate**: `unicodedata.normalize('NFKD', text)` decomposes "ó" into "o" + combining acute accent (U+0301). Then `unicodedata.combining(c)` identifies combining marks to strip. In JS, `String.normalize('NFKD')` does the same, and `/[\u0300-\u036f]/g` strips the combining marks.

- **JS manifest backward compat**: Added both `autodromo-jose-carlos-pace` (new canonical) and `autdromo-jos-carlos-pace` (legacy) keys to the OUTLINES map in `trackOutlineManifest.js`, so sessions recorded before/after the fix both find the outline.