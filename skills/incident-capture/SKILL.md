---
name: incident-capture
description: Preserve and package evidence from an embedded crash, hang, reset, or protocol failure across target debug state, serial logs, BLE observations, firmware identity, and host environment. Trigger when an Agent must capture a failure scene before recovery or produce a reproducible evidence bundle.
---

# Incident Capture

Treat the current device state as evidence. Prefer the installed
`$embedded-debugger`, `$baud`, and `$ble` integrations; otherwise use their own
CLIs with structured output. Keep every component's documented safety and
identity boundaries.

If the project supplies `.embedded/toolchain-lock.json`, validate it with the
installed toolkit's `component_lock.py inspect`, pass it to doctor, and use only
its hash-bound component paths. Do not let environment overrides mask that lock.
Otherwise use a selected workstation lock when available and record the doctor's
lock source with the incident evidence; ambient PATH resolution is not a stable
tool identity.
When a different lock is proposed, run `component_lock.py compare` first and
surface every changed path, version, and hash before selecting it.
Do not install or upgrade components while preserving an incident scene. If a
required tool is absent, record that collection gap; defer the offline
`component_install.py plan` and any host changes to a separate recovery or setup
operation.

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

If the incident bundle spans multiple interfaces, optional `board-registry` may
adapt and resolve only the already saved discovery files; read
[offline board identity resolution](../../docs/board-registry.md). Preserve both
native and adapted files, and record `no_match` or `ambiguous` without changing
selectors during capture.

Redact BLE identifiers and user data when the bundle leaves the workstation,
but retain stable internal correlation keys. Do not rewrite missing evidence as
an empty successful observation.

## Leave recovery separate

Finish capture before proposing reset, resume, reflash, power cycle, or protocol
write. Recovery is a new operation with its own target identity, risks, current
plan, and authorization; incident capture itself grants none of them.
