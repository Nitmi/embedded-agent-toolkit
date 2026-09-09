# Installation and lifecycle

## Prerequisites

Install all three component CLIs and verify that their executable directories
are on `PATH`:

```powershell
uv tool install git+https://github.com/Nitmi/baud-cli
uv tool install git+https://github.com/Nitmi/blea
cargo install --git https://github.com/Nitmi/embedded-debugger embedded-debugger
```

For source development, use each repository's documented environment instead
of installing an unrelated package with a similar command name.

## Trusted component acquisition

Toolkit 0.9.0 includes a strict standalone-artifact installer. Inspect its bundled,
release-bound catalog without network or component execution:

```powershell
python scripts/component_install.py plan `
  --install-root C:\Tools\embedded-agent-components `
  --json
```

The current catalog includes the attested Windows x86_64 releases of `baud 0.1.2`,
`BLEA 0.6.5`, and `embedded-debugger 0.2.1`. The offline plan therefore reports
`complete=true` on that platform and binds every URL, SHA-256, executable member,
version, and destination before any download or process execution.

Install the complete catalog with:

```powershell
python scripts/component_install.py install `
  --install-root C:\Tools\embedded-agent-components `
  --lock-output C:\Tools\embedded-agent-toolkit\component-locks\workstation.next.json `
  --json
```

Installation accepts only exact `https://github.com/<catalog repository>/releases/download/v<version>/...`
assets, validates bounded ZIP contents and SHA-256 before writing, installs each
executable under `<root>/<component>/<version>/`, runs only one `--version` per
component, and creates a new component lock. It never edits PATH or accesses
hardware. It refuses an existing lock or a different existing executable. A
late failure can leave already verified version directories for inspection, but
no lock is produced; review and compare the new lock before selecting it.
Installed entry points suppress Python bytecode writes before importing sibling
modules, so running these host-side tools does not add `__pycache__` to the
verified plugin directory.

An externally supplied `--catalog` is only structured input. It has publisher
authority only when its bytes came from a Toolkit release whose GitHub
attestation was independently verified.

The authenticated release bootstrap can combine plugin and component setup when
the user explicitly selects fresh component and lock destinations:

```powershell
python bootstrap.py `
  --install-root C:\Tools\embedded-agent-toolkit `
  --component-install-root C:\Tools\embedded-agent-components `
  --lock-output C:\Tools\embedded-agent-toolkit\component-locks\workstation.json `
  --json
```

This mode uses the catalog inside the authenticated plugin installation. It is
mutually exclusive with `--component-lock` and with explicit `--baud`, `--blea`,
and `--debugger` selections. Component versions remain installed when a later
step fails, but a newly generated lock is removed if strict doctor fails. The
component root and lock must remain outside the immutable installed plugin
directory.

## Install the plugin

For a versioned ZIP, follow [release installation](releases.md). The recommended
single command verifies and installs the package, creates an exact component
lock from explicit executable paths, and runs strict host-only readiness checks.
It does not change the active plugin. Component CLIs still need their own
installation.

Clone `embedded-agent-toolkit`, then add that directory as a local plugin in
the Agent host. The selected directory must directly contain
`.codex-plugin/plugin.json`; do not select its parent directory.

Reload the host, invoke one of the four Skills, and run:

```powershell
python scripts/toolkit_doctor.py --json
```

The initial plugin load can succeed while a component CLI is missing from
`PATH`. The default doctor reports `ready_with_warnings` and an exact-path
fallback while returning exit code 0. Use `--strict` when setup validation or
CI requires every default CLI entry; strict mode returns exit code 2 for an
incomplete toolchain. Real layout, override, launch, and version errors fail in
both modes.

## Lock exact component versions

For a stable project or test station, create one explicit component lock rather
than relying on ambient command precedence:

```powershell
python scripts/component_lock.py create --output .embedded/toolchain-lock.json `
  --baud (Get-Command baud -CommandType Application).Source `
  --blea (Get-Command ble -CommandType Application).Source `
  --debugger C:\Tools\embedded-debugger\embedded-debugger.exe `
  --json
python scripts/component_lock.py inspect .embedded/toolchain-lock.json --json
python scripts/toolkit_doctor.py --component-lock .embedded/toolchain-lock.json --strict --json
```

Before switching a project or test station to a candidate lock, compare it with
the currently selected lock:

```powershell
python scripts/component_lock.py compare `
  .embedded/toolchain-lock.json `
  .embedded/toolchain-lock.next.json `
  --json
```

`compare` validates both locks and their executable hashes, starts no process,
and reports each changed path, version, and SHA-256. Keep the old lock and its
referenced component installations available when rollback is required.

When installing a release, prefer the combined command in
[versioned releases](releases.md); use the standalone commands above when the
plugin is already installed or when replacing a lock intentionally after
reviewing the component changes.

Creation runs only each executable's `--version`; inspection performs no process
execution. Comparison also performs no process execution. The lock requires
absolute regular-file paths and binds each file's
version and SHA-256. Doctor verifies hashes before starting `--version` and
requires observed versions to match. A selected lock is authoritative:
`EMBEDDED_AGENT_BAUD`, `EMBEDDED_AGENT_BLE`, or `EMBEDDED_AGENT_DEBUGGER` in the
same process is treated as a conflict, not as an override. The lock does not edit
`PATH`, activate plugins, authorize hardware access, or proxy component commands.
Commit a project lock only when its host-specific absolute paths are intentional;
otherwise keep it as test-station configuration outside source control.

## Component MCP servers

The toolkit does not register component MCP servers. Install and enable the
BLEA plugin separately when BLE MCP tools are needed. Keeping the server in its
component plugin prevents duplicate tool registrations and duplicate processes
when users also install the standalone component.

## Native debug MCP

The plugin deliberately omits a target-specific debug MCP entry. Add one in the
project's MCP configuration only after `embedded-debugger` has returned the
exact probe-rs target identifier. Keep that target in project configuration,
not in this reusable plugin.

## Project runtime setup

Use `embedded-debugger 0.2.0` or newer for project runtime setup. Check
`embedded-debugger runtime --help` for
`init` and `inspect`; early `0.1.0` builds predate those commands, so the version
string alone does not establish their availability. Use the exact new build
path during source development. Follow the
[project contract workflow](../skills/hardware-test/references/runtime-contract.md)
to prepare `.embedded/runtime.json` without enumerating or opening hardware.
The toolkit keeps no second copy of the runtime schema and starts no additional
MCP server for this workflow.

## Upgrade

Update this repository and each component independently, rerun the doctor, and
review release notes before the next state-changing hardware operation. A
component upgrade invalidates assumptions based on an earlier executable hash
or confirmation digest.

## Uninstall

Remove the local plugin entry and reload the Agent host. This removes the four
orchestration Skills; it does not uninstall component plugins, component CLIs,
or hardware evidence. Remove those separately only when that is the intended
scope.
