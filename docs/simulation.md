# Optional simulation workflow (local candidate)

Toolkit 0.26.0 source adds simulation routing for the tested local candidates
sim-runner 0.2.0, HIL Runner 0.3.0 and Embedded Trace 0.3.0. These versions have
not been published or attested. `simulation-runtime.json` binds their source
commits, wheel hashes and all 58 installed source/schema/metadata/license files.
It contains no download URL or implicit install step. Use the selected local
candidate wheels; do not substitute the older published HIL/Trace wheels.
The existing `hil-runtime.json` and `trace-runtime.json` still describe their
published hardware/offline workflows. Their inspectors do not accept these newer
candidates. Native component locks and workstation selection remain independent.

## Choose the appropriate domain

| Request | Native route | Result boundary |
| --- | --- | --- |
| One supported model/firmware regression | sim-runner plan / inspect-plan / run / inspect-report | Simulated firmware assertions and emulator cleanup |
| Sequential firmware builds or mixed supported backends | HIL Runner simulation plan / run / inspect | Stops after a failed/indeterminate case; no hardware lease |
| Search or report saved simulated UART | Embedded Trace correlate / inspect / query / report | Offline derived view; preserves recorded failures |
| Verify a physical board, radio, electrical behavior or real timing | Existing bring-up/hardware-test workflows | Requires physical evidence; simulation is insufficient |

Simulation-only requests do not require native hardware doctor, USB discovery,
board-registry selection, serial observation or debugger attach. There is no
automatic fallback to hardware on a missing model or failed simulation. Reuse
the user's development-task authorization; locally computed input hashes are
bindings, not additional user approval steps.

## Select and inspect the software

During requested host setup, install the three hash-checked candidate wheels
into a dedicated Python 3.11+ environment. Do not update the active station,
PATH or installed plugin to run an isolated simulation. Inspect all three:

```powershell
python scripts/simulation_runtime.py inspect 'D:\Tools\simulation\venv' --json
```

For a single component, add `--component sim-runner`, `--component hil-runner`
or `--component embedded-trace`. The default checks all three; requested missing
or changed payloads fail. Inspection never imports those packages, starts their
interpreter, downloads files or enumerates hardware. It reports declared Python
version/layout, selected components, exact source/wheel identities and file counts.
It rejects extra package files except generated `.pyc` caches. Interpreter,
stdlib, import hooks and bytecode authenticity are not checked. Use normal trusted
host software and isolated module mode; this is a point-in-time payload check,
not a sandbox or authenticated execution proof. `release_attestation_verified`,
`backend_runtime_verified` and `physical_board_verified` remain false.

An explicit `toolkit_doctor.py --simulation-environment '<venv>' --strict --json`
includes the same three file-only checks alongside the selected native components'
version commands. This is for a combined host-readiness task. Default doctor
does not search for simulation software; its success does not imply simulation
readiness. For simulation-only work the standalone inspector is sufficient.

Use the checked environment's trusted interpreter for native CLI commands:

```powershell
$python = 'D:\Tools\simulation\venv\Scripts\python.exe'
& $python -I -m sim_runner --version
& $python -I -m hil_runner --version
& $python -I -m embedded_trace --version
```

On POSIX inspection uses `bin/python`; execution of the current emulator profiles
and HIL simulation suites is Windows-only. Static environment inspection does not
check or execute the separate Renode/QEMU distribution. Native sim-runner does
that using its complete runtime lock before and after execution.

## Prepare a native simulation plan

Select the firmware and backend explicitly. Current profiles are deliberately
bounded:

- Renode 1.17.0: `nrf52840-uart-v1`, raw Cortex-M vector-table BIN, UART readiness;
  zero-initialized model state, a virtual execution budget and host deadline.
- Espressif QEMU `esp-develop-9.2.2-20260417`: `esp32c3-ram-uart-v1`, RAM-loaded
  RV32IMC ELF and UART readiness. No ESP-IDF flash boot, ESP32-S3, radio or enforced
  virtual-time budget. A host deadline is not a virtual-time measurement.

These are not full-chip/electrical models. Unsupported requested behavior must
remain unsupported; silent upstream peripheral stubs cannot always be detected.
Consult the selected sim-runner source's `docs/profile.md` and
`docs/esp32c3-qemu.md` for image layout, runtime inventory and assertion limits.

```powershell
& $python -I -m sim_runner doctor --backend espressif-qemu `
  --runtime-lock '<runtime-lock.json>' --runtime-sha256 '<runtime-lock-sha256>'
