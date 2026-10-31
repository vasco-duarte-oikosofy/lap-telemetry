# Slice 05 — Type size in the compare app

The labels render, but the type is too small in `dist/compare.html` (and this
format only — the reviewed 5.75 px on a 250 px map is fine).

Root cause: `fontMax: 8` was the 250 px spike's ceiling and it bound on the
product's 500–950 px map panel, so the type never grew.

Fix the constant, keep small maps untouched, and prove it on every packaged
outline at three real viewport sizes.
