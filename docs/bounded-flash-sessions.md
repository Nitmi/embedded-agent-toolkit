# Bounded flash sessions (design and current status)

The current `embedded-debugger flash execute --confirm <digest>` checks that
the executed plan is identical to the reviewed plan. The digest changes with
the firmware. The current Toolkit Skills additionally require a fresh user
confirmation for each physical flash. No released or local session-based
auto-flash interface exists yet. Do not interpret this design as permission
to pass a freshly copied digest without user approval.

## Intended user flow

For a firmware iteration task, the user reviews and approves one narrowly
bounded development session. Its grant binds the exact backend and debugger
executable identity, probe selector including a stable serial, target,
project/build root, allowed firmware format, write window and complete erase
window, default post-flash reset/halt/snapshot/resume policy, maximum flashes,
expiry, and a unique session nonce. Each new build has its own SHA-256 and fresh
plan. The executor, not the Agent or Toolkit test contract, checks every plan
against the grant and then passes its fresh digest to the existing confirmed
execution path. Every execution uses a unique evidence file. On success, the
Agent checks read-back verification, cleanup and, when configured, a bounded
runtime readiness assertion before the next iteration.

Any changed probe/target, source outside the approved build root, non-code
NVM, UICR/APPROTECT/security configuration, recover, whole-chip erase,
out-of-window sector erase, changed post-flash effects, unsupported plan,
expired/exhausted grant, missing evidence, or indeterminate/failed execution
halts the session. There is no automatic retry or silent new grant. The native
component's safety and target-specific capability gates remain mandatory.

## Implementation boundary

An editable JSON session file plus a counter is **not** a safe implementation:
an old copy can be restored to regain uses. A hash or user-supplied digest of
that file prevents accidental scope drift but does not stop such rollback.
Implement the lease and use counter behind a single executor process or in a
trusted non-rollbackable store with exclusive ownership and crash-consistent
commit-before-flash semantics. Reject stale clients, concurrent processes,
restarted leases, and unverifiable state. Persist a terminal stop state before
returning a failed or uncertain execution. Test file replacement, power loss,
concurrent attempts, scope drift, and firmware replacement offline with Replay
before enabling physical use. Do not expose a global `--yes` flag or relax the
existing `--confirm` path.

The Toolkit may describe the workflow and consume native structured evidence,
but must neither issue grants on its own nor present a host-only contract as
write permission. After the native implementation and Replay acceptance, the
Toolkit Skills can recognize a verified active grant; until then, per-execution
user confirmation remains required.
