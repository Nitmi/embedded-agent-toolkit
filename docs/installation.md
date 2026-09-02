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

The initial plugin load can succeed while a component is missing. The doctor
returns exit code 2 and a per-component remedy when the toolchain is incomplete.

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
orchestration Skills and aggregate BLEA MCP registration; it does not uninstall
the component CLIs or delete hardware evidence. Remove those separately only
when that is the intended scope.
