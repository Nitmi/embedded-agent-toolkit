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

## Frame the question

Define the symptom, observation window, exact firmware artifact and hash, exact
target/core, and the smallest state needed to decide between hypotheses. Record
whether firmware identity is verified on the running target or merely selected
from a local build.

## Gather evidence conservatively

1. Start with bounded, zero-transmit serial observation and read-only BLE
   evidence when those interfaces remain alive.
2. Use the component debug Skill to establish an exact session and current core
   state. Halting, stepping, continuing, resetting, installing breakpoints or
   watchpoints, and recovery are state changes; apply its current confirmation
   policy and never reuse a prior digest.
3. Request only the registers, frame count, and declared memory range needed by
   the hypothesis. Never infer RAM/NVM/MMIO semantics from an address alone.
4. If symbols are used, bind the exact ELF hash and distinguish offline
   annotation from proof that the target runs that ELF.
5. Correlate events by recorded timestamps and operation boundaries. Host clocks
   and transport buffering may differ, so describe ordering uncertainty.

## Close deliberately

Delete only resources created by this workflow, close the exact sessions, and
verify cleanup. Do not resume an incident target merely to return to a familiar
state; restoration needs an explicit policy and evidence. Report observations,
inferences, rejected hypotheses, remaining unknowns, exact artifact paths, and
the least invasive next experiment.
