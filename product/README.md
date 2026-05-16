# product/

Production/final code and product-owned assets will live here.

This folder is the future extraction boundary for a standalone product repository or Git submodule. Code placed here should be able to move with minimal dependency on repo-local development history.

## Belongs here

- Browser comparison app source.
- Python package code used by the product.
- Product-owned data required at runtime.
- Releasable product artifacts, if the project chooses to track them.

## Does not belong here

- Test reports or generated local output.
- Mission plans, handoffs, or temporary artifacts.
- Development-only scripts and one-off tools.
- Third-party/vendor code.

## Current subfolders

- `web/` — browser comparison app source.
- `python/` — Python package source.
- `data/` — product-owned data and track outline assets.
- `dist/` — generated standalone browser bundle.
