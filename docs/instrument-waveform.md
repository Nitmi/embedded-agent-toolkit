# Saved analog waveform evidence

Use this workflow for voltage assertions on saved AD3 or SIGLENT SDS804X data.
First inspect the explicitly selected published environment as described in
[instrument setup](instruments.md). Toolkit 0.33.0 selects lab-instruments 0.9.0,
HIL Runner 0.10.0 and Embedded Trace 0.10.0. Digital UART/I2C/SPI/PWM checks
continue to use `logic` in lab and `instrument` in HIL/Trace.

## Evaluate the original samples

Use the inspected environment's interpreter with `-I -B`. Hashes bind saved
bytes; ordinary offline evaluation needs no per-file user confirmation.

```powershell
$python = '<inspected-venv>\Scripts\python.exe'
& $python -I -B -m lab_instruments waveform check --spec '<spec.json>' --spec-sha256 '<hash>' `
  --capture '<capture.json>' --capture-sha256 '<hash>' --output '<new-report.json>' --json
& $python -I -B -m lab_instruments waveform inspect-check-report '<report.json>' --sha256 '<hash>' `
  --spec '<spec.json>' --spec-sha256 '<hash>' --capture '<capture.json>' --capture-sha256 '<hash>' --json
& $python -I -B -m lab_instruments waveform junit '<report.json>' --sha256 '<hash>' `
  --spec '<spec.json>' --spec-sha256 '<hash>' --capture '<capture.json>' --capture-sha256 '<hash>' `
  --output '<new.xml>' --json
```

Lab decodes saved channel-major f64 AD3 samples or SDS804X WORD/preamble data
and applies the selected probe conversion. It computes `minimum_v`, `maximum_v`,
`mean_v`, `peak_to_peak_v`, `rms_v` and `ac_rms_v` over explicit sample windows.
RMS includes DC; AC RMS removes only the population mean. Limits are inclusive;
no filtering, clipping correction or bandwidth correction is implied.

V1 supports DC coupling, at most eight checks and 16,384 samples per window.
Missing channels, oversized windows and AC/GND coupling retain
`invalid_evidence` and JUnit errors. Follow the selected native release's spec
and help for complete field definitions. Check and JUnit return 0 for passed
checks and 3 for complete failed/invalid checks. Report inspection returns 0 for
consistent evidence even when the test failed. Input, consistency and output
errors return 2. Preserve original stdout, JSON, XML and exit codes;
upload XML even for a completed failing test. Stop on incomplete evidence rather
than editing data or reacquiring samples automatically.

## Preserve a native verification

Prepare a portable relative-path import manifest:

```json
{
  "schema_version": "embedded-hil-runner.waveform-spec.v1",
  "native_exit_code": 0,
  "inputs": {
    "report": {"path": "report.json", "sha256": "<hash>"},
    "spec": {"path": "spec.json", "sha256": "<hash>"},
    "capture": {"path": "capture.json", "sha256": "<hash>"},
    "native_result": {"path": "native-result.json", "sha256": "<hash>"},
    "junit": {"path": "junit.xml", "sha256": "<hash>"}
  },
  "source_files": []
}
```

`native_result` is the unchanged JSON stdout of `waveform junit`, including its
full report verification and XML reference. Set `native_exit_code` to that
actual completed result, 0 or 3; do not change it to satisfy CI.

For AD3, `source_files` is empty because the f64 sample bytes are in the capture.
For SDS804X, explicitly bind **every** ancillary native `input_files` entry in
its recorded order as `{name,path,sha256}`. The capture is already selected in
`inputs`; exclude that first entry from the ancillary list. Include the plan,
transcript, all wire TX/RX, channel preambles, WORD bytes and CSV. A zero-byte
wire response is valid evidence; a missing file is not an empty response.
Use the ordered inventory, not JSON object iteration order after key sorting.
Recorded paths inside reports are labels, never additional files to follow.

```powershell
& $python -I -B -m hil_runner waveform import '<import.json>' --sha256 '<hash>' `
  --output '<new-bundle.json>' --json
& $python -I -B -m hil_runner waveform inspect '<bundle.json>' --sha256 '<hash>' --json
```

HIL checks explicit bytes/hashes, the native input inventory, report/spec/result
bindings, metric comparisons, recorded conversion metadata and canonical native
JUnit. It preserves the original inputs, source bytes, six metrics, windows,
raw spans and cleanup/freshness evidence in a self-contained bundle. It does
not convert voltage samples again or replay SCPI. Import returns 0 or 3 for
the recorded verdict; inspect returns 0 for successful processing even when
the test failed. Input/consistency/output errors return 2.

## Review without changing the verdict

```powershell
& $python -I -B -m embedded_trace waveform inspect '<bundle.json>' --sha256 '<hash>' --json
& $python -I -B -m embedded_trace waveform query '<bundle.json>' --sha256 '<hash>' `
  --channel 1 --status passed --json
& $python -I -B -m embedded_trace waveform report '<bundle.json>' --sha256 '<hash>' `
  --check '<check-id>' --output '<new.md>' --json
```

Query/report combine exact check ID, channel 1..4, status, offset 0..8 and
limit 1..8. Passing-only and empty pages retain the entire native verdict and
JUnit failure/error counts. Exit 0 means view processing succeeded. Retain the
bundle for full evidence: Markdown is an inert bounded preview, with at most
8,192 characters per selected check and 1 MiB output.

Native lab recomputation, HIL import and Trace views are distinct operations.
HIL/Trace retain `native_recomputation_recorded=true`,
`native_recomputed_now=false`; Trace also retains
`hil_import_checks_reperformed=false`. Trace checks embedded bytes and summaries
but does not reconstruct native XML. Bundle inspection never reopens original
paths (`source_files_rechecked=false`). Consistent unsigned reports do not prove
authenticated historical execution, genuine acquisition or DUT identity.

Keep test-double origin and false physical instrument, calibration, clipping
absence, analog bandwidth, clock alignment, authorization and UTC sample-origin
claims visible. These software releases have not qualified a real AD3/SDS804X.
Descriptor/sample-relative time is not a synchronized serial/RTT host timestamp;
do not merge it into a host timeline or infer causality from it.

## Bounds and cost

Native saved sources are at most 1,615 files, 1 MiB per file and 8 MiB combined.
Report/capture/XML are at most 1 MiB each, spec 64 KiB and native stdout 128 KiB.
HIL's manifest is at most 512 KiB; all explicitly selected inputs including it
total at most 1,620 distinct files and 11,206,656 bytes. Links, duplicate paths
and duplicate file identities are rejected. Self-contained output is separately
capped at 20 MiB with JSON depth 32, so base64/path overhead can still exceed
that limit. No evidence is dropped to force a fit.

HIL/Trace inspection validates the entire bundle even for a one-check page;
cost grows with source bytes and inventory size. Native metric cost also grows
with selected checks and window length. JSON/base64 copies add allocations.
Byte limits are not process RSS guarantees. Measure full-bundle work separately
from interpreter startup, cold disk access and physical instrument performance.
