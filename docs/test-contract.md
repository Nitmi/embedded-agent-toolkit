# Hardware test contracts

`scripts/test_contract.py` compiles one reviewed project test specification into
a hash-bound, non-authorizing orchestration contract. It does not run baud,
BLEA, embedded-debugger, a shell, or any hardware operation.

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
```

Both commands are host-only. `compile` refuses to overwrite the contract or to
accept a pre-existing evidence output. `inspect` rehashes the source spec, board
selection, firmware, and native component inputs so post-compilation drift is a
stopping state.

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

Flash execution must depend on an earlier flash-plan stage using the same
firmware. Runtime acceptance must depend on an earlier runtime-inspect stage
using the same runtime contract. Missing transport bindings, missing baseline
effects, undeclared extra effects, stale inputs, later-stage dependencies, and
non-zero retries for state-changing stages all fail closed.

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

Machine-readable authoring and compiled formats are published in
`schemas/test-spec.schema.json` and `schemas/test-contract.schema.json`.
