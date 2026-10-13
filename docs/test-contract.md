# Hardware test contracts

`scripts/test_contract.py` compiles one reviewed project test specification into
a hash-bound, non-authorizing orchestration contract, inspects its bound inputs,
and evaluates previously captured JSON evidence. The current 0.23.0 candidate
also exports fresh evaluation to CI JUnit XML. It does not run baud, BLEA,
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

All commands are host-only. `compile` refuses to overwrite the contract or to
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

`blea.pair` and `blea.unpair` are supported state-changing stages. They bind no
PIN or other secret in the Toolkit contract and cannot authorize themselves.
Execute them through BLEA 0.7.0 or newer with an exact `id:<identifier>`, the
matching native confirmation value, and its explicit pairing guard. Pairing
declares `host_process_start`, `ble_scan`, `ble_connect`, and
`ble_pairing_change`; unpairing omits `ble_connect`. Both are persistent-write
risk and require `max_retries=0`. One user authorization may cover multiple
operations inside an explicitly agreed device and task scope, but every native
identity check and component guard remains mandatory.

## Evidence evaluation

Toolkit `0.19.0` adds `embedded-debugger.rtt-plan` and
`embedded-debugger.rtt-capture`. Read [bounded RTT workflows](rtt.md) before
using them. Both bind the same firmware input and capture requires the earlier
plan. Capture declares the selected RAM read-cursor write and zero retries.
Evaluation checks the unchanged native summary plus its hash-bound raw JSONL;
it starts no component. Boolean stop/disconnect fields are assertions, not
invented cleanup strings. Integrity does not establish project-specific READY
or runtime build identity.

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

## JUnit XML for CI

The local `0.23.0` candidate adds a one-command evaluation and export:

```powershell
python scripts/test_contract.py junit test-contract.json `
  --run test-run.json --output test-results.xml --json
```

This invokes the same evaluator as `evaluate`: it rechecks the source spec,
board selection, firmware/native inputs, contract/run hashes and saved evidence.
It does not trust a previously edited report file, rerun a stage, execute a
component or authorize hardware. Keep the bound files at their declared paths;
moving an evidence bundle to another filesystem requires a new reviewed
contract/run rather than silently rebasing references.

Each contract currency gate, bound input, stage evidence check, assertion and
cleanup requirement becomes a distinct testcase. Names remain stable by board,
category and native ID, so a stage and an assertion with the same ID do not
collide. Evaluated value mismatches use `<failure>`; missing, drifted, invalid
or unevaluable evidence uses `<error>`. These conditions are never reported as
skipped or passed. The suite and root counts equal the emitted testcase nodes.

The command writes XML even for a failed or incomplete evaluation and exits 2;
an all-passed evaluation exits 0. Invalid contract/run structure, an existing
output, invalid output destination or export limit is rejected without producing
a new report. Use a new `.xml` filename and existing parent directory. Do not
ignore the exit code: displaying JUnit results alone does not make a CI job fail.

The JSON result uses `embedded-agent-toolkit.test-junit.v1` and binds the XML
path, byte size and SHA-256, original contract/run hashes, evaluation summary
and the unchanged no-hardware/no-execution/no-authorization fields. Suite
properties retain scope and source hashes. Per-case JSON diagnostics are XML
escaped, including control characters, and capped at 4096 characters with an
explicit truncation marker. Preserve the native JSON evidence for full details.
Reports have at most 263 cases and 4 MiB XML. No target duration or execution
timestamp is invented from offline evaluation.

For a GitLab job that already has valid saved evidence:

```yaml
embedded_evidence:
  script:
    - python scripts/test_contract.py junit test-contract.json --run test-run.json --output test-results.xml --json
  artifacts:
    when: always
    paths:
      - test-results.xml
    reports:
      junit: test-results.xml
```

This uses GitLab's documented JUnit subset and uploads the diagnostic artifact
after a nonzero test result; see [GitLab unit test reports](https://docs.gitlab.com/ci/testing/unit_test_reports/).
It does not configure a runner, publish to GitLab or prove a hardware stage ran.
Other CI hosts need their own JUnit reader/artifact setup; GitHub Actions does
not display these files merely because the CLI created them.

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

Repeated firmware builds still require native flash authorization. See
[bounded flash sessions](bounded-flash-sessions.md) for the executor-owned
flow; the Toolkit test contract does not authorize repeated flashing or
automatically confirm changing firmware digests.

Machine-readable authoring, compiled, run-manifest, and evaluation-report formats
are published in `schemas/test-spec.schema.json`,
`schemas/test-contract.schema.json`, `schemas/test-run.schema.json`, and
`schemas/test-report.schema.json`.
The JUnit export JSON is specified by `schemas/test-junit.schema.json`; that
schema describes the export result, not a universal JUnit XML dialect.
