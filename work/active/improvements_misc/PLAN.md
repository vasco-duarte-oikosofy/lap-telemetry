# Mission: Miscellaneous Improvements

**Goal:** Fix UX regressions and visual inconsistencies in the comparison app.

---

## Vertical slices

| Slice | Item | Description | Status |
|---|---|---|---|
| `01-u3c-tc-panel` | U3c | TC active panel shows both laps in session/ref colours | 🔲 Not started |
| `02-u3b-throttle-strip` | U3b | Remove redundant TC activity strip from Throttle panel | 🔲 Not started |
| `03-u3-slip-colours` | U3 | Fix Slip angle panel trace colours to use session/ref identity | 🔲 Not started |
| `04-u5-panel-audit` | U5 | Audit all panels for consistent colour/line-style convention | 🔲 Not started |
| `05-u4-tooltip-colours` | U4 | Colour tooltip speed values by lap identity | 🔲 Not started |

Slices are ordered by impact: U3c first because it's a missing ref trace (core regression), then U3b (clutter removal), then U3/U5 (visual consistency), then U4 (nice-to-have).

---

## References

- [NEXT_STEPS.md](../../docs/NEXT_STEPS.md) — full backlog with descriptions
- [panelConfig.js](../../product/web/js/panelConfig.js) — panel/channel definitions