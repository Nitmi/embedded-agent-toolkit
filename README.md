# Embedded Agent Toolkit

[![CI](https://github.com/Nitmi/embedded-agent-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/Nitmi/embedded-agent-toolkit/actions/workflows/ci.yml)
[![Release provenance](https://github.com/Nitmi/embedded-agent-toolkit/actions/workflows/release-attestation.yml/badge.svg)](https://github.com/Nitmi/embedded-agent-toolkit/actions/workflows/release-attestation.yml)
[![Release](https://img.shields.io/github/v/release/Nitmi/embedded-agent-toolkit)](https://github.com/Nitmi/embedded-agent-toolkit/releases/latest)
[![License](https://img.shields.io/github/license/Nitmi/embedded-agent-toolkit)](LICENSE)

Embedded Agent Toolkit is the orchestration layer for Nitmi's embedded Agent
tools. It combines their existing contracts instead of hiding the underlying
tools behind another hardware abstraction:

| Component | Responsibility | Interface |
| --- | --- | --- |
| [baud-cli](https://github.com/Nitmi/baud-cli) | Serial and firmware consoles | CLI + Skill |
| [BLEA](https://github.com/Nitmi/blea) | Bluetooth Low Energy diagnostics and automation | CLI + Skill + MCP |
| [embedded-debugger](https://github.com/Nitmi/embedded-debugger) | Probe discovery, flash, debug, evidence, and replay | CLI + Skill + MCP |
| `board-registry` (optional, pre-release) | Offline fail-closed correlation of saved component discovery evidence | CLI |

The value of the toolkit is the cross-tool workflow: one identity ledger, one
safety policy, correlated evidence, and deterministic cleanup across serial,
BLE, and debug transports. Each component remains independently usable.

## Install the current release

The latest published release is `0.10.1`, which provides a standalone `bootstrap.py`
alongside the plugin ZIP. Download the bootstrap with GitHub CLI,
authenticate it before execution, and keep its exact filename:

```powershell
gh release download v0.10.1 --repo Nitmi/embedded-agent-toolkit `
  --pattern bootstrap.py
gh attestation verify bootstrap.py `
  --repo Nitmi/embedded-agent-toolkit `
  --source-ref refs/tags/v0.10.1 `
  --signer-workflow Nitmi/embedded-agent-toolkit/.github/workflows/release-attestation.yml `
  --deny-self-hosted-runners
python bootstrap.py --install-root C:\Tools\embedded-agent-toolkit --json
```

The bootstrap requires Python 3.11+, an authenticated GitHub CLI, and network
access to GitHub. It verifies itself again, downloads the exact versioned ZIP
and checksum into a temporary directory, enforces the tag and signer workflow,
and delegates installation to the authenticated package's existing installer.
It does not activate the plugin, install component CLIs, change `PATH`, launch
MCP servers, or access hardware. Upgrades retain the previous version for
rollback. See [release and upgrade instructions](docs/releases.md) and
[release provenance](docs/provenance.md) for the manual path and trust boundary.

## Readiness check

After activating the plugin through your Agent host and installing the three
component CLIs, run the host-only doctor:

```powershell
python scripts/toolkit_doctor.py --strict --json
```

For a stable workstation or CI setup, create a component lock that binds the
exact paths, versions, and SHA-256 hashes of `baud`, `blea`, and
`embedded-debugger`; then pass it to doctor. See [installation](docs/installation.md).
Toolkit release installation and bootstrap can reuse that lock with
`--component-lock`, while `component_lock.py compare` provides a host-only review
of an intentional component change before selecting a new lock.

The current source can explicitly select a hash-bound workstation lock once:

```powershell
python scripts/station_config.py select C:\Tools\embedded-agent-toolkit\component-locks\workstation.json --json
python scripts/toolkit_doctor.py --strict --json
```

Doctor selection order is an explicit `--component-lock`, the current project's
`.embedded/toolchain-lock.json`, the selected workstation lock, then ambient
environment/PATH resolution. Its JSON result reports the selected source, path,
and lock SHA-256. Use `--no-auto-lock` only when intentionally diagnosing the
ambient environment.

`board-registry` is an optional fourth host-only component. The trusted catalog
pins its standalone release, but default installation still selects only the
three core components. Opt in with `--include-optional board-registry` and check
it explicitly with `--component board-registry`; a v2 component lock may include
its exact path, version, and SHA-256 while existing v1 three-component locks remain valid. See
[offline board identity resolution](docs/board-registry.md).

The Toolkit also includes `component_install.py`. Its offline `plan`
validates the release-bound component catalog and reports exact sources,
hashes, destinations, and availability without network or process execution.
Its `install` mode is fail-closed. The current catalog
pins attested Windows x86_64 releases of `baud 0.1.2`, `BLEA 0.6.5`, and
`embedded-debugger 0.2.1`, plus opt-in `board-registry 0.1.0`, so its default
Windows plan is complete without falling back to ambient package-manager resolution.

For a new workstation, the authenticated bootstrap can perform the complete
host setup in one explicit command:

```powershell
python bootstrap.py `
  --install-root C:\Tools\embedded-agent-toolkit `
  --component-install-root C:\Tools\embedded-agent-components `
  --lock-output C:\Tools\embedded-agent-toolkit\component-locks\workstation.json `
  --json
```

Add `--include-optional board-registry` to install and lock the offline resolver
in the same transaction.

This opt-in mode installs only the catalog-pinned component executables, creates
the exact component lock, and runs strict doctor. The default bootstrap remains
plugin-only. Neither mode edits `PATH`, activates plugins, launches MCP servers,
or accesses hardware.

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

## Host doctor details

The doctor checks only executable versions and the local plugin layout. It does
not enumerate or open adapters, probes, ports, or targets.

```powershell
python scripts/toolkit_doctor.py
python scripts/toolkit_doctor.py --json
python scripts/toolkit_doctor.py --strict
```

Use `EMBEDDED_AGENT_BAUD`, `EMBEDDED_AGENT_BLE`, or
`EMBEDDED_AGENT_DEBUGGER` to point a core check at a specific executable. Use
`EMBEDDED_AGENT_BOARD_REGISTRY` only for an explicit optional-component check. The
default check reports a missing `PATH` entry as `ready_with_warnings`; use
`--strict` when every component CLI must be directly invocable.

For stable project or test-station selection, `scripts/component_lock.py` creates
an explicit lock of the three core executable paths, versions, and SHA-256 values,
with optional `board-registry` identity in a v2 lock.
Pass it to doctor with `--component-lock`; it remains host-only and does not
modify `PATH` or proxy hardware commands. See [installation](docs/installation.md).
Release installation can create or reuse this lock and complete strict doctor in
the same command; see [versioned releases](docs/releases.md).
Tagged GitHub builds can add repository-bound provenance; see
[release provenance](docs/provenance.md).

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
