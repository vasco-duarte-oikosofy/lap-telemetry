# Learnings — Slice 02 (rear-slip-aware advice)

## The trigger session had a 13.78° slide and the old advice was "brake later"

It is worth stating plainly, because it justifies the whole slice: at Becketts
on the Silverstone P3 race the rear slip reached **13.78°** at the apex — an
order of magnitude above the 1.71° clean-lap baseline — and the debrief's
instruction was *"hold the brake 20 m longer"*. The evidence existed on disk and
the advice was computed without it. Nothing in this slice invented new physics;
it connected a number that was already measurable to a sentence that was
already being generated.

Corollary for future slices: the missing piece was not a channel, it was a
**consumer**. `corner_extras` had facts; `suggest_change` had no parameter for
them.

## "Suppress", not "soften" — and the difference is testable

The first instinct was to append a qualifier ("…but watch the rear"). That is
still asking the driver to brake later into a corner that just bit them. The
rule that shipped removes the braking/speed clauses entirely when the slide
overlaps the brake, and the test asserts the absence of "hold the brake …" in
the suggestion — an assertion about what is **not** said, which is what a
safety-relevant contract needs.

## The prose and the structure must come from the same object

Every surface (suggestion, grounding, report, plan, no-LLM answer) formats one
`RearStability` object via `describe()`. That is what makes the acceptance
criterion "report, grounding, named-corner block, no-LLM answers and plan carry
consistent evidence" testable at all: there is only one producer.

It also keeps the coach's number validator honest: `describe()` only prints
numbers the facts contain, so a reply that repeats the sentence passes
`validate_reply` instead of being flagged as invented.

## A top-3-only implementation silently drops the important case

The Barcelona session's measured slide (Repsol) ranks **#4** in the priorities.
The first implementation only summarised rear stability for the top three
priorities — so the one genuine slide in the session was absent from both the
grounding and the plan, while the report still showed it. Two different truths in
one conversation is exactly the failure mode the slice exists to prevent.

Fixed with two rules: *every* measured instability is listed in the grounding
(wherever it ranks), and the plan gets an `Also measured:` line for a slide that
is not one of its three targets. Only the `unknown` state is limited to the
coached corners, because that is where an unanswered question would otherwise be
read as a clean bill of health.

## `unknown` is the state that will regress first

Every fixture used by the older debrief tests is a pre-column parquet, so the
whole suite now exercises the unknown path by default — which is the right
default, and it is why the "advice unchanged when unknown" assertions could be
exact (`suggestion == control.suggestion`) rather than fuzzy. Keep the old
fixture in the suite: it is the cheapest guard against a future refactor that
starts inventing slip numbers for old sessions.

## The test suite was lying about being green

`--pw` had failed for everyone since remote commit `15dc971` added a tracked
`.agents/` directory: the root-cleanup guard's allowlist did not know it. Nobody
noticed because feature runs are green and the full suite is run at milestones.
That is the second time in two slices a repo-root guard caught something no
feature suite can see — worth remembering when a milestone "passes".

## Small mechanics

- `build_targets` and `render_plan` are pure functions of the facts; the
  artifact generation for a real session is three calls, no REPL needed.
- The grounding budget (4096 B) is generous today (Silverstone 3727 B) but the
  block order matters more than the size: constraint before the lap table.
- A target's caveat is structured (`Target.caveat`, serialized in the
  transcript), not just Markdown — a UI should not have to parse prose.
- Synthetic slip injection on a real facts object (`_inject_slip` in the tests)
  is the cheapest way to test the measured path: the physics stays real, only the
  numbers are made up.
