# Learnings — Barcelona/P3 qualifying refresh

- The session is finalised and canonical: no shard merge/freeze is needed.
- Summary and debrief inventory both display lap 6's 1:31.518 with valid flags.
  It is not a complete lap: distance ends at 4295.19 m versus a 4653.58 m peak.
  The guarded export's coverage check rejects it and selects lap 4, 1:36.040.
  Valid flags alone are insufficient; do not export a fastest-looking table row.
- The source contains lap 4 at zero-based rows [21361, 26151), exactly 4790
  samples. Authoritative lap-start elapsed-time difference is 96.039978 s,
  correctly rounded to 96.040 s for metadata and the reference filename.
- The extractor CLI's --segment numbering is one-based; the internal segment
  lists/review indices are zero-based. Use --segment 4 to extract lap 3 here.
- The updated reference supersedes an on-disk, uncommitted 1:36.319 race
  candidate. The previously committed reference was 1:36.456; do not confuse
  those two baselines when interpreting the final git deletion.
- The same curation limits seen in the race candidate remain: two secondary
  turns lack independent detected events, Campsa's candidate overlaps its
  predecessor, eight other candidates exceed the 40 m geometry guard. Retain
  those eleven reviewed objects; refresh only Renault (8/4/5 m changes).
- Historical exact-value tests were tied to the mutable active reference/model.
  Pin their original 1:36.456 pair as dev fixtures instead of changing the
  numerical assertions. The new PB also changes the old t3 earlier/later-exit
  example, so its loss-distance-sign regression needs the same fixed pair.
- Barcelona's shared outline is backed by the Ferrari model (14 turns), not
  this 12-corner P3 model. No map rebake/TinyPedal update is needed or intended.
- On this environment, invoke Python with PYTHONPATH=product/python for module
  entry points/extractor. The installed lap-telemetry executable does not
  resolve the package by itself. All checks here were deterministic, no LLM.
- The user explicitly removed archive-wide provenance scans from this workflow.
  Validate only the changed reference against the selected source session. The
  three runbooks now make the whole-folder validator optional on explicit request,
  not a pre-commit requirement. Do not repeat the slow all-sessions scan.
