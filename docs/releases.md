# Versioned releases

## Contents and scope

The `0.6.0` release is a portable **plugin-only** ZIP. It contains the four
orchestration Skills, their references, host-only scripts, user documentation,
license, and both plugin manifests. Component executables, component MCP servers,
Git internals, tests, local hardware evidence, and build outputs are not bundled.
Use Python 3.11 or newer for the release commands; only the standard library is
required. The debugger's offline runtime setup commands are versioned in
`embedded-debugger 0.2.0`; install that component separately.

The archive has a single `embedded-agent-toolkit` root. Its
`release-manifest.json` binds the source commit and every payload file's SHA-256
and byte count. ZIP member order, permissions, and timestamps are fixed. Entries
are stored without compression, making identical commit inputs byte-for-byte
reproducible without depending on a compression-library version. Development
cachebuster suffixes are removed from the packaged manifests, not from installed
Codex settings.

## Build locally

After tests and a cohesive commit, from this repository:

```powershell
python scripts/release.py build --output-dir dist --json
python scripts/release.py verify dist/embedded-agent-toolkit-0.6.0.zip --checksum dist/embedded-agent-toolkit-0.6.0.zip.sha256 --json
```

The builder requires a clean worktree and reads pinned Git blobs rather than
checkout files, so Windows line-ending conversion cannot change the package.
It refuses existing release outputs; use another output directory to reproduce
a build. Neither command accesses hardware. Building does not create a Git tag,
push commits, or publish a remote release.

## Bootstrap without cloning

Each tagged release publishes `bootstrap.py` as a separately attested asset.
Download and authenticate the script before executing it:

```powershell
gh release download v0.6.0 --repo Nitmi/embedded-agent-toolkit `
  --pattern bootstrap.py
gh attestation verify bootstrap.py `
  --repo Nitmi/embedded-agent-toolkit `
  --source-ref refs/tags/v0.6.0 `
  --signer-workflow Nitmi/embedded-agent-toolkit/.github/workflows/release-attestation.yml `
  --deny-self-hosted-runners
python bootstrap.py --install-root C:\Tools\embedded-agent-toolkit --json
```

Keep the exact `bootstrap.py` filename because it is part of the attestation
subject. The bootstrap requires Python 3.11+, an authenticated GitHub CLI, and
network access to GitHub. It verifies its own bytes again, downloads the exact
release ZIP and checksum into a temporary directory with strict size and redirect
limits, verifies the archive's attestation, requires both attestations to name
the same tag commit, and extracts only the fixed installer scripts before running
the existing package installer. Downloads and extracted scripts are deleted when
the command exits.

The optional `--lock-output`, `--baud`, `--blea`, and `--debugger` arguments must
be supplied together. When supplied, the final installer invokes those three
executables only with `--version`, creates the component lock, and runs strict
doctor. No device discovery or hardware access occurs.

## Install a downloaded version manually

Use the release script from a trusted source checkout. Obtain the ZIP and its
checksum from a trusted channel, then install into a directory you own:

```powershell
python scripts/release.py install dist/embedded-agent-toolkit-0.6.0.zip `
  --checksum dist/embedded-agent-toolkit-0.6.0.zip.sha256 `
  --install-root C:\Tools\embedded-agent-toolkit `
  --lock-output C:\Tools\embedded-agent-toolkit\component-locks\workstation.json `
  --baud C:\Users\you\.local\bin\baud.exe `
  --blea C:\Users\you\.local\bin\ble.exe `
  --debugger C:\Tools\embedded-debugger\embedded-debugger.exe `
  --json
```

This creates `C:\Tools\embedded-agent-toolkit\0.6.0\embedded-agent-toolkit`,
then creates the requested component lock and runs strict doctor against the
installed plugin. The three component executables are invoked only with
`--version`; no hardware command is run. All four setup options (`--lock-output`,
`--baud`, `--blea`, and `--debugger`) are optional as a group: omit all four to
perform plugin-only installation with the earlier behavior.

An existing lock is rejected before installation and is never overwritten. If
strict doctor fails after a new lock is created, that lock is removed; the
verified, inactive version directory is retained for diagnosis. The combined
command does not activate Codex, install component CLIs, edit PATH or persistent
environment variables, modify marketplaces, or launch MCP servers.

On another OS, choose an appropriate explicit install root. Archive validation
completes before installation begins: the checksum, manifest inventory, member hashes,
sizes, versions, paths, regular-file types, and plugin service boundaries must
all pass. Traversal, absolute paths, Windows alternate streams/reserved names,
case collisions, links, and extra archive members are rejected.

An identical existing version returns `already_installed`. A modified or
incomplete directory is never merged or overwritten. An I/O failure can leave
a partial new directory; it remains inactive and is retained for inspection.
No cleanup of old versions or user files happens automatically.

Installation here means verified local files, **not activation in Codex**. The
installer does not execute anything from the ZIP, install CLIs, edit PATH,
modify marketplaces, or launch MCP servers. Add the returned `plugin_path` as
a local plugin through your Agent host's supported installation flow. Do not
select its parent version directory. Keep BLEA's component MCP registration in
the BLEA plugin, and debug-target configuration in the project.

## Upgrade and roll back

Install a later release under the same install root. Each version occupies a
separate directory; the prior version is retained. Activate the new plugin path
in the host and use a new task to load its Skills. To roll back, select the old
path again. These commands deliberately do not switch the active plugin.

For an existing source-backed personal marketplace, updating that source and
reinstalling its existing entry is a separate development workflow; extracting
a release elsewhere does not redirect the marketplace or refresh its cache.
Do not edit marketplace files to pretend the new package is already active.

Run the installed `scripts/toolkit_doctor.py --strict --json` after configuring
component executables. Doctor is host-only; it reports actual CLI versions and
layout readiness, not firmware readiness or hardware compatibility.

SHA-256 detects changed content relative to the supplied checksum. A checksum
delivered with a maliciously replaced archive is not publisher authentication.
For tagged GitHub builds, verify the repository-bound artifact attestation as
described in [release provenance](provenance.md). Until that remote workflow has
successfully run, a local candidate has integrity evidence but no GitHub
attestation. Artifact provenance is not Windows code signing.
