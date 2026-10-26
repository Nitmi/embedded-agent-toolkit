# Toolkit development handoff

Read this file and AGENTS.md before starting another task.

## Current local work

- Local version 0.34.0 routes saved SDL load assertions alongside digital/analog
  checks. instrument-runtime.json binds published lab0.10 (b953725f), HIL0.11
  (28bd2275), Trace0.11 (029233a8), exact release wheel identities and 88 files.
  Trace's initial 9b6bc76 candidate is not its final published source; the test-only
  CI correction preserves wheel bytes, but source provenance must bind 029233a8.
  Toolkit0.33 is already published and remains the active workstation plugin.
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
   Digital verifier0.10 accepts producers0.7/0.8/0.9/0.10, verifier0.9 accepts
   0.7/0.8/0.9, verifier0.8 accepts 0.7/0.8. Waveform verifier0.10 accepts
   producers0.9/0.10. Load producer/verifier must be0.10. Never relabel sources.
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
6. Inspection reads at most 88 published or 74 candidate payloads
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

Cross-repository state and evidence are recorded in the workspace HANDOFF.md at
C:\Users\Nitmi\Documents\Codex\2026-08-13\guan. The desktop plan is
D:\Desktop\嵌入式-Agent-工具包开发计划.md. Preserve sealed historical evidence.
