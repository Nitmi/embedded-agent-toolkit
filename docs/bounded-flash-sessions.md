# Bounded flash sessions

The published `embedded-debugger 0.2.2` implements `flash session plan|inspect|serve`.
The current workstation lock still selects 0.2.1 until a separately reviewed
candidate lock is activated. Check `flash session --help` on the **exact hash-bound
debugger executable** before choosing this path. Until 0.2.2 is installed and
qualified on the intended board, keep using the per-flash confirmation workflow.

For a supported development target, create a host-only scope plan covering
the exact probe and target, canonical build directory, image format/options,
code-Flash write window and whole-sector erase window, flash count (at most
100), and duration (at most two hours). The plan also binds the debugger binary
SHA-256 and a nonce. Surface that complete scope and ask the user to approve
its `confirm_digest` **once**. Do not use a Toolkit test contract as that
approval.

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
plan, nonce and user approval. Do not remove the marker to reactivate an old
grant.

This is a trusted local development workflow, not protection against a user
deliberately deleting or editing the plan and marker. A copied plan is rejected
because the original absolute path is in its digest. Refer to the debugger
source document `docs/flash-sessions.md` for command details; no physical
board acceptance is claimed here.
