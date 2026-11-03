# EGU0 task, event and interrupt regressions

Toolkit 0.40.0 routes published sim-runner 0.12.0, HIL Runner 0.17.0 and
Embedded Trace 0.17.0 for `nrf52840-egu-v1`. The fixed model generates tasks on
channels 0/3/15 and observes guest IRQ service. Channel 1 is a disabled sentinel;
PPI and physical timing remain unqualified.

## Select and plan

Follow [simulation setup](simulation.md) to authenticate the exact wheels.
The default pin checks 105 installed files: sim 38, HIL 37 and Trace 30.
Static inspection reads files without importing components, starting their
interpreter/backend or verifying signatures. Historical candidate mode has no
EGU profile; older or mixed published environments cannot satisfy this pin.

Use sim-runner 0.12.0's `examples/nrf52840-egu` builder with the fixed
Renode 1.17.0 runtime, or an already-built compatible Cortex-M4 raw BIN bound
to its exact SHA-256 and BUILD marker. This is simulation-only fixture firmware.

```powershell
$python = '<simulation-venv>\Scripts\python.exe'
& $python -I -B -m sim_runner plan --backend renode `
  --profile nrf52840-egu-v1 --fault none `
  --runtime-lock '<renode-lock.json>' --runtime-sha256 '<lock-sha256>' `
  --firmware '<firmware.bin>' --firmware-sha256 '<firmware-sha256>' `
  --ready-line 'SIM_NRF_EGU_READY v1' `
  --build-line 'SIM_NRF_EGU_BUILD <build-id>' `
  --heartbeat-prefix SIM_NRF_EGU_SAMPLE --output '<new-plan.json>'
```

`--fault` is required, including `none`. Continue with native inspect-plan,
run and inspect-report from the simulation guide. Preserve the independent
`embedded-sim-runner.egu-plan.v1` and `embedded-sim-runner.egu-report.v1`
schemas; do not relabel another peripheral's evidence.

For ordered EGU or mixed EGU/RTC/watchdog suites, use HIL 0.17.0's
`embedded-hil-runner.simulation-spec.v1` with the exact sim 0.12.0 wheel.
HIL preflights every plan before execution, runs each case once and stops at
failed or indeterminate evidence, retaining later cases as not run. Reuse the
agreed development-task scope without per-case approval. Keep negative paths
in separate suites and do not fall back to physical hardware.

## Read task, event and IRQ evidence

The fixed model maps EGU0 at 0x40014000 to IRQ20, exception vector 36.
Over 40 virtual ms, the monitor writes nine tasks: channels 0/3/15 repeat three
times at 2/6/10/14/18/22/26/30/34 ms. Every task has paused PRE and POST model
snapshots separated by a 2 ms guest-service budget. Eighteen snapshots bind
event latches 0/1/3/15 and INTEN to raw stdout offsets, lengths and SHA-256.

The nominal oracle requires nine sequential ISR samples, correct channel order,
event before=1/after=0, mask=0x8009, vector 36 and matching model observations.
The monitor is the task producer; these results do not test a guest producer.

| Fault at the fifth stimulus, index 4 | Independent effect evidence | Nominal outcome |
| --- | --- | --- |
| `none` | Nine ISR samples and expected PRE/POST states; sentinel stays clear | Pass only when protocol, model and cleanup agree |
| `egu-irq-mask` | Channel 3 stays pending with its enable cleared; 0/15 continue, seven ISR samples | Failed even when masking is observed |
| `egu-channel-misroute` | One channel-3 task targets disabled sentinel 1; sentinel stays pending, eight ISR samples | Failed even when misrouting is observed |

A fault marker records a request. Independent guest/model observations establish
the effect; keep effect true/false/null separate from the native nominal verdict.
Wrong BUILD is rejected before sample parsing, while model observations may
still exist. Timeout and unevaluated assertions remain unknown. Successful
import, an empty query or an observed fault never turns a source failure into
a pass or permits HIL to continue after a failed case.

Trace retains native EGU context, ordered model/ISR raw spans and a separate
request marker in full, sampled, empty and Markdown views. Renode's asynchronous
stdout can insert up to four exact paused/resumed INFO lines before each value;
they stay inside the original hashed span. Other interleaving, excess INFO,
missing values or contradictory rehashed evidence remain errors. Saved views
read the self-contained timeline without reopening original firmware/runtime
paths or rerunning the native policy.

## Model limits and cost

The audited [Renode Infrastructure source](https://github.com/renode/renode-infrastructure/blob/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Peripherals/Peripherals/Miscellaneous/NRF52840_EGU.cs)
is pinned to the Renode 1.17 model semantics. Coverage excludes PPI, external
routing, a guest task producer, all-channel completeness, interrupt priority,
preemption, IRQ latency, sleep/power and physical timing. Keep
`model_coverage_complete`, `physical_timing_verified` and `ppi_routing_verified`
false. Virtual schedule labels, guest ISR order and host run windows are
distinct clock domains, not verified synchronization.

Sim 0.12 isolates each Renode history file using its absolute per-run INI path;
parallel runs must not share AntShell history. Native host bounds remain
30 seconds, 1 MiB/output, one backend process and 1024 MiB Windows Job memory,
with zero retries. HIL retains eight cases and bounded child deadlines.
Static inspection reads at most 105 payloads, 1 MiB/file, 4 MiB/component and
256 entries/component. Trace validates the full timeline before filtering;
a small page does not reduce validation cost. Record wall time and Python
allocation separately from backend RSS, cold IO and startup; no SLA follows.
