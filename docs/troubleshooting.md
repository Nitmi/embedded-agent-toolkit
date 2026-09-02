# Troubleshooting

## Doctor reports `not_found`

Install the named component or put its executable directory on `PATH`. To test
an exact development binary without changing `PATH`, set its override variable:

```powershell
$env:EMBEDDED_AGENT_DEBUGGER = 'D:\Code\ai\embedded-debugger\target\debug\embedded-debugger.exe'
python scripts/toolkit_doctor.py --json
```

Overrides must identify one executable, not a command line with arguments.

## Doctor reports an unexpected version

Run the reported executable path manually with `--version`. An executable with
the expected filename but incompatible output is treated as a different tool;
do not continue to hardware discovery until the ambiguity is resolved.

## BLEA MCP does not start

Confirm `ble --version` and `ble mcp --help` work in the same environment as the
Agent host, then confirm the standalone BLEA plugin is installed and enabled.
The aggregate toolkit does not register that server. MCP startup does not prove
Bluetooth permission or adapter health; use the BLEA Skill's doctor flow for
that later, explicit hardware check.

## BLEA tools or processes appear twice

More than one installed plugin is registering BLEA. Upgrade the aggregate
toolkit to a version that contains no active `.mcp.json`, then start a new Agent
conversation. Keep the standalone BLEA plugin as the sole server owner.

## Embedded debugger MCP is absent

This is intentional. Native debug startup needs an exact target, while the
aggregate plugin is target-neutral. Add the project-level MCP configuration
from the README after exact target discovery. Do not copy the ESP32-S3 example
into an nRF52840 project or infer a target from a board label.

## A workflow fails after changing target state

Stop automatic retries. Preserve the structured result and stderr, inspect the
component's cleanup fields, and determine the exact current device state before
any recovery. A flash, halt, reset, resume, BLE write, or serial control-line
action needs the component's own current confirmation and safety gates.
