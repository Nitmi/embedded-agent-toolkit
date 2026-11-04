# Toolkit development handoff

Read this file and AGENTS.md before starting another task.

## Current local work

- Local0.41.0 on feat/published-gpiote-simulation routes published sim0.13 /
  HIL0.18 / Trace0.18:108 files (40/37/31). Instruments retain lab0.11/HIL0.12,
  using the same Trace0.18 for99 files; standalone31. Pins derive from formal
  wheel bytes and24 completed genuine checks in D:/Code/tmp/gpiote-release-20261103.
  This task adds no signature verifier, executor, MCP or per-case confirmation.
- Read docs/simulation-gpiote.md. Preserve CONFIG/current-state, GPIO input,
  event, pin-level ISR and fault request spans; nominal faults remain failed,
  BUILD mismatch keeps model observations and timeout stays unknown. TASKS_OUT,
  PORT/SENSE/LATCH/DETECTMODE/PPI/electrical/physical timing remain unqualified.
  Trace0.17 admits EGU but not GPIOTE; older layouts remain explicit.
- Acceptance root D:/Code/tmp/toolkit-gpiote-0410-20261104. Reuse formal
  gpiote-0130-0180-0180/joint311 and joint313 and saved31 GPIOTE results;
  do not repeat native runs or component cold installs. New isolated instrument
  environments and candidate plugin installs are local only. Toolkit/plugin0.40,
  station/locks/PATH and existing environments remain unchanged.
- Use skill-creator for three short routes to one guide; include the guide in
  release.REQUIRED_FILES and keep both manifests/bootstrap at0.41.0. Current
  source, package, compatibility and cost checks must finish before claiming
  acceptance. Initial host reads guessed a missing fixture README; actual
  native guide is sim-runner/docs/nrf52840-gpiote.md. One multi-file patch had
  an incorrect simulation.md header and was rejected atomically; no partial
  guide was created. Corrected with exact source context. Broad reads were
  truncated; use focused ranges. Preserve these as host issues, not failures
  of simulation or physical evidence. Review current-selection replacements
  separately from historical introduction versions in docs/embedded-trace.md.
- First Python3.11 full run reached282 tests with two failing subtests: the
  instrument Windows/POSIX fixtures still expected current Trace0.17 instead
  of0.18. Updated only that stale expectation; original tests-311 output remains.
  New complete runs use tests-final-311/313, never overwrite the failed result.
  An auxiliary progress read tried buffered stderr before call completion;
  the file was not created yet. Wait for the controlled receipt instead.
- The one-line fixture patch introduced extra indentation. format-final exited1
  before another test run; Ruff formatting corrected it. Preserve this output,
  use format-fixed for the completed check and do not replay passed lint.
- Final Python3.11/3.13 suites each282 tests:279 passed/three existing platform
  skips. Ruff/format/diff, repository plugin layout/release identity and four
  official Skill validators passed. Both existing formal joint environments'
  31 GPIOTE saved results match full baseline hashes; each new instrument
  environment preserves52 views from26 old bundles after root viewer_version
  normalization only. Candidate package/installation and static inspection
  cost remain tracked in the execution root; no public write or activation.

- Local0.40.0 on feat/published-egu-simulation routes published sim0.12 /
  HIL0.17 / Trace0.17:105 files (38/37/30). Instruments retain lab0.11/HIL0.12
  with the same Trace0.17,98 files; standalone30. Exact wheel bytes and the
  completed24 genuine signature checks come from D:/Code/tmp/egu-release-20261103.
  Static readers do not verify signatures or authenticate interpreters.
- Read docs/simulation-egu.md. Native sim owns EGU policy; HIL preserves
  preflight/fail-stop/cleanup; Trace preserves PRE/POST, ISR and request spans,
  including bounded asynchronous INFO. A fault effect can be observed while
  nominal stays failed. Unknowns and wrong-BUILD model snapshots stay explicit.
  No PPI, guest producer, all-channel or physical IRQ timing claim follows.
- Historical Trace layouts remain explicit:0.16 admits rtc.py but no egu.py;
  0.13.1/0.14/0.15 admit neither. Candidate69/74 inventories, native catalog /
  managed HIL pins and station selections remain independent. The active
  Toolkit/plugin0.39 and old environments are not changed by this local task.
- Acceptance work is D:/Code/tmp/toolkit-egu-0400-20261103. Source checks,
  dual builds/candidate installs,105/98/30 static readers,31 saved EGU operations
  and26 instrument bundles/52 views per Python are tracked there. Consult its
  final completed.json before claiming them complete. Reuse the two formal EGU
  joint environments; do not repeat native captures or component cold installs.
- This task uses skill-creator for three short EGU routes to one guide; no
  executor/MCP or extra per-case confirmation is added. Keep the EGU guide in
  release.REQUIRED_FILES and bootstrap/manifests at0.40.0.
- Source Python3.11/3.13 suites each ran281 tests:278 passed/three existing
  platform skips. Ruff/format, repository plugin layout/release identity and
  four official Skill validators passed. No official plugin-creator validator
  is installed; do not label the repository layout check as that validator.
  Candidate builds/installs, saved evidence and cost are tracked separately.
