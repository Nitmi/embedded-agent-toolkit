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

## Release packages

Version `0.3.0` provides reproducible plugin-only ZIPs with per-file manifests and
SHA-256 checksums. The host-only `scripts/release.py` builds, verifies, and
installs versioned directories without activating plugins, changing PATH, or
installing component CLIs. Upgrades retain the previous version for rollback.
See [release and upgrade instructions](docs/releases.md).

## Included workflows

- `embedded-bringup`: discover interfaces, verify identities, plan flashing,
  observe startup, and collect failure evidence.
- `firmware-debug`: correlate bounded target, serial, and BLE evidence while
  preserving point-in-time identity and continuity boundaries. It can bind a
  freshly enumerated USB serial interface to build-bound firmware telemetry
  before escalating to a debugger attach. See the
  [validated identity-ledger example](docs/examples/esp32s3-identity-ledger-2026-09-03.md).
- `hardware-test`: run a staged, assertion-driven hardware test with explicit
  mutation gates and cleanup. Prepare per-project serial/reset contracts with
  the debugger's offline `runtime init` and `runtime inspect` commands before
  hardware access; see the
  [project contract workflow](skills/hardware-test/references/runtime-contract.md).
- `incident-capture`: preserve a failure scene and collect a read-mostly
  evidence bundle without silently recovering the target.

## Host doctor

The doctor checks only executable versions and the local plugin layout. It does
not enumerate or open adapters, probes, ports, or targets.

```powershell
python scripts/toolkit_doctor.py
python scripts/toolkit_doctor.py --json
python scripts/toolkit_doctor.py --strict
```

Use `EMBEDDED_AGENT_BAUD`, `EMBEDDED_AGENT_BLE`, or
`EMBEDDED_AGENT_DEBUGGER` to point a check at a specific executable. The
default check reports a missing `PATH` entry as `ready_with_warnings`; use
`--strict` when every component CLI must be directly invocable.

For stable project or test-station selection, `scripts/component_lock.py` creates
an explicit lock of all three executable paths, versions, and SHA-256 values.
Pass it to doctor with `--component-lock`; it remains host-only and does not
modify `PATH` or proxy hardware commands. See [installation](docs/installation.md).
Release installation can create this lock and complete strict doctor in the same
command; see [versioned releases](docs/releases.md).

## MCP policy

The aggregate manifest intentionally registers no component MCP servers.
Install and enable the BLEA plugin separately when BLE MCP tools are needed.
This avoids duplicate tool namespaces and duplicate server processes. Configure
embedded-debugger per project rather than guessing a default target; use an
exact target:

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
python scripts/validate_identity_ledger.py docs/examples/esp32s3-identity-ledger-2026-09-03.json --json
python <plugin-creator-skill-root>/scripts/validate_plugin.py .
```

The repository is an Agent Plugin, not another hardware runtime. Scripts added
here must remain host-only; physical operations belong in the component tools.
