---
name: hardware-test
description: Design or run repeatable embedded hardware tests that coordinate flashing, serial or BLE readiness, guarded interactions, assertions, evidence, and cleanup. Trigger for hardware-in-the-loop checks, manufacturing checks, firmware smoke tests, regression reproduction, or CI workflows involving real boards.
---

# Hardware Test

Compose `$embedded-debugger`, `$baud`, and `$ble`; keep each component's native
workflow format and evidence as the source of truth. Do not create a second
untyped command runner in this plugin.

## Define the test contract

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
