---
name: firmware-debug
description: Diagnose firmware failures using bounded target state, serial/RTT/BLE evidence and offline PC/LR-to-source lookup. Trigger for crashes, hangs, resets, missing output, bad peripheral behavior, register or stack inspection, breakpoint diagnosis and comparisons between target state and external observations.
---

# Firmware Debug

Prefer `$embedded-debugger` for target control, `$baud` for serial evidence, and
`$ble` for BLE evidence when those Skills or MCP tools are installed. Otherwise
use the corresponding component CLI with structured output. Preserve each
component's capability and safety limits instead of translating a successful
process exit into a hardware claim.

For a failure reproduced in a supported Renode/QEMU model, read
[optional simulation](../../docs/simulation.md). Use the explicitly selected
sim-runner/HIL native CLI, preserve failed or partial UART and process cleanup,
and use its matching Trace version for offline simulated evidence. Retain model diagnostics and
`passed_with_model_limits` instead of flattening a qualified pass. A simulation-only diagnosis
needs no hardware discovery or attach. Do not infer a physical fault, radio or
electrical behavior from a simulated pass, or silently switch to a real board.
GPIO RunFor boundaries and guest timer captures remain separate from UART/host
event times; use the saved model observation spans when reviewing the raw source.
S3 uses the separate Xtensa backend with an unmeasured device clock; keep its
runtime/core declarations and native limitations when comparing it with C3/Renode.
For a saved or requested GPIO/TIMER0 fault experiment, read
[model fault evidence](../../docs/simulation-faults.md). Keep injection requests,
observed/unknown effects and native regression failures distinct; raw counter/IRQ
spans describe the model, not a physical fault or confirmed root cause. Select
local candidate payloads explicitly; do not replace the published environment.

If the project supplies `.embedded/toolchain-lock.json`, validate it with the
installed toolkit's `component_lock.py inspect`, pass it to doctor, and use only
its hash-bound component paths. Do not let environment overrides mask that lock.
Otherwise use a selected workstation lock when available and verify the doctor
reports its lock source before correlating evidence across component tools.
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

## Inspect local builds when relevant

For artifact identity, linker layout, or footprint regressions, use optional
`firmware-inspect` if available through the selected component lock; read
[offline firmware inspection](../../docs/firmware-inspect.md). This file-only
analysis needs no target attach or hardware confirmation. Do not block an
unrelated debug workflow or install a missing component during diagnosis.
Its file hashes, Build IDs, section sums and load ranges are not proof of the
running firmware, board memory capacity, or permission to flash.
For an exact variable, function or `_SEGGER_RTT` request, use the guide's
`symbols` workflow with a selected firmware-inspect 0.2.0+ executable. Check each
query's resolution status and original definition metadata; the largest-symbol
list is incomplete for exact lookup. Preserve raw ELF values, including ABI
bits, and distinguish TLS offsets and unresolved entries from target addresses.

For PC/LR or code addresses already present in logs or a snapshot, use the guide's
`addresses` workflow with selected firmware-inspect 0.3.0+. Bind the exact ELF
hash and preserve input/lookup addresses, then read function and line statuses
independently. Choose `arm-thumb` explicitly for ARM32 Thumb pointer inputs;
do not silently adjust LR or relocation. Retain ambiguous results and unverified
DWARF paths. A metadata line match does not establish a function's source, call
stack, fault cause or running identity. No new target reads are needed for this
offline annotation, and file-only requests can end with the native report.

For a question spanning saved serial/RTT logs, read
[Embedded Trace timelines](../../docs/embedded-trace.md). Its hash-bound line
spans and host-recorded envelopes can link observations without new target reads.
Keep clock domains and capture failures explicit; a matching log line does not
establish causality or firmware identity.

## Build an identity ledger

When evidence spans multiple transports, operations, or observation windows,
read [references/identity-ledger.md](references/identity-ledger.md) and preserve a
machine-readable ledger beside the human report.

- Classify each claim as observed, documented, inferred, rejected, or unknown,
  and attach exact source paths, hashes, and validity times.
- For multi-interface or multi-board ambiguity, adapt the saved discovery JSON
  through optional `board-registry`; read
  [offline board identity resolution](../../docs/board-registry.md). Preserve the
  native files and do not treat resolution as runtime continuity.
- Keep USB-interface association, physical-board identity, target/core identity,
  firmware artifact identity, and current runtime identity as separate claims.
- Treat runtime attestation and target state as point-in-time evidence. Do not
  carry them into a later serial or BLE window without fresh proof.
- For counters or other expected-monotonic state, bind the initialization,
  update, width, and cadence semantics before interpreting a rollback. A
  rollback can reject uninterrupted continuity, but does not alone distinguish
  reset, power loss, reflash, alternate firmware, or a different device.

## Gather evidence conservatively

For firmware exposing RTT, read [bounded RTT workflows](../../docs/rtt.md).
Debugger 0.2.4 provides native CLI capture for probe-rs/nRF52840, not a
persistent-session or MCP RTT request. Bind the initialized address to the exact
ELF and record read-cursor consumption plus attachment effects. Keep raw JSONL,
summary and serial evidence separately hashed; clocks do not establish shared
identity or continuity. Do not install another RTT consumer during diagnosis.
For saved captures, use the offline reader in the RTT guide to verify integrity,
preview bounded lines with chunk/byte references, or extract binary bytes before
project-specific decoding. Truncated previews and incomplete tails cannot stand
in for complete runtime assertions.

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
