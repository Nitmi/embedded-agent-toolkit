# Local plugin acceptance — 2026-09-02

## Scope

This checkpoint installed the aggregate plugin, validated its cached contents,
smoke-tested the component MCP contract, and ran a discovery-only embedded
bring-up. It did not open a serial port, connect to a BLE device, attach a debug
target, flash, erase, reset, halt, resume, or transmit device data.

## Plugin installation

- Marketplace: `personal` at `C:\Users\Nitmi\.agents\plugins\marketplace.json`.
- Source: a directory junction from
  `C:\Users\Nitmi\plugins\embedded-agent-toolkit` to
  `D:\Code\ai\embedded-agent-toolkit`.
- Installed plugin: `embedded-agent-toolkit@personal`, enabled, base version
  `0.1.0`.
- The installed cache contained all four orchestration Skills with hashes equal
  to the source files.
- The final aggregate cache contained no `.mcp.json` or `mcp.json`.

Skill injection was checked in a new Agent conversation. `embedded-bringup`
automatically triggered and loaded.

## BLEA MCP smoke test

A fresh bounded stdio client performed only MCP `initialize` and `tools/list`:

- server `BLEA`, version `0.6.4`;
- protocol version `2025-11-25`;
- 22 tools advertised;
- no BLE tool was called and the smoke-test process exited cleanly.

The first aggregate build also registered BLEA itself. Installing it alongside
the standalone BLEA plugin created a second server process and duplicate tool
ownership. The aggregate registration was removed, the plugin doctor now rejects
active component MCP manifests, and only the standalone BLEA process tree was
retained after cleanup.

## Discovery-only bring-up

| Interface | Observed evidence | Binding decision |
| --- | --- | --- |
| Serial | `COM3`, USB `303A:1001`, serial `E0:72:A1:D4:1F:DC` | Exact interface identity recorded; port not opened |
| Debug probe | Accessible `EspJtag`, ID `303a:1001:E0:72:A1:D4:1F:DC` | Same USB identity as COM3; no target selected or attached |
| BLE adapter | Available through BLEA 0.6.4; 27 advertisements observed in the bounded doctor window | Adapter accepted; no peripheral identity selected |
| nRF52840 | No matching serial or debug interface observed | Not present or not enumerable in this checkpoint |

The debugger doctor reported probe-rs CLI `0.32.0` available and guarded
probe-rs flashing supported. `openocd` was not available through ambient `PATH`;
this does not invalidate earlier explicit-executable OpenOCD acceptance, but a
future workflow must continue to bind its exact executable path.

## Result and remaining boundary

The plugin installation, cache integrity, MCP protocol handshake, duplicate
server correction, automatic `embedded-bringup` discovery, and discovery-only
ESP32-S3 identity correlation passed. The new-conversation run reported one
environment warning: `embedded-debugger` was not on `PATH`. It then bound the
exact development executable at
`D:\Code\ai\embedded-debugger\target\release\embedded-debugger.exe`, verified
it, and enumerated the probe without selecting a target or attaching.

At that checkpoint, device-specific BLE selection, serial monitoring, target
attachment, firmware identity, and every state-changing operation remained
untested and required their own evidence and authorization.

The doctor regression suite now has 9 unit tests covering the warning/error
state split; a manual check also verified strict-mode exit behavior.

## Read-only ESP32-S3 serial observation — 2026-09-03

A fresh gate immediately before opening the port found exactly one serial
interface: `COM3`, USB `303A:1001`, serial
`E0:72:A1:D4:1F:DC`. Windows PnP independently reported
`USB\VID_303A&PID_1001&MI_00` for `COM3`, and no residual `baud monitor`
process was present.

Exactly one command was run with baud 0.1.0:

`baud monitor --port COM3 --baud 115200 --duration 8 --dtr false --rts false --json --log-dir <evidence-dir>`

The structured run-start event records `dtr=false` and `rts=false`; the
JSONL contains receive events only and no transmit event. The eight-second
monitor step received 328 bytes containing eight complete, consecutive
heartbeats `3766..3773` with the repeating RGB sequence. The startup capture
also preserved 41 bytes for heartbeat `3765`, so the evidence files contain
369 received bytes and nine complete heartbeats in total.

