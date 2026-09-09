from __future__ import annotations

import contextlib
import io
import json
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from scripts import component_lock, release, toolkit_doctor


def source_files(version: str = "0.2.0") -> dict[str, bytes]:
    files = {name: b"fixture\n" for name in release.REQUIRED_FILES}
    manifest = {"name": release.PLUGIN, "version": version, "skills": "./skills/"}
    for name in ("plugin.json", ".codex-plugin/plugin.json"):
        files[name] = release.json_bytes(manifest)
    return files


class ReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.archive = self.root / "release.zip"
        self.checksum = self.root / "release.zip.sha256"

    def save(self, payload: bytes) -> None:
        self.archive.write_bytes(payload)
        self.checksum.write_text(
            f"{release.digest(payload)}  {self.archive.name}\n", encoding="ascii"
        )

    def prepare(self, version: str = "0.2.0") -> bytes:
        _, payload = release.make_archive("1" * 40, source_files(version))
        self.save(payload)
        return payload

    def rewrite(self, transform) -> None:
        buffer = io.BytesIO()
        with (
            zipfile.ZipFile(self.archive) as original,
            zipfile.ZipFile(buffer, "w") as new,
        ):
            for entry in original.infolist():
                transform(new, entry, original.read(entry))
        self.save(buffer.getvalue())

    def test_deterministic_archive_has_hidden_manifest_and_no_cachebuster(self) -> None:
        files = source_files()
        codex = json.loads(files[".codex-plugin/plugin.json"])
        codex["version"] += "+codex.local-test"
        files[".codex-plugin/plugin.json"] = release.json_bytes(codex)
        version, first = release.make_archive("1" * 40, files)
        _, second = release.make_archive("1" * 40, dict(reversed(list(files.items()))))
        self.assertEqual(version, "0.2.0")
        self.assertEqual(first, second)
        self.save(first)
        manifest, unpacked = release.verify_release(self.archive, self.checksum)
        self.assertEqual(manifest["source_revision"], "1" * 40)
        self.assertEqual(
            json.loads(unpacked[".codex-plugin/plugin.json"])["version"], "0.2.0"
        )
        self.assertEqual(set(unpacked), set(files) | {release.MANIFEST})

    def test_changed_commit_or_file_changes_archive_hash(self) -> None:
        files = source_files()
        _, first = release.make_archive("1" * 40, files)
        _, changed_commit = release.make_archive("2" * 40, files)
        files["README.md"] = b"changed"
        _, changed_file = release.make_archive("1" * 40, files)
        self.assertNotEqual(release.digest(first), release.digest(changed_commit))
        self.assertNotEqual(release.digest(first), release.digest(changed_file))

    def test_source_allowlist_excludes_evidence_builds_and_local_acceptance(
        self,
    ) -> None:
        for name in (
            "evidence/log.json",
            "target/app.exe",
            "dist/archive.zip",
            ".git/config",
            "docs/local-acceptance.md",
            "tests/test_release.py",
            "AGENTS.md",
        ):
            self.assertFalse(release.included(name), name)
        for name in (
            ".codex-plugin/plugin.json",
            "scripts/release.py",
            "scripts/bootstrap.py",
            "skills/hardware-test/references/runtime-contract.md",
            "docs/releases.md",
        ):
            self.assertTrue(release.included(name), name)

    def test_dirty_source_is_rejected_before_output_creation(self) -> None:
        with (
            mock.patch.object(release, "git_bytes", return_value=b" M README.md\n"),
            self.assertRaises(release.ReleaseError),
        ):
            release.build_release(self.root, self.root / "out")
        self.assertFalse((self.root / "out").exists())

    def test_snapshot_reads_pinned_commit_blobs_not_worktree_files(self) -> None:
        revision = "a" * 40
        self.root.joinpath("README.md").write_bytes(b"worktree bytes")

        def git(_root, *args):
            if args[0] == "status":
                return b""
            if args[0] == "rev-parse":
                return revision.encode()
            if args[0] == "ls-tree":
                return b"100644 blob " + b"b" * 40 + b" 16\tREADME.md\0"
            self.assertEqual(args, ("show", f"{revision}:README.md"))
            return b"committed bytes\n"

        with mock.patch.object(release, "git_bytes", side_effect=git):
            actual_revision, files = release.source_snapshot(self.root)
        self.assertEqual(actual_revision, revision)
        self.assertEqual(files, {"README.md": b"committed bytes\n"})

    def test_build_never_overwrites_existing_release(self) -> None:
        with mock.patch.object(
            release, "source_snapshot", return_value=("1" * 40, source_files())
        ):
            report = release.build_release(self.root, self.root / "out")
            original = Path(report["archive"]).read_bytes()
            with self.assertRaises(release.ReleaseError):
                release.build_release(self.root, self.root / "out")
        self.assertEqual(Path(report["archive"]).read_bytes(), original)

    def test_release_tag_must_exactly_match_plugin_version(self) -> None:
        snapshot = ("a" * 40, source_files("0.5.0"))
        with (
            mock.patch.object(release, "source_snapshot", return_value=snapshot),
            mock.patch.object(release, "git_bytes", return_value=b"a" * 40 + b"\n"),
        ):
            report = release.check_release_tag(self.root, "v0.5.0")
            self.assertEqual(report["version"], "0.5.0")
            with self.assertRaisesRegex(release.ReleaseError, "exactly v0.5.0"):
                release.check_release_tag(self.root, "v0.5.1")

    def test_release_tag_must_resolve_to_checked_out_commit(self) -> None:
        snapshot = ("a" * 40, source_files("0.5.0"))
        with (
            mock.patch.object(release, "source_snapshot", return_value=snapshot),
            mock.patch.object(release, "git_bytes", return_value=b"b" * 40 + b"\n"),
            self.assertRaisesRegex(release.ReleaseError, "checked-out commit"),
        ):
            release.check_release_tag(self.root, "v0.5.0")

    def test_windows_reparse_points_are_rejected_without_path_is_junction(self) -> None:
        path = mock.Mock()
        path.lstat.return_value = mock.Mock(
            st_mode=stat.S_IFDIR, st_file_attributes=0x400
        )
        self.assertTrue(release.is_link(path))
        path.lstat.return_value.st_file_attributes = 0
        self.assertFalse(release.is_link(path))

    def test_checksum_detects_tamper_and_wrong_archive_name(self) -> None:
        payload = self.prepare()
        self.archive.write_bytes(payload + b"changed")
        with self.assertRaisesRegex(release.ReleaseError, "SHA-256"):
            release.verify_release(self.archive, self.checksum)
        self.save(payload)
        self.checksum.write_text(
            f"{release.digest(payload)}  other.zip\n", encoding="ascii"
        )
        with self.assertRaises(release.ReleaseError):
            release.verify_release(self.archive, self.checksum)

    def test_inventory_detects_tampered_member_even_with_updated_archive_checksum(
        self,
    ) -> None:
        self.prepare()
        self.rewrite(
            lambda new, entry, data: new.writestr(
                entry, b"changed" if entry.filename.endswith("/README.md") else data
            )
        )
        with self.assertRaisesRegex(release.ReleaseError, "integrity mismatch"):
            release.verify_release(self.archive, self.checksum)

    def test_unlisted_member_is_rejected(self) -> None:
        self.prepare()
        with zipfile.ZipFile(self.archive, "a") as archive:
            archive.writestr(f"{release.PLUGIN}/unlisted.txt", b"extra")
        self.save(self.archive.read_bytes())
        with self.assertRaisesRegex(release.ReleaseError, "outside its manifest"):
            release.verify_release(self.archive, self.checksum)

    def test_unsafe_archive_paths_are_rejected_before_installation(self) -> None:
        for name in (
            "../escape.txt",
            "/absolute.txt",
            "C:/escape.txt",
            "a\\b",
            "a//b",
            "a/./b",
            "a/../b",
            "a:stream",
            "a/NUL.txt",
            "a/COM1",
            "a/COM0",
            "a/CONIN$",
            "a/CONOUT$",
            "a/COM\u00b9",
            "a/trailing.",
            "a/trailing ",
        ):
            with self.subTest(name=name):
                self.prepare()
                with zipfile.ZipFile(self.archive, "a") as archive:
                    archive.writestr(name, b"unsafe")
                self.save(self.archive.read_bytes())
                with self.assertRaises(release.ReleaseError):
                    release.install_release(
                        self.archive, self.checksum, self.root / "install"
                    )
                self.assertFalse((self.root / "install").exists())

    def test_case_collisions_and_parent_file_collisions_are_rejected(self) -> None:
        for names in (["a", "A"], ["a", "a/b"], ["A", "a/b"], ["a", "a"]):
            with self.assertRaises(release.ReleaseError):
                release.validate_names(names)

    def test_symlink_archive_entry_is_rejected(self) -> None:
        self.prepare()

        def replace(new, entry, data):
            if entry.filename.endswith("/README.md"):
                entry.external_attr = (stat.S_IFLNK | 0o777) << 16
            new.writestr(entry, data)

        self.rewrite(replace)
        with self.assertRaisesRegex(release.ReleaseError, "Unsupported archive entry"):
            release.verify_release(self.archive, self.checksum)

    def test_manifest_version_schema_duplicate_fields_and_inventory_are_checked(
        self,
    ) -> None:
        for kind in (
            "version",
            "schema",
            "duplicate-json",
            "duplicate-file",
            "bool-size",
        ):
            self.prepare()

            def replace(new, entry, data, kind=kind):
                if entry.filename.endswith("/" + release.MANIFEST):
                    manifest = json.loads(data)
                    if kind == "version":
                        manifest["version"] = "../escape"
                    elif kind == "schema":
                        manifest["schema_version"] = "unknown"
                    elif kind == "duplicate-file":
                        manifest["files"].append(manifest["files"][0])
                    elif kind == "bool-size":
                        manifest["files"][0]["size"] = True
                    data = release.json_bytes(manifest)
                    if kind == "duplicate-json":
                        data = data.replace(b"{", b'{"version":"0.2.0",', 1)
                new.writestr(entry, data)

            self.rewrite(replace)
            with self.subTest(kind=kind), self.assertRaises(release.ReleaseError):
                release.verify_release(self.archive, self.checksum)

    def test_component_mcp_and_mismatched_versions_cannot_be_packaged(self) -> None:
        for kind in ("mcp", "version", "missing", "service-file"):
            files = source_files()
            document = json.loads(files["plugin.json"])
            if kind == "mcp":
                document["mcpServers"] = "./mcp.json"
            if kind == "version":
                document["version"] = "0.3.0"
            files["plugin.json"] = release.json_bytes(document)
            if kind == "missing":
                del files["LICENSE"]
            if kind == "service-file":
                files[".mcp.json"] = b"{}"
            with self.subTest(kind=kind), self.assertRaises(release.ReleaseError):
                release.make_archive("1" * 40, files)

    def test_limits_are_enforced(self) -> None:
        self.prepare()
        for limit in (
            "MAX_ARCHIVE_BYTES",
            "MAX_TOTAL_BYTES",
            "MAX_FILE_BYTES",
            "MAX_FILES",
        ):
            with (
                mock.patch.object(release, limit, 1),
                self.assertRaises(release.ReleaseError),
            ):
                release.verify_release(self.archive, self.checksum)

    def test_install_is_idempotent_and_does_not_execute_components(self) -> None:
        self.prepare()
        with mock.patch.object(release.subprocess, "run") as process:
            report = release.install_release(
                self.archive, self.checksum, self.root / "install"
            )
            repeated = release.install_release(
                self.archive, self.checksum, self.root / "install"
            )
        process.assert_not_called()
        self.assertEqual(report["status"], "installed")
        self.assertEqual(repeated["status"], "already_installed")
        self.assertFalse(report["activated"])
        self.assertFalse(report["path_modified"])
        self.assertFalse(report["components_installed"])
        self.assertEqual(Path(report["plugin_path"]).name, release.PLUGIN)

    def test_ready_install_creates_lock_and_runs_strict_installed_doctor(self) -> None:
        self.prepare("0.4.0")
        executables = {}
        outputs = {
            "baud": "baud 0.1.0\n",
            "blea": "ble 0.6.4\n",
            "embedded-debugger": "embedded-debugger 0.2.0\n",
        }
        for name in component_lock.SPECS:
            path = self.root / f"{name}.exe"
            path.write_bytes(name.encode())
            executables[name] = str(path)

        def completed(args, **_kwargs):
            name = Path(args[0]).stem
            return release.subprocess.CompletedProcess(args, 0, outputs[name], "")

        lock = self.root / "station" / "toolchain-lock.json"
        with (
            mock.patch.dict(release.os.environ, {}, clear=True),
            mock.patch.object(toolkit_doctor.platform, "system", return_value="Test"),
            mock.patch.object(toolkit_doctor.platform, "release", return_value="1"),
            mock.patch.object(toolkit_doctor.platform, "machine", return_value="x64"),
            mock.patch.object(
                toolkit_doctor.platform, "python_version", return_value="3.12"
            ),
            mock.patch.object(
                component_lock.subprocess, "run", side_effect=completed
            ) as process,
        ):
            report = release.install_ready_release(
                self.archive,
                self.checksum,
                self.root / "install",
                lock,
                executables,
                1.0,
            )

        self.assertTrue(report["ready"])
        self.assertTrue(report["doctor"]["complete"])
        self.assertEqual(report["doctor"]["status"], "ready")
        self.assertTrue(lock.is_file())
        self.assertEqual(process.call_count, 6)
        self.assertFalse(report["activated"])
        self.assertFalse(report["path_modified"])
        self.assertFalse(report["components_installed"])

    def test_ready_install_removes_new_lock_when_strict_doctor_fails(self) -> None:
        self.prepare("0.4.0")
        executables = {}
        outputs = {
            "baud": "baud 0.1.0\n",
            "blea": "ble 0.6.4\n",
            "embedded-debugger": "embedded-debugger 0.2.0\n",
        }
        for name in component_lock.SPECS:
            path = self.root / f"{name}.exe"
            path.write_bytes(name.encode())
            executables[name] = str(path)
        calls = 0

        def completed(args, **_kwargs):
            nonlocal calls
            calls += 1
            name = Path(args[0]).stem
            if calls == 6:
                return release.subprocess.CompletedProcess(args, 1, "", "failed")
            return release.subprocess.CompletedProcess(args, 0, outputs[name], "")

        lock = self.root / "toolchain-lock.json"
        with (
            mock.patch.dict(release.os.environ, {}, clear=True),
            mock.patch.object(toolkit_doctor.platform, "system", return_value="Test"),
            mock.patch.object(toolkit_doctor.platform, "release", return_value="1"),
            mock.patch.object(toolkit_doctor.platform, "machine", return_value="x64"),
            mock.patch.object(
                toolkit_doctor.platform, "python_version", return_value="3.12"
            ),
            mock.patch.object(component_lock.subprocess, "run", side_effect=completed),
            self.assertRaisesRegex(release.ReleaseError, "strict component doctor"),
        ):
            release.install_ready_release(
                self.archive,
                self.checksum,
                self.root / "install",
                lock,
                executables,
                1.0,
            )
        self.assertFalse(lock.exists())
        self.assertTrue((self.root / "install" / "0.4.0" / release.PLUGIN).is_dir())

    def test_ready_install_rejects_existing_lock_before_installation(self) -> None:
        self.prepare("0.4.0")
        lock = self.root / "toolchain-lock.json"
        lock.write_text("preserve", encoding="ascii")
        with self.assertRaisesRegex(release.ReleaseError, "already exists"):
            release.install_ready_release(
                self.archive,
                self.checksum,
                self.root / "install",
                lock,
                {name: str(self.root / name) for name in component_lock.SPECS},
                1.0,
            )
        self.assertEqual(lock.read_text(encoding="ascii"), "preserve")
        self.assertFalse((self.root / "install").exists())

    def test_cli_rejects_partial_ready_setup_before_installation(self) -> None:
        self.prepare("0.4.0")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = release.main(
                [
                    "install",
                    str(self.archive),
                    "--checksum",
                    str(self.checksum),
                    "--install-root",
                    str(self.root / "install"),
                    "--lock-output",
                    str(self.root / "toolchain-lock.json"),
                    "--json",
                ]
            )
        report = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertFalse(report["ok"])
        self.assertIn("required together", report["error"])
        self.assertFalse((self.root / "install").exists())

    def test_upgrade_retains_previous_version_and_old_install_can_be_selected(
        self,
    ) -> None:
        self.prepare("0.1.0")
        first = release.install_release(
            self.archive, self.checksum, self.root / "install"
        )
        original = Path(first["plugin_path"]).joinpath("plugin.json").read_bytes()
        self.prepare("0.2.0")
        second = release.install_release(
            self.archive, self.checksum, self.root / "install"
        )
        self.assertNotEqual(first["plugin_path"], second["plugin_path"])
        self.assertEqual(
            Path(first["plugin_path"]).joinpath("plugin.json").read_bytes(), original
        )

    def test_modified_or_incomplete_install_is_not_overwritten(self) -> None:
        self.prepare()
        report = release.install_release(
            self.archive, self.checksum, self.root / "install"
        )
        readme = Path(report["plugin_path"]) / "README.md"
        readme.write_bytes(b"user change")
        with self.assertRaisesRegex(release.ReleaseError, "refusing to overwrite"):
            release.install_release(self.archive, self.checksum, self.root / "install")
        self.assertEqual(readme.read_bytes(), b"user change")

    def test_cli_emits_structured_failure_without_traceback(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = release.main(
                [
                    "verify",
                    str(self.archive),
                    "--checksum",
                    str(self.checksum),
                    "--json",
                ]
            )
        self.assertEqual(code, 2)
        report = json.loads(output.getvalue())
        self.assertFalse(report["ok"])
        self.assertFalse(report["hardware_access"])

    def test_empty_existing_version_and_unexpected_directories_are_preserved(
        self,
    ) -> None:
        self.prepare()
        destination = self.root / "install" / "0.2.0" / release.PLUGIN
        destination.mkdir(parents=True)
        with self.assertRaises(release.ReleaseError):
            release.install_release(self.archive, self.checksum, self.root / "install")
        self.assertEqual(list(destination.iterdir()), [])
        other_root = self.root / "other-install"
        report = release.install_release(self.archive, self.checksum, other_root)
        extra = Path(report["plugin_path"]) / "unexpected"
        extra.mkdir()
        with self.assertRaises(release.ReleaseError):
            release.install_release(self.archive, self.checksum, other_root)
        self.assertTrue(extra.is_dir())


if __name__ == "__main__":
    unittest.main()
