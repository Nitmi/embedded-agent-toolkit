# SPI / LM74 model regressions

Toolkit 0.37.0 routes published sim-runner 0.9.0, HIL Runner 0.14.0 and
Embedded Trace 0.14.0 for `nrf52840-spi-sensor-v1`. Use it for signed fractional
temperature, two-byte frame order, stale reads and bounded model faults. It
does not qualify a physical SPI driver, sensor or board.

## Select the environment

Follow [simulation setup](simulation.md) to authenticate the selected release
wheels and install them offline without dependencies in an isolated environment.
The default pin binds 97 installed files: sim 32, HIL 37, Trace 28.

```powershell
python scripts/simulation_runtime.py inspect '<simulation-venv>' --json
```

Require `ok=true`, `candidate_mode=false`, `resolution_source=pinned_releases`
and the three versions above. This file-only check does not start the selected
interpreter, authenticate a release, verify Renode or accept physical hardware.
The historical 69-file `--candidate` environment has no SPI profile and cannot
satisfy this selection. Instrument and native station selections are independent.

## Plan and run natively

Use Renode 1.17.0 and the released sim-runner's
`examples/nrf52840-spi-sensor` fixture builder, or a compatible already-built
Cortex-M4 BIN with its exact hash and build markers. The fixture is a model
test image, not a board-ready firmware image.

```powershell
$python = '<simulation-venv>\Scripts\python.exe'
& $python -I -B -m sim_runner plan --backend renode `
  --profile nrf52840-spi-sensor-v1 --fault none `
  --runtime-lock '<renode-lock.json>' --runtime-sha256 '<lock-sha256>' `
  --firmware '<firmware.bin>' --firmware-sha256 '<firmware-sha256>' `
  --ready-line 'SIM_NRF_SPI_READY v1' `
  --build-line 'SIM_NRF_SPI_BUILD <build-id>' `
  --heartbeat-prefix SIM_NRF_SPI_SAMPLE --output '<new-plan.json>'
```

`--fault` is mandatory, including `none`. Continue with native
inspect-plan/run/inspect-report in the [simulation guide](simulation.md).
The independent native schemas are `embedded-sim-runner.spi-sensor-plan.v1`
and `embedded-sim-runner.spi-sensor-report.v1`; do not relabel an I2C report.
The native inspector owns readiness, sample and fault assertions.

For ordered SPI or mixed SPI/I2C/GPIO suites, use HIL 0.14's existing
`embedded-hil-runner.simulation-spec.v1` with the exact 0.9.0 sim wheel.
HIL preflights every plan before starting a backend, executes each case once
and stops after failure or uncertainty. Reuse the agreed development task's
authorization; no new per-run hash confirmation or hardware fallback is added.
Negative paths belong in separately declared suites, not an override that
changes the failed nominal verdict or permits later cases to run.

## Interpret the evidence

The fixed legacy SPI0 model uses `easyDMA=false`, ENABLE=1 and two TXD/RXD byte
exchanges per guest sample. LM74 words encode signed Q4 in units of 1/16 C:
`((Q4 << 3) | 7) & 0xffff`. Preserve both raw bytes and the arithmetic sign shift.
Normal model temperatures 25.0625, -10.125, 85.5 and 0.0625 C correspond to
words `0C8F`, `FAF7`, `2AC7`, `000F`. These are model values, not calibrated data.

Sixteen TIMER0 IRQ samples span 82 requested virtual ms. Four observations
while paused retain Temperature, SPI ENABLE and a timer capture. Model inputs
change at 0/22/42/62 ms; observations occur at 20/40/60/80 ms.

| Fault | Model action at 22 virtual ms | Native nominal outcome |
| --- | --- | --- |
| `none` | Continue the four-temperature schedule | Passed when all protocol, words, Q4 and observations match |
| `temperature-stuck` | Keep the initial Temperature | Failed; snapshots and guest data must separately establish the effect |
| `frame-slip` | Consume one byte through the fixed model `Transmit(0)` | Failed; returned byte, model observations and the slipped guest stream must agree |

Frame-slip consumes a model byte; it is not a wire bit error or electrical
fault. LM74 caches alternating high/low bytes, including the old low byte at a
temperature transition. Selecting the enum or seeing a monitor marker alone
does not prove the guest effect. Preserve request, observation, guest effect
or null, native errors and `nominal_regression_passed` separately.

Keep native plans/reports, firmware/runtime identities, UART, backend
stdout/stderr and the HIL journal. Trace retains raw words, signed Q4, model
observation spans and `spi_frame_slip_span` with exact byte offsets/hashes.
Full, sample and empty pages keep the global failure/unknown verdict and model
limits. Successful import or inspection is not a successful firmware test.
After import, views read the self-contained timeline; they do not execute a
backend, repeat native policy or reopen original firmware/runtime sources.

## Limits and cost

The audited Renode 1.17 Infrastructure revision is
[`066a7f13c052215632d469c995c89aea37c573b1`](https://github.com/renode/renode-infrastructure/tree/066a7f13c052215632d469c995c89aea37c573b1).
This controller does not route chip-select or call `FinishTransmission`; the
fixture starts aligned. Pin routing, bus frequency/mode, electrical behavior,
real CS framing, conversion delay, calibration, EasyDMA/PPI, physical timing
and complete peripheral coverage remain unverified. Do not substitute newer
model register semantics or treat a model pass as hardware acceptance.

Keep paused model times, guest timer ticks and the host UART window distinct.
Host defaults remain 30 seconds, 1 MiB/output, one backend process, 1024 MiB
Windows Job memory and zero retries. HIL retains eight cases and bounded child
deadlines. Trace validates the full timeline before filtering; a small or empty
page is not a cheaper validation shortcut. Static inspection reads at most 97
payloads, 1 MiB/file, 4 MiB/component and 256 package entries/component. Measure
host wall time and Python allocation separately from virtual time, startup,
cold IO, backend RSS and physical throughput.