& $python -I -m sim_runner plan --backend espressif-qemu `
  --runtime-lock '<runtime-lock.json>' --runtime-sha256 '<runtime-lock-sha256>' `
  --firmware '<firmware.elf>' --firmware-sha256 '<firmware-sha256>' `
  --ready-line '<complete READY line>' --build-line '<complete unique BUILD line>' `
  --heartbeat-prefix '<heartbeat prefix>' --min-heartbeats 3 `
  --timeout 30 --output '<new-plan.json>'
& $python -I -m sim_runner inspect-plan --plan '<plan.json>' --sha256 '<plan-sha256>'
& $python -I -m sim_runner run --plan '<plan.json>' --sha256 '<plan-sha256>' `
  --output-dir '<new-run-directory>'
& $python -I -m sim_runner inspect-report --report '<run-directory>\report.json' `
  --sha256 '<report-sha256>'
```

These sim-runner commands always emit JSON; do not add `--json`. Doctor, plan
and inspect-plan do not start the emulator. `run` owns the fixed emulator command,
budgets, raw UART and descendant-process cleanup. Preserve nonzero exits,
failed assertions, partial output and cleanup uncertainty. A valid file inspection
is not a repeated execution or proof of a physical firmware identity.

## Coordinate a bounded suite

Use HIL 0.3.0's `embedded-hil-runner.simulation-spec.v1` with 1..8 ordered cases:

```json
{
  "schema_version": "embedded-hil-runner.simulation-spec.v1",
  "python": {"path": "<trusted-absolute-python-path>", "sha256": "<python-sha256>"},
  "sim_runner_wheel": {"path": "<selected-0.2.0-wheel>", "sha256": "<wheel-sha256>"},
  "cases": [
    {"id": "a", "plan": {"path": "a.json", "sha256": "<native-plan-sha256>"}},
    {"id": "b", "plan": {"path": "b.json", "sha256": "<native-plan-sha256>"}}
  ],
  "timeout_seconds": 180
}
```

```powershell
& $python -I -m hil_runner simulation plan suite.json --output suite-plan.json --json
& $python -I -m hil_runner simulation run suite-plan.json --sha256 '<suite-plan-sha256>' `
  --output-dir '<new-suite-directory>' --json
& $python -I -m hil_runner simulation inspect '<suite-directory>\report.json' `
  --sha256 '<suite-report-sha256>' --json
```

The wheel is staged into HIL's private child package, not imported in HIL or
installed into the system. The interpreter executable is hash-bound; its complete
stdlib/DLL distribution remains trusted host software. Do not add shell commands,
argv or physical-board selections to this spec. Planning binds files but reports
`native_validation_performed=false`. Run preflights every native plan before
starting any backend, then executes each case once. Failed/indeterminate cases
stop subsequent cases; no automatic retries or recovery. Gate CI on the run's
exit/verdict, retain artifacts even on failure, and inspect host-process cleanup
separately. Simulation does not grant flash authorization or prove target cleanup.

## Review the recorded evidence

For completed, natively inspected cases HIL emits `trace-input.json`, including
valid failed reports. An interrupted attempt without a native report remains
partial evidence and must not be fabricated into a Trace source.

```powershell
& $python -I -m embedded_trace correlate '<suite-directory>\trace-input.json' `
  --output '<new-timeline.json>' --json
& $python -I -m embedded_trace inspect '<timeline.json>' --sha256 '<timeline-sha256>' --json
& $python -I -m embedded_trace query '<timeline.json>' --sha256 '<timeline-sha256>' `
  --contains HEARTBEAT --limit 100 --json
& $python -I -m embedded_trace report '<timeline.json>' --sha256 '<timeline-sha256>' `
  --output '<new-report.md>' --json
```

Trace 0.3.0's `sim-runner-report` adapter checks the selected report and adjacent
hash-bound artifacts offline. Keep the native reports, plans, locks, firmware,
UART bytes, CLI outputs and suite journal. UART is labelled `simulation.uart`;
line windows cover the host run, with no invented per-byte timestamps or measured
virtual time. Never mix simulation and device captures under one clock-domain ID.
Recorded native failures stay failed even if import/query/report exits zero.
`native_summary_verified=false` and `native_assertions_reexecuted=false` distinguish
offline import from native validation. A derived timeline cannot replace the
native/HIL verdict or a compatible physical test-contract evaluation.
