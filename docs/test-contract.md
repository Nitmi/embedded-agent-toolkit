# Hardware test contracts

`scripts/test_contract.py` compiles one reviewed project test specification into
a hash-bound, non-authorizing orchestration contract, inspects its bound inputs,
and evaluates previously captured JSON evidence. It does not run baud, BLEA,
embedded-debugger, a shell, or any hardware operation.

Use it after `board-registry select` has emitted a unique
`embedded-board-registry.selection.v1` document. The compiler validates that
selection, maps each transport binding to its owning component, verifies every
declared firmware or native workflow SHA-256, and makes stage dependencies,
effects, deadlines, retries, structured assertions, and cleanup explicit.

```powershell
python scripts\test_contract.py compile `
  docs\examples\esp32s3-test-spec.json `
  --output test-contract.json --json
python scripts\test_contract.py inspect test-contract.json --json
python scripts\test_contract.py evaluate test-contract.json `
  --run test-run.json `
  --output test-report.json --json
```

All three commands are host-only. `compile` refuses to overwrite the contract or to
accept a pre-existing evidence output. `inspect` rehashes the source spec, board
selection, firmware, and native component inputs so post-compilation drift is a
stopping state. `evaluate` repeats that inspection, verifies each evidence path
and SHA-256, applies the contract's assertions and cleanup requirements, and
writes a report without overwriting an existing file.

## Native ownership

Resources may be firmware artifacts or existing component-owned contracts:

- `baud-workflow`
- `blea-workflow`
- `debugger-runtime-contract`
- `firmware`

The Toolkit does not parse those native formats as if it owned them. Validate
each with its component before execution. A stage names one supported semantic
operation, never a command string, shell fragment, argv list, confirmation
digest, or executable path. The contract cannot execute itself.

Discovery can be the first contract gate. These operations preserve each
component's native JSON shape and permit only the listed observation effects:

| Semantic operation | Native command | Required transport | Allowed effects |
| --- | --- | --- | --- |
| `baud.list` | `baud list --json` | `serial` | `host_process_start`, `hardware_discovery` |
| `blea.doctor` | `ble doctor --scan-timeout <seconds> --json` | `ble` | `host_process_start`, `ble_scan` |
| `embedded-debugger.probes-list` | `embedded-debugger --backend probe-rs probes list --json` | `debug` | `host_process_start`, `hardware_discovery` |

BLEA doctor performs a short discovery scan to prove adapter availability; it
is not host-only. None of these operations opens a serial port, connects to a
BLE peripheral, attaches to a target, or changes target state. Assertions should
bind the newly observed exact identity to the selected board. See
`docs/examples/esp32s3-discovery-test-spec.json` for a serial and probe baseline.

Flash execution must depend on an earlier flash-plan stage using the same
firmware. Runtime acceptance must depend on an earlier runtime-inspect stage
using the same runtime contract. Missing transport bindings, missing baseline
effects, undeclared extra effects, stale inputs, later-stage dependencies, and
non-zero retries for state-changing stages all fail closed.

## Evidence evaluation

Execute each stage separately through its owning component and preserve that
component's native JSON output at the contract's exact `evidence_output` path.
The Toolkit does not translate, normalize, or regenerate this evidence. Create a
small run manifest only after those bounded component operations have finished:

```json
{
  "schema_version": "embedded-agent-toolkit.test-run.v1",
  "contract_sha256": "<sha256-of-test-contract.json>",
  "stage_evidence": [
    {
      "stage": "flash-plan",
      "path": "evidence/flash-plan.json",
      "sha256": "<sha256-of-native-json>"
    }
  ],
  "cleanup_evidence": [
    {
      "resource": "target",
      "path": "evidence/runtime.json",
      "sha256": "<sha256-of-native-json>",
      "json_pointer": "/cleanup/target"
    }
  ],
  "authorization": {
    "granted": false,
    "allowed_operations": [],
    "manifest_is_authorization": false
  }
}
```

`stage_evidence` must contain exactly one entry per contract stage, in order,
and every resolved path must equal that stage's compiled `evidence_output`.
`cleanup_evidence` must contain exactly one entry per declared cleanup resource,
also in order. Multiple entries may bind the same evidence file when they use
the same digest.

Assertions use RFC 6901 JSON Pointers. A missing path never passes, including
for `not_equals`. `equals` and `not_equals` preserve JSON types, so `true` is not
equal to `1`. `at_least` and `at_most` require finite numbers. `contains` means
substring containment for strings, exact JSON-value membership for arrays, and
key presence for objects. Cleanup pointers must resolve to a string matching the
contract's required state.

The generated `embedded-agent-toolkit.test-report.v1` report records contract
input currency, evidence hashes and sizes, every assertion, every cleanup result,
and summary counts. A value mismatch produces a complete failed report. Missing,
invalid, oversized, or drifted evidence produces an incomplete failed report.
Malformed contracts or run manifests are rejected before an output is created.

## Authorization boundary

Every compiled contract contains:

```json
{
  "authorization": {
    "allowed_operations": [],
    "contract_is_authorization": false,
    "granted": false,
    "native_component_gates_preserved": true
  },
  "execution_supported": false,
  "hardware_access": false,
  "executables_started": false
}
```

The contract is preparation evidence, not permission. At execution time use
the exact hash-bound component from the active lock, revalidate current hardware
identity, generate the component's native plan, and honor its confirmation or
authorization boundary. Do not store a flash confirmation digest in the test
contract.

Machine-readable authoring, compiled, run-manifest, and evaluation-report formats
are published in `schemas/test-spec.schema.json`,
`schemas/test-contract.schema.json`, `schemas/test-run.schema.json`, and
`schemas/test-report.schema.json`.
