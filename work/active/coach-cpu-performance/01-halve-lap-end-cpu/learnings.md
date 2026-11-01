# Learnings

- The dominant local cost was neural synthesis: ~59.27 warm CPU-s versus only
  ~0.50 CPU-s for full-session read/comparison/template generation. Optimizing
  the comparator first would not meet the requested whole-pipeline target.
- ORT auto threading spent ~60 CPU-s per event, peaking around 8.5 cores. A
  bounded one-thread/no-spin session costs ~14.2 CPU-s while wall time stays
  near 15.2 s. More inference threads were wasting CPU, not delivering a useful
  latency benefit on this machine. Always compare CPU-seconds, not just wall time.
- The original engine also consumed ~0.328 CPU-s in the idle second after
  synthesis. Disabling worker spinning removes that measured tail.
- Exact waveforms are possible despite the thread-policy change: all 12 outputs
  are bit/sample-identical. There is no need to trade speech quality for this win.
- Windows venv python.exe is a launcher with a child interpreter. Sample the
  whole process tree, not the launcher alone; launcher thread counts are useless
  for inferring ONNX concurrency. Exact process_time inside the worker captures
  its native threads; exact completed-child times capture short-lived Node work.
- Windows cannot os.replace a marker while another process briefly reads it
  without delete sharing. Simple marker writes plus tolerant metadata reads avoid
  perturbing the benchmark. Markers are outside measured phase work.
- Large benchmark outputs do not belong in var/coach-cpu (not ignored). Use
  var/tmp/coach-cpu; committed compact reports and waveform hashes are enough.
- The original nonblocking test fixture is stale/unregistered, ending at 1900 m
  for a 5000 m model. The production partial-lap guard correctly rejects it;
  don't weaken the guard to make unrelated historical tests green.
- At ~23.6% of original CPU, remaining synthesis dominates. A 10% total budget
  needs another ~59% reduction in synthesis work, not a small JSON/cache tweak.
  Exact audio caching needs a realistic hit-rate study; fixed replay repetitions
  would produce misleadingly excellent cache numbers. Priority/isolation can
  improve FPS interference without reducing total CPU work: report separately.
