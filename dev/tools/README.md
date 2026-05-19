# dev/tools/

Development tools live here.

Use this folder for browser helpers, validation pages, diagnostics, and one-off utilities that support development but are not part of the production product boundary.

## Track outline generation

See [`README-GENERATE-OUTLINE.md`](README-GENERATE-OUTLINE.md) for the detailed workflow to generate and register a new track outline from simulator trajectory/session data. That guide covers the required data, scripts, validation, and rebuild steps.

## Reference lap export

See [`README-REFERENCE-LAPS.md`](README-REFERENCE-LAPS.md) for how to regenerate the reference lap parquets in `product/data/reference-laps/` — one fastest-clean-lap per track, named with the vehicle slug so users know which car produced the lap.
