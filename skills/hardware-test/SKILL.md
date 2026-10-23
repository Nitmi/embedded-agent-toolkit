---
name: hardware-test
description: Design or run repeatable embedded tests across flashing, serial/RTT/BLE readiness, assertions, evidence and cleanup. Use for hardware-in-the-loop checks, firmware build/flash loops, board regressions, supported simulation or model fault suites, and offline instrument protocol/PWM checks.
---

# Hardware Test

Prefer the installed `$embedded-debugger`, `$baud`, and `$ble` integrations;
otherwise use their own CLIs with structured output. Keep each component's
native workflow format and evidence as the source of truth. Do not create a
second untyped command runner in this plugin.

For saved instrument captures or logic assertion evidence, read
[offline instrument workflows](../../docs/instruments.md). Use the explicitly
selected environment's native lab/HIL/Trace commands. Inspect published pins by
default; choose historical local builds only with explicit candidate mode. The standalone
payload inspector is sufficient for this file-only domain; board discovery and
native hardware doctor are unnecessary. Preserve failed/invalid evidence and
distinguish recorded native recomputation from current import/view success.

For simulation-only regressions, read [optional simulation](../../docs/simulation.md)
first. Inspect the explicitly selected payloads with `simulation_runtime.py`, then
use sim-runner or HIL's native `simulation` CLI and the matching Trace evidence
views. Skip hardware doctor/discovery/selection for this domain. Reuse development
task consent without per-run hash confirmation. Stop on unsupported models or
failed/indeterminate cases; never fall back to physical hardware automatically.
Preserve `passed_with_model_limits`, its diagnostics and false coverage/security
claims; Trace retains `succeeded_with_model_limits`. Simulation results remain
distinct from physical-board acceptance.
For GPIO/TIMER0, keep guest samples, paused model snapshots and host run windows
distinct; inspect/query/report retain the recorded context and false physical timing claim.
For ESP32-S3, select the independent Xtensa runtime and keep its unmeasured
device clock/core declarations and qualified outcome in filtered evidence views.
For experimental ESP-EMU WASM, read [WASM simulation](../../docs/simulation-wasm.md).
Use the published default pin; choose recorded local builds only explicitly.
Keep string UART provenance,
opaque ROM/eFuse state, model-clock claims, restart requests and native failures
visible; encoded UART strings are not verified original UART bytes.
For GPIO/TIMER0 fault regressions, read [model fault evidence](../../docs/simulation-faults.md).
Use the published default for released fault components; select `--candidate`
only for an explicitly chosen recorded local build. Keep the native nominal verdict, effect/null state,
counter/IRQ raw spans and failure stop. Successful injection never makes a failed
regression pass or allows a later case to run.

If the project supplies `.embedded/toolchain-lock.json`, validate it with the
installed toolkit's `component_lock.py inspect`, pass it to doctor, and use only
its hash-bound component paths. Do not let environment overrides mask that lock.
Otherwise honor a workstation lock selected by `station_config.py`; confirm the
doctor report names `project`, `workstation`, or `command_line` as its lock source
before treating component readiness as stable. Ambient PATH readiness is only a
host diagnostic, not a stable test-station identity.
When a different lock is proposed, run `component_lock.py compare` first and
surface every changed path, version, and hash before selecting it.
For a new test station, run `component_install.py plan` before any hardware
discovery. The plan is offline and starts no component. Run its install mode
only when the user requested host setup and every pinned platform artifact is
available; it may download and write versioned host executables but must not be
treated as hardware authorization. Compare its new lock before adopting it.
For a fresh station, the authenticated Toolkit bootstrap may perform the same
catalog-backed component installation and strict doctor in one explicit command.
Require separate component and new-lock destinations, and do not interpret
successful host setup as permission to enumerate or operate a board.

## Define the test contract

For project setup without hardware access, use the component's host-only
`embedded-debugger runtime init` and `runtime inspect` commands. Read
[runtime-contract.md](references/runtime-contract.md) when creating a project's
serial/reset acceptance contract. Keep this native format as the source of
truth; do not add a toolkit execution wrapper or copy another board's identity.

Before hardware access, record:

- exact board, probe, target, serial, and BLE selection rules;
- firmware artifact hashes and expected memory layout;
- preconditions, allowed mutations, physical hazards, and abort conditions;
- positive and negative assertions with bounded deadlines;
- cleanup and recovery policy for every stage.

