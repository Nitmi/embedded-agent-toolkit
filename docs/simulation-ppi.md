# TIMER0, PPI and GPIOTE functional routing

Toolkit 0.42.0 routes published sim-runner 0.14.0, HIL Runner 0.19.0 and
Embedded Trace 0.19.0 for `nrf52840-ppi-v1`. The fixed Renode 1.17 model
checks TIMER0 compare0 routing through PPI channel 0 and its fork to GPIOTE
task outputs. It does not establish event alignment or physical timing.

## Select and plan

Follow [simulation setup](simulation.md) to authenticate the exact wheels.
The default pin checks 111 installed files: sim 42, HIL 37 and Trace 32.
Static inspection reads files without importing components, launching their
interpreter/backend or verifying signatures. Historical candidates and older
published environments cannot satisfy this selection.

Build simulation-only firmware with sim-runner 0.14.0's
`examples/nrf52840-ppi/build.py` into a new directory, or select compatible
Cortex-M4 raw BIN firmware with an exact SHA-256 and BUILD marker.

```powershell
$python = '<simulation-venv>\Scripts\python.exe'
& $python -I -B -m sim_runner plan --backend renode `
  --profile nrf52840-ppi-v1 --fault none `
  --runtime-lock '<renode-lock.json>' --runtime-sha256 '<lock-sha256>' `
  --firmware '<firmware.bin>' --firmware-sha256 '<firmware-sha256>' `
  --ready-line 'SIM_NRF_PPI_READY v1' `
  --build-line 'SIM_NRF_PPI_BUILD <build-id>' `
  --heartbeat-prefix SIM_NRF_PPI_SAMPLE --output '<new-plan.json>'
```

`--fault` is required, including `none`. Continue with native inspect-plan,
run and inspect-report from the simulation guide. Keep the independent
`embedded-sim-runner.ppi-plan.v1` and `embedded-sim-runner.ppi-report.v1`
schemas; GPIO, GPIOTE input and EGU evidence are separate profiles.

For ordered PPI or mixed PPI/GPIOTE/EGU suites, use HIL 0.19.0's
`embedded-hil-runner.simulation-spec.v1` with the exact sim 0.14.0 wheel.
HIL preflights the whole suite, runs each case once and stops on failed or
indeterminate evidence, retaining later cases as not run. Keep negative paths
in separate suites. Reuse the agreed development-task scope without per-case
confirmation; simulation never falls back to a physical board.

## Read routing and output evidence

| Producer | Route | Consumer |
| --- | --- | --- |
| TIMER0.EVENTS_COMPARE0, 0x40008140 | CH0 EEP / TEP | GPIOTE.TASKS_OUT0, 0x40006000: P0.11 toggle |
| Same event | CH0 FORK.TEP | GPIOTE.TASKS_OUT1, 0x40006004: P1.3 toggle |
| Fault-only fork destination | 0x40006008 | GPIOTE.TASKS_OUT2: P0.13 sentinel toggle |

The guest configures task mode, PRESCALER=4, CC0=1000 and the route; IRQs remain
disabled. Eight STOP/CLEAR/START intervals begin at 2/6/10/14/18/22/26/30 virtual
ms, each with a 2 ms service budget, over 40 virtual ms. A 100 microsecond global
quantum bounds the schedule; it does not measure task latency or emulate missing
timer SHORTS with guest writes.

Sixteen paused PRE/POST snapshots bind 14 fields to raw stdout offsets, lengths
and SHA-256: timer event/prescaler/CC0, channel mask/EEP/TEP/FORK.TEP, three
GPIOTE configurations and both GPIO OUT/IN registers. PRE requires the cleared
event; POST requires the compare event and expected routed states. Retain bounded
asynchronous lifecycle messages inside each hashed span. Missing, reordered,
partial or contradictory observations fail.

UART requires exact READY/BUILD lines and eight nominal samples with ordered
sequence, main/fork/sentinel fields (`A`, `B`, `S`), each eight uppercase hex
digits. Guest pin polling after a settling loop does not replace independent
model observations. Wrong BUILD can retain model snapshots while guest samples
stay empty and the fault effect is unknown; timeouts do not become false or pass.

| Fault at trigger index 4 | Independent effect | Nominal outcome |
| --- | --- | --- |
| `none` | Both routed pins toggle; sentinel stays clear | Pass only when protocol, model and cleanup agree |
| `ppi-channel-disable` | CHENCLR=1; compare events continue, routed outputs stop, four samples remain | Failed even when disabling is observed |
| `ppi-fork-misroute` | FORK.TEP targets OUT2; main toggles, expected fork stops, sentinel toggles | Failed even when misrouting is observed |

A marker records a request; model and identity-checked guest evidence establish
the effect. Keep true/false/null effects separate from the nominal verdict.
Import success, an observed effect or an empty filtered page cannot turn native
failure into pass or permit a later HIL case to run.

Trace preserves route/register, output/sample and fault-request spans in full,
filtered, empty and Markdown views. It checks saved representation and bindings,
not a second firmware oracle. Views do not reopen original firmware/runtime paths
or repeat native runs; keep native files beside derived evidence.

## Model limits and cost

The audited Renode Infrastructure revision is
`066a7f13c052215632d469c995c89aea37c573b1`; details are in sim-runner's
`docs/nrf52840-ppi.md`. Both PPI tasks use `ExecuteInNearestSyncedState`.
Functional routing does not prove event alignment, precise timing, broad PPI
qualification or complete model coverage; the corresponding native flags remain
false. Virtual schedule, guest order and host capture windows are separate clocks.

The first PPI write lazily subscribes preprogrammed routes to TIMER0, RTC0 and
RADIO events. Inactive RTC0/RADIO mappings support those subscriptions; fixed
channels remain disabled, RTC is not started and RADIO has no medium. They add
no radio or RTC coverage. Groups, other channels, capture/counter modes,
SHORTS/BITMODE, GPIOTE SET/CLR/PORT/SENSE and electrical behavior remain unqualified.

Native bounds remain 30 seconds, 1 MiB per captured output, one backend process
and 1024 MiB Windows Job memory, with zero automatic retries and complete process
and capture cleanup. Keep absolute Renode history paths isolated in parallel runs.
HIL retains its eight-case bound and child deadlines. Static inspection checks
111 selected files, at most 1 MiB/file, 4 MiB/component and 256 entries/component.
Trace validates complete evidence before filtering; a small page does not lower
that cost. Measure host wall time and Python allocations separately from startup,
cold IO, backend RSS and virtual time; these checks establish no physical SLA.
