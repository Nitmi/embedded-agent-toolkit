# Toolkit development handoff

Read this file and AGENTS.md before starting another task.

## Current local work

- Local 0.36.0 on feat/published-sensor-simulation routes fixed Renode TMP103
  signed-temperature and model-fault evidence. Read docs/simulation-sensors.md.
  The simulation default now binds published sim0.8 (7f542e0), HIL0.13
  (ceea67dd), Trace0.13 (f07f0051), exact official wheel URLs/hashes and95 files
  (30/37/28). Inventory comes from authenticated formal wheels and frozen prior
  release receipts, not candidate containers. No fresh network verification or
  native simulation is needed for this Toolkit-only integration.
- Historical simulation-candidates.json stays byte-identical at sim0.7/HIL0.8/
  Trace0.8 and69 files. Its explicit audited CANDIDATE_SPECS is independent from
  the new default; do not derive the old inventory from a growing published
  table. Both directions of version/inventory mismatch must fail without fallback.
  Sensor code/model substitution and the full HIL/Trace dependencies are checked;
  selecting a simulation wheel does not activate its instrument functions.
- Native sensor policy remains in sim-runner, HIL preserves results and Trace
  views retain guest samples, raw model spans, failures/nulls and clock/coverage
  qualifications. Three short Skill routes share the new guide. No additional
  executor, decoder, repeated per-run approval or physical fallback is added.
  Include the sensor guide in release.REQUIRED_FILES; keep bootstrap VERSION
  aligned with both0.36 manifests.
- Source checks: each Python3.11/3.13 ran274 unittest cases,271 passed/3 expected
  symlink-permission skips; Ruff, four official Skill validators and repository
  plugin layout/version check passed. Official plugin-creator is absent; do not
  mislabel the repository check. Clean-source double builds/candidate installs,
  mode compatibility, byte-only checks and warm cost are recorded separately in
  D:\Code\tmp\toolkit-sensor-0360-20261029; use its final completed receipt.
- Active Toolkit0.35, instrument published96/candidate74, native component catalog,
  managed/HIL pins, workstation locks and PATH remain separate and unchanged.
  This local task does not publish or activate Toolkit and never starts hardware
  or an emulator. Source0.35 notes below are historical; it has been published
  and its actual Skill loading was accepted before this task.

- Local version 0.35.0 adds saved thermal ROI routing alongside digital/analog
  and SDL load assertions. instrument-runtime.json binds published lab0.11
  (8d8ea174), HIL0.12 (81c3b6fd), Trace0.12 (c365536b), exact formal release
  wheel identities and 96 files. Prior formal wheel provenance/installed-payload
  receipts from the completed three-component release are reused; no new network
  verification is needed for this routing change. Toolkit0.34 remains the active
  workstation plugin until a separately scoped release/upgrade.
  The historical instrument-candidates.json
  remains byte-identical: lab 0.8 / HIL 0.9 / Trace 0.9, 74 files, explicit mode.
  Published and candidate versions AND inventories differ; never reuse one mode's
  SPECS for the other's validation or fall back between them.
- Default doctor, published simulation pins, component catalog, active plugin,
  workstation selection and native locks must remain independent. This task does
  not authorize publishing, activation, lock changes or hardware/simulator access.
- Keep native decoding/assertions in lab, evidence import/XML consistency in HIL
  and independent views in Trace. Do not add another executor or decoder here.
  Recorded recomputation is not a new decode or authenticated execution; a passing
  filtered page cannot replace the complete failing verdict.
- Source acceptance for this change: Python3.11/3.13 each ran271 unittest cases,
  268 passed/3 expected platform skips; Ruff and all four official Skill checks
  passed, plus the repository plugin layout/version check. No official plugin
  creator validator is installed. Clean-source double builds and candidate
  installs are recorded separately in D:\Code\tmp\toolkit-thermal-0350-20261028;
  use its final completed receipt and workspace handoff for later status, without
  rewriting this source commit or relabeling candidates as published Toolkit.

## Pitfalls and acceptance

