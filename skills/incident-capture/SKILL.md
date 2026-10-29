---
name: incident-capture
description: Preserve and package evidence from an embedded crash, hang, reset, or protocol failure across target debug state, serial and RTT logs, BLE observations, firmware identity, and host environment. Trigger when an Agent must capture a failure scene before recovery or produce a reproducible evidence bundle.
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

For saved TMP103 model failures, read
[sensor simulation](../../docs/simulation-sensors.md). Preserve native reports,
UART, model stdout spans and failed/unknown outcomes as simulation evidence;
packaging these files requires no board discovery or new emulator run.

For already saved thermal evidence, read
[thermal evidence](../../docs/instrument-thermal.md). Preserve the full raw
inventory, controls, telemetry, failed assertions and cleanup context. Package
the original bytes without reconnecting the camera or changing FFC/gain settings;
surface-temperature observations do not establish junction temperature.

When the scene already includes saved load measurements, read
[load evidence](../../docs/instrument-load.md). Preserve the original result,
plan, transcript, assertions and cleanup/error context beside the derived bundle.
Packaging those files does not require reconnecting or commanding input OFF.

For RTT collection, read [bounded RTT workflows](../../docs/rtt.md) first.
RTT consumes the selected RAM read cursor and attachment may perturb the target.
Preserve the native summary and raw JSONL, including partial evidence and cleanup
failures. Treat cursor offsets as positions in one capture, not target addresses
or continuity across captures. Stop/disconnect does not prove the core is running.
The RTT guide's offline reader can derive a bounded preview or lossless binary
export from a complete, verified capture. Keep native inputs unchanged and link
derived files to their input/payload hashes. Partial failed captures are retained
as failures; an integrity-rejected reader result is not an empty successful log.

For offline correlation of saved serial/RTT logs, read
[Embedded Trace timelines](../../docs/embedded-trace.md). Use its inspected
environment and exact input hashes; preserve native files beside the derived
timeline. Host clock domains, successful imports and matching text do not prove
runtime identity, capture success or final target state. No new hardware access
is needed for this optional analysis.

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