- An initial auxiliary rg used an unexpanded Windows docs/simulation*.md
  argument and failed. Use `rg ... docs -g 'simulation*.md'` instead. Earlier
  combined reads truncated; inspect focused ranges and keep output bounded.

- Local0.39.0 on feat/published-rtc-simulation routes published sim0.11 /
  HIL0.16 / Trace0.16,102 files (36/37/29). Instruments retain lab0.11/HIL0.12
  and select that same Trace0.16 wheel/source,97 files; standalone29. Pins come
  from formal wheel bytes and completed24 genuine GitHub signature results in
  D:/Code/tmp/rtc-release-20261102, not a new network verification. Reuse the two
  formal rtc-0110-0160-0160 joint environments; old installations stay intact.
- Read docs/simulation-rtc.md. Native sim owns the RTC verdict; HIL preserves
  preflight/fail-stop/cleanup; Trace preserves ordered counter/event/compare/IRQ
  spans, raw snapshots and a separate request marker. Observed stop/mask effects
  remain failed nominal regressions. BUILD mismatch parses no samples; timeout
  nulls remain unknown. No LFCLK, overflow/wrap, PPI, sleep/power/wakeup or
  physical clock qualification, executor/MCP or per-run confirmation is added.
- Published readers admit exact new RTC source/model inventories. Standalone
  retains audited0.1/0.13.1/0.14/0.15 layouts and admits rtc.py only at0.16;
  a matching version string never expands an older layout. Historical69/74,
  native catalog/managed HIL pins, station/locks/PATH and active Toolkit/plugin
  0.38 are independent. This task does not publish or activate Toolkit.
- Acceptance root D:/Code/tmp/toolkit-rtc-0390-20261102 owns source checks,
  clean-source builds, two candidate plugin installs,102/97/29 static checks,
  saved31 RTC results and26 instrument bundles/52 views per Python. Use its
  final completed.json before claiming later steps complete. No native captures
  or component formal cold installations are repeated. The RTC guide stays in
  release.REQUIRED_FILES; bootstrap and manifests are0.39.0.
- Initial auxiliary reads included a nonexistent pyproject.toml and an unexpanded
  PowerShell glob for rg. The repository has no pyproject; use actual files and
  rg -g filters. Wide combined output truncated; subsequent targeted reads
  recover actual content. These are host read errors, not evidence failures.
- Python3.11/3.13 final suites each ran280 tests,277 passed/three existing skips;
  Ruff/format, repository plugin layout/release identity and four official Skill
  validators passed. The official plugin-creator validator is absent. Each
  Python's31 RTC saved results match complete formal hashes, and26 instrument
  bundles retain52 full/empty views after only root viewer_version normalization.
  A new RTC inspection negative was initially placed in TracePinAndCliTests,
  which has no inspection fixture; move fixture-dependent tests to
  TraceInspectionTests. The initial AttributeError remains in tests-311 logs;
  both corrected complete suites pass, with no evidence or simulator retry.

- Local0.38.0 on feat/published-watchdog-simulation routes the released watchdog
  profile and independent plan/report schemas. Published selection is sim0.10 /
  HIL0.15 / Trace0.15 with99 files (34/37/28). Instrument lab0.11/HIL0.12 stays
  fixed; only its Trace changes to the same0.15 wheel/source,96 files; standalone28.
  Pins are generated from actual formal wheel bytes, bound to the completed24
  real GitHub signature results. The previous release is not re-published or
  re-installed. Reuse its joint311/joint313 environments and saved31 watchdog
  results; only new isolated instrument and Toolkit candidate installs are needed.
- Read docs/simulation-watchdog.md. Keep native sim verdicts, HIL preflight /
  fail-stop / cleanup and Trace raw model/reset/callback/guest spans separate.
  An observed fault cannot turn a failed nominal regression into a pass; timeout
  remains unknown. Model resets, CONFIG tags and guest reboot markers establish
  no physical reset, power, protection or complete-model qualification. Three
  Skills gain short routes; no executor, MCP or per-run confirmation is added.
- Historical candidate69/74 inventories, native catalog/managed pins, active
  Toolkit/plugin0.37, workstation selection/locks/PATH and old environments are
  independent. Standalone retains explicit audited0.1/0.13.1/0.14 layouts and
  adds0.15 only, not arbitrary semver. Missing/drifted watchdog code/model or a
  coherent previous0.9/0.14/0.14 selection must fail without fallback.
- Local acceptance D:/Code/tmp/toolkit-watchdog-0380-20261030 owns source checks,
  clean dual builds, two candidate plugin installs,99/96/28 static checks,
  saved watchdog/instrument compatibility and measured cost. Read its final
  completed.json for actual completion; this integration does not publish or
  activate Toolkit or rerun native simulation/captures. The new watchdog guide
  must stay in release.REQUIRED_FILES; bootstrap and manifests are0.38.0.
- Source qualification on3.11/3.13 each ran279 tests,276 passed/three existing
  platform skips; Ruff/format, repository plugin layout/release identity and
  four official Skill validators passed. The official plugin-creator validator
  is absent. Saved31 watchdog results per Python match complete frozen hashes;
  26 existing instrument bundles retain52 full/empty views per Python after
  normalizing only the root viewer_version. Native captures were not repeated.