1. Instrument inspection defaults to the published pin; explicit candidate mode
   selects only the historical pin. It checks payload bytes
   and declared layout only, never imports selected packages, starts their Python,
   loads SDKs or accesses devices/network. Interpreter, bytecode, runtime, physical
   instrument and remote provenance verification remain false. Installed payload
   equality cannot identify the original wheel container. Record separate exact
   gh verification results without turning a static inspection into provenance.
   Current HIL/Trace sources include digital producer/verifier compatibility;
   do not select the earlier waveform-only d25/140 preparation builds. Native
   Digital verifier0.11 accepts producers0.7..0.11; verifier0.10 accepts
   producers0.7..0.10, verifier0.9 accepts
   0.7/0.8/0.9, verifier0.8 accepts 0.7/0.8. Waveform verifier0.11 accepts
   producers0.9..0.11; verifier0.10 accepts0.9/0.10. Load verifier0.11 accepts
   producers0.10/0.11; verifier0.10 still requires0.10. Thermal requires native
   producer/verifier0.11 and HIL0.12. Never relabel sources.
2. Shared bounded layout/payload helpers live in simulation_runtime.py. Changes
   must retain simulation's published/candidate behavior and regression coverage;
   instrument inventories and versions stay independent of simulation selections.
3. release.py, toolkit_doctor.py and bootstrap.py share an import graph. Include a
   new imported script in bootstrap's installer-script inventory and verify cold
   installed execution, not only in-repository imports.
4. Validate plugin layout/release identity, all four Skills, full tests on Python
   3.11/3.13, Ruff and diff before committing. Official plugin-creator validator is
   not installed here; do not label the repository's checks as that validator.
   Existing isolated dev environments include PyYAML for the official Skill check.
5. Build only clean committed source; compare both Python builds byte for byte.
   Install exact wheels offline without dependencies into separate candidate
   environments. Never activate a local candidate or silently replace station pins.
6. Inspection reads at most 96 published or 74 candidate payloads
   (1 MiB/file, 4 MiB/component), bounded pin
   and venv declarations, and at most 256 package entries/component. Cost grows
   with selected bytes and entries; report warm timings and Python allocation
   measurements separately from interpreter startup, cold I/O and process RSS.
7. Analog workflow details live in docs/instrument-waveform.md; keep entrypoint
   routing short. Bind five primary inputs plus every SDS ancillary native source
   in recorded inventory order. Zero-byte RX is valid; missing RX is not. HIL
   preserves native voltage conversion, not a fresh conversion; Trace does not
   reconstruct native XML. Passing/empty filtered pages retain the full verdict.
   Native report inspection exit 0 means consistency, even for failed tests;
   check/JUnit/import return 3 for complete failure/error evidence. RMS includes
   DC and AC RMS removes only the population mean. Physical qualification and
   synchronized sample origin remain false; software provenance proves neither.
8. A Toolkit version bump also changes scripts/bootstrap.py VERSION, not only
   the two plugin manifests. Keep the version-binding regression test enabled.
9. docs/instrument-load.md owns saved-load details; entrypoint Skills route there.
   Bind seven native inputs, including plan/transcript, instead of waveform's
   source_files. Lab performs native replay; HIL checks recorded consistency/XML;
   Trace does not repeat HIL XML or native replay. Complete failures and unknown
   cleanup retain unscored readings and global verdict under every page/filter.
   Keep hardware gates scoped to hardware tests so file-only tasks do not invoke
   board doctor/discovery. Hash selection adds no per-command confirmation.
10. Validate existing published digital/waveform views with the new instrument
    environment, not just load. Reuse the already verified formal bundles rather
    than decoding or acquiring again for a Toolkit-only change. Compare new/old
    environment rejection, historical candidate mode and simulation separately.
11. docs/instrument-thermal.md owns saved thermal steps. Bind five primary inputs
    plus every original source entry in recorded inventory order, including raw
    Y16/warmup, GET, telemetry, CSV and empty stdout/stderr. HIL validates canonical
    native XML/recorded consistency; Trace does not recompute pixels, temperatures
    or XML. Preserve apparent surface units, invalid-pixel budgets, FFC/effective
    gain/resolution/mask qualifications, unknown cleanup and unscored partial frames.
    Global failure stays under passing/empty pages. No junction temperature,
    physical identity, radiometric accuracy or clock alignment is established.
12. A prior task's config.toml hash may change between user turns. Record that
    one-file drift and protect current bytes without opening contents or changing
    settings; never overwrite old sealed baselines or claim cross-turn equality.
    Existing dev313 lacks Ruff; use the already installed dev311 Ruff. No package
    installation is necessary for this task.

Cross-repository state and evidence are recorded in the workspace HANDOFF.md at
C:\Users\Nitmi\Documents\Codex\2026-08-13\guan. The desktop plan is
D:\Desktop\嵌入式-Agent-工具包开发计划.md. Preserve sealed historical evidence.
