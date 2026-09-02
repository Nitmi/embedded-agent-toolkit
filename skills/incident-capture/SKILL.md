---
name: incident-capture
description: Preserve and package evidence from an embedded crash, hang, reset, or protocol failure across target debug state, serial logs, BLE observations, firmware identity, and host environment. Trigger when an Agent must capture a failure scene before recovery or produce a reproducible evidence bundle.
---

# Incident Capture

Treat the current device state as evidence. Use `$embedded-debugger`, `$baud`,
and `$ble` only within their documented safety and identity boundaries.

## Freeze scope before state

1. Record the symptom, host time, user action, exact known identities, firmware
   artifact hashes, tool versions, and what was already attempted.
2. Determine whether the core is known running, halted, reset, disconnected, or
   indeterminate. Do not infer state from a silent serial port alone.
3. Prefer observations that do not change target state: existing logs, bounded
   zero-transmit serial monitoring, read-only BLE capture, saved debug results,
   and offline artifact inspection.
4. If a new target snapshot is essential, describe the perturbation first.
   Debug attach, halt, stack unwind, memory reads, and detach may alter state or
   access unbound addresses. Use `$embedded-debugger`'s narrowest current plan
   and confirmation flow.

## Build the evidence bundle

Keep raw structured component outputs and include a small index containing:

- incident and operation identifiers plus timestamps;
- exact device/interface identities and confidence source;
- firmware, ELF, configuration, and executable hashes;
- bounded serial/BLE observations and target snapshots;
- every state-changing effect and authorization boundary;
- cleanup results, final known state, unknowns, and failed collection steps.

Redact BLE identifiers and user data when the bundle leaves the workstation,
but retain stable internal correlation keys. Do not rewrite missing evidence as
an empty successful observation.

## Leave recovery separate

Finish capture before proposing reset, resume, reflash, power cycle, or protocol
write. Recovery is a new operation with its own target identity, risks, current
plan, and authorization; incident capture itself grants none of them.
