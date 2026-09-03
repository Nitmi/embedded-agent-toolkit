# Identity ledger

Use an identity ledger when a firmware diagnosis combines more than one
transport, tool operation, or observation window. The ledger prevents a valid
point-in-time result from silently becoming a claim about another time or
interface.

## Evidence states

- `observed`: a named artifact directly supports the claim inside its recorded
  window.
- `documented`: project or device documentation states the expected value, but
  the running device has not proved it.
- `inferred`: the claim follows only when listed assumptions hold.
- `rejected`: evidence contradicts the claim or its required assumptions.
- `unknown`: available evidence does not decide the claim.

Do not use confidence words as a replacement for these states. An inferred
claim must list its assumptions and a rejected claim must identify the
contradicting observations.

## Required ledger content

Record:

1. A schema version, generation date, offline/live mode, and the diagnostic
   question.
2. Every source artifact with its path, SHA-256, observation time or validity
   window, tool, and whether it is point-in-time evidence.
3. Separate identities for each serial interface, debug probe, BLE peripheral,
   target/core, local firmware artifact, and runtime firmware observation.
4. Relationships with one of the evidence states above. Every observed,
   documented, inferred, or rejected claim must list the exact supporting
   source IDs; unknown claims may omit sources when no artifact bears on them.
   Matching VID/PID and serial values may associate interfaces of one USB
   composite device; they do not prove silicon identity, target state, or
   firmware identity.
5. Observations and derived comparisons, including timestamp uncertainty and
   transport buffering where relevant.
6. Accepted, rejected, and still-possible hypotheses.
7. The least invasive next experiment, with any new authorization boundary.

## Time and continuity rules

Runtime firmware identity, core state, memory contents, breakpoints,
watchpoints, and liveness are valid only for their observation window. Keep a
historical verified identity distinct from the current identity unless one
operation binds both or fresh evidence re-attests it.

Before treating a counter rollback as a reset signal, record its initial value,
integer width, update rule, expected cadence, and whether wrap is plausible in
the elapsed interval. If rollback cannot be explained by wrap, reject
uninterrupted counter continuity. Report the cause as a disjunction unless
another artifact distinguishes reset, power loss, reflash, alternate firmware,
or a different device.

A serial pattern that matches local source behavior is compatibility evidence,
not a build identity. A local ELF hash matching an earlier target descriptor is
historical runtime evidence only until the current target is re-attested.

A periodic serial record can provide current build correlation when it carries
an exact final-artifact hash from runtime-patched or post-link metadata. Bind
that hash to a freshly enumerated physical serial identity and record the
monitor window. This is point-in-time runtime evidence, not signed attestation;
firmware-controlled output cannot defend against a malicious or corrupted image
that deliberately reports another hash. See
[serial-firmware-identity.md](serial-firmware-identity.md) for the guarded
workflow.

## Closeout

Hash the completed ledger and its human report. State which source artifacts
were not copied, whether any hardware operation occurred while building the
ledger, and whether the proposed next experiment requires a fresh plan or
confirmation. When this toolkit checkout is available, validate the machine
ledger with `python scripts/validate_identity_ledger.py <ledger.json> --json`.
The validator checks schema, source identity, claim-to-source references,
evidence-state requirements, and unique IDs without opening any hardware.
Never treat the ledger itself as
authorization for a target operation.
