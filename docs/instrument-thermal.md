# Saved thermal ROI evidence

Use this file-only workflow for saved native PureThermal/Lepton captures. First
inspect the explicitly selected environment as in [instrument setup](instruments.md).
Toolkit 0.38.0 pins published lab0.11/HIL0.12/Trace0.15.0 and 96 payloads. Historical
candidate mode lacks this domain; it cannot repair a mismatched published setup.
Use the inspected trusted interpreter with `-I -B`. Hashes select bytes without
per-command confirmations. No camera, SDK, board doctor or discovery is needed.

## Evaluate the original buffers

Keep `thermal-result.json`, sibling `plan.json`, CSVs and the full `native/`
inventory unchanged. Put a separate check spec and all new outputs outside that
capture directory. A native spec has exactly
`schema_version=lab-instruments.thermal-check-spec.v1` and 1..8 checks:

```json
{
  "schema_version": "lab-instruments.thermal-check-spec.v1",
  "checks": [{
    "id": "surface_roi",
    "roi": {"x": 20, "y": 10, "width": 40, "height": 30},
    "window": {"start": 0, "end_exclusive": 2},
    "maximum_invalid_pixels": 0,
    "expect": {"max_c": {"minimum": 15, "maximum": 60}}
  }]
}
```

Choose bounds appropriate to the task; the example is not a device safety limit.
Integer half-open ROIs lie inside the 160x120 image, with top-left origin and no
clipping. Footer telemetry is not a temperature pixel. Half-open windows select
1..8 delivered buffers, not elapsed time; unavailable buffers remain invalid
evidence. The explicit invalid-pixel budget is 0..ROI area-1; no pixel is filled.

`min_c`, `max_c`, `mean_c`, `p95_c` apply inclusive bounds to every selected
buffer's valid pixels. P95 is nearest rank; tied hotspots use row-major order.
Optional `hotspot_within` selects a rectangle inside the ROI. `mean_delta_c` and
`max_delta_c` compare last minus first unique frame. Follow the selected native
release's spec/help for all field/range constraints.

```powershell
$python = '<inspected-venv>\Scripts\python.exe'
& $python -I -B -m lab_instruments thermal check --spec '<checks.json>' --spec-sha256 '<hash>' `
  --capture '<capture/thermal-result.json>' --capture-sha256 '<hash>' --output '<new-report.json>' --json
& $python -I -B -m lab_instruments thermal inspect-check-report '<report.json>' --sha256 '<hash>' `
  --spec '<checks.json>' --spec-sha256 '<hash>' --capture '<capture/thermal-result.json>' --capture-sha256 '<hash>' --json
& $python -I -B -m lab_instruments thermal junit '<report.json>' --sha256 '<hash>' `
  --spec '<checks.json>' --spec-sha256 '<hash>' --capture '<capture/thermal-result.json>' --capture-sha256 '<hash>' `
  --output '<new.xml>' --json
```

Lab snapshots the full explicit source, rechecks GET/telemetry/TLinear units,
native CSVs, masks, raw buffers and cleanup, then recomputes ROI assertions.
Report inspection and JUnit regenerate the entire report from explicit inputs;
recorded path labels are never followed. Keep raw SHA-256/ROI byte spans, controls,
source errors and qualifications. A failed source leaves every check invalid,
with partial frames unscored. Exceeded invalid-pixel budgets, no valid pixels,
unavailable windows and unsupported requested trends remain `invalid_evidence`.

Delta checks need increasing unique frame counters/uptime and identical FFC time,
effective gain, resolution and ROI valid-pixel masks. Exact duplicates count only
once for a trend. An absolute-only check may remain valid when a delta is not.
`max_delta_c` compares maxima that may move; it is not point tracking or a heating
rate. User bounds retain exact native comparisons without an added tolerance.

Check/JUnit return 0 for a passing verdict, 3 for complete failed/invalid evidence,
2 for input/consistency/output errors. Inspection exit0 means consistency even
when the test failed. Preserve stdout, actual exit, JSON and XML on exit3;
invalid evidence is a JUnit error, never skipped. Stop on incomplete evidence
without editing data or reacquiring it to obtain a pass.

