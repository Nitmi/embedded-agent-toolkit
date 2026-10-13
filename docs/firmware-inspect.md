# Offline firmware inspection

Toolkit `0.18.0` introduced `firmware-inspect` as an optional host-only
component. The current `0.22.0` source catalog pins the immutable,
provenance-verified component Release `0.3.0` for Windows x86_64, adding offline
code-address and DWARF source-line lookup. Published Toolkit `0.21.0` selects
`0.2.0` with exact ELF symbols; `0.18.0`–`0.20.0` catalogs select `0.1.0`.
Existing locks are not upgraded automatically. Default
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
`embedded-firmware-inspect-0.3.0-windows-x86_64.zip`, SHA-256
`7441569224e830fbc1e7c59bf063da54970137246560d893c988d5c10ff88897`.
Its Release source is `5487be08737d5ab80d90b9195b735c78beda85a2` and signer is
`Nitmi/firmware-inspect/.github/workflows/binary-release.yml@refs/tags/v0.3.0`.
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

## PC/LR and code addresses

With a selected firmware-inspect `0.3.0` or newer, annotate addresses already
captured in a log or native debugger snapshot using the exact matching ELF:

```powershell
firmware-inspect addresses C:\project\build\app.elf `
  --address 0x101 --address 0x120 --address-mode arm-thumb --json
```

Use the exact lock-bound executable, not an unverified PATH alternative. Supply
1..32 distinct unsigned byte addresses in the ELF's link-time address context.
The default `raw` mode keeps query values unchanged. Explicit `arm-thumb` requires
ELF32 EM_ARM and clears only query bit 0; retain `address` and `lookup_address`.
Function matches keep `raw_value` and separately record Thumb-bit code-range
normalization. Exact-name `symbols` continues to preserve raw values unchanged.
Neither mode subtracts from LR, guesses instruction width, relocates an image,
unwinds a stack or rebuilds inline frames. An adjusted return address needs an
explicit analyst rationale and a separate query value.

Read each `address_queries` row's `function_status` and `line_status` independently:
`unique`, `ambiguous` or `not_found`. Preserve all `functions` and `lines` with
their table/section/CU/line-program metadata. Functions use declared STT_FUNC
ranges in allocated executable sections; a zero-sized function matches only
its exact code start. DWARF 2–5 lines use half-open intervals and sequence ends;
gaps and line 0 supply no location. A successful CLI exit means a completed query,
even when no metadata resolves. Use `--no-lines` for function-only lookup.

Line paths remain unverified compiler metadata in `file_name`, `directory` and
`compilation_directory`; the query never opens or rebases them. Functions and
lines can disagree after optimization or discarded code. A unique line location
is not verified against source contents or proof of the matching function's body.
Do not merge the independent matches into a claimed call stack or root cause.
External/split, compressed, VLIW and segmented DWARF are unsupported; malformed
or oversized units return structured errors instead of partial successful data.

`source.sha256` binds the bounded snapshot used for parsing. Preserve the native
`embedded-firmware-inspect.addresses.v1` JSON alongside the original log/snapshot;
record address adjustments separately. This is offline annotation, not renewed
firmware attestation or permission to read target memory. With an older selected
component, report the missing 0.3.0+ capability without installing or changing
locks during diagnosis. File-only annotation does not require a hardware session.
