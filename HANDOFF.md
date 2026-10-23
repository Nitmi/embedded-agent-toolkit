# Toolkit development handoff

Read this file and AGENTS.md before starting another task.

## Current local work

- Version 0.32.0 adds optional **offline** instrument routing and static payload
  inspection for lab-instruments 0.8.0, HIL Runner 0.9.0 and Embedded Trace 0.9.0.
  Published source/tag/repository/URL/wheel identities and 74 installed files are
  bound in instrument-runtime.json. instrument-candidates.json retains historical
  local builds, selected only with --candidate; never silently fall back.
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
   Lab's official source is a772f805, not the earlier 3cc861f/335b178 preparation.
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
6. Inspection reads at most 74 payloads (1 MiB/file, 4 MiB/component), bounded pin
   and venv declarations, and at most 256 package entries/component. Cost grows
   with selected bytes and entries; report warm timings and Python allocation
   measurements separately from interpreter startup, cold I/O and process RSS.

Cross-repository state and evidence are recorded in the workspace HANDOFF.md at
C:\Users\Nitmi\Documents\Codex\2026-08-13\guan. The desktop plan is
D:\Desktop\嵌入式-Agent-工具包开发计划.md. Preserve sealed historical evidence.
