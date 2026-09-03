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

## Install the plugin

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
