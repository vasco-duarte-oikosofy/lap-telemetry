# Slice 10 learnings

## `--print-facts` vs `--debug`

Both flags expose facts but serve different audiences. `--debug` goes to
stderr and is aimed at tracing the full run including the LLM response.
`--print-facts` goes to stdout, exits before the LLM, and is designed for
piping (`| jq '.top_losses'`). Keeping both preserves the debug trail without
breaking the clean inspector use case.

## JS wrapper: `python` not `python3` on Windows

All existing JS wrappers call `python3`, which is not available on this
Windows dev box and causes all those tests to fail in CI. The new wrapper
uses `python` instead, which resolves correctly here. Left the pre-existing
wrappers alone — fixing them is out of scope for this slice.

## `args.print_facts` attribute name

`argparse` converts `--print-facts` (kebab) to `args.print_facts` (snake).
No special handling needed.
