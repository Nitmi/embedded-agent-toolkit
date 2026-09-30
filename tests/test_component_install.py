from __future__ import annotations

import contextlib
import io
import json
import stat
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
            "optional_components": {},
        }
        self.write_catalog()

    def write_catalog(self) -> None:
        self.catalog.write_text(json.dumps(self.payload), encoding="utf-8")

    def completed(self, args, **_kwargs):
        outputs = {
            "baud": "baud 0.1.0\n",
            "ble": "ble 0.6.4\n",
            "embedded-debugger": "embedded-debugger 0.2.0\n",
            "board-registry": "board-registry 0.1.0\n",
            "firmware-inspect": "firmware-inspect 0.1.0\n",
        }
        return subprocess.CompletedProcess(args, 0, outputs[Path(args[0]).stem], "")

    def add_optional_board_registry(self) -> None:
        self.add_optional_component("board-registry")

    def add_optional_component(self, name: str) -> None:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(f"bundle/{name}.exe", f"fixture {name}".encode())
        data = buffer.getvalue()
        self.archives[name] = data
        self.payload["optional_components"][name] = {
            "repository": f"Nitmi/{name}",
            "version": "0.1.0",
            "artifacts": {
                "windows-x86_64": {
                    "url": (
                        f"https://github.com/Nitmi/{name}/releases/download/"
                        f"v0.1.0/{name}.zip"
                    ),
                    "sha256": component_install.sha256(data),
                    "format": "zip",
                    "executable": f"bundle/{name}.exe",
                }
            },
        }
        self.write_catalog()

    def test_two_optional_components_are_explicit_and_install_a_five_component_lock(self) -> None:
        self.add_optional_board_registry()
        self.add_optional_component("firmware-inspect")
        defaults = component_install.plan(self.catalog, self.root / "defaults", "windows-x86_64")
        self.assertEqual(
            {item["name"] for item in defaults["components"]},
            set(component_install.component_lock.SPECS),
        )
        by_url = {
            artifact["url"]: self.archives[name]
            for group in ("components", "optional_components")
            for name, record in self.payload[group].items()
            for artifact in record["artifacts"].values()
        }
        output = self.root / "five-components.json"
        with (
            mock.patch.object(
                component_install, "download", side_effect=lambda url, _: by_url[url]
            ),
            mock.patch.object(
                component_install.component_lock.subprocess, "run", side_effect=self.completed
            ),
        ):
            report = component_install.install(
                self.catalog, self.root / "installed-five", output, "windows-x86_64", 1.0,
                ["board-registry", "firmware-inspect"],
            )
        self.assertEqual(
            set(report["component_lock"]["components"]),
            set(component_install.component_lock.ALL_SPECS),
        )
        self.assertFalse(report["hardware_access"])

    def test_missing_optional_entry_is_rejected_before_download_or_write(self) -> None:
        destination = self.root / "absent-firmware-inspect"
        lock = self.root / "must-not-exist.json"
        with (
            mock.patch.object(
                component_install, "download", side_effect=AssertionError("no network")
            ),
            self.assertRaisesRegex(component_install.InstallError, "absent from catalog"),
        ):
            component_install.install(
                self.catalog, destination, lock, "windows-x86_64", 1.0, ["firmware-inspect"]
            )
        self.assertFalse(destination.exists())
        self.assertFalse(lock.exists())

    def test_install_preserves_only_allowlisted_sibling_companions(self) -> None:
        self.add_optional_component("firmware-inspect")
        buffer = io.BytesIO()
        companions = {
            "LICENSE": b"license terms",
            "THIRD-PARTY-NOTICES.txt": b"third-party terms",
            "release-manifest.json": b'{"version":"0.1.0"}',
        }
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("bundle/firmware-inspect.exe", b"fixture firmware-inspect")
            for name, contents in companions.items():
                archive.writestr(f"bundle/{name}", contents)
            archive.writestr("other/LICENSE", b"unrelated")
            archive.writestr("bundle/extra.exe", b"not selected")
            archive.writestr("../escape.txt", b"not extracted")
        self.archives["firmware-inspect"] = buffer.getvalue()
        artifact = self.payload["optional_components"]["firmware-inspect"]["artifacts"][
            "windows-x86_64"
        ]
        artifact["sha256"] = component_install.sha256(self.archives["firmware-inspect"])
        self.write_catalog()
        by_url = {
            entry["url"]: self.archives[name]
            for group in ("components", "optional_components")
            for name, record in self.payload[group].items()
            for entry in record["artifacts"].values()
        }
        install_root = self.root / "installed"
        with (
            mock.patch.object(
                component_install, "download", side_effect=lambda url, _: by_url[url]
            ),
            mock.patch.object(
                component_install.component_lock.subprocess, "run", side_effect=self.completed
            ) as run,
        ):
            report = component_install.install(
                self.catalog, install_root, self.root / "lock.json", "windows-x86_64", 1.0,
                ["firmware-inspect"],
            )
        installed = install_root / "firmware-inspect" / "0.1.0"
        self.assertEqual(
            {path.name for path in installed.iterdir()}, set(companions) | {"firmware-inspect.exe"}
        )
        for name, contents in companions.items():
            self.assertEqual((installed / name).read_bytes(), contents)
        inspector = next(
            item for item in report["components"] if item["name"] == "firmware-inspect"
        )
        self.assertEqual({item["name"] for item in inspector["companion_files"]}, set(companions))
        self.assertTrue(all(call.args[0][1:] == ["--version"] for call in run.call_args_list))
        self.assertFalse((self.root / "escape.txt").exists())
        (installed / "LICENSE").write_bytes(b"user changes")
        with (
            mock.patch.object(
                component_install, "download", side_effect=lambda url, _: by_url[url]
            ),
            mock.patch.object(
                component_install.component_lock.subprocess, "run", side_effect=self.completed
            ),
            self.assertRaisesRegex(component_install.InstallError, "destination differs"),
        ):
            component_install.install(
                self.catalog, install_root, self.root / "second-lock.json", "windows-x86_64", 1.0,
                ["firmware-inspect"],
            )
        self.assertEqual((installed / "LICENSE").read_bytes(), b"user changes")
        self.assertFalse((self.root / "second-lock.json").exists())

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

    def test_optional_component_requires_explicit_selection(self) -> None:
        self.add_optional_board_registry()
        default = component_install.plan(
            self.catalog, self.root / "default", "windows-x86_64"
        )
        selected = component_install.plan(
            self.catalog,
            self.root / "selected",
            "windows-x86_64",
            ["board-registry"],
        )
        self.assertEqual(
            {item["name"] for item in default["components"]},
            set(component_install.component_lock.SPECS),
        )
        self.assertEqual(
            {item["name"] for item in selected["components"]},
            set(component_install.component_lock.SPECS) | {"board-registry"},
        )
        self.assertEqual(selected["included_optional_components"], ["board-registry"])

    def test_install_can_create_four_component_v2_lock(self) -> None:
        self.add_optional_board_registry()
        by_url = {
            artifact["url"]: self.archives[name]
            for group in ("components", "optional_components")
            for name, record in self.payload[group].items()
            for artifact in record["artifacts"].values()
        }
        lock = self.root / "optional-lock.json"
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
                self.root / "optional-install",
                lock,
                "windows-x86_64",
                1.0,
                ["board-registry"],
            )
        self.assertEqual(
            set(report["component_lock"]["components"]),
            set(component_install.component_lock.SPECS) | {"board-registry"},
        )
        self.assertEqual(
            json.loads(lock.read_text(encoding="utf-8"))["schema_version"],
            component_install.component_lock.SCHEMA,
        )

    def test_legacy_catalog_remains_supported(self) -> None:
        self.payload["schema_version"] = component_install.LEGACY_CATALOG_SCHEMA
        del self.payload["optional_components"]
        self.write_catalog()
        report = component_install.plan(
            self.catalog, self.root / "legacy", "windows-x86_64"
        )
        self.assertTrue(report["complete"])
        with self.assertRaisesRegex(
            component_install.InstallError, "absent from catalog"
        ):
            component_install.plan(
                self.catalog,
                self.root / "legacy-optional",
                "windows-x86_64",
                ["board-registry"],
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
            component_install.files_from_zip(self.archives["baud"], "other.exe")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("Tool.exe", b"one")
            archive.writestr("tool.exe", b"two")
        with self.assertRaisesRegex(component_install.InstallError, "duplicate paths"):
            component_install.files_from_zip(buffer.getvalue(), "Tool.exe")

    def test_zip_rejects_unsafe_or_oversized_companions(self) -> None:
        for kind in (stat.S_IFLNK, stat.S_IFDIR, stat.S_IFIFO):
            with self.subTest(kind=kind):
                buffer = io.BytesIO()
                with zipfile.ZipFile(buffer, "w") as archive:
                    archive.writestr("bundle/Tool.exe", b"executable")
                    entry = zipfile.ZipInfo("bundle/LICENSE")
                    entry.external_attr = (kind | 0o644) << 16
                    archive.writestr(entry, b"not regular")
                with self.assertRaisesRegex(component_install.InstallError, "not a regular file"):
                    component_install.files_from_zip(buffer.getvalue(), "bundle/Tool.exe")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("bundle/Tool.exe", b"executable")
            archive.writestr("bundle/LICENSE", b"oversized")
        with (
            mock.patch.object(component_install, "MAX_COMPANION_BYTES", 1),
            self.assertRaisesRegex(component_install.InstallError, "size is invalid"),
        ):
            component_install.files_from_zip(buffer.getvalue(), "bundle/Tool.exe")

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
        self.assertEqual(
            report["available_optional_components"], ["board-registry", "firmware-inspect"]
        )

    def test_current_catalog_pins_authenticated_firmware_release_and_all_opt_in_plans(self) -> None:
        official = (
            Path(component_install.__file__).resolve().parents[1] / "component-catalog.json"
        )
        catalog, _ = component_install.read_catalog(official)
        inspector = catalog["optional_components"]["firmware-inspect"]
        self.assertEqual(inspector["repository"], "Nitmi/firmware-inspect")
        self.assertEqual(inspector["version"], "0.1.0")
        artifact = inspector["artifacts"]["windows-x86_64"]
        self.assertEqual(artifact["sha256"],
                         "4de53a107b3286c67fea86a36ef91779ca15e85fff682d2ff20374afca5c5c15")
        self.assertEqual(artifact["url"],
                         "https://github.com/Nitmi/firmware-inspect/releases/download/"
                         "v0.1.0/embedded-firmware-inspect-0.1.0-windows-x86_64.zip")
        self.assertEqual(artifact["executable"],
                         "embedded-firmware-inspect-0.1.0-windows-x86_64/firmware-inspect.exe")
        for optional in ([], ["board-registry"], ["firmware-inspect"],
                         ["board-registry", "firmware-inspect"]):
            with self.subTest(optional=optional):
                report = component_install.plan(
                    official, self.root / "candidate", "windows-x86_64", optional
                )
                self.assertTrue(report["complete"])
                self.assertEqual(
                    {item["name"] for item in report["components"]},
                    set(component_install.component_lock.SPECS) | set(optional),
                )
                self.assertFalse(report["network_access"])
                self.assertFalse(report["executables_started"])
                self.assertFalse(report["hardware_access"])

    def test_current_catalog_pins_board_registry_selection_release(self) -> None:
        official = (
            Path(component_install.__file__).resolve().parents[1]
            / "component-catalog.json"
        )
        catalog, _ = component_install.read_catalog(official)
        registry = catalog["optional_components"]["board-registry"]
        artifact = registry["artifacts"]["windows-x86_64"]
        self.assertEqual(registry["version"], "0.2.3")
        self.assertEqual(
            artifact["url"],
            "https://github.com/Nitmi/board-registry/releases/download/"
            "v0.2.3/embedded-board-registry-0.2.3-windows-x86_64.zip",
        )
        self.assertEqual(
            artifact["sha256"],
            "a6168a5d73144dbc9f81db306497313796f7772d0d28fce5146262d6d0015a91",
        )

    def test_current_catalog_pins_bounded_flash_debugger_release(self) -> None:
        official = (
            Path(component_install.__file__).resolve().parents[1]
            / "component-catalog.json"
        )
        catalog, _ = component_install.read_catalog(official)
        debugger = catalog["components"]["embedded-debugger"]
        artifact = debugger["artifacts"]["windows-x86_64"]
        self.assertEqual(debugger["version"], "0.2.2")
        self.assertEqual(
            artifact["url"],
            "https://github.com/Nitmi/embedded-debugger/releases/download/"
            "v0.2.2/embedded-debugger-0.2.2-x86_64-pc-windows-msvc.zip",
        )
        self.assertEqual(
            artifact["sha256"],
            "b117a67f06e977f9d53143bd1a87c681f87ae8a5c368cea1103f56dc897d12d6",
        )
        self.assertEqual(
            artifact["executable"],
            "embedded-debugger-0.2.2-x86_64-pc-windows-msvc/embedded-debugger.exe",
        )

    def test_current_catalog_pins_blea_pairing_release(self) -> None:
        official = (
            Path(component_install.__file__).resolve().parents[1]
            / "component-catalog.json"
        )
        catalog, _ = component_install.read_catalog(official)
        blea = catalog["components"]["blea"]
        artifact = blea["artifacts"]["windows-x86_64"]
        self.assertEqual(blea["version"], "0.7.0")
        self.assertEqual(
            artifact["url"],
            "https://github.com/Nitmi/blea/releases/download/"
            "v0.7.0/blea-0.7.0-windows-x86_64.zip",
        )
        self.assertEqual(
            artifact["sha256"],
            "e26001160916e5350d5074a3036e0b9a13e53126e1b75b6c64f4fc2688d8e054",
        )
        self.assertEqual(
            artifact["executable"], "blea-0.7.0-windows-x86_64/ble.exe"
        )


if __name__ == "__main__":
    unittest.main()
