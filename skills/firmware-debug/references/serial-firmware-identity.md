# Serial firmware identity

Use this workflow when firmware can expose an exact final-build identifier over
periodic serial telemetry. It is the least-invasive way to correlate a running
device with a local artifact when serial is already available and a debugger
attach or reset would disturb the target.

## Required identity bindings

Bind all three layers in one observation:

1. Hash the final linked artifact that image tooling consumes. Record its path,
   SHA-256, target, profile, and build provenance.
2. Make firmware report that exact value from runtime-patched or post-link
   metadata. Do not embed a precomputed hash string into the bytes being hashed.
3. Bind the serial port to freshly enumerated USB VID, PID, and serial number
   before opening it. A port name alone is not a stable physical identity.

For ESP-IDF-compatible images, the app descriptor reserves a 32-byte ELF
SHA-256 field. Image tooling can hash the final ELF and patch the flash image
afterward. Firmware should use volatile reads from the mapped descriptor so the
compiler does not replace the field with its zero-valued ELF initializer.

## Receive-only Baud workflow

Use Baud's physical identity guard and a monitor-only step:

```yaml
version: 1
name: verify-running-firmware
serial:
  port: COM3
  baudrate: 115200
  line_ending: none
  dtr: false
  rts: false
  settle_ms: 300
  drain_ms: 500
  expected_vid: "303A"
  expected_pid: "1001"
  expected_serial_number: "E0:72:A1:D4:1F:DC"
steps:
  - id: observe_exact_firmware
    monitor: 8
    expect:
      response_required: true
      contains:
        - "firmware_sha256=<exact lowercase ELF SHA-256>"
      not_contains:
        - "firmware_identity=unavailable"
      regex:
        - "heartbeat=[0-9]+, .*firmware_sha256=<exact lowercase ELF SHA-256>"
```

Keep the identifier in periodic records rather than only a startup banner; a
non-resetting monitor can begin at any point. The workflow must contain no
`send` step. Preserve structured output and raw receive evidence, close the
port after the bounded window, and do not retry automatically after an identity
mismatch or empty observation.

## Claim boundary

A successful workflow establishes that the freshly enumerated physical serial
interface emitted the expected artifact identifier during the recorded window.
It can upgrade current firmware identity from unknown to observed in an identity
ledger. It does not prove silicon identity, uninterrupted execution before or
after the window, a healthy CPU state, or cryptographic authenticity. Because
the firmware controls its own telemetry, use signed attestation or protected
boot measurements when an adversarial image is in scope.
