# Release provenance

## What is attested

The release provenance workflow accepts an existing exact
`vMAJOR.MINOR.PATCH` tag, checks that it matches both plugin manifests, runs the
test suite, builds the plugin ZIP twice, and rejects different outputs. It then
verifies the selected ZIP and submits its SHA-256 as the subject of a GitHub
artifact attestation using `actions/attest`.

The workflow pins every external Action to a full commit SHA. Its token can read
repository contents and write attestations and artifact metadata, but cannot
write repository contents or create a GitHub Release. Pull requests cannot
trigger it. Manual runs must name an existing version tag, which is checked out
and must resolve to the current commit as well as match the plugin version before
building.

## Verify a downloaded archive

After the workflow has successfully produced an attestation in the expected
repository, verify both the repository identity and the downloaded ZIP:

```powershell
gh attestation verify embedded-agent-toolkit-0.5.0.zip `
  --repo Nitmi/embedded-agent-toolkit
```

Only proceed when verification succeeds and the reported subject digest matches
the file being installed. The adjacent `.sha256` remains useful for transport
integrity, but it is not a substitute for repository-bound provenance.

## Trust boundary

An attestation proves that a particular GitHub Actions workflow in the named
repository produced the exact archive from the recorded source revision. It is
not Windows Authenticode signing, malware analysis, a firmware signature, or a
claim that component binaries are included. Local builds and artifacts created
before a successful remote workflow run have no GitHub attestation.
