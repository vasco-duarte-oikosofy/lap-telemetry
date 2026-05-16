# Learnings: 05-product-subtree

## Notes

- Moving the product subtree requires updating both direct filesystem paths and module import paths used by Node tests.
- Python package imports still use `lap_telemetry`; only the source location changed to `product/python/lap_telemetry`.
- `dev/scripts/test-summary.sh` now sets `PYTHONPATH` so Python subprocess tests can import the moved package without requiring an editable install.
- `product/dist/compare.html` replaces root `dist/compare.html` as the standalone viewer bundle.
- `AGENTS.md` still references the old bundle path and should be updated only after explicit permission.
