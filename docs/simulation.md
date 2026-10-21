# Optional simulation workflow

Toolkit 0.29.0 source adds S3 routing for the published
[sim-runner 0.5.0](https://github.com/Nitmi/sim-runner/releases/tag/v0.5.0),
[HIL Runner 0.6.0](https://github.com/Nitmi/hil-runner/releases/tag/v0.6.0) and
[Embedded Trace 0.6.0](https://github.com/Nitmi/embedded-trace/releases/tag/v0.6.0).
[Toolkit 0.29.0](https://github.com/Nitmi/embedded-agent-toolkit/releases/tag/v0.29.0) is published. `simulation-runtime.json`
v2 binds each component's official tag/ref and source commit, exact release wheel
URL and hash, and all 65 installed source/schema/metadata/license files.
Use those official wheels; there is no implicit download or install step.
The existing `hil-runtime.json` and `trace-runtime.json` still describe their
earlier published hardware/offline workflows. Their inspectors do not accept these
newer releases. Native component locks and workstation selection remain independent.

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

During requested host setup, download the three exact release wheels named in the
pin. Verify each wheel's SHA-256 and GitHub attestation against its repository,
`source_ref`, `source_revision` and `.github/workflows/python-release.yml` signer at the
same revision, with self-hosted runners denied. For example, substituting the
selected component's exact pin values:

```powershell
gh attestation verify '<wheel>' --repo '<repository>' `
  --source-ref '<source_ref>' --source-digest '<source_revision>' `
  --signer-workflow '<repository>/.github/workflows/python-release.yml' `
  --signer-digest '<source_revision>' --deny-self-hosted-runners
```

Install the three authenticated wheels with `--no-index --no-deps`
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
not a sandbox or authenticated execution proof. `distribution_status=published`
and `resolution_source=pinned_releases` describe the bundled release records;
the inspector does not contact GitHub or verify a signature. `release_attestation_verified`,
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
- Renode 1.17.0: `nrf52840-gpio-timer-v1`, fixed 82 ms digital input / TIMER0 IRQ /
  output-loopback scenario, 16 native UART samples and four paused model snapshots.
  Guest timer captures and requested RunFor boundaries are not host/UART timestamps
  or physical timing; no complete GPIO/timer, sense/latch or PPI coverage is claimed.
- Espressif QEMU `esp-develop-9.2.2-20260417`: `esp32c3-ram-uart-v1`, RAM-loaded
  RV32IMC ELF and UART readiness. No ESP-IDF flash boot in this RAM profile, ESP32-S3, radio or enforced
  virtual-time budget. A host deadline is not a virtual-time measurement.
- Separate Xtensa QEMU of the same fixed release: `esp32s3-idf-flash-v1`, S3 ROM /
  ESP-IDF5.5.2 4 MiB factory Flash / dual-core fixture UART. Device clock is
  unmeasured; reviewed Flash/debug-query limitations remain qualified success.
- The same QEMU with `esp32c3-idf-flash-v1`: fixed 4 MiB DIO merged image,
  ROM and ESP-IDF 5.5.2 bootloader/application UART startup, private Flash/eFuse
  copies and revision-0.3 eFuse seed. No secure-boot/encryption verification,
  radio/electrical coverage or enforced virtual time. Known native Flash/PMP model
  diagnostics remain a qualified pass, never evidence of full-chip compatibility.

These are not full-chip/electrical models. Unsupported requested behavior must
remain unsupported; silent upstream peripheral stubs cannot always be detected.
Consult the selected sim-runner source's `docs/profile.md` and
`docs/esp32c3-qemu.md` and `docs/esp32c3-idf-flash.md` for image layout,
runtime inventory and assertion limits.

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

For ESP-IDF Flash boot, explicitly add `--profile esp32c3-idf-flash-v1` to the
QEMU `plan` command and use the fixed-layout merged `flash.bin` and its hash in
place of the ELF. Omitting the profile retains RAM behavior; do not pass a
Flash image as an ELF. Use sim-runner's fixture builder or a compatible audited
SDK build/merge flow; it builds host files without flashing a board.

For GPIO/TIMER0, use `--backend renode --profile nrf52840-gpio-timer-v1`, the
native `examples/nrf52840-gpio-timer` raw BIN fixture and its build-bound markers.
`--min-heartbeats` defaults to/must be 16 IRQ samples and `--virtual-ms` to/must
be 82 for that profile. Consult native `docs/nrf52840-gpio-timer.md`; unsupported
pin schedules or timer modes require another audited profile.

## Coordinate a bounded suite

Use HIL 0.6.0's `embedded-hil-runner.simulation-spec.v1` with 1..8 ordered cases:

```json
{
  "schema_version": "embedded-hil-runner.simulation-spec.v1",
  "python": {"path": "<trusted-absolute-python-path>", "sha256": "<python-sha256>"},
  "sim_runner_wheel": {"path": "<selected-0.5.0-wheel>", "sha256": "<wheel-sha256>"},
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

Successful Flash cases keep the exact native `passed_with_model_limits` status,
`model_diagnostics` message/count/meaning and false `model_coverage_complete` /
`security_features_verified`. They allow the next case to run and make a
successful suite `passed_with_model_limits`. Failed/indeterminate cases still
stop subsequent cases. Never turn exit zero into an unqualified model/physical pass.

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

Trace 0.6.0's `sim-runner-report` adapter checks the selected report and adjacent
hash-bound artifacts offline. Keep the native reports, plans, locks, firmware,
UART bytes, CLI outputs and suite journal. UART is labelled `simulation.uart`;
line windows cover the host run, with no invented per-byte timestamps or measured
virtual time. Never mix simulation and device captures under one clock-domain ID.
Recorded native failures stay failed even if import/query/report exits zero.
`native_summary_verified=false` and `native_assertions_reexecuted=false` distinguish
offline import from native validation. A derived timeline cannot replace the
native/HIL verdict or a compatible physical test-contract evaluation.

A limited native pass stays `capture_outcome=succeeded_with_model_limits` with
`recorded_status=passed_with_model_limits`, native model diagnostics and both
false coverage/security fields. The timeline becomes `correlated_with_warnings`;
inspect, query and Markdown retain that outcome. Import binds ROM, initial
eFuse, input/work Flash and raw stderr diagnostic counts. It does not emulate
the CPU or rerun native policy. Flash evidence has a 12 MiB/source budget and
simulation-containing input a 96 MiB total; physical captures retain their
8 MiB/source and 16 MiB combined limits. Native reports stay capped at 128 KiB.
An incomplete attempt without a native report is retained by HIL and cannot
be promoted into a Trace source.

For GPIO/TIMER0, HIL cases and Trace source views retain the native
`gpio_evidence.samples` and `gpio_evidence.model_observations`, coverage/time
semantics and false `model_coverage_complete` / `physical_timing_verified` claims.
Trace binds each paused register observation to `gpio_observation_spans` in
raw `backend.stdout.bin`, retaining offsets, raw bytes and SHA-256. Those spans
are model-state provenance, not UART/host event timing or an electrical waveform.
Inspect/query/Markdown keep the context even when searching only SAMPLE lines.

Native GPIO `passed` remains passed/succeeded within the fixed scenario. Trace
also retains a `model_coverage_incomplete` warning; importing successfully is
not complete peripheral or real-board acceptance. It never reruns native GPIO/
IRQ readiness policy. Failed/unevaluated assertions remain null, partial native
attempts without inspected reports remain HIL evidence, and no stage silently
switches to physical hardware. Derived query/report checks do not reopen sources
or authenticate a report; retain the raw artifacts for independent review.

For ESP32-S3, select native backend `espressif-qemu-xtensa` and profile
`esp32s3-idf-flash-v1`, the separately pinned Xtensa QEMU distribution and a
native-compatible S3 ESP-IDF5.5.2 4 MiB factory Flash image. Consult the selected
sim-runner's `docs/esp32s3-qemu.md`. C3 RISC-V runtime/ROM/image identities are
not interchangeable. The native S3 fixture includes ordered CPU0/CPU1 markers,
exact READY/BUILD and five heartbeats; their policy stays in sim-runner.

HIL0.6 and Trace0.6 preserve `backend`, `backend_version`,
`runtime_archive_sha256`, `app_core_markers` and `virtual_time` alongside model
diagnostics and false coverage/security claims. S3 uses no C3 icount setting:
its domain remains `qemu_device_clock_unmeasured`, elapsed=null, budget=false.
Host timeouts, UART log ticks and core markers do not establish measured virtual
time, complete SMP or physical behavior. Unevaluated core declarations stay null.
Filtered inspect/query/Markdown retain the same context. A qualified pass can
continue a suite; a failed/indeterminate native attempt stops later cases.