The command returned `ok=true`, `exit_code=0`, closed cleanly, and left no
monitor process. It was not retried. This proves bounded device-to-host serial
activity and a continuously advancing heartbeat for the exact observed USB
interface. It does not bind a firmware build identity, prove host-to-device
traffic, select a BLE peripheral, attach a debug target, or authorize any
state-changing operation.

Evidence is under
`evidence/2026-09-03-esp32s3-com3-115200-8s`. The JSONL SHA-256 is
`0407F115F37F9F4BD0EA96FC0BAA6BB24299CEA2AAF5EEFFD933C531D4EFC5FE`;
the human log SHA-256 is
`E257D1A5A2F0FF18177B621F140B741C517FA8450FD35A5B95161F6A3CB53C2F`.

## Offline cross-tool identity ledger — 2026-09-03

The `firmware-debug` workflow correlated the current serial artifacts with
three hashed 2026-09-02 embedded-debugger acceptances and the unchanged local
ELF. The analysis was host-only: it did not enumerate or open a serial port,
connect BLE, enumerate or select a probe, attach a target, or change device
state.

The earlier ESP app descriptor acceptance directly verified, at that point in
time, project `yd-esp32-s3-rust-demo` version `0.1.0` with embedded ELF
SHA-256
`676a89d78556f07500fcbe50a17c046c27d9d6e1e425ed9732c6f257a09f7b20`.
At this offline checkpoint, that historical result was preserved separately
from the then-current runtime identity, which remained unknown because the
workflow had only read existing serial evidence. The later confirmed closure is
recorded below.

The selected source initializes a u32 heartbeat to zero, increments it before
logging, waits 1,000 ms, and cycles red/green/blue. The current `3765..3773`
sequence matches that rule, but compatibility is not a unique build identity.
The prior final complete heartbeat was 8545 at
`2026-09-02T05:05:24.288Z`; the next window began with 3765 at
`2026-09-03T01:32:11.715Z`. A u32 wrap is impossible in the elapsed
20h26m47s, so uninterrupted counter continuity is rejected. The artifacts do
not distinguish reset, power loss, reflash, alternate firmware, or another
identity discontinuity.

The example was later extended with the confirmed flash and runtime evidence.
Its current human report is
`docs/examples/esp32s3-identity-ledger-2026-09-03.md` (SHA-256
`98DD7ECB54690EA27208CB611232E62D982A3260DB1083F61BC9639CD6DA808F`),
and the machine ledger is
`docs/examples/esp32s3-identity-ledger-2026-09-03.json` (SHA-256
`DE56E341D4E12BCF6FB655AA97A0E6B1A3E415E5AE8B89E8A680D4B7CDC3CE94`).
The Skill now routes multi-window work to
`skills/firmware-debug/references/identity-ledger.md`, whose SHA-256 is
`6F3C15BB00C81FB57F2AC644F1CCE8D24E040676EE722B7D5F88FA702945D3F2`.


## Host-only serial firmware identity implementation — 2026-09-03

The least-invasive identity improvement from the ledger was implemented without
accessing hardware. Baud commit `29ebd49` adds a fail-closed pre-open USB identity
gate for VID, PID, and serial number in both direct commands and YAML workflows.
Its validation passed 14 tests, Ruff lint and format checks, and the bundled
Skill validator; the user-level Baud Skill copy was refreshed and matched the
source digest.

The ESP32-S3 demo firmware commit `c3b7970` reads the ESP app descriptor's
runtime-patched ELF SHA-256 with volatile loads and includes the exact value in
every heartbeat. The release ELF SHA-256 is
`26acd68ba2d9676be1e8b804b54560b647c0f5055a192ca43e2a30931e690242`.
An offline `espflash 4.5.0` image build placed that same value at app
descriptor offset `0x100B0`, confirming the post-link identity path without a
self-hash cycle.

