# vendor/

Third-party and externally sourced code lives here.

Use this folder for code whose primary ownership is outside this repository, including Git submodules and vendored dependencies.

## Current contents

- `vendor/pyLMUSharedMemory/` — TinyPedal fork of the LMU shared-memory Python bindings, tracked as a Git submodule.
- `vendor/pyRfactor2SharedMemory/` — TinyPedal fork of the rFactor 2 shared-memory Python bindings, tracked as a Git submodule.

## Belongs here

- Shared-memory dependency submodules.
- External code copied or mirrored for integration.
- Notes needed to update or verify vendored dependencies.

## Does not belong here

- First-party product code.
- Development-only scripts.
- Mission plans or temporary artifacts.

Update these dependencies through normal Git submodule commands from the repository root, for example `git submodule update --init --recursive`.
