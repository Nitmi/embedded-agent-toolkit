# GPIO/TIMER0 model fault regressions

Toolkit 0.30.0 routes the published sim-runner
0.6.0, HIL Runner 0.7.0 and Embedded Trace 0.7.0 wheels. Their fixed profile is
`nrf52840-gpio-timer-fault-v1` on Renode 1.17.0. It extends the nominal GPIO/TIMER0
fixture with `none`, `gpio-stuck-low`, `gpio-stuck-high`, `timer-stop` and
`timer-irq-mask`. These are simulated inputs, not physical board tests.

## Select the published component environment

Use the exact released wheels recorded in `simulation-runtime.json`. Verify
their hashes and GitHub attestation using the repository, source ref/digest and
signer workflow/digest in [simulation setup](simulation.md). During requested
host setup, install with `--no-index --no-deps` in an isolated Python 3.11+
environment. Local computed hashes do not require new user approval.

```powershell
python scripts/simulation_runtime.py inspect '<simulation-venv>' --json
```

This checks 66 source/schema/metadata/license files without importing or launching
components. Expect `candidate_mode=false`, `resolution_source=pinned_releases`,
three `distribution_status=published` entries and the exact release refs/commits.
`executables_started`, `release_attestation_verified`, `backend_runtime_verified`
and physical-board claims remain false. Interpreter/stdlib/bytecode authentication
is outside this file check. A static payload check does not itself verify a
signature, import code, run a backend or accept a physical board.

Combined host readiness may explicitly use `toolkit_doctor.py --simulation-environment
'<simulation-venv>' --strict --json`. Simulation-only tasks
use the file inspector and skip hardware doctor, discovery, attach and selection.
Neither route changes station configuration, PATH or the active plugin.

The earlier local build identities remain in `simulation-candidates.json`,
available only through explicit `--candidate` / `--simulation-candidate` flags.
Those records retain local-candidate status and no release URL/ref, even when
wheel bytes match a later release. Use the published default for normal use.

## Plan and run through the native components

Use the selected interpreter and native sim-runner GPIO/TIMER0 BIN fixture, exact
firmware hash, Renode runtime lock/hash and build-bound markers. For example:

```powershell
$python = '<simulation-venv>\Scripts\python.exe'
& $python -I -m sim_runner plan --backend renode `
  --profile nrf52840-gpio-timer-fault-v1 --fault timer-stop `
  --runtime-lock '<runtime-lock.json>' --runtime-sha256 '<runtime-lock-sha256>' `
  --firmware '<firmware.bin>' --firmware-sha256 '<firmware-sha256>' `
  --ready-line '<complete READY line>' --build-line '<complete BUILD line>' `
  --heartbeat-prefix '<sample prefix>' --output '<new-fault-plan.json>'
```

The native profile fixes the virtual budget at 82 ms and minimum at 16 nominal
IRQ samples. `--fault` is required here and rejected for other profiles. Read the
selected sim-runner's `docs/nrf52840-gpio-fault.md` for the exact fixed model
and observer limitations. Use `--fault none` for the control; do not alter the
firmware merely to produce the four different fault inputs.

Follow [native simulation planning and suites](simulation.md) for inspect-plan,
single run or HIL's typed simulation spec. Bind the exact 0.6.0 wheel for HIL.
HIL preflights every case before any backend starts, then runs cases in order
without per-case confirmation. A failed/indeterminate case stops later cases,
including when injection was observed. No expected-failure override, retry,
recovery, arbitrary monitor command or hardware fallback is provided.

When testing the negative paths themselves, use separately declared suites and
record their expected nonzero results. This does not make the failed native or
suite verdict a pass or permit continuation inside that suite.

## Retain native analysis and raw evidence

Keep native reports, plans, firmware, runtime locks, UART, backend stdout/stderr
and HIL journals. HIL provides Trace input for inspected failed reports too;
an interrupted attempt without a report stays partial HIL evidence.

- `fault_request` records the selected fault and requested virtual injection
  boundary (22 ms, or null for `none`). It is not proof the effect occurred.
- `fault_evidence` retains the complete native assertions, including
  `nominal_regression_passed`, `nominal_failure` and `fault.effect_observed` /
  `fault.status`. Timeout assertions remain null; do not invent an observed or
  unobserved effect from a selected enum or a successful process launch.
- `gpio_evidence` retains guest samples separately from paused model snapshots.
  Each snapshot includes OUT/IN, TIMER0 counter and interrupt-enable state.
- `gpio_observation_spans` binds the four complete `SIM_FAULT_OBS_n` stdout
  records to raw bytes, offsets and hashes. The final newline is required.
- `native_errors`, recorded failed outcome, virtual time and false model/physical
  coverage claims remain visible through inspect, SAMPLE-filtered query and Markdown.

An observed injection with a failing nominal test stays native/suite `failed`,
exit 1, and Trace `capture_outcome=failed`. Offline correlate/inspect/query may
exit zero for valid evidence of that failure; gate execution on its native verdict.
Trace does not rerun native assertions. Model observation boundaries at
20/40/60/80 ms, guest capture ticks and the host run window are different time
semantics, not measured electrical timing. Neither successful nor failed
simulation proves a physical failure or root cause.