When the station has multiple boards or a test spans interfaces, use optional
`board-registry` only on saved discovery evidence; read
[offline board identity resolution](../../docs/board-registry.md). Require a
unique result for every transport in the test contract. Resolution narrows the
board selection but does not authorize flash, reset, serial transmit, BLE write,
or debug control.

For a multi-stage test, read [hardware test contracts](../../docs/test-contract.md)
and use the host-only `test_contract.py compile`, `inspect`, and `evaluate`
commands. Reference component-native workflows and firmware by path and SHA-256;
never put shell commands, argv, executable paths, confirmation digests, or
authorization claims in the contract or run manifest. Treat input drift, missing
evidence, or an incomplete effect declaration as a stopping state. The compiled
contract orders and constrains native workflows but cannot execute them or bypass
their own gates. After separately gated component operations, bind the unchanged
native JSON evidence in a non-authorizing run manifest and evaluate assertions
and cleanup offline.

For CI reporting, Toolkit 0.23.0+ adds `test_contract.py junit <contract> --run
<run> --output <new.xml> --json`; read the test-contract guide's JUnit section.
It reevaluates the hash-bound saved evidence and exports assertions, input/stage
checks and cleanup as distinct CI cases without rerunning hardware. Preserve
nonzero exit status and upload XML on failure; missing or unevaluable evidence
is an error, never a skip. Keep native JSON for details truncated in XML.

Friendly names and discovery order are not exact selection rules. Make retries
explicit per stage; default state-changing operations to zero retries.

## Execute in gates

1. Run the host-only toolkit doctor. When discovery belongs to a repeatable
   test, declare `baud.list`, `blea.doctor`, or
   `embedded-debugger.probes-list` as the first contract stage and assert the
   exact native identity fields. BLEA doctor performs a short scan; none of
   these discovery stages may open a serial port, connect, attach, or control a
   target.
2. Verify preconditions and acquire exclusive ownership of the relevant ports,
   probes, adapters, and board. Do not run competing transports concurrently
   when reset lines, boot modes, or target state can interact.
3. Plan and confirm flashing through `$embedded-debugger`; preserve the exact
   result and cleanup evidence. For repeated firmware builds, read
   [bounded flash sessions](../../docs/bounded-flash-sessions.md). A native
   session can reuse one user-approved scope for bounded code-Flash builds
   only while its executor remains alive. Do not turn a test contract into
   authorization or auto-forward per-build digests through the old CLI path.
   For continuous build/flash/observe loops or shared-board ownership, read
   [optional HIL Runner](../../docs/hil-runner.md). Use its native managed owner
   with the inspected runtime and qualified debugger, including the additional
   per-build runtime reset in the agreed scope. Reuse valid task authorization;
   do not add a confirmation before each build or require HIL for a single flash.
4. Wait for a bounded ready assertion through zero-transmit serial observation,
   RTT when supported by the debugger, or read-only BLE evidence.
   For RTT, read [bounded RTT workflows](../../docs/rtt.md). Use the native
   CLI, declare read-cursor consumption and attach effects, and preserve both
   summary and raw JSONL. Offline integrity checks do not replace a project's
   complete READY/build/heartbeat assertions or prove final core state.
   Use the RTT guide's offline inspect/preview/extract commands for saved logs;
   bind the derived payload hash and evaluate the full bytes for readiness,
   not a bounded or truncated preview.
5. Perform only the declared interactions. Serial transmissions, BLE writes,
   pairing changes, reset control lines, and debug target control retain their
   component gates. For `blea.pair` or `blea.unpair`, require an exact observed
   identifier and BLEA's native pairing guard. An authorization already granted
   for the agreed device and bounded task remains valid; do not interrupt each
   stage to ask for the same authorization again. Never place a pairing PIN in
   a Toolkit contract, evidence file, process argument, or report, and never
   retry an indeterminate pairing change.
6. Evaluate hash-bound structured evidence with `test_contract.py evaluate`, not
   console appearance. A missing pointer, mismatched digest, or unverified cleanup
   state is a failure, never an implicit pass.
7. Close the exact sessions and report target, process, port, and adapter cleanup.

For offline review across saved serial/RTT evidence, use optional
[Embedded Trace timelines](../../docs/embedded-trace.md). Retain native evidence
and full runtime assertions: a successful import or bounded READY query does not
replace per-build native acceptance or Toolkit contract evaluation. This analysis
adds no hardware action or per-flash confirmation.

Stop at the first indeterminate state-changing result. Preserve all evidence and
require an explicit recovery decision instead of retrying or switching devices.
