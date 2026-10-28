# Optional offline instrument workflows

Toolkit 0.35.0 routes the published lab-instruments 0.11.0,
HIL Runner 0.12.0 and Embedded Trace 0.12.0 releases. This optional domain
evaluates **saved** digital/analog captures, load/thermal measurements and native reports; it does not open an
instrument or acquire a new waveform. Real devices, vendor SDK/ABI, wiring,
calibration and timing accuracy have not been qualified by these software checks.

`instrument-runtime.json` binds each repository, immutable source tag/revision,
wheel download URL/SHA-256 and 96 installed code/schema/metadata/license files.
Its release identities are:

| Component | Tag | Source revision |
| --- | --- | --- |
| [lab-instruments](https://github.com/Nitmi/lab-instruments/releases/tag/v0.11.0) | `v0.11.0` | `8d8ea1743699e3a0bd889d2612bdd19d4552b590` |
| [HIL Runner](https://github.com/Nitmi/hil-runner/releases/tag/v0.12.0) | `v0.12.0` | `81c3b6fd8b23bc7ac2c3da5ce0d9b98bb39ed883` |
| [Embedded Trace](https://github.com/Nitmi/embedded-trace/releases/tag/v0.12.0) | `v0.12.0` | `c365536bdd91d4c2c2453115e0e035ea2f8ef26d` |

Published identity in a pin is not an attestation verification. Do not substitute the
older HIL/Trace versions selected by the separate simulation pin or managed HIL
pin. A dedicated instrument environment keeps these selections explicit.

## Inspect the selected software

During requested host setup, download the exact three release wheels named in
the published pin and independently compare each SHA-256 before installation.
For authenticated setup, verify each wheel with GitHub CLI, taking values from
that component's pin entry:

```powershell
gh attestation verify '<wheel>' --repo '<repository>' --source-ref '<source_ref>' `
  --source-digest '<source_revision>' --signer-digest '<source_revision>' `
  --signer-workflow '<repository>/.github/workflows/python-release.yml' `
  --predicate-type https://slsa.dev/provenance/v1 --deny-self-hosted-runners
```

Preserve that command's independent result. The file-only inspector does not run
it, fetch attestations or authenticate installed files' download history. Equal
installed bytes do not establish which wheel container installed them.
Install into a dedicated Python 3.11+ environment, using
`uv pip install --python '<venv-python>' --no-index --no-deps '<wheel>' ...`.
The inspector never downloads or installs anything. Installing/activating a
plugin or modifying the active workstation is not needed to review saved data.

```powershell
python scripts/instrument_runtime.py inspect '<absolute-venv-directory>' --json
```

All three components are checked by default; repeat `--component lab-instruments`,
`--component hil-runner` or `--component embedded-trace` to select only those needed
by the task. Missing/changed requested files fail; an unselected component is not
silently installed or accepted. Inspection defaults to the published pin.
The historical `instrument-candidates.json` remains available only with explicit
`--candidate`. Its local source/wheel identities are different and carry no
release ref, URL or provenance claim. Neither mode falls back to the other when
its selected pin or payload is missing or invalid.

Success reports `resolution_source=pinned_releases` (or `pinned_local_candidates`
in candidate mode), each component's version/source/wheel and verified file count,
and the selected interpreter path. Published entries also name repository/ref.
It checks file bytes and declared venv layout/version only. It never imports a
component, starts its interpreter, loads an SDK, enumerates devices, uses network
or evaluates a test. Bytecode, interpreter/stdlib/import customization, release
attestation and vendor/runtime behavior remain unverified. Use normal trusted
host software: this is a point-in-time payload check, not an execution sandbox.

For a combined host-readiness task, optionally run:

```powershell
python scripts/toolkit_doctor.py --instrument-environment '<absolute-venv-directory>' `
  --strict --json
```

Add `--instrument-candidate` only to inspect the historical local candidates;
it requires `--instrument-environment` before native version commands can run.
This doctor also executes the selected native components' `--version` checks;
its nested `instruments` check remains file-only. Default doctor does not inspect
instruments. For a task concerned only with saved files, the standalone inspector
is sufficient; a connected board or successful hardware doctor is unnecessary.
Native component locks and workstation selection remain independent.

## Choose the native operation

For AD3/SDS804X voltage assertions, read [analog waveform evidence](instrument-waveform.md)
and use the separate `waveform` command domain. For SDL1020X-E measurement
assertions, read [load evidence](instrument-load.md) and use the independent
`load` domain. For saved PureThermal/Lepton ROI assertions, read
[thermal evidence](instrument-thermal.md) and use `thermal` throughout.
The table and manifest below
describe digital protocol/PWM evidence.

Use the inspected environment's trusted interpreter in isolated module mode.
On Windows its entry is `Scripts/python.exe`; POSIX uses `bin/python`. Component
execution is separate from the static inspection. Input hashes bind selected
bytes; they are not additional user confirmations for ordinary offline work.

| Goal | Native command | Meaning |
| --- | --- | --- |
| Evaluate original digital samples | `-m lab_instruments logic check` | Exact UART/I2C/SPI data/boundaries/ACK and per-cycle PWM bounds |
| Recheck a saved report against originals | `-m lab_instruments logic inspect-check-report` | Full native decoder/assertion recomputation with explicit report/spec/capture hashes |
| Create CI XML from a verified report | `-m lab_instruments logic junit` | Full recomputation; failures and invalid evidence remain failure/error |
| Preserve a completed native verification with its original inputs | `-m hil_runner instrument import` | Byte/hash/binding/status consistency and canonical native XML; self-contained artifact |
| Inspect that artifact | `-m hil_runner instrument inspect` | Rechecks embedded evidence, not a new signal decode |
| Find or report checks | `-m embedded_trace instrument inspect/query/report` | Independent offline view with original analysis/raw spans and global verdict |

For example, after selecting the exact local paths and hashes:

```powershell
$python = '<inspected-venv>\Scripts\python.exe'
& $python -I -B -m lab_instruments logic check --spec '<spec.json>' --spec-sha256 '<sha256>' `
  --capture '<capture.json>' --capture-sha256 '<sha256>' --output '<new-report.json>' --json
& $python -I -B -m lab_instruments logic junit '<report.json>' --sha256 '<report-sha256>' `
  --spec '<spec.json>' --spec-sha256 '<spec-sha256>' --capture '<capture.json>' `
  --capture-sha256 '<capture-sha256>' --output '<new.xml>' --json
& $python -I -B -m hil_runner instrument import '<import.json>' --sha256 '<import-sha256>' `
  --output '<new-bundle.json>' --json
& $python -I -B -m embedded_trace instrument query '<bundle.json>' --sha256 '<bundle-sha256>' `
  --status invalid_evidence --json
```

Check/JUnit/import may return 3 while still saving a complete **failing** result.
Stop on input/verification/output errors rather than repairing or retrying data.
Preserve stdout, exit code, original JSON and XML. For CI, collect XML on failure;
an invalid native result without completed verification cannot be imported as a
test pass. Native help and the selected source/sdist docs define the complete
specs; Toolkit adds no shell/argv executor or alternate contract language.

The HIL import manifest contains exactly `schema_version` set to
`embedded-hil-runner.instrument-spec.v1`, recorded `native_exit_code` (0 or 3),
and five `inputs`: `report`, `spec`, `capture`, `native_result`, `junit`. Each input
has a portable relative `path` and lowercase `sha256`. `native_result` is the
preserved JSON stdout from lab 0.11.0 `logic junit`; it includes full verification
bindings and XML reference/counts. HIL reads all explicitly bound files once,
checks consistency and preserves their original bytes in a new artifact. It
never follows SDK, plan or file paths recorded inside that evidence.

The selected HIL/Trace releases accept digital producers0.7..0.11 verified by0.11.
They retain verifier0.10 for producers0.7..0.10, verifier0.9 for producers0.7/0.8/0.9 and
verifier0.8 for producers0.7/0.8. Keep actual producer/verifier versions; newer
producers with an older unsupported verifier, or unknown versions, are rejected.
Do not relabel old reports to make them pass.

## Keep the result boundaries

The native lab verifier recomputes signal assertions. HIL import records that
verification and checks byte/binding/result/XML consistency;
`native_recomputation_recorded=true` and `native_recomputed_now=false` are distinct.
Trace validates embedded inputs and summaries but does not rerun the decoder or
HIL's canonical XML check; `hil_import_checks_reperformed=false` stays visible.
Native verification records and their exit codes are unsigned historical data,
not authenticated execution or device evidence.

Inspect/view exit 0 means processing succeeded, including for a failing test.
Read the original `verdict`, `verdict_ok`, check status and JUnit failure/error
counts. `invalid_evidence` never becomes skipped or passed. A filtered passing
page or an empty page retains the complete global failing verdict. Markdown is
an inert, bounded preview; full native analysis and raw sample byte spans remain
inside the bundle. Keep the raw JSON for review.

Samples use `sample_relative_no_verified_utc_origin`. A recorded SDK sample rate
is not an independently measured clock. Do not place these observations on the
serial/RTT host timeline or infer causality, board/firmware identity or clock
alignment. Source cleanup failures, partial/invalid signal status, test-double
origin and false physical/calibration/authorization claims remain visible.

## Bounds and cost

Static inspection reads at most 96 published payload files (74 historical candidate
files), each at most 1 MiB and
each package at most 4 MiB, plus bounded venv configuration/pin data. Package
inventory walks are capped at 256 entries per component. It rejects links,
unexpected package content, ambiguous layouts and mismatched payloads. Generated
`.pyc` files may exist but are not authenticated. It holds one payload at a time;
runtime/environment overhead is additional, so limits are not an RSS guarantee.

Native digital lab evaluation supports at most eight checks and 16,384 samples, report/
capture/XML up to 1 MiB and spec up to 64 KiB. Recomputing costs depend on checks
and samples. HIL import accepts up to 3,358,720 explicit input bytes and an 8 MiB
self-contained report. HIL/Trace views validate the entire report regardless of
page length; base64 and JSON add memory. Preserve each component's bounds/errors
instead of stripping evidence to force a result. Local performance measurements
belong in acceptance records with warm/cold conditions, not universal timing claims.
