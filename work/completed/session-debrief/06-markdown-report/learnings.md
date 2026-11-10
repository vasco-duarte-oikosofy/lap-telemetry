# Learnings — Slice 06: Markdown report

- **The renderer must not compute.** The first version printed "23% of your
  average 1.969 s gap" in the headline while the priority's `share_of_gap` was
  computed against the 3.037 s *mean* gap — two different answers to the same
  question in one document. `LapPace.mean_gap_s` now exists in the facts and the
  priorities are built with it, so every percentage in the report has one
  denominator.
- **Evidence that contradicts the claim is worse than no evidence.** Bretelle's
  headline phase is minimum speed with a 0.29 s loss, but the driver's apex speed
  (71.0 km/h) was *higher* than the reference's (65.0). Printing that line next
  to the loss invites "but I was faster". The report now only shows the evidence
  line when the driver's value is worse.
- **Corner names can be digits.** The Paul Ricard model calls turn 2 `"2"`, so
  the report read "The one to fix is **2**". Labels are now "corner 2" when the
  name is numeric.
- **"gear 1 vs 1" is noise.** Showing a comparison where both sides agree makes
  the whole evidence block look untrustworthy; the gear is only printed when the
  two differ.
- **The report is a contract for the conversation.** Because the Markdown is
  deterministic and complete, slice 07's prompt can quote it verbatim instead of
  re-summarising the facts — and a mismatch between what the coach says and what
  the report says is now a test-visible bug.
- **Determinism is cheap to keep and expensive to lose.** No timestamps, no
  floats formatted through the locale, no iteration over unordered maps. The test
  asserts two renders are byte-identical, which catches accidental `set`
  iteration immediately.
- **A gate that writes nothing is a feature.** The Lusail session (4 eligible
  laps) must not leave a half-written report next to the recording; the test
  checks the output directory stays empty.
