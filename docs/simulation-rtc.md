# RTC0 compare regressions

Toolkit 0.41.0 routes published sim-runner 0.13.0, HIL Runner 0.18.0 and
Embedded Trace 0.18.0 for `nrf52840-rtc-v1`. It covers a fixed CC0 interrupt,
event-clear protocol and two bounded model faults. It does not qualify LFCLK,
physical timing, sleep, power or wakeup.

## Select and plan

Follow [simulation setup](simulation.md) to authenticate the exact wheels.
The default pin checks 108 installed files: sim 40, HIL 37 and Trace 31.
Static inspection never imports the selected components, starts their
interpreter/backend, or verifies a signature. Historical candidate mode has no
RTC profile; coherent older environments cannot satisfy this published pin.

Use the released sim-runner's `examples/nrf52840-rtc` builder with the fixed
Renode 1.17.0 runtime, or a compatible already-built Cortex-M4 raw BIN with
its exact SHA-256 and BUILD marker. This fixture is simulation-only firmware.

```powershell
$python = '<simulation-venv>\Scripts\python.exe'
& $python -I -B -m sim_runner plan --backend renode `
  --profile nrf52840-rtc-v1 --fault none `
  --runtime-lock '<renode-lock.json>' --runtime-sha256 '<lock-sha256>' `
  --firmware '<firmware.bin>' --firmware-sha256 '<firmware-sha256>' `
  --ready-line 'SIM_NRF_RTC_READY v1' `
  --build-line 'SIM_NRF_RTC_BUILD <build-id>' `
  --heartbeat-prefix SIM_NRF_RTC_SAMPLE --output '<new-plan.json>'
```

`--fault` is required, including `none`. Continue with native inspect-plan,
run and inspect-report from the simulation guide. Keep the independent
`embedded-sim-runner.rtc-plan.v1` and `embedded-sim-runner.rtc-report.v1`
schemas; do not relabel a timer, watchdog or sensor report.

For an ordered RTC or mixed RTC/SPI/watchdog/I2C/GPIO suite, use HIL 0.18's
`embedded-hil-runner.simulation-spec.v1` with the exact sim 0.13.0 wheel.
HIL preflights all plans, runs each case once and stops on failed or
indeterminate evidence, retaining later cases as not run. Reuse the agreed
development task's authorization without per-run confirmation; declare negative
paths as separate suites and never fall back to physical hardware.

## Read counter, event and IRQ evidence

The fixed model maps RTC0 at 0x4000B000 to IRQ11, uses PRESCALER=31 (1024 Hz)
and advances CC0 in 16-tick intervals. The nominal run requires ten sequential
samples over 162 virtual ms: event 1 before clearing and 0 afterwards, next
compare 32..176, the fixed prescaler and exception vector 27. Independent paused
snapshots at 40/80/120/160 ms bind COUNTER, PRESCALER, CC0, EVENTS_COMPARE0
and INTENSET with raw stdout offsets, lengths and hashes.

| Fault at 42 virtual ms | Independent effect evidence | Nominal outcome |
| --- | --- | --- |
| `none` | Ten IRQ samples and four advancing snapshots | Pass only when protocol, model and cleanup agree |
| `rtc-stop` | Two samples, frozen counter near 43, CC0=48, no pending event, interrupt still enabled | Failed even when the stop effect is observed |
| `rtc-irq-mask` | Two samples, advancing counter, CC0=48, pending event and zero interrupt mask | Failed even when masking is observed |

A marker records a requested fault. Only independent model/guest evidence can
establish its effect. Wrong BUILD is rejected before sample parsing; timeout
may leave fields null. Retain native errors, effect true/false/null and the
nominal regression verdict separately. Successful import or an empty query
never changes a source failure or unknown into a pass.

Preserve native plan/report, firmware/runtime identities, raw UART,
stdout/stderr and the HIL journal. Trace binds ordered counter/event/compare/
prescaler/vector guest spans, model spans and a separate fault marker. Full,
sampled and empty views preserve the source outcome and model qualifications.
Saved views read the self-contained timeline without reopening the original
runtime/firmware or rerunning native policy.

## Model limits and cost

The audited Renode 1.17 Infrastructure revision is
[`066a7f13c052215632d469c995c89aea37c573b1`](https://github.com/renode/renode-infrastructure/tree/066a7f13c052215632d469c995c89aea37c573b1).
The profile uses the model's fixed divider; it does not exercise CLOCK/LFCLK
startup, oscillator drift, TICK/overflow, TRIGOVRFLW, 24-bit wrap or PPI.
Guest `wfi` proves no physical sleep/wakeup or power behavior. The two-tick
tolerance is a fixed emulator/guest allowance, not a measured oscillator error.
Requested virtual boundaries, guest counters, paused snapshots and host run
windows remain separate domains.

Host bounds remain 30 seconds, 1 MiB per output, one backend process and
1024 MiB Windows Job memory, with zero retries. HIL retains eight cases and
bounded child deadlines. Static inspection reads at most 108 payloads,
1 MiB/file, 4 MiB/component and 256 entries/component. Trace validates the full
timeline before filtering. Record wall time and Python allocation separately
from startup, cold IO, backend RSS and physical timing; no SLA follows.
