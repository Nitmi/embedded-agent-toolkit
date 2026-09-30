# Offline firmware inspection

The `0.18.0` source candidate includes `firmware-inspect` as an optional host-only
component. This integration is not yet in a published Toolkit release. Its v2
catalog pins the immutable, provenance-verified component Release `0.1.0` for
Windows x86_64. Default
installation and doctor still select only baud, BLEA, and embedded-debugger.

The component checks local ELF/HEX/BIN artifacts without reading a target,
opening a transport, or invoking a toolchain. It provides file identity, sparse
address ranges, ELF load/run addresses, section sums, GNU Build IDs and bounded
symbols, plus comparison of payload, layout and section changes.

## Exact component selection

When a project or workstation lock is active, use its exact executable path.
An optional component absent from that lock does not fall back to ambient PATH.
Add an already reviewed firmware-inspect executable to a new candidate v2 lock
using `component_lock.py create --firmware-inspect <absolute-executable-path>`
along with the existing core selections and optional `--board-registry`.
Compare the candidate with the selected lock before intentionally choosing it.
Never overwrite the active lock or install a component during hardware diagnosis.

Check the new candidate explicitly:

```powershell
python scripts/component_lock.py inspect C:\project\.embedded\candidate-lock.json --json
python scripts/toolkit_doctor.py --component-lock C:\project\.embedded\candidate-lock.json `
  --component firmware-inspect --strict --json
```

Only the inspector's `--version` is started by doctor. A reviewed standalone
candidate can be examined in an explicit host setup using a process-local
`EMBEDDED_AGENT_FIRMWARE_INSPECT` override and `--no-auto-lock`; do not use that
mode to hide a lock conflict.

In this candidate, `--include-optional firmware-inspect` opts into catalog-backed
installation and lock generation. Inspect a host-only plan before installation:

```powershell
python scripts/component_install.py plan --install-root C:\Tools\embedded-agent-components `
  --include-optional firmware-inspect --json
python scripts/component_install.py install --install-root C:\Tools\embedded-agent-components `
  --lock-output C:\Tools\embedded-agent-toolkit\component-locks\candidate.json `
  --include-optional firmware-inspect --timeout 120 --json
```

Add `--include-optional board-registry` to include both optional tools in a
five-component v2 lock. Selecting just firmware-inspect produces four components;
omitting both still installs only three. Installation preserves the executable's
sibling `LICENSE`, `THIRD-PARTY-NOTICES.txt`, and `release-manifest.json` when
present in the hash-verified archive. It does not extract arbitrary extra files
or claim that a copied component manifest has independently been authenticated.

The pinned asset is
`embedded-firmware-inspect-0.1.0-windows-x86_64.zip`, SHA-256
`4de53a107b3286c67fea86a36ef91779ca15e85fff682d2ff20374afca5c5c15`.
Its Release source is `17f1fc24c53c9e31ca9169d9de277929545d7e11` and signer is
`Nitmi/firmware-inspect/.github/workflows/binary-release.yml@refs/tags/v0.1.0`.
The component's verification is separate from publishing and authenticating the
Toolkit candidate. An arbitrary external catalog is not publisher authority.

## Use the native CLI

Invoke the executable path verified above. These examples assume that exact
executable is already selected:

```powershell
firmware-inspect inspect C:\project\build\app.elf --json
firmware-inspect inspect C:\project\build\whole.hex --json
firmware-inspect inspect C:\project\build\app.bin --base-address 0x10000 --json
firmware-inspect diff C:\build-A\app.elf C:\build-B\app.elf --json
```

No hardware confirmation is needed for this file-only analysis. BIN requires
an explicit project base address; never guess one. ELF section totals are not
board RAM/Flash percentage, and `programmed_ranges` is not an erase plan.
High HEX addresses such as UICR remain visible. A file hash or GNU Build ID does
not verify what is running on a board or authenticate a firmware signature.

Preserve native JSON when saving inspection evidence. A successful `diff` means
the two files were analyzed, not that they fit a requested budget or are correct.
Inspection does not authorize flashing or replace the debugger's native plan,
bounded flash-session scope, target identity checks or cleanup.
No additional MCP server is registered by the Toolkit.
