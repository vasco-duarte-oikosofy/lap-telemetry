# Learnings — Slice 46 (when a faster lap is not a better reference)

- **20 ms is not a reference lap.** The delta threshold in the exporter is 1 ms
  because that is enough to keep *one* file per combo; it is not a statement
  that the lap is a better model source. Here the faster lap carried no new
  corner information, so the honest answer to "update if needed" was "not
  needed" — with the numbers to back it.

- **Ask what a corner's zone came from before trusting a refresh.** Two of Fuji's
  eleven corners (`13th Corner`, `Netz`) have no braking event within 5 m of
  their apex even on the reference the model was built from. They are manual
  markers. Any future refresh must treat them as `--preserve-geometry`, and the
  matcher's "unmatched" warning for them is expected, not a problem to fix.

- **Bug 29 is not a rare edge case: it fires on this corner every time.** The
  greedy, model-order matcher gives `Netz` (3310 m, listed first) the
  `Netz Hairpin` event (3385 m) and leaves the hairpin unmatched — +136 m of
  exit movement that the audit would print as a normal refresh. The only
  reliable guard today is `--preserve-geometry` or a `--max-geometry-delta-m`
  below the displacement (`40` aborted this run).

- **Check apex stability across *clean* laps, not across all laps.** Including
  the 1:45 lap-1 rolling start made 100R look like it spanned 208 m; restricted
  to laps within 1.5 s of the best, the honest spread is 135 m — still far more
  than the +44 m the refresh proposed. A corner whose event apex wanders 100 m
  between laps cannot be defined by a single lap.

- **A read-only slice still needs its hashes.** The deliverable is a decision,
  so the proof that nothing was written is as important as the reasoning:
  `before-state.json` + `git status` show zero product changes.

- **Documenting the safe command matters more than documenting the veto.** The
  next agent will meet the same 20 ms temptation; giving the exact
  `--preserve-geometry` incantation (and why it is still not worth it) prevents
  both a blind re-run and a silent bug-29 corruption.