- Harness reuse pitfall: a bulk version replacement also changed the historical
  instrument-candidate path in the temporary helper. It was corrected before
  any candidate checks; the source historical pin and installed environment were
  never modified. Preserve instrument project fields when regenerating Trace.

- Local0.37.0 on feat/published-spi-simulation adds SPI0/LM74 routing. The
  simulation default selects authenticated published sim0.9/HIL0.14/Trace0.14
  and97 payloads; instruments retain lab0.11/HIL0.12 with the same Trace0.14
  and96 files; standalone28. Formal wheel bytes and original24 GitHub signature
  results are reused from the completed three-component release, not replaced
  by candidate metadata or new network validation. Read docs/simulation-spi.md.
- Keep independent native SPI plan/report schemas, signed Q4/two-byte words,
  four model observations and spi_frame_slip_span. Native sim owns assertions;
  HIL preserves fail-stop/cleanup; Trace preserves failed/unknown full/sample/
  empty results without a second executor or physical fallback. The fixed
  monitor Transmit call consumes a model byte, not an electrical bus glitch.
- Current source tests on Python3.11/3.13 each279,276 passed/three existing
  symlink skips; Ruff/format, repository plugin layout/release identity and all
  four official Skill validators pass. The official plugin-creator validator
  remains absent. Three short Skill routes use one SPI guide, which must stay
  in release.REQUIRED_FILES. Bootstrap VERSION and both manifests are0.37.0.
- Historical candidate69/74, native component catalog, managed HIL pins,
  active Toolkit0.36.1/plugin, workstation locks/PATH and old environments stay
  independent. Local acceptance D:/Code/tmp/toolkit-spi-0370-20261030 owns later
  clean-source dual builds, candidate installs, mode rejection, saved31 SPI
  results and26 instrument bundles/52 views per Python. Consult completed.json
  for completion; do not rerun native captures or public release stages.
- New pin generation must preserve each domain's schema. Instrument components
  retain project in addition to repository/source_ref; replacing one with a
  simulation component object drops that required field. The first generator
  stopped before writing the instrument pin; corrected to update its fields
  and regenerated deterministic pins. Ruff found one new dict() literal rule;
  fixed directly, raw lint failure retained. No runtime check was relaxed.
- A coherent older release pin, including matching tag/URL/metadata and old
  inventory, still cannot satisfy the new simulation default. Missing/drifted
  SPI source/model files fail, as do SPI files added to historical candidates.
  Standalone explicitly retains audited0.1/0.13.1 layouts, not arbitrary semver.

- Local 0.36.1 on fix/trace-0131-runtime-pins selects the authenticated Trace
  0.13.1 wheel (c28cf02) for standalone, simulation and instrument inspection.
  Inventories are 28 standalone, 95 simulation (sim0.8/HIL0.13/Trace0.13.1),
  and 96 instrument (lab0.11/HIL0.12/Trace0.13.1) files. Other components and
  historical 69/74-file candidate pins are unchanged. Do not conflate a directory
  containing published wheels with the explicit historical --candidate mode.
- The standalone reader has audited per-version inventories for legacy0.1 and
  current0.13.1. A version-looking string cannot expand the reviewed inventory;
  walking accepts only the selected pin's package files. All three current
  routes bind identical Trace bytes/metadata; an old environment must fail the
  new default rather than fall back. Static inspections never start/import the
  selected interpreter/components or turn provenance/runtime/physical flags true.
- Two Python versions each ran277 source tests:274 passed/three existing platform
  skips. Ruff/format, all four official Skill validators and repository plugin
  layout/release identity passed. The official plugin-creator validator is absent;
  retain that distinction. No Skill content or hardware confirmation rule changed.
- Separate new simulation/instrument environments on3.11/3.13 install the exact
  formal wheels offline without dependencies. Saved26 digital/waveform/load/
  thermal bundles retain52 full/empty views per Python, matching Trace0.12 after
  normalizing only root viewer_version; twelve saved sensor views per Python
  match their complete Trace0.13.1 hashes. No native decoding/capture is repeated.
- Local acceptance D:\Code\tmp\toolkit-trace-0361-20261030 owns later clean-source
  builds, candidate installation, mode rejection and cost records. Use its final
  completed receipt. Active Toolkit0.36, station/locks/PATH and old environments
  stay unchanged; this task does not publish or activate Toolkit.
- Pitfalls: instrument '*-import.json' files are import specs, not normalized
  bundles. Compare explicit case/bundle.json files against prior result.json
  SHA-256s. Initial wrapper failure read only a spec; preserve that log. Ruff
  first rejected two formatting changes; corrected format passes. PowerShell
  passes literal glob path arguments to rg; use an explicit directory plus -g.
  Large combined reads can be display-truncated; use small selected regions or
  structured fields, never infer validation from a truncated result.

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
6. Inspection reads at most97 simulation,96 instrument or28 standalone payloads;
   historical simulation/instrument candidates retain69/74 payloads
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
