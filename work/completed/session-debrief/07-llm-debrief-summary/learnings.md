# Learnings — Slice 07: LLM debrief summary

- **Grounding is a budget, not a summary.** 18 laps × 9 corners is 338 KB of
  JSON; the coach gets 2.8 KB. The number that made it work was putting the
  *mean* gap, the envelope and the top three priorities in the first screen — the
  model's opening sentence comes from those lines, and the lap table is there
  only so it can answer "which lap was best".
- **The drill-down belongs in the user turn, not the system prompt.** The system
  prompt (contract + session grounding) is identical for every turn, so it can be
  cached; the corner detail is about this question. Moving it also made the test
  assertion honest ("a named corner brings its drill-down" now checks the user
  message).
- **Validation has to allow rounding, or it cries wolf.** "0.7 seconds" against a
  fact of `0.702` is correct coaching, not an invented number. The matcher
  rounds the fact to the precision the reply used and compares strings; a real
  invention ("4.7 s") still fails.
- **The template path is not a toy.** `--no-llm` answers from the facts and must
  obey the same contract: one positive with a number, one loss, one fix, exactly
  one question. It is what makes the feature testable in CI and usable offline,
  and its answers pass the same validator as a model's.
- **Unrounded floats leak.** The first corner block printed
  `brake peak 0.20694518089294434`, which is both unreadable and a waste of the
  byte budget. The brief now rounds every value and the test asserts no float
  with six or more decimals appears.
- **A missing corner is a valid answer.** Asked about a corner with no measurable
  loss, the template says so ("not costing you measurable time on the clean
  laps") instead of inventing a fault — the same principle as slice 05's
  "no single measurable cause".

## Still unverified

The real provider path (`call_llm` with Ollama) is exercised only by hand, not in
CI: no key and no network in the test environment. The message assembly, the
contract and the validation are all covered by the fake adapter.

## What the first live run taught (added after the mission closed)

- **"At most 120 words" is a trap for small models.** `glm-5.3-flash` started
  literally counting: `Count: Positive(1) first(2): … You(57) arrive(58)`. The
  word limit now lives only in the validator; the prompt asks for brevity
  without a number, and annotation is flagged as degenerate output.
- **Validate against what you actually sent.** The drill-down numbers
  (22.9 km/h spread, lap 4 at 86.4, +1.559 s) were reported as invented because
  `validate_reply` only saw the session grounding. The validator now receives
  grounding + drill-down, exactly the text the model was given.
- **A dead provider must not be a traceback.** A retired model id
  (`glm-5.1:cloud`, 410) crashed the REPL; provider SDK errors are now wrapped
  in `LLMAdapterError` and the conversation continues with one sentence saying
  what happened and how to recover.
- **Providers can split a reply.** One answer arrived starting mid-word because
  the first characters went into the `reasoning` field. Not recoverable, so it
  is detected: a reply that does not end in a sentence terminator is flagged.
