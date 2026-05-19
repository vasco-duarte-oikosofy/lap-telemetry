# dev/scripts/

Development script implementations live here.

This includes test runners, build implementation scripts, data-prep utilities, diagnostics, and one-off development automation.

Stable root commands may keep compatibility wrappers in `scripts/` while implementation code lives here.

## Track outline generation

The implementation scripts used by the outline-generation workflow live here, including `average_trajectory_outline.py`, `register_outline.py`, and related helpers. See [`../tools/README-GENERATE-OUTLINE.md`](../tools/README-GENERATE-OUTLINE.md) for the detailed guide to generating and registering a new track outline from simulator trajectory/session data.

## Reference lap export

`export_fastest_reference_laps.py` scans all session parquets and writes one fastest-lap parquet per track to `product/data/reference-laps/`. See [`../tools/README-REFERENCE-LAPS.md`](../tools/README-REFERENCE-LAPS.md) for when and how to re-run it.
