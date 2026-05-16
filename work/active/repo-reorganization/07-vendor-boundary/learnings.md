# Learnings: 07-vendor-boundary

- Moving Git submodule working trees with `git mv` also updated `.gitmodules` paths in this repository state; still verify `.gitmodules` explicitly because the path is the durable clone/init contract.
- The recorder imports the shared-memory libraries by module name (`pyLMUSharedMemory`, `pyRfactor2SharedMemory`), so the source-checkout import path must add `vendor/`, not the repository root.
- A layout-only vendor test is not enough: `dev/scripts/test_track_outline_recorder_channels.js` now imports both shared-memory struct modules through the recorder path so this recorder dependency cannot silently break.
