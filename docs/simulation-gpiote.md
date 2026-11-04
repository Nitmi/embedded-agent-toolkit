# GPIOTE input-edge and interrupt regressions

Toolkit 0.42.0 routes published sim-runner 0.14.0, HIL Runner 0.19.0 and
Embedded Trace 0.19.0 for `nrf52840-gpiote-v1`. The fixed Renode 1.17 model
observes three input channels, event state and guest interrupt service.
Model input changes do not establish electrical behavior or physical wiring.
For the separate task-output routing profile, read [PPI simulation](simulation-ppi.md);
its coverage does not extend the input/IRQ profile's qualifications.

## Select and plan

Follow [simulation setup](simulation.md) to authenticate the exact wheels.
The default pin checks 111 installed files: sim 42, HIL 37 and Trace 32.
Static inspection reads files without importing components, starting their
interpreter/backend or verifying signatures. Historical candidate mode has no
GPIOTE profile; older or mixed published environments cannot satisfy this pin.

Use sim-runner 0.14.0's `examples/nrf52840-gpiote/build.py` with an explicit
new output directory, or compatible Cortex-M4 raw BIN firmware bound to its
exact SHA-256 and BUILD marker. The fixture is simulation-only firmware.

```powershell
$python = '<simulation-venv>\Scripts\python.exe'
& $python -I -B -m sim_runner plan --backend renode `
  --profile nrf52840-gpiote-v1 --fault none `
  --runtime-lock '<renode-lock.json>' --runtime-sha256 '<lock-sha256>' `
  --firmware '<firmware.bin>' --firmware-sha256 '<firmware-sha256>' `
  --ready-line 'SIM_NRF_GPIOTE_READY v1' `
  --build-line 'SIM_NRF_GPIOTE_BUILD <build-id>' `
  --heartbeat-prefix SIM_NRF_GPIOTE_SAMPLE --output '<new-plan.json>'
```

`--fault` is required, including `none`. Continue with native inspect-plan,
run and inspect-report from the simulation guide. Preserve the independent
`embedded-sim-runner.gpiote-plan.v1` and `embedded-sim-runner.gpiote-report.v1`
schemas; do not relabel GPIO/TIMER0, EGU or RTC evidence as GPIOTE evidence.

For ordered GPIOTE or mixed GPIOTE/EGU/RTC suites, use HIL 0.19.0's
`embedded-hil-runner.simulation-spec.v1` with the exact sim 0.14.0 wheel.
HIL preflights the whole suite, runs each case once and stops on failed or
indeterminate evidence, retaining later cases as not run. Reuse the agreed
development-task scope without per-case confirmation. Keep negative paths in
separate suites; simulation never falls back to a physical board.

## Read input, event and IRQ evidence

GPIOTE is mapped at 0x40006000 to IRQ6, exception vector 22. Channel 0 selects
P0.11 rising, channel 1 P0.12 falling and channel 2 P1.3 toggle. P0.12 starts
high; the other selected pins start low. INTEN is 7; PORT interrupt is disabled.
Nine changes at 2/6/10/14/18/22/26/30/34 virtual ms cover P0.11 high/low,
P0.12 low/high, P1.3 high/low, then P0.11 high, P0.12 low and P1.3 high.
Two nonmatching edges must produce no channel IRQ.

Each change has paused PRE/POST observations separated by a 2 ms guest-service
budget. Eighteen snapshots bind EVENTS_IN0/1/2, INTENSET, CONFIG0/1/2 and both
GPIO IN registers to raw stdout offsets, lengths and SHA-256. The nominal
oracle requires seven sequential ISR samples on channels 0/1/2/2/0/1/2,
matching `pin_level`, event before=1/after=0, mask=7 and vector=22. Guest fields
do not substitute for independent model observations.

CONFIG bit 20 reads the channel's current state in this model, not a constant
copy of OUTINIT. Matching pin changes assign EventPending; the model does not
implement every silicon latch guarantee. Preserve these semantics when
comparing snapshots instead of diagnosing an electrical fault from CONFIG.

| Fault at stimulus index 4 | Independent effect evidence | Nominal outcome |
| --- | --- | --- |
| `none` | Seven ISR samples and expected input/register states | Pass only when protocol, model and cleanup agree |
| `gpiote-irq-mask` | INTENCLR masks channel 2; its event stays pending while channels 0/1 run; four ISR samples | Failed even when masking is observed |
| `gpiote-wrong-polarity` | CONFIG2 changes toggle to falling; two rising events disappear, one falling event remains; five ISR samples | Failed even when polarity change is observed |

A marker records a request; independent guest/model evidence establishes its
effect. Keep effect true/false/null distinct from the native nominal verdict.
Wrong BUILD is rejected before accepting ISR samples, while model observations
may still exist. Timeouts and unevaluated assertions remain unknown. Import
success, an empty query or observed effect cannot turn a failed source into a
pass or permit HIL to continue after a failed case.

Trace preserves CONFIG/input/event, pin-level ISR and request-marker raw spans
in full, filtered, empty and Markdown views. Up to four exact asynchronous
paused/resumed INFO lines before each value remain inside its bounded hashed
span. Unrelated messages, excessive lines and rehashed contradictions fail.
Saved timeline views do not reopen original firmware/runtime paths or rerun
the native policy; retain native files beside derived evidence.

## Model limits and cost

The audited Renode Infrastructure revision is
`066a7f13c052215632d469c995c89aea37c573b1`; its input GPIOTE and GPIO semantics
are documented in sim-runner's `docs/nrf52840-gpiote.md`. TASKS_OUT/SET/CLR,
PORT/SENSE/LATCH/DETECTMODE, PPI, debounce, pulls/drive, all-channel/pin coverage,
electrical behavior, IRQ latency/preemption, sleep/power and physical timing
remain unqualified. Keep `model_coverage_complete`, `physical_timing_verified`
and `ppi_routing_verified` false. Virtual schedule, ISR order and host windows
remain separate clocks without verified synchronization.

Native bounds remain 30 seconds, 1 MiB/output, one backend process and 1024 MiB
Windows Job memory, with zero automatic retries and complete process/capture
cleanup. Keep per-run absolute Renode history paths isolated in parallel runs.
HIL retains its eight-case bound and child deadlines. Static inspection checks
at most 111 selected files, 1 MiB/file, 4 MiB/component and 256 entries/component.
Trace validates full evidence before filtering; small pages do not reduce that
cost. Record host wall time and Python allocations separately from startup,
cold IO, backend RSS and modeled time; these checks establish no physical SLA.
