# Learnings: 08-root-cleanup

- The remaining tracked root clutter was the three legacy `phases_*` execution-history directories; root compatibility wrappers like `scripts/` are intentional because stable commands still use them.
- Archived phase prompts/handoffs contain historical self-references to their old root paths. Those were left untouched because they describe past execution state, while the stable spec was updated to point future work at `work/`.
