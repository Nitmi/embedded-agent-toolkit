# Embedded Agent Toolkit

Embedded Agent Toolkit is the orchestration layer for Nitmi's embedded Agent
tools. It combines their existing contracts instead of hiding the underlying
tools behind another hardware abstraction:

| Component | Responsibility | Interface |
| --- | --- | --- |
| [baud-cli](https://github.com/Nitmi/baud-cli) | Serial and firmware consoles | CLI + Skill |
| [BLEA](https://github.com/Nitmi/blea) | Bluetooth Low Energy diagnostics and automation | CLI + Skill + MCP |
| [embedded-debugger](https://github.com/Nitmi/embedded-debugger) | Probe discovery, flash, debug, evidence, and replay | CLI + Skill + MCP |

The value of the toolkit is the cross-tool workflow: one identity ledger, one
safety policy, correlated evidence, and deterministic cleanup across serial,
BLE, and debug transports. Each component remains independently usable.

## Included workflows

- `embedded-bringup`: discover interfaces, verify identities, plan flashing,
  observe startup, and collect failure evidence.
- `firmware-debug`: correlate a bounded target snapshot with serial and BLE
  observations.
- `hardware-test`: run a staged, assertion-driven hardware test with explicit
  mutation gates and cleanup.
- `incident-capture`: preserve a failure scene and collect a read-mostly
  evidence bundle without silently recovering the target.

## Host doctor

The doctor checks only executable versions and the local plugin layout. It does
not enumerate or open adapters, probes, ports, or targets.

```powershell
python scripts/toolkit_doctor.py
python scripts/toolkit_doctor.py --json
```

Use `EMBEDDED_AGENT_BAUD`, `EMBEDDED_AGENT_BLE`, or
`EMBEDDED_AGENT_DEBUGGER` to point a check at a specific executable.

## MCP policy

The aggregate manifest registers BLEA because its server can start without a
device or target selection. It intentionally does not register a native debug
server with a guessed default target. Configure embedded-debugger per project
with an exact target:

```json
{
  "mcpServers": {
    "embedded-debugger": {
      "type": "stdio",
      "command": "embedded-debugger",
      "args": [
        "--backend",
        "probe-rs",
        "supervisor",
        "mcp",
        "--target",
        "<exact-probe-rs-target>"
      ]
    }
  }
}
```

See [installation](docs/installation.md) and
[troubleshooting](docs/troubleshooting.md) for setup and lifecycle guidance.

## Development

```powershell
python -m unittest discover -s tests -v
python C:\Users\Nitmi\.codex\skills\.system\plugin-creator\scripts\validate_plugin.py .
```

The repository is an Agent Plugin, not another hardware runtime. Scripts added
here must remain host-only; physical operations belong in the component tools.
