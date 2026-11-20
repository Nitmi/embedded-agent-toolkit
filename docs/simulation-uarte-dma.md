# UARTE1 EasyDMA RX and descriptor faults

Toolkit 0.43.0 routes published sim-runner 0.15.0, HIL Runner 0.20.0 and
Embedded Trace 0.20.0 for `nrf52840-uarte-dma-v1`. The fixed Renode 1.17 model
supplies eight four-byte inputs to UARTE1 and compares paused descriptor,
event and SRAM snapshots with the guest's reports through separate UART0.

## Select and plan

Follow [simulation setup](simulation.md) to authenticate the exact wheels.
The default pin checks 114 installed files: sim 44, HIL 37 and Trace 33.
Static inspection checks their bytes without importing components, executing
their interpreter/backend or verifying signatures. Older published environments
and historical candidate modes cannot satisfy this selection.

Build simulation-only firmware with sim-runner 0.15.0's
`examples/nrf52840-uarte-dma/build.py` into a new directory, or select compatible
Cortex-M4 raw BIN firmware with an exact SHA-256 and BUILD marker.

```powershell
$python = '<simulation-venv>\Scripts\python.exe'
& $python -I -B -m sim_runner plan --backend renode `
  --profile nrf52840-uarte-dma-v1 --fault none `
  --runtime-lock '<renode-lock.json>' --runtime-sha256 '<lock-sha256>' `
  --firmware '<firmware.bin>' --firmware-sha256 '<firmware-sha256>' `
  --ready-line 'SIM_NRF_UARTE_READY v1' `
  --build-line 'SIM_NRF_UARTE_BUILD <build-id>' `
  --heartbeat-prefix SIM_NRF_UARTE_SAMPLE --output '<new-plan.json>'
```

`--fault` is required, including `none`. Continue with native inspect-plan,
run and inspect-report from the simulation guide. Preserve the independent
`embedded-sim-runner.uarte-dma-plan.v1` and `uarte-dma-report.v1` schemas.
For ordered UARTE or mixed-profile suites, use HIL 0.20.0's
`embedded-hil-runner.simulation-spec.v1` and the exact sim 0.15.0 wheel.
HIL preflights the whole suite, runs each case once and stops on failed or
indeterminate evidence, retaining later cases as not run. Put negative paths
in separate suites; reuse the agreed development-task scope without per-case
confirmation. Simulation never falls back to a physical board.

## Interpret snapshots and faults

The 40 virtual ms schedule contains 16 PRE/POST snapshots with 12 fields each:
ENABLE, RXD.PTR/MAXCNT/AMOUNT, ENDRX/RXDRDY/RXSTARTED/RXTO, INTEN, both guard
words and the four-byte buffer. The monitor pauses the guest while taking
snapshots; model `WriteChar` input is not external UART pin activity. Preserve
the guest sequence, received word, amount and guards alongside model bytes.

Immediately before the fifth frame, `rx-short-buffer` changes MAXCNT to 3,
while `rx-pointer-shift` moves PTR by one byte. Each restarts RX. Shortening
leaves a poison byte; shifting overwrites part of the high guard. A guard
detects corruption and does not prevent the write. An observed fault effect
keeps `status=failed` and `nominal_regression_passed=false`.

Wrong BUILD retains available model observations without establishing guest
identity or fault effect. Unsupported MMIO retains `MODEL_COVERAGE_FAILED`
with unevaluated assertions. Neither is a successful nominal regression.

Trace 0.20.0 preserves hash-bound raw 12-field observation spans, guest
word/amount/guard spans and descriptor request markers. Full, filtered, empty
and Markdown views keep native failures and unknowns. Trace checks structure
and raw-byte representation; it does not rerun native firmware policy. Keep
the native/HIL reports and adjacent hash-bound artifacts with derived views.

## Limits and cost

This fixed profile does not qualify TX DMA, interrupts, PPI, STOPRX/FLUSHRX,
SHORTS, zero-length descriptors, flow control, baud/parity/line errors,
electrical behavior, physical DMA/timing or complete EasyDMA coverage.
The model oracle and guard words do not establish silicon protection.
Physical, event-alignment and complete-coverage claims remain false.

Bounds remain one owned process, a 30 s host timeout, 1 MiB per capture file
and a 1024 MiB Windows Job ceiling. Sixteen snapshots add 192 numeric
observations. Keep host startup/run cost, warm evaluation/inspection cost and
virtual time separate; static payload inspection still reads every pinned
file. See the component's [profile limits](https://github.com/Nitmi/sim-runner/blob/v0.15.0/docs/nrf52840-uarte-dma.md).
