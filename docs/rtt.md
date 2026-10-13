# Bounded RTT workflows

Toolkit `0.19.0` pins the published `embedded-debugger 0.2.4`
Windows asset. Its SHA-256 is
`f46287d2b981afaa67578e4204ba584c1e29b0a0e788b04a9641d0531995b92c`;
the source and signer commit is `7053f54e1b9fcca000d1e7e9f1f6d4b904399137`,
from `.github/workflows/binary-release.yml@refs/tags/v0.2.4` in
`Nitmi/embedded-debugger`. This component provenance is separate from the
enclosing Toolkit release provenance.

Use the exact executable in the active component lock. RTT is currently a native
CLI workflow: `rtt plan` and `rtt capture`. Persistent-session and MCP RTT requests
are unavailable. Native capture supports probe-rs, `nRF52840_xxAA`, core 0, one
selected up channel. Replay is available for offline checks; OpenOCD and other
native targets return `CAPABILITY_UNAVAILABLE`.

## Plan the observation

Bind the exact probe, target, firmware ELF/hash, initialized `_SEGGER_RTT`
address, core/channel, sampling duration and maximum bytes. Obtain the address
from that build's symbols/linker output, never a sample or another board.
Optional firmware-inspect 0.2.0+ can query `_SEGGER_RTT` directly using
`symbols <exact-build.elf> --name _SEGGER_RTT --json`; read
[exact ELF symbol guidance](firmware-inspect.md#exact-elf-symbols).
Use a unique section-defined object with allocated writable storage and an
appropriate declared size. Bind its ELF hash and raw value to the native plan's
target RAM checks. Neither ELF identity nor an address establishes which
firmware is running or whether the block is initialized.

`rtt plan` is host-only: no enumeration, attachment or memory access. It binds
the inputs and effects in a native confirmation digest. `rtt capture` enumerates
and attaches to the exact probe, reads the selected channel's metadata and
data, and **writes its RAM read cursor**. It consumes bytes even if saving them
later fails. It preserves channel mode and does not issue down-channel writes,
reset/halt/resume, register operations, flash, erase or recover. Attach and
disconnect may affect the target; post-disconnect core state remains unknown.

One task authorization may cover the agreed bounded observation. Generate and
use the current native digest within that scope; do not ask for the same user
authorization repeatedly or extend a flash session's scope to RTT implicitly.
The digest remains a machine gate. No automatic retry or competing RTT consumer.

Sampling duration is 10..60000 ms, payload 1..1048576 bytes, poll interval
1..1000 ms and no greater than duration; at most 4096 nonempty chunks of 4096
bytes. Probe I/O may extend wall time. A byte/chunk/deadline stop or zero-byte
success is not a ready assertion, and firmware-side overflow is not measured.

## Keep native evidence

Preserve stdout's unchanged `1.0` envelope containing
`embedded-debugger.rtt-capture.v1`, plus its referenced
`embedded-debugger.rtt-evidence.v1` JSONL file. Use new paths for each operation.
Keep the native path valid during evaluation; copying a bundle does not justify
editing native evidence to replace its path. Relative references, when present,
are resolved from the saved summary's directory.

Chunks are hex bytes with sequence, capture-relative cursor/next_cursor, UTC and
elapsed time. Reconstruct bytes before decoding text: lines and UTF-8 characters
can span chunks, and binary bytes are valid. The cursor is neither a target
address nor a token for resuming another capture.

Declare `embedded-debugger.rtt-plan` and `embedded-debugger.rtt-capture` in a
[test contract](test-contract.md). Both bind the same firmware resource; capture
requires the earlier plan. The plan declares only `host_process_start`.
Capture declares exactly:

```json
[
  "debug_attach", "hardware_discovery", "host_process_start", "memory_read",
  "rtt_read_cursor_write", "target_state_may_change"
]
```

Use `max_retries=0`. The cursor effect is classified as target control, not
generic persistent-memory programming. The example
[nrf52840-rtt-test-spec.json](examples/nrf52840-rtt-test-spec.json) is an authoring
template: replace its selection, ELF path/hash, expected probe and channel
address using project evidence before compilation. It executes nothing.

`test_contract.py evaluate` automatically checks native plan/capture schemas,
the selected probe and target, exact equality with prerequisite plan evidence,
session/channel binding, and the raw artifact size/SHA-256. It verifies record
order, capture ID, monotonic elapsed time, sequence/byte cursors, chunk and
payload bounds, raw payload SHA-256, stop reason and stop/disconnect evidence.
The report's `rtt_artifact` records these checks without embedding payload or
rewriting native JSON. A missing/corrupt artifact makes evaluation incomplete.
All evaluation is file-only, with no component process or hardware access.

Boolean `/data/channel_stopped` and `/data/disconnected` fields remain native
booleans. Assert them with `equals: true`; do not invent string cleanup states
or claim `/target=running`. These RTT cleanup checks are mandatory in the native
evidence validator, even with `cleanup: []`; other stages retain their existing
cleanup requirements. Cleanup evidence from a preceding flash is valid for that
operation's end, not proof of core state after a subsequent RTT attachment.
The template verifies identity and integrity, not
firmware readiness. Apply a project-bound decoder to the verified raw bytes for
exact READY/BUILD_ID and complete heartbeat assertions; preserve that separate
report and parser/input hashes. A source build banner is not a final ELF hash or
cryptographic runtime attestation.

## Inspect saved logs without a device

Toolkit `0.20.0` provides a file-only reader using the existing integrity API:

```powershell
python scripts/rtt_evidence.py inspect capture-summary.json --json
python scripts/rtt_evidence.py preview capture-summary.json --max-lines 40 --json
python scripts/rtt_evidence.py extract capture-summary.json --output payload.bin --json
```

Each command verifies the unchanged native summary and its referenced JSONL
before returning any payload. It binds the input paths, byte sizes and SHA-256
hashes, reconstructs bytes from the same verified file read, and starts no
component or hardware operation. `inspect` reports metadata only; `preview`
returns bounded derived lines; `extract` writes exact binary bytes to one
explicit, new file. It refuses existing destinations, including either native
input. Parent directories must already exist. An output I/O failure may leave
a partial derived file; an unsuccessful report is not a usable export.

Preview decodes UTF-8 after reconstructing chunks, preserving characters and
LF/CRLF lines split across chunks. A binary/invalid UTF-8 line has `text=null`
and bounded `data_hex`; no replacement characters are inserted. `complete=false`
marks a tail without LF. `truncated=true` means only a prefix is displayed, even
when the source line is complete. The response limits are 1..100 lines,
1..4096 bytes per line and a fixed 16384-byte content budget. Text output escapes
terminal control sequences rather than replaying firmware ANSI commands.

Each line carries capture byte `cursor`/`next_cursor` and first/last source
chunk observations. These timestamps describe host chunk reads, not precise
firmware event times. Use `--cursor <preview.next_cursor>` to request the next
page. The cursor advances past the entire source line, including a truncated
prefix's omitted bytes; use the binary export when those bytes matter. An
arbitrary cursor can start mid-line or mid-character; `initial_fragment=true`
makes that ambiguity explicit. It is a file offset, never a target resume token.

The JSON format is [rtt-read.schema.json](../schemas/rtt-read.schema.json),
`embedded-agent-toolkit.rtt-read.v1`. Success exits 0; rejected evidence, invalid
preview limits, missing inputs or refused output exits 2. A verified preview is
not READY/BUILD_ID/heartbeat acceptance or proof of current firmware identity.
Partial or failed native captures remain incident evidence; these commands
reject them instead of presenting an unchecked successful log.

## Associate RTT with serial or BLE

For more than one interface/window, keep an
[identity ledger](../skills/firmware-debug/references/identity-ledger.md).
Name the plan, capture summary, JSONL, serial raw capture and any saved board
selection as separate hashed sources. Record probe routing, serial USB identity,
firmware artifact and runtime banner independently. Matching probe/VCOM serial
numbers associate a USB device; an external SWD target still needs routing
evidence. Clocks alone do not prove a shared board or firmware.

Use capture ID, native session/operation IDs, UTC windows and capture-relative
byte offsets to reference exact events. Describe serial buffering and clock
uncertainty. A shared protocol build ID/counter can support correlation with its
defined semantics, but does not prove uninterrupted execution across captures.
Do not present a timestamp-sorted concatenation as a verified common timeline.

For an incident, explicitly account for cursor consumption and attach effects
before choosing RTT. Preserve partial JSONL and cleanup errors after failure;
capture does not authorize reset, resume, recovery or reflashing.
