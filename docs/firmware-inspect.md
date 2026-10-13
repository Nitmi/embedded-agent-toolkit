# Offline firmware inspection

Toolkit `0.18.0` introduced `firmware-inspect` as an optional host-only
component. Published Toolkit `0.21.0`'s v2 catalog pins the immutable,
provenance-verified component Release `0.2.0` for Windows x86_64, adding exact
ELF symbol lookup. Published Toolkit `0.18.0`–`0.20.0` catalogs still select
`0.1.0`, and existing locks are not upgraded automatically. Default
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

In Toolkit `0.18.0`, `--include-optional firmware-inspect` opts into catalog-backed
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
`embedded-firmware-inspect-0.2.0-windows-x86_64.zip`, SHA-256
`44018887462bdc2fb88db8296a7f24711d0b1c06d46b1f863dcdce3c353e4b27`.
Its Release source is `575b1cca7a21c17c16e0b3affabc5b1c7d0e1e87` and signer is
`Nitmi/firmware-inspect/.github/workflows/binary-release.yml@refs/tags/v0.2.0`.
The component's verification is separate from authenticating the enclosing
Toolkit Release. An arbitrary external catalog is not publisher authority.

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

## Exact ELF symbols

With a selected firmware-inspect `0.2.0` or newer, query names directly:

```powershell
firmware-inspect symbols C:\project\build\app.elf --name _SEGGER_RTT --name main --json
```

Use its exact lock-bound executable path in actual commands. Supply up to 32
distinct, case-sensitive names; this scans all symbol tables independently of
`inspect`'s largest-symbol limit. `source.sha256` binds the parsed snapshot.
Preserve `queries[].matches` with table, section, type, binding, visibility, raw
`value`, `value_kind` and `size_bytes`. A completed query can return `not_found`,
`undefined_only` or `no_definition`; successful exit is not successful resolution.
`ambiguous` retains conflicting definitions without selecting one. Equivalent
definition metadata can produce `unique` while preserving multiple table entries.

The value is ELF `st_value`, not a validated live address. Do not clear ABI bits
or interpret TLS offsets, COMMON alignment or relocated PIE values as ordinary
target RAM. Zero-sized symbols provide no inferred extent. For RTT, require a
unique section-defined object with an allocated writable section and a suitable
declared size; bind the same ELF hash and pass the value through the debugger's
native target RAM checks. No file query proves control-block initialization.

With an older selected component, keep using its supported inspection commands
and report that exact queries require 0.2.0+. Do not install another tool or
change locks during diagnosis, and do not replace a missing result with a guessed
address or a symbol from another build.
