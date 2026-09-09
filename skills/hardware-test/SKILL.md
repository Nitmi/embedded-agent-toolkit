---
name: hardware-test
description: Design or run repeatable embedded hardware tests that coordinate flashing, serial or BLE readiness, guarded interactions, assertions, evidence, and cleanup. Trigger for hardware-in-the-loop checks, manufacturing checks, firmware smoke tests, regression reproduction, or CI workflows involving real boards.
---

# Hardware Test

Prefer the installed `$embedded-debugger`, `$baud`, and `$ble` integrations;
otherwise use their own CLIs with structured output. Keep each component's
native workflow format and evidence as the source of truth. Do not create a
second untyped command runner in this plugin.

If the project supplies `.embedded/toolchain-lock.json`, validate it with the
installed toolkit's `component_lock.py inspect`, pass it to doctor, and use only
its hash-bound component paths. Do not let environment overrides mask that lock.
When a different lock is proposed, run `component_lock.py compare` first and
surface every changed path, version, and hash before selecting it.
For a new test station, run `component_install.py plan` before any hardware
discovery. The plan is offline and starts no component. Run its install mode
only when the user requested host setup and every pinned platform artifact is
available; it may download and write versioned host executables but must not be
treated as hardware authorization. Compare its new lock before adopting it.

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

Friendly names and discovery order are not exact selection rules. Make retries
explicit per stage; default state-changing operations to zero retries.

## Execute in gates

1. Run the host-only toolkit doctor, then component discovery and health checks.
2. Verify preconditions and acquire exclusive ownership of the relevant ports,
   probes, adapters, and board. Do not run competing transports concurrently
   when reset lines, boot modes, or target state can interact.
3. Plan and confirm flashing through `$embedded-debugger`; preserve the exact
   result and cleanup evidence.
4. Wait for a bounded ready assertion through zero-transmit serial observation,
   RTT when supported by the debugger, or read-only BLE evidence.
5. Perform only the declared interactions. Serial transmissions, BLE writes,
   reset control lines, and debug target control retain their component gates.
6. Evaluate assertions from structured evidence, not console appearance.
7. Close the exact sessions and report target, process, port, and adapter cleanup.

Stop at the first indeterminate state-changing result. Preserve all evidence and
require an explicit recovery decision instead of retrying or switching devices.
