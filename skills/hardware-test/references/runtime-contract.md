# Project runtime contracts

Use this path when the project needs exact serial READY/build/heartbeat
assertions around one debugger reset-capture. For serial-only observation use
baud's native workflow; this runtime command is not a BLE or arbitrary OpenOCD
test runner.

## Prepare offline

Check `embedded-debugger runtime --help` for `init` and `inspect`. An older
installed binary may lack them; use an explicitly selected newer executable.
Do not run `accept` as a substitute for offline validation.

Use the project's known device selectors and firmware log protocol. Do not
discover hardware during a task restricted to project setup, and do not copy
the reference DK's COM port, serial number, build ID, or UICR policy.

```console
embedded-debugger runtime init --name app-smoke --board "My board" \
  --probe "<exact-probe-selector>" --target "<exact-target>" \
  --port "<exact-port>" --vid 1234 --pid 5678 --serial-number "<usb-serial>" \
  --baud 115200 --dtr false --rts false --duration 15 \
  --ready-line "APP_READY v1" --build-id-line "APP_BUILD v1 <build-id>" \
  --heartbeat-line "APP_HEARTBEAT" --forbid-line "APP_FAULT" \
  --output .embedded/runtime.json --json
embedded-debugger runtime inspect .embedded/runtime.json --json
```

Replace example USB IDs, selectors, and exact log lines with project inputs.
Choose DTR/RTS from board documentation; their false defaults are not universally
correct (the reference nRF52840 DK UART requires DTR=true). The optional
`--interface` must match what baud actually reports, not a guessed PnP label.

The generated strict JSON is directly consumed by `runtime accept`. It never
overwrites existing files, transmits bytes, or starts a component process during
setup. Missing build identity means no build assertion. `firmware` and `visual`
are descriptive metadata, not script hooks or enforced artifact checks; keep
firmware hashes and Flash layout in the component's separate flash plan.

An inspection success proves valid configuration only. Keep
`hardware_identity_verified=false`, `runtime_firmware_identity_verified=false`,
and `flash_authorized=false`. Commit the project contract with the firmware
inputs, or keep fixture-specific selections in an explicitly chosen local file.

## Execute within the task's scope

Only when runtime hardware testing is in scope, continue the hardware-test
workflow with fresh identities and the existing component readiness checks.
After any separately needed flash, use `runtime accept --contract <file>
--evidence <new-path> --json` with the intended backend. This opens serial,
performs one R1 reset-capture, restores expected post-reset core states, and
disconnects; it is not read-only or equivalent to `runtime inspect`.

Review complete assertions, effects, captured contract hash, artifacts, and
cleanup. Preserve a failed report and do not retry an indeterminate operation.
Reuse valid task authorization without inventing another approval for offline
setup; a contract hash is not a flash confirmation digest.
