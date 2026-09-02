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

Actual Skill injection must be checked in a new Agent conversation because an
existing conversation retains the plugin snapshot with which it started.

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
server correction, and discovery-only ESP32-S3 identity correlation passed.
The next acceptance must start in a new conversation and verify that the four
aggregate Skills are discoverable there. Device-specific BLE selection, serial
monitoring, target attachment, firmware identity, and every state-changing
operation remain untested and require their own evidence and authorization.