## Preserve the native verification

Use an independent HIL manifest with five primary inputs and ordered sources:

```json
{
  "schema_version": "embedded-hil-runner.thermal-spec.v1",
  "native_exit_code": 0,
  "inputs": {
    "report": {"path": "report.json", "sha256": "<hash>"},
    "spec": {"path": "checks.json", "sha256": "<hash>"},
    "capture": {"path": "capture/thermal-result.json", "sha256": "<hash>"},
    "native_result": {"path": "native-junit-stdout.json", "sha256": "<hash>"},
    "junit": {"path": "checks.xml", "sha256": "<hash>"}
  },
  "source_files": [
    {"name": "native/frame-0000.y16", "path": "capture/native/frame-0000.y16", "sha256": "<hash>"}
  ]
}
```

Replace the illustrative source entry with **every** native report `input_files`
entry after the first capture entry, in recorded order. Each has exactly
`name,path,sha256`; name is the original top-level or `native/` artifact name.
Bind plan, CSVs, raw/warmup frames, GET payloads, telemetry, source inventory,
completion and empty stdout/stderr too. Missing and empty are different. Select
portable relative paths under the manifest; relocated originals can be bound
explicitly without following their saved labels.

`native_result` is unchanged stdout from this native `thermal junit`; use its
actual exit0/3 and XML. Thermal requires native producer/verifier0.11 and HIL0.12.
Never wrap thermal evidence in the digital, waveform or load schema.

```powershell
& $python -I -B -m hil_runner thermal import '<import.json>' --sha256 '<hash>' --output '<new-bundle.json>' --json
& $python -I -B -m hil_runner thermal inspect '<bundle.json>' --sha256 '<hash>' --json
& $python -I -B -m embedded_trace thermal query '<bundle.json>' --sha256 '<hash>' --status passed --json
& $python -I -B -m embedded_trace thermal report '<bundle.json>' --sha256 '<hash>' --output '<new.md>' --json
```

HIL preserves all source bytes and checks bindings, recorded metadata/statistics,
comparisons/trends, inventory, cleanup and canonical native JUnit XML. It does not
convert pixels or compute temperatures again. Import exits0/3 for the retained
verdict; inspect/view exit0 means processing succeeded even for a failing test.
Input/output/consistency errors exit2. Outputs must be new and outside the source
capture directory. A self-contained bundle needs no original source paths.

Trace validates the entire bundle before exact check/status filters or pagination
(offset0..8, limit1..8). Passing-only and empty pages retain the full global
verdict, source context, failed/invalid counts and JUnit errors. Markdown keeps
global counts outside bounded inert previews. Original bytes remain in the Bundle.

`native_recomputation_recorded=true` records historical native verification;
HIL/Trace retain `native_recomputed_now=false`,
`native_temperature_conversion_performed=false` and
`source_execution_performed=false`. Trace also retains
`hil_import_checks_reperformed=false` and `source_files_rechecked=false`:
it checks bound XML bytes/counts without reconstructing native XML. Hashes cannot
authenticate a coherently fabricated unsigned record set or genuine acquisition.

## Qualification and cost

Values are apparent surface Celsius temperatures, not chip junction temperature.
Keep camera/DUT identity, calibration, scene parameters, radiometric accuracy and
physical clock alignment unverified. Emissivity/flux settings are recorded, not
applied a second time. Sensor uptime, host receipt and Media Foundation clocks
stay distinct; do not infer UTC, causality or serial/RTT timeline alignment.
Saved evidence work grants no camera connection or FFC/gain/control change.

Source snapshot <=16MiB/101 files, each artifact/result/report/XML <=1MiB;
spec <=64KiB. Lab supports at most8 checks of8 frames of19,200 pixels; native
CSV validation still runs but there is no per-check CSV generation. HIL manifest
<=256KiB, native stdout<=128KiB, at most106 explicit file reads, each once.
Bundle<=32MiB/depth32. Trace processes it fully on every page; Markdown<=1MiB
with8192-character previews. Masks, sorting, JSON/base64 and canonical copies
add time and allocation cost; these bounds do not guarantee RSS or latency.
Measure whole import/view costs separately from startup and cold I/O.
