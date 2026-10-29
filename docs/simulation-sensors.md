# TMP103 sensor simulation

Local Toolkit 0.36.0 routes published [sim-runner 0.8.0](https://github.com/Nitmi/sim-runner/releases/tag/v0.8.0),
[HIL Runner 0.13.0](https://github.com/Nitmi/hil-runner/releases/tag/v0.13.0) and
[Embedded Trace 0.13.0](https://github.com/Nitmi/embedded-trace/releases/tag/v0.13.0).
Use this workflow for signed-temperature conversion, stale reads or bounded
sensor-response regressions in Renode. It does not test physical sensors,
board wiring or I2C electrical behavior.

## Select the software

Follow [simulation setup](simulation.md) to authenticate the exact release
wheels and install them with `--no-index --no-deps` in an isolated environment.
The default pin checks 95 installed files: sim 30, HIL 37, Trace 28. HIL/Trace's
complete wheels include instrument modules; that does not select an instrument
workflow. Inspect before component execution:

```powershell
python scripts/simulation_runtime.py inspect '<absolute-simulation-venv>' --json
```

Require `ok=true`, `candidate_mode=false`, `resolution_source=pinned_releases`
and the three versions above. Static inspection does not import packages, start
their interpreter, verify signatures or check Renode. Its attestation, runtime,
interpreter/bytecode and physical-verification flags remain false. Native
sim-runner checks the full selected runtime inventory before/after execution.

Historical `--candidate` still selects sim 0.7 / HIL 0.8 / Trace 0.8 and 69 files;
it cannot run this sensor profile. Neither mode falls back to the other.
The simulation environment, plugin, instrument environment and workstation locks
are separate selections; inspection changes none of them.

## Prepare a native plan

Select Renode 1.17.0, `nrf52840-i2c-sensor-v1` and the native
`examples/nrf52840-i2c-sensor` Cortex-M4 BIN fixture. Build using that component's
audited fixture builder, or select an already built compatible image and exact
READY/BUILD markers. The fixture is not a hardware-ready board image.

```powershell
$python = '<simulation-venv>\Scripts\python.exe'
& $python -I -m sim_runner plan --backend renode `
  --profile nrf52840-i2c-sensor-v1 --fault none `
  --runtime-lock '<renode-lock.json>' --runtime-sha256 '<lock-sha256>' `
  --firmware '<firmware.bin>' --firmware-sha256 '<firmware-sha256>' `
  --ready-line 'SIM_NRF_SENSOR_READY v1' `
  --build-line 'SIM_NRF_SENSOR_BUILD <build-id>' `
  --heartbeat-prefix SIM_NRF_SENSOR_SAMPLE --output '<new-plan.json>'
```

`--fault` is required even for `none`. Continue with native inspect-plan/run/
inspect-report in the [simulation guide](simulation.md); sim-runner emits JSON
without `--json`. Sequential/mixed suites use HIL's existing simulation spec and
exact 0.8.0 wheel. HIL preflights all plans, runs each case once and stops after
failure or uncertainty. Reuse development-task authorization without per-run
hash confirmation. Do not switch to a physical board when a model fails.

Native schemas are `embedded-sim-runner.sensor-plan.v1` and
`embedded-sim-runner.sensor-report.v1`. HIL retains
`embedded-hil-runner.simulation-spec.v1`; Toolkit adds no executor or sensor
policy. Native inspection owns readiness/sensor assertions; HIL preserves their
projection and Trace constructs offline views.

## Evidence and fault meaning

The fixed TWI0/TMP103 register-zero sensor is at `0x48`. A 250 kHz TIMER0 IRQ
produces 16 guest samples over 82 requested virtual ms, with four paused model
observations. Raw byte `F6` must become -10, not 246. UART values remain guest
declarations; snapshots separately retain the model Temperature property,
TWI0 address and TIMER0 counter.

| Fault selection | Four model temperatures, Celsius | Native nominal verdict |
| --- | --- | --- |
| `none` | 25, -10, 85, 25 | passed / exit 0 |
| `temperature-stuck` | 25, 25, 25, 25 | failed / exit 1 |
| `temperature-offset` | 25, 0, 95, 35 | failed / exit 1 |

Faults begin at 22 requested virtual ms. Keep `fault_request`, observed effect
and `nominal_regression_passed` separate. Observed injection never changes a
failed regression to passed or allows the next case. For negative-path tests,
declare separate suites and retain their expected nonzero verdicts. Missing/
unevaluated assertions stay null; a requested enum is not proof of effect.

Preserve native reports/plans, firmware/runtime identities, UART, backend
stdout/stderr and HIL calls journal. Trace 0.13 uses the usual correlate/inspect/
query/report route. Full `sensor_evidence`, native errors, failed/unknown
outcomes and `sensor_observation_spans` survive sample filters and empty pages.
Spans bind exact stdout offsets, raw bytes and SHA-256, including negative values
and final newlines. Successful import or inspection of a failed capture is not
a regression pass. Views use only the self-contained timeline after import;
they do not reopen runtimes, execute firmware or repeat native sensor policy.
Saved consistency is not authentication.

## Limits and cost

Paused RunFor boundaries, guest TIMER0 ticks and the whole host UART run window
have distinct clock meanings. Model coverage, physical timing, sensor accuracy
and I2C electrical verification flags remain false. There is no NACK/disconnect,
conversion-delay, calibration, thermal-dynamics, bus-speed/electrical, EasyDMA or
PPI acceptance; TMP108 is not a separately validated model in this release.

Native defaults remain 30 host seconds, 1 MiB/output, one backend process,
1024 MiB Windows Job memory and zero retries. HIL permits eight cases and
bounded 1..600 s child deadlines; include startup and runtime hashing overhead.
Trace keeps an 8 MiB sensor-source budget and validates the whole timeline before
filtering; empty pages do not reduce verification work. Sixteen samples/four
spans bound added data. Static inspection reads at most 95 files (1 MiB/file,
4 MiB/component) and 256 package entries/component. Warm timings and Python
allocation costs exclude startup, cold I/O, runtime RSS and physical timing.
