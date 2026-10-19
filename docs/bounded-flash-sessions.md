# Bounded flash sessions

`embedded-debugger 0.2.2+` implements `flash session plan|inspect|serve`.
Toolkit 0.24.0's catalog pins 0.2.5; the actual selected component lock remains
authoritative. Check `flash session --help` on the exact hash-bound executable.
For continuous flash/runtime loops with shared-board ownership, use the
[optional HIL Runner workflow](hil-runner.md), qualified against debugger 0.2.5.
Direct native sessions remain useful without that coordinator.

For a supported development target, create a host-only scope plan covering
the exact probe and target, canonical build directory, image format/options,
code-Flash write window and whole-sector erase window, flash count (at most
100), and duration (at most two hours). The plan also binds the debugger binary
SHA-256 and a nonce. Surface that complete scope and reuse the user's task
authorization when it already covers the bounded run. Obtain any missing scope
approval once; the native digest is a machine binding, not a request to copy
every new build hash. Do not use a Toolkit test contract as authorization.

Start `flash session serve <scope-file> --confirm <approved-scope-digest>`
as a long-lived debugger process. It accepts one JSONL `flash` request per
new build, containing only the firmware and a unique evidence path. The native
executor recomputes the current plan and its digest, checks exact identities,
image format, write and erase windows, target capability gates, and evidence
before it calls the original confirmed execution path. On each success, inspect
verification and cleanup evidence; correlate a bounded runtime readiness
assertion before moving to the next build. The Agent does not ask the user to
copy every new firmware digest.

Any scope drift, unsupported image, UICR/APPROTECT/security write, non-boot
NVM, out-of-window erase, failure or indeterminate result ends the executor
without retry. The grant also ends on expiry, count exhaustion, process exit,
or explicit close. The original scope path gets a persistent `.active`
marker on first start; it cannot be started again. A new session needs a new
plan and nonce. Existing task authorization can cover the new scope only when
its effects and limits remain covered; re-confirm an uncovered or changed scope,
not each ordinary build. Do not remove the marker to reactivate an old grant.

This is a trusted local development workflow, not protection against a user
deliberately deleting or editing the plan and marker. A copied plan is rejected
because the original absolute path is in its digest. Refer to the debugger
source document `docs/flash-sessions.md` for command details; no physical
board acceptance is claimed here.
