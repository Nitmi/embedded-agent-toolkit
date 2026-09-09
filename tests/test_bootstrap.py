from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from scripts import bootstrap


class Response:
    def __init__(self, payload: bytes, url: str, length: str | None = None) -> None:
        self.payload = io.BytesIO(payload)
        self.url = url
        self.headers = {} if length is None else {"Content-Length": length}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def geturl(self) -> str:
        return self.url

    def read(self, size: int = -1) -> bytes:
        return self.payload.read(size)


class BootstrapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def attestation(self, name: str, digest: str, revision: str = "a" * 40) -> str:
        return json.dumps(
            [
                {
                    "verificationResult": {
                        "signature": {
                            "certificate": {
                                "sourceRepositoryRef": bootstrap.SOURCE_REF,
                                "sourceRepositoryDigest": revision,
                                "githubWorkflowTrigger": "push",
                                "githubWorkflowRepository": bootstrap.REPOSITORY,
                                "githubWorkflowSHA": revision,
                                "buildSignerDigest": revision,
                                "runnerEnvironment": "github-hosted",
                            }
                        },
                        "verifiedTimestamps": [{"type": "Tlog"}],
                        "statement": {
                            "subject": [{"name": name, "digest": {"sha256": digest}}]
                        },
                    }
                }
            ]
        )

    def test_download_rejects_untrusted_redirect_before_writing(self) -> None:
        output = self.root / "payload"
        response = Response(b"data", "https://example.com/payload")
        with (
            mock.patch.object(
                bootstrap.urllib.request, "urlopen", return_value=response
            ),
            self.assertRaisesRegex(bootstrap.BootstrapError, "untrusted host"),
        ):
            bootstrap.download("https://github.com/example", output, 100, 1)
        self.assertFalse(output.exists())

    def test_download_enforces_streamed_size_limit(self) -> None:
        output = self.root / "payload"
        response = Response(b"12345", "https://objects.githubusercontent.com/payload")
        with (
            mock.patch.object(
                bootstrap.urllib.request, "urlopen", return_value=response
            ),
            self.assertRaisesRegex(bootstrap.BootstrapError, "size limit"),
        ):
            bootstrap.download("https://github.com/example", output, 4, 1)
        self.assertFalse(output.exists())

    def test_checksum_requires_exact_archive_name(self) -> None:
        checksum = self.root / "release.sha256"
        checksum.write_text(f"{'a' * 64}  other.zip\n", encoding="ascii")
        with self.assertRaisesRegex(bootstrap.BootstrapError, "exact release archive"):
            bootstrap.expected_checksum(checksum, "expected.zip")

    def test_attestation_policy_binds_subject_tag_runner_and_revision(self) -> None:
        artifact = self.root / "bootstrap.py"
        artifact.write_bytes(b"trusted")
        digest = hashlib.sha256(b"trusted").hexdigest()
        completed = subprocess_result(self.attestation(artifact.name, digest))
        with mock.patch.object(
            bootstrap.subprocess, "run", return_value=completed
        ) as run:
            report = bootstrap.verify_attestation(artifact, Path("gh.exe"), 1)
        self.assertEqual(report["source_revision"], "a" * 40)
        command = run.call_args.args[0]
        self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")
        self.assertIn(bootstrap.SOURCE_REF, command)
        self.assertIn(bootstrap.SIGNER_WORKFLOW, command)
        self.assertIn("--deny-self-hosted-runners", command)

    def test_attestation_rejects_manual_workflow(self) -> None:
        artifact = self.root / "bootstrap.py"
        artifact.write_bytes(b"trusted")
        digest = hashlib.sha256(b"trusted").hexdigest()
        payload = json.loads(self.attestation(artifact.name, digest))
        payload[0]["verificationResult"]["signature"]["certificate"][
            "githubWorkflowTrigger"
        ] = "workflow_dispatch"
        with (
            mock.patch.object(
                bootstrap.subprocess,
                "run",
                return_value=subprocess_result(json.dumps(payload)),
            ),
            self.assertRaisesRegex(bootstrap.BootstrapError, "policy"),
        ):
            bootstrap.verify_attestation(artifact, Path("gh.exe"), 1)

    def test_attestation_rejects_malformed_subject_digest(self) -> None:
        artifact = self.root / "bootstrap.py"
        artifact.write_bytes(b"trusted")
        digest = hashlib.sha256(b"trusted").hexdigest()
        payload = json.loads(self.attestation(artifact.name, digest))
        payload[0]["verificationResult"]["statement"]["subject"][0]["digest"] = []
        with (
            mock.patch.object(
                bootstrap.subprocess,
                "run",
                return_value=subprocess_result(json.dumps(payload)),
            ),
            self.assertRaisesRegex(bootstrap.BootstrapError, "policy"),
        ):
            bootstrap.verify_attestation(artifact, Path("gh.exe"), 1)

    def test_extracts_only_fixed_installer_scripts(self) -> None:
        archive = self.root / "release.zip"
        output = self.root / "installer"
        output.mkdir()
        with zipfile.ZipFile(archive, "w") as package:
            for relative in bootstrap.INSTALLER_SCRIPTS:
                package.writestr(f"{bootstrap.PLUGIN}/{relative}", relative)
            package.writestr(f"{bootstrap.PLUGIN}/untrusted.py", "ignored")
        installer = bootstrap.extract_installer(archive, output)
        self.assertEqual(installer, output / "release.py")
        self.assertEqual(
            {path.name for path in output.iterdir()},
            {Path(name).name for name in bootstrap.INSTALLER_SCRIPTS},
        )

    def test_extracted_installer_has_all_import_dependencies(self) -> None:
        archive = self.root / "release.zip"
        output = self.root / "installer"
        output.mkdir()
        repository = Path(__file__).resolve().parents[1]
        with zipfile.ZipFile(archive, "w") as package:
            for relative in bootstrap.INSTALLER_SCRIPTS:
                package.write(repository / relative, f"{bootstrap.PLUGIN}/{relative}")

        installer = bootstrap.extract_installer(archive, output)
        process = bootstrap.subprocess.run(
            [bootstrap.sys.executable, str(installer), "--help"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        self.assertEqual(process.returncode, 0, process.stderr)

    def test_installer_setup_is_all_or_nothing(self) -> None:
        with self.assertRaisesRegex(bootstrap.BootstrapError, "required together"):
            bootstrap.run_installer(
                self.root / "release.py",
                self.root / "release.zip",
                self.root / "release.sha256",
                self.root / "install",
                {
                    "component_lock": None,
                    "lock_output": self.root / "lock",
                    "baud": None,
                    "blea": None,
                    "debugger": None,
                },
                1,
            )

    def test_installer_accepts_one_existing_component_lock(self) -> None:
        lock = self.root / "existing-lock.json"
        completed = subprocess_result(
            json.dumps({"ok": True, "hardware_access": False, "data": {}})
        )
        with mock.patch.object(
            bootstrap.subprocess, "run", return_value=completed
        ) as run:
            bootstrap.run_installer(
                self.root / "release.py",
                self.root / "release.zip",
                self.root / "release.sha256",
                self.root / "install",
                {
                    "component_lock": lock,
                    "lock_output": None,
                    "baud": None,
                    "blea": None,
                    "debugger": None,
                },
                1,
            )
        command = run.call_args.args[0]
        self.assertIn("--component-lock", command)
        self.assertIn(str(lock), command)
        self.assertNotIn("--lock-output", command)

    def test_installer_passes_catalog_component_install_mode(self) -> None:
        lock = self.root / "new-lock.json"
        components = self.root / "components"
        completed = subprocess_result(
            json.dumps({"ok": True, "hardware_access": False, "data": {}})
        )
        with mock.patch.object(
            bootstrap.subprocess, "run", return_value=completed
        ) as run:
            bootstrap.run_installer(
                self.root / "release.py",
                self.root / "release.zip",
                self.root / "release.sha256",
                self.root / "install",
                {
                    "component_lock": None,
                    "component_install_root": components,
                    "lock_output": lock,
                    "baud": None,
                    "blea": None,
                    "debugger": None,
                },
                1,
            )
        command = run.call_args.args[0]
        self.assertIn("--component-install-root", command)
        self.assertIn(str(components), command)
        self.assertIn("--lock-output", command)
        self.assertIn(str(lock), command)
        self.assertNotIn("--component-lock", command)
        self.assertEqual(run.call_args.kwargs["timeout"], 39)

    def test_catalog_component_install_requires_lock_output(self) -> None:
        with self.assertRaisesRegex(bootstrap.BootstrapError, "requires"):
            bootstrap.run_installer(
                self.root / "release.py",
                self.root / "release.zip",
                self.root / "release.sha256",
                self.root / "install",
                {
                    "component_lock": None,
                    "component_install_root": self.root / "components",
                    "lock_output": None,
                    "baud": None,
                    "blea": None,
                    "debugger": None,
                },
                1,
            )

    def test_installer_rejects_existing_and_new_lock_modes_together(self) -> None:
        with self.assertRaisesRegex(bootstrap.BootstrapError, "cannot be combined"):
            bootstrap.run_installer(
                self.root / "release.py",
                self.root / "release.zip",
                self.root / "release.sha256",
                self.root / "install",
                {
                    "component_lock": self.root / "existing-lock.json",
                    "lock_output": self.root / "new-lock.json",
                    "baud": "baud",
                    "blea": "ble",
                    "debugger": "debugger",
                },
                1,
            )

    def test_bootstrap_binds_script_and_archive_before_installing(self) -> None:
        script = self.root / "bootstrap.py"
        script.write_bytes(b"bootstrap")
        archive_payload = b"archive"
        archive_digest = hashlib.sha256(archive_payload).hexdigest()

        def download(_url, destination, _limit, _timeout):
            if destination.name.endswith(".sha256"):
                destination.write_text(
                    f"{archive_digest}  {bootstrap.PLUGIN}-{bootstrap.VERSION}.zip\n",
                    encoding="ascii",
                )
            else:
                destination.write_bytes(archive_payload)

        attestation = {
            "source_revision": "a" * 40,
            "source_ref": bootstrap.SOURCE_REF,
        }
        install_report = {"ok": True, "hardware_access": False, "data": {}}
        with (
            mock.patch.object(bootstrap, "download", side_effect=download) as fetch,
            mock.patch.object(
                bootstrap, "verify_attestation", return_value=attestation
            ) as verify,
            mock.patch.object(
                bootstrap, "extract_installer", return_value=self.root / "release.py"
            ),
            mock.patch.object(
                bootstrap, "run_installer", return_value=install_report
            ) as install,
        ):
            report = bootstrap.bootstrap(
                self.root / "install",
                Path("gh.exe"),
                {
                    "component_lock": None,
                    "lock_output": None,
                    "baud": None,
                    "blea": None,
                    "debugger": None,
                },
                1,
                script,
            )

        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(verify.call_count, 2)
        self.assertEqual(install.call_count, 1)
        self.assertEqual(report["archive_sha256"], archive_digest)
        self.assertTrue(report["bootstrap_attestation_verified"])

    def test_bootstrap_rejects_different_attested_revisions(self) -> None:
        script = self.root / "bootstrap.py"
        script.write_bytes(b"bootstrap")
        archive_payload = b"archive"
        archive_digest = hashlib.sha256(archive_payload).hexdigest()

        def download(_url, destination, _limit, _timeout):
            if destination.name.endswith(".sha256"):
                destination.write_text(
                    f"{archive_digest}  {bootstrap.PLUGIN}-{bootstrap.VERSION}.zip\n",
                    encoding="ascii",
                )
            else:
                destination.write_bytes(archive_payload)

        with (
            mock.patch.object(bootstrap, "download", side_effect=download),
            mock.patch.object(
                bootstrap,
                "verify_attestation",
                side_effect=[
                    {"source_revision": "a" * 40},
                    {"source_revision": "b" * 40},
                ],
            ),
            mock.patch.object(bootstrap, "run_installer") as install,
            self.assertRaisesRegex(bootstrap.BootstrapError, "different revisions"),
        ):
            bootstrap.bootstrap(
                self.root / "install",
                Path("gh.exe"),
                {
                    "component_lock": None,
                    "lock_output": None,
                    "baud": None,
                    "blea": None,
                    "debugger": None,
                },
                1,
                script,
            )
        install.assert_not_called()


def subprocess_result(stdout: str, returncode: int = 0):
    return bootstrap.subprocess.CompletedProcess([], returncode, stdout, "")


if __name__ == "__main__":
    unittest.main()
