from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from scripts import component_install


class ComponentInstallTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.catalog = self.root / "catalog.json"
        self.archives = {}
        components = {}
        versions = {
            "baud": "0.1.0",
            "blea": "0.6.4",
            "embedded-debugger": "0.2.0",
        }
        repositories = {
            "baud": "Nitmi/baud-cli",
            "blea": "Nitmi/blea",
            "embedded-debugger": "Nitmi/embedded-debugger",
        }
        executables = {
            "baud": "baud.exe",
            "blea": "ble.exe",
            "embedded-debugger": "embedded-debugger.exe",
        }
        for name, version in versions.items():
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as archive:
                archive.writestr(
                    f"bundle/{executables[name]}", f"fixture {name}".encode()
                )
            data = buffer.getvalue()
            self.archives[name] = data
            components[name] = {
                "repository": repositories[name],
                "version": version,
                "artifacts": {
                    "windows-x86_64": {
                        "url": (
                            f"https://github.com/{repositories[name]}/releases/download/"
                            f"v{version}/{name}.zip"
                        ),
                        "sha256": component_install.sha256(data),
                        "format": "zip",
                        "executable": f"bundle/{executables[name]}",
                    }
                },
            }
        self.payload = {
            "schema_version": component_install.CATALOG_SCHEMA,
            "components": components,
        }
        self.write_catalog()

    def write_catalog(self) -> None:
        self.catalog.write_text(json.dumps(self.payload), encoding="utf-8")

    def completed(self, args, **_kwargs):
        outputs = {
            "baud": "baud 0.1.0\n",
            "ble": "ble 0.6.4\n",
            "embedded-debugger": "embedded-debugger 0.2.0\n",
        }
        return subprocess.CompletedProcess(args, 0, outputs[Path(args[0]).stem], "")

    def test_plan_is_offline_and_reports_exact_destinations(self) -> None:
        with mock.patch.object(
            component_install,
            "download",
            side_effect=AssertionError("must stay offline"),
        ):
            report = component_install.plan(
                self.catalog, self.root / "install", "windows-x86_64"
            )
        self.assertTrue(report["complete"])
        self.assertFalse(report["network_access"])
        self.assertFalse(report["executables_started"])
        self.assertTrue(
            report["components"][0]["destination"].endswith("baud\\0.1.0\\baud.exe")
            or report["components"][0]["destination"].endswith("baud/0.1.0/baud.exe")
        )

    def test_install_verifies_downloads_creates_versioned_files_and_lock(self) -> None:
        by_url = {
            artifact["url"]: self.archives[name]
            for name, record in self.payload["components"].items()
            for artifact in record["artifacts"].values()
        }
        lock = self.root / "lock.json"
        with (
            mock.patch.object(
                component_install, "download", side_effect=lambda url, _: by_url[url]
            ),
            mock.patch.object(
                component_install.component_lock.subprocess,
                "run",
                side_effect=self.completed,
            ),
        ):
            report = component_install.install(
                self.catalog,
                self.root / "install",
                lock,
                "windows-x86_64",
                1.0,
            )
        self.assertTrue(report["ok"])
        self.assertTrue(report["network_access"])
        self.assertEqual(report["executed_command"], "--version only")
        self.assertFalse(report["hardware_access"])
        self.assertTrue(lock.is_file())
        self.assertEqual(
            set(report["component_lock"]["components"]), set(self.archives)
        )

    def test_unavailable_catalog_fails_before_network_or_filesystem_writes(
        self,
    ) -> None:
        for record in self.payload["components"].values():
            record["artifacts"] = {}
        self.write_catalog()
        with (
            mock.patch.object(
                component_install,
                "download",
                side_effect=AssertionError("must stay offline"),
            ),
            self.assertRaisesRegex(component_install.InstallError, "catalog has no"),
        ):
            component_install.install(
                self.catalog,
                self.root / "install",
                self.root / "lock.json",
                "windows-x86_64",
                1.0,
            )
        self.assertFalse((self.root / "install").exists())

    def test_wrong_hash_and_existing_lock_fail_closed(self) -> None:
        self.payload["components"]["baud"]["artifacts"]["windows-x86_64"]["sha256"] = (
            "0" * 64
        )
        self.write_catalog()
        with (
            mock.patch.object(
                component_install, "download", return_value=self.archives["baud"]
            ),
            self.assertRaisesRegex(component_install.InstallError, "hash differs"),
        ):
            component_install.install(
                self.catalog,
                self.root / "install",
                self.root / "lock.json",
                "windows-x86_64",
                1.0,
            )
        lock = self.root / "existing.json"
        lock.write_text("preserve", encoding="utf-8")
        with self.assertRaisesRegex(component_install.InstallError, "already exists"):
            component_install.install(
                self.catalog,
                self.root / "other",
                lock,
                "windows-x86_64",
                1.0,
            )
        self.assertEqual(lock.read_text(encoding="utf-8"), "preserve")

    def test_download_enforces_total_deadline_during_slow_response(self) -> None:
        released = threading.Event()

        class BlockingResponse:
            def __init__(self):
                self.headers = {}

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                self.close()

            def geturl(self):
                return "https://release-assets.githubusercontent.com/component.zip"

            def read(self, _size):
                released.wait(2)
                return b""

            def close(self):
                released.set()

        opener = mock.Mock()
        opener.open.return_value = BlockingResponse()
        started = time.monotonic()
        with (
            mock.patch.object(
                component_install.urllib.request,
                "build_opener",
                return_value=opener,
            ),
            self.assertRaisesRegex(component_install.InstallError, "total timeout"),
        ):
            component_install.download(
                "https://github.com/Nitmi/baud-cli/releases/download/v0.1.0/baud.zip",
                0.05,
            )
        self.assertLess(time.monotonic() - started, 0.5)

    def test_catalog_rejects_untrusted_url_duplicate_json_and_unsafe_member(
        self,
    ) -> None:
        artifact = self.payload["components"]["baud"]["artifacts"]["windows-x86_64"]
        artifact["url"] = "http://example.com/component.zip"
        self.write_catalog()
        with self.assertRaises(component_install.InstallError):
            component_install.read_catalog(self.catalog)
        self.catalog.write_text(
            '{"schema_version":"x","schema_version":"x","components":{}}',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(component_install.InstallError, "duplicate JSON"):
            component_install.read_catalog(self.catalog)
        with self.assertRaises(component_install.InstallError):
            component_install.validate_asset_path("../escape.exe")

    def test_zip_requires_one_exact_bounded_regular_executable(self) -> None:
        with self.assertRaisesRegex(component_install.InstallError, "missing"):
            component_install.executable_from_zip(self.archives["baud"], "other.exe")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("Tool.exe", b"one")
            archive.writestr("tool.exe", b"two")
        with self.assertRaisesRegex(component_install.InstallError, "duplicate paths"):
            component_install.executable_from_zip(buffer.getvalue(), "Tool.exe")

    def test_cli_plan_current_catalog_reports_all_components_without_network(
        self,
    ) -> None:
        official = (
            Path(component_install.__file__).resolve().parents[1]
            / "component-catalog.json"
        )
        output = io.StringIO()
        with (
            contextlib.redirect_stdout(output),
            mock.patch.object(
                component_install,
                "download",
                side_effect=AssertionError("must stay offline"),
            ),
        ):
            code = component_install.main(
                [
                    "plan",
                    "--catalog",
                    str(official),
                    "--install-root",
                    str(self.root / "install"),
                    "--platform",
                    "windows-x86_64",
                    "--json",
                ]
            )
        report = json.loads(output.getvalue())
        self.assertEqual(code, 0)
        self.assertTrue(report["complete"])
        statuses = {item["name"]: item["status"] for item in report["components"]}
        self.assertEqual(
            statuses,
            {
                "baud": "available",
                "blea": "available",
                "embedded-debugger": "available",
            },
        )


if __name__ == "__main__":
    unittest.main()
