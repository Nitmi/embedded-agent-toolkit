# Saved load measurement evidence

Use this file-only workflow for already saved SDL1020X-E measurements. First
inspect the explicitly selected environment as in [instrument setup](instruments.md).
Toolkit 0.38.0 pins published lab0.11.0/HIL0.12.0/Trace0.15.0, with 96 payloads.
Load verifier0.11 accepts producers0.10/0.11; verifier0.10 still requires producer0.10.
The historical `--candidate` mode selects older components without these commands;
it cannot repair a missing or mismatched published environment.

No instrument connection, SDK, board doctor or discovery is needed here. Use
the inspected interpreter with `-I -B`. Input hashes select bytes; ordinary
saved-data work needs no per-command user confirmation. This workflow does not
authorize new acquisition, input enable/OFF or a change to an incident scene.

## Evaluate saved readings

Select an original native result plus its fixed sibling `plan.json` and
`transcript.jsonl`; keep all three unchanged. Define a separate native spec:

```json
{
  "schema_version": "lab-instruments.load-check-spec.v1",
  "checks": [{
    "id": "rail_loaded",
    "phase": "loaded",
    "window": {"start": 0, "end_exclusive": 5},
    "expect": {
      "minimum_voltage_v": {"minimum": 4.8, "maximum": 5.2},
      "maximum_current_a": {"minimum": 0.09, "maximum": 0.11},
      "input_on": true
    }
  }]
}
```

There are 1..8 checks. Choose `before_load` (one CC baseline, native index -1),
`loaded` (CC measurements), or `observe` explicitly. Half-open windows select
1..50 phase-relative readings; missing phases or windows remain invalid evidence,
never clamped. Native min/max/mean metrics cover each returned voltage/current/
power quantity; optional `input_on` applies to every selected reading.

```powershell
$python = '<inspected-venv>\Scripts\python.exe'
& $python -I -B -m lab_instruments load check --spec '<checks.json>' --spec-sha256 '<hash>' `
  --capture '<run/load-result.json>' --capture-sha256 '<hash>' --output '<new-report.json>' --json
& $python -I -B -m lab_instruments load inspect-check-report '<report.json>' --sha256 '<hash>' `
  --spec '<checks.json>' --spec-sha256 '<hash>' --capture '<run/load-result.json>' --capture-sha256 '<hash>' --json
& $python -I -B -m lab_instruments load junit '<report.json>' --sha256 '<hash>' `
  --spec '<checks.json>' --spec-sha256 '<hash>' --capture '<run/load-result.json>' --capture-sha256 '<hash>' `
  --output '<new.xml>' --json
```

Lab snapshots the originals once, validates their bindings and performs strict
in-memory successful-session SCPI replay. Verification regenerates the report,
not just its summary. It sends no SCPI. Failed/timeout/cleanup-unknown sources
keep their error, recorded cleanup and unscored partial readings; all checks
remain `invalid_evidence` rather than a passing subset.

Check/JUnit exit 0 for passed checks, 3 for complete failed/invalid evidence,
and 2 for input/consistency/output errors. Preserve JSON and XML on exit 3;
invalid evidence is an error, never skipped. Report inspection exit 0 only
means consistency; read its original verdict. Never edit a failure or reconnect
to make the saved data pass.

## Preserve the completed native verification

Create a separate HIL manifest with exactly these seven explicit inputs:

```json
{
  "schema_version": "embedded-hil-runner.load-spec.v1",
  "native_exit_code": 0,
  "inputs": {
    "report": {"path": "report.json", "sha256": "<hash>"},
    "spec": {"path": "checks.json", "sha256": "<hash>"},
    "capture": {"path": "run/load-result.json", "sha256": "<hash>"},
    "native_result": {"path": "native-junit-stdout.json", "sha256": "<hash>"},
    "junit": {"path": "checks.xml", "sha256": "<hash>"},
    "plan": {"path": "run/plan.json", "sha256": "<hash>"},
    "transcript": {"path": "run/transcript.jsonl", "sha256": "<hash>"}
  }
}
```

Paths are portable relative paths under the manifest. `native_result` is the
unchanged stdout of this native `load junit`, including bindings and XML counts;
native_exit_code is its actual 0 or 3. Unlike waveform imports there is no
`source_files` list. Never follow recorded path labels or substitute missing files.
A failed-source transcript may be empty; a missing transcript is still an error.

```powershell
& $python -I -B -m hil_runner load import '<import.json>' --sha256 '<hash>' --output '<new-bundle.json>' --json
& $python -I -B -m hil_runner load inspect '<bundle.json>' --sha256 '<hash>' --json
& $python -I -B -m embedded_trace load query '<bundle.json>' --sha256 '<hash>' --phase loaded --status passed --json
& $python -I -B -m embedded_trace load report '<bundle.json>' --sha256 '<hash>' --output '<new.md>' --json
```

HIL reads the manifest and seven files once, preserves all original bytes and
checks bindings, recorded metrics/comparisons, source state, raw query byte spans
and transaction indices, plus canonical JUnit XML. It does not repeat native
SCPI replay. Import exits 0 or 3 for the retained verdict; inspect/view exit 0
means processing succeeded even for a failing test. Input/output errors exit 2.

Trace validates the whole embedded evidence before exact check/phase/status
filters or pagination (offset0..8, limit1..8). Passing-only and empty pages retain
the complete global verdict, JUnit failure/error counts and source context.
Markdown keeps those global counts outside bounded inert previews. Full original
bytes stay in the Bundle; original files need not remain at recorded paths.

`native_recomputation_recorded=true` is historical native verification, not a
fresh decode or authenticated execution. HIL/Trace keep native_recomputed_now,
native_scpi_replay_performed and source_execution_performed false. Trace also
keeps hil_import_checks_reperformed=false; it does not reconstruct native XML.
SHA-256 detects drift relative to selected inputs, not a coherently fabricated set.

V/I/P are separate sequential queries. Power uses the returned power value;
means are arithmetic, not time-weighted. There is no energy integration,
simultaneous sampling or verified physical clock alignment. Historical OFF does
not prove current input state. Keep calibration, DUT/physical identity, timing,
authentication and current-state qualification false; preserve recorded source
effects separately without granting new authority.

## Bounds and cost

Lab spec <=64KiB; result/transcript <=1MiB each; plan <=32KiB. Report/XML
<=1MiB each. HIL adds native stdout <=128KiB and manifest <=16KiB, eight reads
total at most 4,440,064 bytes. Self-contained Bundle <=16MiB, JSON depth32.
Trace reads that entire Bundle regardless of selected page size; Markdown is
<=1MiB with 8192-character source/check previews and full global counts.
JSON/base64/canonical copies add allocation cost; byte caps are not RSS guarantees.
Measure whole-import/view costs separately from interpreter startup and cold I/O.
