# Optional HIL Runner workflow

Use HIL Runner for a continuous build/flash/observe loop or cooperating clients
sharing one board. Direct native commands remain suitable for a single operation.
The runner owns debug/serial leases across one bounded native flash scope and
per-build runtime acceptance; Toolkit does not implement another executor.

## Host setup and inspection

HIL Runner 0.2.0 is a Python 3.11+ wheel with no runtime dependencies. Install the
[verified official release](https://github.com/Nitmi/hil-runner/blob/v0.2.0/docs/installation.md)
in its own environment. Toolkit does not install it through the native executable
catalog or place a Python launcher in the component lock. That lock continues
to describe baud/BLEA/debugger and the existing optional native tools.

`hil-runtime.json` pins the official wheel, source revision and 19 installed
source/schema/metadata files. Verify a Windows environment without importing HIL
or starting its Python interpreter:

```powershell
python scripts/hil_runtime.py inspect 'C:\Tools\hil-runner\venv' --json
python scripts/toolkit_doctor.py --component-lock '<reviewed-native-lock.json>' `
  --hil-environment 'C:\Tools\hil-runner\venv' --strict --json
```

The standalone inspection reports `status=payload_verified`, the package version,
verified file count and interpreter path/hash. It checks declared Python 3.11+,
but does not execute or authenticate the interpreter, stdlib or generated Python
cache. `interpreter_version_verified=false` stays explicit. It checks the current
installed payload, not board identity or authorization.

The optional doctor check also requires Windows and the qualified debugger
0.2.5 executable from the selected lock. An old selected debugger fails this
check; doctor does not silently choose another executable or replace the lock.
Default doctor does not inspect HIL. Existing three/five-component locks remain
valid. The native catalog in Toolkit 0.24.0 pins debugger 0.2.5; review a new lock
with `component_lock.py compare` before selecting it.

Using the inspected interpreter, check the CLI once before the managed task:

```powershell
$hilPython = 'C:\Tools\hil-runner\venv\Scripts\python.exe'
& $hilPython -I -m hil_runner --version
```

Expect `hil-runner 0.2.0`. This version command is host-only; it is distinct from
the static inspector. Keep the environment under normal host trust. Inspection
is a point-in-time check, not an execution sandbox or environment freeze.

## Prepare one bounded development run

Use the project's exact saved board-registry debug + serial selection, native
component lock, bounded flash scope and runtime contract. HIL 0.2.0 supports
self-contained BIN/HEX for Windows managed execution. ELF/ESP-IDF image sets,
BLE-driven acceptance and arbitrary commands are outside this managed mode.

Use the [native project contract guide](../skills/hardware-test/references/runtime-contract.md)
for serial identity, DTR/RTS and expected READY/BUILD/HEARTBEAT lines. Firmware
must emit a different complete BUILD line for each different image. Debugger
0.2.5 accepts BUILD and heartbeat evidence only after the last complete READY;
forbidden lines still cover the entire capture. Heartbeat counts do not prove
monotonic sequence numbers.

Prepare the spec using HIL's
[managed schema and commands](https://github.com/Nitmi/hil-runner/blob/v0.2.0/docs/managed.md).
Run `managed plan` with the inspected interpreter:

```powershell
& $hilPython -I -m hil_runner managed plan spec.json --output managed-plan.json --json
```

This reads/hashes saved inputs without starting native executables. The HIL spec
contains the native scope digest; it is not a Toolkit test contract and does not
grant authorization. Keep confirmation digests out of Toolkit test contracts and
run manifests.

The user's task agreement must cover probe/target, build directory, write/erase
windows, count/duration, serial controls and one **additional runtime reset-capture
per build**. Reuse existing authorization for that scope; do not ask the user to
confirm each firmware hash or copy each new digest. Ask only for an uncovered or
materially changed scope. Native security/UICR/recovery gates remain in force.

## Own the complete process lifetime

Start one long-lived managed owner using the native once-approved digest:

```powershell
& $hilPython -I -m hil_runner managed serve managed-plan.json `
  --plan-sha256 '<managed-plan-file-sha256>' --confirm '<native-scope-digest>' `
  --allow-runtime-reset --output-dir '<new-directory-inside-firmware-root>'
```

Keep a parent connected to stdin/stdout. Wait for `managed.ready`, submit a
JSONL `build` request with absolute firmware/runtime-contract paths and hashes,
then wait for its successful `managed.build` result before submitting the next
build. Only firmware hash and BUILD line may vary from the runtime template.
Do not put shell commands or argv into requests. The HIL documentation defines
the complete protocol; do not recreate an executor inside Toolkit.

Count exhaustion, expiry, close or EOF ends ownership after native process trees
stop. Drift, a failed/indeterminate flash or runtime result, timeout or incomplete
cleanup stops the run and prevents the next build. Preserve evidence; do not
retry hardware, recover, erase extra regions, delete lock files or remove native
`.active` markers. A fresh owner needs a fresh native scope; reuse task consent
only when it still covers that new scope and its limits.

## Evidence and reporting

Preserve the managed result, native transcript, private firmware/contract
snapshots, each build's native flash/runtime evidence and raw receive bytes.
Managed host-process cleanup does not establish target state after disconnect.
Top-level `authorization_granted=false` and `target_cleanup_verified=false` do
not erase the separately recorded native per-build results.

Use Toolkit evaluation/JUnit only with a compatible reviewed test contract and
the exact native evidence files that its operations expect. A managed summary
is not a substitute for an `embedded-debugger.flash-execute` or
`embedded-debugger.runtime-accept` payload. Do not silently adapt a bounded-session
result to a per-flash plan/execute schema. A contract evaluates saved evidence;
it neither starts the HIL owner nor renews its native grant.

Replay plus a fake serial component can validate host integration. Replay alone
does not prevent a real serial component from opening hardware; both component
selection and native backend must be explicit for a host-only test.
