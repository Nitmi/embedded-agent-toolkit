# Toolkit development handoff

Read this file and AGENTS.md before starting another task.

## Current local work

- Version 0.33.0 routes saved analog waveform checks alongside digital checks.
  instrument-runtime.json binds published lab-instruments 0.9.0 (5eb1e8e5),
  HIL Runner 0.10.0 (f5063e3e), Trace 0.10.0 (3154e735), exact release wheel
  identities and 80 installed files. The historical instrument-candidates.json
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
   verifier 0.9 accepts producer 0.7/0.8/0.9, verifier 0.8 accepts 0.7/0.8 only.
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
6. Inspection reads at most 80 published or 74 candidate payloads
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

Cross-repository state and evidence are recorded in the workspace HANDOFF.md at
C:\Users\Nitmi\Documents\Codex\2026-08-13\guan. The desktop plan is
D:\Desktop\嵌入式-Agent-工具包开发计划.md. Preserve sealed historical evidence.
