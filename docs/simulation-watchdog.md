# Watchdog model regressions

Toolkit 0.38.0 routes published sim-runner 0.10.0, HIL Runner 0.15.0 and
Embedded Trace 0.15.0 for `nrf52840-watchdog-v1`. Use it for dual-channel reload,
stopped feeding, disabled-model and guest reboot evidence. Model results do not
qualify a physical watchdog, board reset, low-power behavior or protection.

## Select and plan

Follow [simulation setup](simulation.md) to authenticate the exact release
wheels. The default pin checks 99 installed files: sim 34, HIL 37, Trace 28.
Historical candidate mode has no watchdog profile. Static inspection starts
neither the selected interpreter nor a backend and does not verify a signature.

Use the released sim-runner's `examples/nrf52840-watchdog` fixture builder with
the fixed Renode 1.17.0 runtime, or a compatible already-built Cortex-M4 BIN
with its exact hash and BUILD marker. The fixture is simulation-only firmware.

```powershell
$python = '<simulation-venv>\Scripts\python.exe'
& $python -I -B -m sim_runner plan --backend renode `
  --profile nrf52840-watchdog-v1 --fault none `
  --runtime-lock '<renode-lock.json>' --runtime-sha256 '<lock-sha256>' `
  --firmware '<firmware.bin>' --firmware-sha256 '<firmware-sha256>' `
  --ready-line 'SIM_NRF_WDT_READY v1' `
  --build-line 'SIM_NRF_WDT_BUILD <build-id>' `
  --heartbeat-prefix SIM_NRF_WDT_SAMPLE --output '<new-plan.json>'
```

`--fault` is required even for `none`. Continue with native inspect-plan, run
and inspect-report from the simulation guide. Preserve the independent
`embedded-sim-runner.watchdog-plan.v1` and
`embedded-sim-runner.watchdog-report.v1` schemas;
do not relabel a GPIO or sensor report. Native sim owns the verdict.

For an ordered watchdog or mixed watchdog/SPI/I2C/GPIO suite, use HIL 0.15's
`embedded-hil-runner.simulation-spec.v1` with the exact 0.10.0 sim wheel.
HIL preflights every plan before a backend starts and stops after a failed or
indeterminate case. Reuse the agreed development task's authorization without
per-run hash confirmation. Keep negative paths in separately declared suites;
an observed fault does not permit later cases after failure or a hardware fallback.

## Interpret the evidence

The fixed model uses CRV=1023, RREN=3 and a 32768 Hz reload interval of 31.25
virtual ms. Every 5 ms TIMER0 IRQ writes magic `6E524635` to RR0 then RR1;
REQSTATUS changes from 2 to 3 and RUNSTATUS stays 1. Normal acceptance requires
one guest boot, the selected BUILD and 16 valid samples in 82 virtual ms.
Paused snapshots at 20/40/60/80 ms record WDT state/countdown and timer capture.

| Required fault | Fixed action at 22 virtual ms | Evidence and native nominal outcome |
| --- | --- | --- |
| `none` | Continue feeding both channels | Pass only when guest protocol, model state and complete cleanup agree |
| `feed-timer-stop` | Stop TIMER0 | Failed; frozen timer, one raw WDT reset/callback and valid guest reboot with 4 then 6 samples establish the effect |
| `watchdog-stop` | Set model `Enabled=false` | Failed; no reset, 16 samples and disabled RUNSTATUS/countdown evidence establish the effect |

Keep the fault request, observed effect or null, native errors and nominal
regression verdict distinct. Wrong BUILD or a host timeout is not an observed
watchdog effect. Missing evidence remains unknown; successful import or viewing
an empty page never turns a recorded failed/unknown source into a pass.

The fixed reset macro only logs a marker after the model's own RequestReset;
it does not initiate reset, reload firmware or patch guest state. Repeated
READY/BUILD and restarted sequences show a modeled guest reboot, not physical
reset or firmware authenticity. The fixture initializes its sequence on each
entry, so reboot evidence does not establish RAM clearing or retention.

Preserve native plans/reports, runtime/firmware identities, UART, stdout/stderr
and the HIL journal. Trace retains exact model, raw reset, callback and guest
byte spans with hashes. Full, sampled and empty views retain source failures,
unknowns and model qualifications. Once imported, views read the self-contained
timeline without reopening original firmware/runtime sources or executing policy.

## Limits and cost

The audited Renode 1.17 Infrastructure revision is
[`066a7f13c052215632d469c995c89aea37c573b1`](https://github.com/renode/renode-infrastructure/tree/066a7f13c052215632d469c995c89aea37c573b1).
CONFIG sleep/halt bits are model tags; low-power behavior, timeout IRQ/delay,
RESETREAS, retained RAM, oscillator/reset timing, radio, physical protection and
complete peripheral coverage remain unverified. Guest `wfi` does not qualify
power behavior. Keep requested virtual time, guest ticks and host deadlines separate.

Host bounds remain 30 seconds, 1 MiB/output, one backend process, 1024 MiB Windows
Job memory and zero retries. HIL retains eight cases and bounded child deadlines.
Static inspection reads at most 99 payloads, 1 MiB/file, 4 MiB/component and 256
package entries/component. Trace validates a full timeline before filtering.
Record wall time and Python allocation separately from startup, cold IO, backend
RSS or physical throughput; no physical timing or safety qualification follows.
