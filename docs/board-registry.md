# Offline board identity resolution

`board-registry` is an optional host-only component. It converts saved native
discovery JSON from `baud`, `blea`, and `embedded-debugger` into hash-bound
observations, then resolves exactly one registered board. It never captures the
source evidence or operates hardware.

Use it when a workflow must correlate two or more interfaces, or when more than
one board could satisfy a single transport selector:

```powershell
board-registry adapt baud evidence\baud-list.json > evidence\serial.observations.json
board-registry adapt embedded-debugger evidence\probes-list.json > evidence\debug.observations.json
board-registry merge evidence\serial.observations.json evidence\debug.observations.json `
  > evidence\combined.observations.json
board-registry resolve registry.json evidence\combined.observations.json `
  --require serial --require debug --json
```

Keep the native component JSON beside the adapted observations. A resolved
board ID proves only that the supplied point-in-time observations uniquely
match the declared registry selectors. It does not prove wiring, target type,
running firmware, physical continuity after discovery, or authorization for a
later hardware operation.

Do not add target names to probe-list observations: enumeration has not attached
to a target. Do not match BLE solely by a friendly name. Treat `no_match` and
`ambiguous` as stopping states; do not select the first device or weaken the
registry during the active hardware operation.

The default Toolkit doctor checks only the three hardware-facing core
components. Check the optional resolver explicitly:

```powershell
python scripts\toolkit_doctor.py --component board-registry --strict --json
```

The authenticated Toolkit catalog pins the `board-registry 0.1.0` Windows
standalone release. Include it during catalog-backed installation with
`--include-optional board-registry`; omission keeps the three-core default.

When a component lock is active, `board-registry` must be present in that lock
for an explicit check; doctor will not fall back to PATH. Create a reviewed v2
lock with `component_lock.py create --board-registry <exact-path>` when stable
resolver identity is required. Existing v1 three-component locks remain valid.
