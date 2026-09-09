---
name: firmware-debug
description: Correlate bounded embedded target state with serial and BLE evidence during firmware diagnosis. Trigger for crashes, hangs, unexpected resets, missing output, bad peripheral behavior, register or stack inspection, breakpoint-driven diagnosis, and comparisons between target state and external observations.
---

# Firmware Debug

Prefer `$embedded-debugger` for target control, `$baud` for serial evidence, and
`$ble` for BLE evidence when those Skills or MCP tools are installed. Otherwise
use the corresponding component CLI with structured output. Preserve each
component's capability and safety limits instead of translating a successful
process exit into a hardware claim.

If the project supplies `.embedded/toolchain-lock.json`, validate it with the
installed toolkit's `component_lock.py inspect`, pass it to doctor, and use only
its hash-bound component paths. Do not let environment overrides mask that lock.
When a different lock is proposed, run `component_lock.py compare` first and
surface every changed path, version, and hash before selecting it.
Do not install or upgrade components during an active diagnosis unless the user
explicitly changes the task to host setup. For setup, review the offline
`component_install.py plan`; proceed only when its authenticated bundled catalog
is complete, then compare the generated candidate lock before selecting it.

## Frame the question

Define the symptom, observation window, exact firmware artifact and hash, exact
target/core, and the smallest state needed to decide between hypotheses. Record
whether firmware identity is verified on the running target, was verified only
in an earlier observation window, or is merely selected from a local build.

## Build an identity ledger

When evidence spans multiple transports, operations, or observation windows,
read [references/identity-ledger.md](references/identity-ledger.md) and preserve a
machine-readable ledger beside the human report.

- Classify each claim as observed, documented, inferred, rejected, or unknown,
  and attach exact source paths, hashes, and validity times.
- Keep USB-interface association, physical-board identity, target/core identity,
  firmware artifact identity, and current runtime identity as separate claims.
- Treat runtime attestation and target state as point-in-time evidence. Do not
  carry them into a later serial or BLE window without fresh proof.
- For counters or other expected-monotonic state, bind the initialization,
  update, width, and cadence semantics before interpreting a rollback. A
  rollback can reject uninterrupted continuity, but does not alone distinguish
  reset, power loss, reflash, alternate firmware, or a different device.

## Gather evidence conservatively

1. Start with bounded, zero-transmit serial observation and read-only BLE
   evidence when those interfaces remain alive. When firmware exposes a
   build-bound identifier, read
   [references/serial-firmware-identity.md](references/serial-firmware-identity.md)
   and bind the exact physical serial identity and expected artifact hash in
   the same receive-only workflow.
2. Use the component debug Skill to establish an exact session and current core
   state. Halting, stepping, continuing, resetting, installing breakpoints or
   watchpoints, and recovery are state changes; apply its current confirmation
   policy and never reuse a prior digest.
3. Request only the registers, frame count, and declared memory range needed by
   the hypothesis. Never infer RAM/NVM/MMIO semantics from an address alone.
4. If symbols are used, bind the exact ELF hash and distinguish offline
   annotation from proof that the target runs that ELF.
5. Correlate events by recorded timestamps and operation boundaries. Host clocks
   and transport buffering may differ, so describe ordering uncertainty. Do not
   merge individually valid point-in-time claims into an unproven continuity
   claim.

## Close deliberately

Delete only resources created by this workflow, close the exact sessions, and
verify cleanup. Do not resume an incident target merely to return to a familiar
state; restoration needs an explicit policy and evidence. Report observations,
inferences, rejected hypotheses, remaining unknowns, exact artifact paths, and
the least invasive next experiment. When the toolkit checkout is available, run
`python scripts/validate_identity_ledger.py <ledger.json> --json` before treating
the ledger as complete.
