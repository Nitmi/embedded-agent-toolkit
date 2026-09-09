#!/usr/bin/env python3
"""Download, authenticate, and install one exact toolkit release."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

PLUGIN = "embedded-agent-toolkit"
REPOSITORY = "Nitmi/embedded-agent-toolkit"
VERSION = "0.6.0"
TAG = f"v{VERSION}"
SOURCE_REF = f"refs/tags/{TAG}"
SIGNER_WORKFLOW = f"{REPOSITORY}/.github/workflows/release-attestation.yml"
SCHEMA = "embedded-agent-toolkit.bootstrap.v1"
MAX_ARCHIVE_BYTES = 16 * 1024 * 1024
MAX_CHECKSUM_BYTES = 4096
MAX_SCRIPT_BYTES = 1024 * 1024
INSTALLER_SCRIPTS = (
    "scripts/release.py",
    "scripts/component_lock.py",
    "scripts/toolkit_doctor.py",
)
ALLOWED_DOWNLOAD_HOSTS = {
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
}


class BootstrapError(ValueError):
    pass


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def release_url(name: str) -> str:
    return f"https://github.com/{REPOSITORY}/releases/download/{TAG}/{name}"


def download(url: str, destination: Path, limit: int, timeout: float) -> None:
    request = urllib.request.Request(
        url, headers={"User-Agent": f"{PLUGIN}-bootstrap/{VERSION}"}
    )
    created = False
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            hostname = (urllib.parse.urlparse(response.geturl()).hostname or "").lower()
            if hostname not in ALLOWED_DOWNLOAD_HOSTS:
                raise BootstrapError(
                    f"Release download redirected to untrusted host: {hostname}"
                )
            declared = response.headers.get("Content-Length")
            if declared is not None:
                try:
                    declared_size = int(declared)
                except ValueError as error:
                    raise BootstrapError("Release download has invalid size") from error
                if declared_size < 0 or declared_size > limit:
                    raise BootstrapError("Release download exceeds size limit")
            total = 0
            with destination.open("xb") as output:
                created = True
                while True:
                    chunk = response.read(min(1024 * 1024, limit + 1 - total))
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > limit:
                        raise BootstrapError("Release download exceeds size limit")
                    output.write(chunk)
    except Exception:
        if created:
            destination.unlink(missing_ok=True)
        raise


def expected_checksum(checksum: Path, archive_name: str) -> str:
    if checksum.stat().st_size > MAX_CHECKSUM_BYTES:
        raise BootstrapError("Checksum file exceeds size limit")
    line = checksum.read_text(encoding="ascii")
    match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9._-]+)\n?", line)
    if match is None or match.group(2) != archive_name:
        raise BootstrapError("Checksum file does not name the exact release archive")
    return match.group(1)


def gh_executable(value: Path | None) -> Path:
    candidate = str(value) if value is not None else shutil.which("gh")
    if not candidate:
        raise BootstrapError("GitHub CLI (gh) is required for attestation verification")
    path = Path(candidate).resolve()
    if not path.is_file():
        raise BootstrapError(f"GitHub CLI is not a regular file: {path}")
    return path


def verify_attestation(path: Path, gh: Path, timeout: float) -> dict:
    command = [
        str(gh),
        "attestation",
        "verify",
        str(path),
        "--repo",
        REPOSITORY,
        "--source-ref",
        SOURCE_REF,
        "--signer-workflow",
        SIGNER_WORKFLOW,
        "--deny-self-hosted-runners",
        "--format",
        "json",
    ]
    process = subprocess.run(
        command, capture_output=True, text=True, timeout=timeout, check=False
    )
    if process.returncode:
        detail = process.stderr.strip() or process.stdout.strip()
        raise BootstrapError(f"Attestation verification failed: {detail}")
    try:
        results = json.loads(process.stdout)
    except json.JSONDecodeError as error:
        raise BootstrapError("GitHub CLI returned invalid attestation JSON") from error
    if not isinstance(results, list) or not results:
        raise BootstrapError("GitHub CLI returned no verified attestation")

    actual_digest = sha256(path)
    for result in results:
        try:
            verification = result["verificationResult"]
            certificate = verification["signature"]["certificate"]
            subjects = verification["statement"]["subject"]
            timestamps = verification["verifiedTimestamps"]
        except (KeyError, TypeError):
            continue
        if not isinstance(certificate, dict) or not isinstance(subjects, list):
            continue
        subject_ok = any(
            isinstance(subject, dict)
            and subject.get("name") == path.name
            and isinstance(subject.get("digest"), dict)
            and subject["digest"].get("sha256") == actual_digest
            for subject in subjects
        )
        source_digest = certificate.get("sourceRepositoryDigest")
        if (
            subject_ok
            and certificate.get("sourceRepositoryRef") == SOURCE_REF
            and certificate.get("githubWorkflowTrigger") == "push"
            and certificate.get("githubWorkflowRepository") == REPOSITORY
            and certificate.get("runnerEnvironment") == "github-hosted"
            and isinstance(source_digest, str)
            and re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", source_digest)
            and certificate.get("githubWorkflowSHA") == source_digest
            and certificate.get("buildSignerDigest") == source_digest
            and isinstance(timestamps, list)
            and timestamps
        ):
            return {
                "subject": path.name,
                "sha256": actual_digest,
                "source_ref": SOURCE_REF,
                "source_revision": source_digest,
                "workflow_trigger": "push",
                "runner_environment": "github-hosted",
            }
    raise BootstrapError("Verified attestation does not satisfy bootstrap policy")


def extract_installer(archive: Path, destination: Path) -> Path:
    with zipfile.ZipFile(archive) as package:
        for relative in INSTALLER_SCRIPTS:
            member = f"{PLUGIN}/{relative}"
            try:
                info = package.getinfo(member)
            except KeyError as error:
                raise BootstrapError(
                    f"Release is missing installer file: {relative}"
                ) from error
            if info.is_dir() or info.file_size > MAX_SCRIPT_BYTES:
                raise BootstrapError(f"Invalid installer file: {relative}")
            output = destination / Path(relative).name
            with output.open("xb") as handle:
                handle.write(package.read(info))
    return destination / "release.py"


def run_installer(
    installer: Path,
    archive: Path,
    checksum: Path,
    install_root: Path,
    setup: dict[str, str | Path | None],
    timeout: float,
) -> dict:
    command = [
        sys.executable,
        str(installer),
        "install",
        str(archive),
        "--checksum",
        str(checksum),
        "--install-root",
        str(install_root),
        "--json",
    ]
    if any(value is not None for value in setup.values()):
        if any(value is None for value in setup.values()):
            raise BootstrapError(
                "--lock-output, --baud, --blea, and --debugger are required together"
            )
        command.extend(
            [
                "--lock-output",
                str(setup["lock_output"]),
                "--baud",
                str(setup["baud"]),
                "--blea",
                str(setup["blea"]),
                "--debugger",
                str(setup["debugger"]),
                "--timeout",
                str(timeout),
            ]
        )
    process = subprocess.run(
        command, capture_output=True, text=True, timeout=timeout + 30, check=False
    )
    if process.returncode:
        detail = process.stdout.strip() or process.stderr.strip()
        raise BootstrapError(f"Release installer failed: {detail}")
    try:
        report = json.loads(process.stdout)
    except json.JSONDecodeError as error:
        raise BootstrapError("Release installer returned invalid JSON") from error
    if not isinstance(report, dict) or not report.get("ok"):
        raise BootstrapError("Release installer did not report success")
    if report.get("hardware_access") is not False:
        raise BootstrapError(
            "Release installer did not preserve the host-only contract"
        )
    return report


def bootstrap(
    install_root: Path,
    gh: Path,
    setup: dict[str, str | Path | None],
    timeout: float,
    script_path: Path | None = None,
) -> dict:
    current_script = (script_path or Path(__file__)).resolve()
    script_attestation = verify_attestation(current_script, gh, timeout)
    archive_name = f"{PLUGIN}-{VERSION}.zip"
    checksum_name = f"{archive_name}.sha256"
    with tempfile.TemporaryDirectory(prefix=f"{PLUGIN}-{VERSION}-") as temporary:
        root = Path(temporary)
        archive = root / archive_name
        checksum = root / checksum_name
        download(release_url(archive_name), archive, MAX_ARCHIVE_BYTES, timeout)
        download(release_url(checksum_name), checksum, MAX_CHECKSUM_BYTES, timeout)
        declared = expected_checksum(checksum, archive_name)
        actual = sha256(archive)
        if declared != actual:
            raise BootstrapError("Release archive does not match its checksum")
        archive_attestation = verify_attestation(archive, gh, timeout)
        if (
            archive_attestation["source_revision"]
            != script_attestation["source_revision"]
        ):
            raise BootstrapError(
                "Bootstrap and archive attestations name different revisions"
            )
        installer_dir = root / "installer"
        installer_dir.mkdir()
        installer = extract_installer(archive, installer_dir)
        installation = run_installer(
            installer, archive, checksum, install_root, setup, timeout
        )
    return {
        "version": VERSION,
        "tag": TAG,
        "repository": REPOSITORY,
        "archive_sha256": actual,
        "source_revision": archive_attestation["source_revision"],
        "attestation_verified": True,
        "bootstrap_attestation_verified": True,
        "installation": installation,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--gh", type=Path)
    parser.add_argument("--lock-output", type=Path)
    parser.add_argument("--baud")
    parser.add_argument("--blea")
    parser.add_argument("--debugger")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if not 1.0 <= args.timeout <= 120.0:
            raise BootstrapError("--timeout must be between 1 and 120 seconds")
        data = bootstrap(
            args.install_root,
            gh_executable(args.gh),
            {
                "lock_output": args.lock_output,
                "baud": args.baud,
                "blea": args.blea,
                "debugger": args.debugger,
            },
            args.timeout,
        )
        report = {
            "schema_version": SCHEMA,
            "ok": True,
            "operation": "bootstrap_install",
            "hardware_access": False,
            "data": data,
        }
    except (
        BootstrapError,
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        zipfile.BadZipFile,
        subprocess.SubprocessError,
    ) as error:
        report = {
            "schema_version": SCHEMA,
            "ok": False,
            "operation": "bootstrap_install",
            "hardware_access": False,
            "error": str(error),
        }
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["ok"]:
        print(json.dumps(report["data"], indent=2))
    else:
        print(report["error"], file=sys.stderr)
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
