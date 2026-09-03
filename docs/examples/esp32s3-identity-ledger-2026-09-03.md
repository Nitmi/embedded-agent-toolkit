# ESP32-S3 identity ledger — 2026-09-03

This report correlates hashed flash, serial, source, and historical debug
artifacts. The final ledger update and validation are host-only; the referenced
hardware operations each retained their own authorization and bounded evidence.

## Decided claims

| Claim | State | Decision |
| --- | --- | --- |
| Serial/debug interface association | Observed | COM3 and EspJtag records share `303A:1001 / E0:72:A1:D4:1F:DC`; this associates observed USB interfaces, not silicon identity. |
| Confirmed flash | Observed | One independently confirmed probe-rs execution programmed and verified bootloader, partition table, and application segments derived from ELF SHA-256 `26acd68ba...902421`. |
| Current exact runtime build | Observed | During `2026-09-03T08:38:14.398Z..08:38:23.243Z`, the freshly USB-gated COM3 interface emitted nine periodic records carrying the same complete ELF SHA-256. |
| Current serial liveness | Observed | Heartbeats `1370..1378` were continuous and followed the expected green/blue/red cycle; the workflow transmitted zero bytes with DTR/RTS false. |
| Uninterrupted continuity across the earlier window | Rejected | A confirmed flash/reset occurred between the earlier `3765..3773` observation and the post-flash `1370..1378` observation. |
| Current debugger-defined CPU0 state | Unknown | Post-flash evidence observed CPU0 running earlier, but the later serial-only window did not attach or query core state. |
| BLE peripheral identity | Unknown | No BLE peripheral was selected or connected. |

## Runtime identity boundary

The runtime build correlation is now `observed`, not merely compatible or
historical: the confirmed flash evidence, local final ELF, and nine periodic
runtime records all carry
`26acd68ba2d9676be1e8b804b54560b647c0f5055a192ca43e2a30931e690242`.
The receive workflow bound COM3 to the exact USB VID, PID, and serial before
opening it, ran once for eight seconds, emitted no transmit event, and closed
without a residual process.

This remains point-in-time, non-adversarial build correlation. Firmware controls
its own telemetry, so the result does not prove cryptographic authenticity,
Secure Boot state, silicon identity, or uninterrupted behavior outside the
recorded window.

## Evidence

- Flash evidence: `D:\Code\ai\embedded-debugger\target\host-validation\2026-09-03-esp32s3-firmware-identity-flash\flash-execute.evidence.json`, SHA-256 `7114737d2df18b259303fd1e42fa4e013a8073e4e66f5c9abee053a2d79b454e`.
- Runtime JSONL: `D:\Code\embeded\yd-esp32-s3-rust-demo\target\hardware-validation\2026-09-03-runtime-firmware-identity\20260903-163814-397_COM3_verify-yd-esp32-s3-firmware-identity.jsonl`, SHA-256 `970ecde765953040a927746c54270040426c8172a821f9459131b0f73f525291`.
- Local final ELF: 2,226,432 bytes, SHA-256 `26acd68ba2d9676be1e8b804b54560b647c0f5055a192ca43e2a30931e690242`, source commit `c3b7970`.

The complete source list, validity windows, assumptions, security boundary, and
claim objects are in
[the machine-readable ledger](esp32s3-identity-ledger-2026-09-03.json).
Validate it without hardware access using:

`python scripts/validate_identity_ledger.py docs/examples/esp32s3-identity-ledger-2026-09-03.json --json`
