# Experimental ESP-EMU WASM workflow

Local Toolkit 0.36.0's published default pin selects sim-runner 0.8.0, HIL Runner 0.13.0
and Embedded Trace 0.13.0: 95 source/asset/schema/metadata/license files. Each
component is bound to its release tag/source commit, wheel URL/hash and payload
inventory in `simulation-runtime.json`.

Choose this workflow explicitly for the experimental `esp32c3-wasm-flash-v1`
profile. It does not change native locks or station.

## Select the published environment

During requested host setup, install the exact wheels from
`simulation-runtime.json` in a separate trusted Python 3.11+ environment
using `uv pip install --python <python> --no-index --no-deps <three-wheel-paths>`.
Verify wheel hashes and GitHub attestations before installation as described in
[simulation setup](simulation.md). Local integrity is not authentication.

```powershell
python scripts/simulation_runtime.py inspect '<absolute-simulation-venv>' --json
```

Require `ok=true`, `candidate_mode=false`, `resolution_source=pinned_releases`,
versions 0.8.0/0.13.0/0.13.0 and 95 verified files. Each distribution is
`published`. Existing `--component` supports individual checks. A missing,
changed or unexpected selected payload fails without fallback.
The preserved `simulation-candidates.json` records the earlier local builds;
`--candidate` explicitly selects those older 0.7.0/0.8.0/0.8.0, 69-file
declarations. Versions and inventories differ from the current default;
neither mode falls back to the other. It is unnecessary for normal WASM use.

For a requested combined host check:

```powershell
python scripts/toolkit_doctor.py --strict --json `
  --simulation-environment '<absolute-simulation-venv>'
```

Combined doctor may run native version commands; simulation inspection only
reads files. Its `backend_runtime_verified`, `release_attestation_verified`,
`physical_board_verified` and `executables_started` remain false. It does not
start Node, load WASM, check a board or verify the separate emulator runtime.

## Use the fixed native backend

The profile accepts Windows, hash-bound Node 24.15.0 and official ESP-EMU 0.50.0
WASM, with compatible unsigned ESP-IDF 5.5.2 ESP32-C3 4 MiB DIO factory Flash.
Read sim-runner's `docs/esp-emulator-wasm.md` for runtime pinning, inventory and
image restrictions. Static environment inspection does not install/authenticate
Node or the emulator. S3, arbitrary JS, browser workers, network/radio/UART input
and physical bridges are outside this fixed profile.

```powershell
$python = '<simulation-venv>\Scripts\python.exe'
& $python -I -m sim_runner doctor --backend espressif-esp-emulator-wasm `
  --runtime-lock '<runtime-lock.json>' --runtime-sha256 '<lock-sha256>'
& $python -I -m sim_runner plan --backend espressif-esp-emulator-wasm `
  --profile esp32c3-wasm-flash-v1 `
  --runtime-lock '<runtime-lock.json>' --runtime-sha256 '<lock-sha256>' `
  --firmware '<flash.bin>' --firmware-sha256 '<image-sha256>' `
  --ready-line '<complete READY line>' --build-line '<complete BUILD line>' `
  --heartbeat-prefix '<heartbeat prefix>' --min-heartbeats 5 `
  --instruction-budget 50000000 --timeout 30 --output '<new-plan.json>'
```

Continue with native inspect-plan/run/inspect-report in the
[simulation guide](simulation.md). Native commands emit JSON without `--json`.
HIL 0.13.0 uses the existing simulation spec with the pinned 0.8.0 wheel and
native plans. It preflights all cases before any emulator starts, runs each
once and stops on failure/indeterminate state. Earlier supported profiles may
share a suite. No hardware fallback, lease, per-run approval or recovery is added.

## Preserve the evidence meaning

`uart.bin` holds the ASCII subset of strings returned by WASM, encoded as UTF-8;
it is not verified original UART bytes. HIL and Trace filtered views retain
`uart_representation`, `raw_uart_bytes_verified=false`, `model_limits`, opaque
builtin ROM/eFuse `initial_state`, unmeasured `virtual_time`, native assertions,
native errors and `runtime_observation`, even when metadata events are excluded.

Normal results remain `passed_with_model_limits` / `succeeded_with_model_limits`.
A guest restart request ends execution with `restart_performed=false`; it does
not authorize a restart or another instance. Instruction-budget exhaustion fails.
Requested instruction upper bounds and model cycle/clock claims are not retired
instruction counts or measured timing. A fast budget failure is not a timeout.

Timeout/process failures may leave assertions/observations null. Preserve the
unknown state and partial files. Trace reads only fixed adjacent files and four
fixed `component/` artifacts. Its spans refer to saved encoded strings and
windows to host run times. It does not read live runtime paths, rerun firmware
policy or authenticate reports. Coverage/security/physical timing remain false;
simulation is not real-board acceptance.