A receive-only eight-second Baud workflow was prepared to bind COM3 to USB
`303A:1001 / E0:72:A1:D4:1F:DC` and requires a heartbeat carrying that
ELF hash. At this host-only checkpoint, the workflow had only been
schema-loaded, the new firmware had not been flashed, and the target's runtime
identity therefore remained unknown. The later authorized execution is below.


## Confirmed flash and runtime identity closure — 2026-09-03

After the host-only implementation checkpoint above, `embedded-debugger 0.1.0`
generated two stable ESP32-S3 IDF flash plans and a fresh pre-execution plan for
EspJtag `303a:1001:E0:72:A1:D4:1F:DC`. All used target `esp32s3`, a 16 MiB flash,
chip-revision encoding 2, and final ELF SHA-256
`26acd68ba2d9676be1e8b804b54560b647c0f5055a192ca43e2a30931e690242`.
The confirmation digest remained
`35836c94567e91b2f3e11ccf6c5e6129f8e69a80b199de8e7fb0bc26f87af46b`.

After the user independently returned that exact digest, one physical flash
execution ran with zero retries. It programmed and independently verified the
bootloader, partition table, and application segments, totaling 119,648 bytes.
Offline `snapshot inspect` reported `complete=true` and all eight ordered
operations succeeded through `session.disconnect`. CPU0 finished running; CPU1
remained halted at its expected ROM breakpoint. Flash evidence SHA-256 is
`7114737d2df18b259303fd1e42fa4e013a8073e4e66f5c9abee053a2d79b454e`.

A separate user authorization then allowed exactly one receive-only COM3
workflow. Fresh enumeration bound USB `303A:1001` and serial
`E0:72:A1:D4:1F:DC`; static inspection proved the workflow had zero send steps,
one eight-second monitor, and DTR/RTS false. It ran once with zero retries,
received 1,106 bytes and continuous heartbeats `1370..1378`, and found the exact
ELF SHA-256 in all nine periodic records. The JSONL contains zero transmit
events, the port closed, post-run enumeration retained the same USB identity,
and no serial or debugger process remained. Its SHA-256 is
`970ecde765953040a927746c54270040426c8172a821f9459131b0f73f525291`.

This upgrades current runtime firmware identity to `observed` only inside the
recorded `2026-09-03T08:38:14.398Z..08:38:23.243Z` window. It is firmware-
controlled, non-adversarial build correlation, not signed attestation, Secure
Boot verification, silicon identity, or continuity outside the window. The
updated machine ledger is validated by `scripts/validate_identity_ledger.py`;
the validator is host-only and never enumerates or opens hardware.

## Offline project runtime setup - 2026-09-06

The source `hardware-test` Skill now routes project contract preparation to
the component CLI's `runtime init` and `runtime inspect`. It does not add a
toolkit runner, duplicate schema, or component MCP registration.

From the toolkit checkout, the release debugger at
`D:\Code\ai\embedded-debugger\target\release\embedded-debugger.exe`
generated and inspected a contract using relative output/input paths beneath
`evidence/2026-09-06-project-runtime-setup`. Deliberately offline probe, target,
port, and USB-serial labels established that setup does not require physical
discovery or a valid native target. Both commands returned exit code 0 with
empty stderr and `scope=host_only_no_hardware_access`. The 1,401-byte contract
SHA-256 matched independently:
`5004190c7d47310e03e4460e562f32d81a8b3e3923e30e4c9b489628524332b3`.
The release executable SHA-256 was
`210d033f6328b6fc3ba5b1540b61b9dcd2fc693a9980f60aa0e535fc0fe311d2`.

The debugger suite passed 268 library tests and 95 CLI tests, including
generated-contract Replay acceptance and offline setup under all three backend
selectors with an empty PATH and nonexistent fixture. Toolkit tests passed all
17 cases, and plugin validation plus every source Skill validation passed.
The existing DK contract also passed offline inspection with its original hash.

This checkpoint changes source guidance and the local release executable only.
It does not update the installed plugin cache or PATH, and it does not enumerate,
open, attach, reset, flash, erase, or otherwise access hardware. Offline
configuration validity is not hardware acceptance or firmware identity evidence.
