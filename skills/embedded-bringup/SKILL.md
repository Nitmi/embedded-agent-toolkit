---
name: embedded-bringup
description: Coordinate first boot and board bring-up across an exact debug probe, serial console, and optional BLE interface. Trigger when an Agent must identify a connected board, validate firmware and target identity, plan or perform a guarded flash, observe startup, or preserve cross-tool failure evidence.
---

# Embedded Bring-up

Prefer the installed `$embedded-debugger`, `$baud`, and, when relevant, `$ble`
Skills or MCP tools. If a component Skill is unavailable, use that component's
own CLI with structured output after checking its help. The component contracts
still own hardware access and safety gates; do not replace a missing integration
with ad hoc probe, serial, or Bluetooth scripts.

If the project supplies `.embedded/toolchain-lock.json`, validate it with the
installed toolkit's `component_lock.py inspect`, pass it to doctor, and use only
its hash-bound component paths. Do not let environment overrides mask that lock.

## Establish identities

1. Run `python scripts/toolkit_doctor.py --json`. This is host-only and does not
   prove that any adapter or device is available. Treat `ok: true` with
   `complete: false` as a default-CLI environment warning: record it, then use
   only an already installed component integration or a version-checked exact
   executable path. Treat `ok: false` as a real layout, launch, override, or
   version error for the affected component.
2. Read the project, board, firmware, and wiring documentation. Record expected
   target family, supply voltage, boot mode, serial settings, and BLE identity
   claims separately.
3. Use the component Skills' read-only discovery flows. Record the exact probe
   selector and target, serial port USB identity, and observed BLE identifier.
   Never merge devices solely because friendly names or USB product strings
   resemble one another.
4. Create an identity ledger that labels each relationship as observed,
   documented, or inferred. An inference cannot satisfy a write confirmation.

## Bring up in stages

1. Observe the serial console without transmitting and with DTR/RTS false.
2. Inspect the firmware artifact offline and compare its architecture, target,
   layout, and hash with project evidence.
3. Ask `$embedded-debugger` to produce the exact flash plan. Surface its ranges,
   erases, resets, effects, exclusions, tool identity, and confirmation digest.
4. Execute only after the user provides the current exact confirmation required
   by the component. Never treat earlier approval or a connected board as
   standing authorization, and never retry a failed flash automatically.
5. After cleanup, observe bounded startup logs. Use BLE discovery only after the
   firmware is expected to advertise, and keep it read-only until identity is
   resolved.

## Decide from evidence

Success needs a device-level assertion, such as the expected build identity and
a bounded ready event. Process exit alone is insufficient. On failure, preserve
the flash result, cleanup evidence, serial raw bytes and timestamps, firmware
hash, exact identities, and tool versions. Invoke `$incident-capture` when a
target snapshot is needed; do not silently halt, reset, resume, or reflash while
collecting failure evidence.
