from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import toolkit_doctor as doctor

ROOT = Path(__file__).resolve().parents[1]


class ComponentCheckTests(unittest.TestCase):
    def test_ready_component_reports_version(self) -> None:
        component = doctor.COMPONENTS[0]
        completed = subprocess.CompletedProcess(
            ["C:/tools/baud.exe", "--version"], 0, "baud 0.1.0\n", ""
        )
        with (
            mock.patch.dict("os.environ", {}, clear=True),
            mock.patch.object(doctor.shutil, "which", return_value="C:/tools/baud.exe"),
            mock.patch.object(doctor.subprocess, "run", return_value=completed) as run,
        ):
            result = doctor.check_component(component, 2.0)

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["version"], "0.1.0")
        run.assert_called_once_with(
            ["C:/tools/baud.exe", "--version"],
            capture_output=True,
            check=False,
            encoding="utf-8",
            errors="replace",
            timeout=2.0,
        )

    def test_missing_component_is_actionable(self) -> None:
        component = doctor.COMPONENTS[1]
        with (
            mock.patch.dict("os.environ", {}, clear=True),
            mock.patch.object(doctor.shutil, "which", return_value=None),
        ):
            result = doctor.check_component(component, 1.0)

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "not_found")
        self.assertIn("uv tool install", result["install_hint"])
        self.assertEqual(result["severity"], "warning")
        self.assertIn(component.environment_variable, result["fallback_hint"])

    def test_invalid_environment_override_is_an_error(self) -> None:
        component = doctor.COMPONENTS[2]
        with mock.patch.dict(
            "os.environ",
            {component.environment_variable: "C:/missing/embedded-debugger.exe"},
            clear=True,
        ):
            result = doctor.check_component(component, 1.0)

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "invalid_environment_override")
        self.assertEqual(result["severity"], "error")

    def test_component_lock_is_hash_checked_before_version_execution(self) -> None:
        component = doctor.COMPONENTS[2]
        locked = {"path": __file__, "sha256": "0" * 64, "version": "0.2.0"}
        with mock.patch.object(
            doctor.subprocess, "run", side_effect=AssertionError("must not execute")
        ):
            result = doctor.check_component(component, 1.0, locked)
        self.assertEqual(result["status"], "component_lock_hash_mismatch")
        self.assertFalse(result["ok"])

    def test_environment_override_cannot_mask_a_component_lock(self) -> None:
        component = doctor.COMPONENTS[2]
        locked = {"path": __file__, "sha256": "0" * 64, "version": "0.2.0"}
        with mock.patch.dict(
            "os.environ", {component.environment_variable: __file__}, clear=True
        ):
            result = doctor.check_component(component, 1.0, locked)
        self.assertEqual(result["status"], "environment_conflicts_with_component_lock")
        self.assertFalse(result["ok"])

    def test_component_lock_version_must_match_observed_version(self) -> None:
        component = doctor.COMPONENTS[0]
        locked = {
            "path": __file__,
            "sha256": doctor.component_lock.sha256(Path(__file__)),
            "version": "9.9.9",
        }
        completed = subprocess.CompletedProcess(
            [__file__, "--version"], 0, "baud 0.1.0\n", ""
        )
        with mock.patch.object(doctor.subprocess, "run", return_value=completed):
            result = doctor.check_component(component, 1.0, locked)
        self.assertEqual(result["status"], "component_lock_version_mismatch")
        self.assertFalse(result["ok"])

    def test_timeout_fails_closed(self) -> None:
        component = doctor.COMPONENTS[2]
        with (
            mock.patch.dict("os.environ", {}, clear=True),
            mock.patch.object(doctor.shutil, "which", return_value="debugger"),
            mock.patch.object(
                doctor.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired(["debugger", "--version"], 0.1),
            ),
        ):
            result = doctor.check_component(component, 0.1)

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "timeout")

    def test_unexpected_output_is_not_accepted(self) -> None:
        component = doctor.COMPONENTS[1]
        completed = subprocess.CompletedProcess(
            ["ble", "--version"], 0, "unknown 1.0\n", ""
        )
        with (
            mock.patch.dict("os.environ", {}, clear=True),
            mock.patch.object(doctor.shutil, "which", return_value="ble"),
            mock.patch.object(doctor.subprocess, "run", return_value=completed),
        ):
            result = doctor.check_component(component, 1.0)

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "unexpected_version_output")
        self.assertIsNone(result["version"])


class PluginLayoutTests(unittest.TestCase):
    def test_codex_cachebuster_preserves_base_version(self) -> None:
        self.assertEqual(doctor.base_plugin_version("0.1.0+codex.20260902"), "0.1.0")

    def test_repository_layout_is_consistent(self) -> None:
        result = doctor.check_plugin_layout(ROOT)
        self.assertTrue(result["ok"], result["errors"])
        self.assertFalse(result["component_mcp_registered"])


class ReportStatusTests(unittest.TestCase):
    def test_missing_path_entry_is_an_overall_warning(self) -> None:
        component = doctor.COMPONENTS[2]
        missing = {
            "name": component.name,
            "ok": False,
            "status": "not_found",
        }
        layout = {
            "ok": True,
            "errors": [],
        }
        with (
            mock.patch.object(doctor, "check_component", return_value=missing),
            mock.patch.object(doctor, "check_plugin_layout", return_value=layout),
        ):
            report = doctor.build_report([component], 1.0, ROOT)

        self.assertTrue(report["ok"])
        self.assertFalse(report["complete"])
        self.assertEqual(report["component_lock_source"], "ambient_environment")
        self.assertEqual(report["status"], "ready_with_warnings")
        self.assertEqual(report["warnings"], ["embedded-debugger: not_found"])
        self.assertEqual(report["errors"], [])

    def test_launch_failure_remains_an_overall_error(self) -> None:
        component = doctor.COMPONENTS[2]
        failed = {
            "name": component.name,
            "ok": False,
            "status": "launch_error",
        }
        layout = {
            "ok": True,
            "errors": [],
        }
        with (
            mock.patch.object(doctor, "check_component", return_value=failed),
            mock.patch.object(doctor, "check_plugin_layout", return_value=layout),
        ):
            report = doctor.build_report([component], 1.0, ROOT)

        self.assertFalse(report["ok"])
        self.assertFalse(report["complete"])
        self.assertEqual(report["status"], "error")
        self.assertEqual(report["errors"], ["embedded-debugger: launch_error"])

    def test_locked_report_without_cli_metadata_names_caller_source(self) -> None:
        component = doctor.COMPONENTS[0]
        layout = {"ok": True, "errors": []}
        with (
            mock.patch.object(
                doctor,
                "check_component",
                return_value={"name": component.name, "ok": True, "status": "ready"},
            ),
            mock.patch.object(doctor, "check_plugin_layout", return_value=layout),
        ):
            report = doctor.build_report(
                [component],
                1.0,
                ROOT,
                {
                    component.name: {
                        "path": __file__,
                        "sha256": "0" * 64,
                        "version": "1",
                    }
                },
            )
        self.assertEqual(report["component_lock_source"], "provided_by_caller")

    def test_optional_component_absent_from_lock_does_not_fall_back_to_path(
        self,
    ) -> None:
        component = doctor.OPTIONAL_COMPONENTS[0]
        layout = {"ok": True, "errors": []}
        with (
            mock.patch.object(
                doctor,
                "check_component",
                side_effect=AssertionError("must not resolve ambient executable"),
            ),
            mock.patch.object(doctor, "check_plugin_layout", return_value=layout),
        ):
            report = doctor.build_report(
                [component],
                1.0,
                ROOT,
                {
                    "baud": {
                        "path": __file__,
                        "sha256": "0" * 64,
                        "version": "1",
                    }
                },
            )

        self.assertEqual(report["components"][0]["status"], "not_in_component_lock")
        self.assertFalse(report["complete"])

    def test_optional_component_can_be_checked_explicitly(self) -> None:
        component = doctor.OPTIONAL_COMPONENTS[0]
        completed = subprocess.CompletedProcess(
            ["board-registry", "--version"], 0, "board-registry 0.1.0\n", ""
        )
        with (
            mock.patch.dict("os.environ", {}, clear=True),
            mock.patch.object(doctor.shutil, "which", return_value="board-registry"),
            mock.patch.object(doctor.subprocess, "run", return_value=completed),
        ):
            result = doctor.check_component(component, 1.0)

        self.assertTrue(result["ok"])
        self.assertEqual(result["version"], "0.1.0")


class LockSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.lock = self.root / "toolchain-lock.json"
        components = {}
        for name in doctor.component_lock.SPECS:
            executable = self.root / f"{name}.exe"
            executable.write_bytes(name.encode("ascii"))
            components[name] = {
                "path": str(executable.resolve()),
                "sha256": doctor.component_lock.sha256(executable),
                "version": "1.0.0",
            }
        self.lock.write_text(
            json.dumps(
                {
                    "schema_version": doctor.component_lock.SCHEMA,
                    "components": components,
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def ready(self, args, **_kwargs):
        name = Path(args[0]).stem
        prefix = "ble" if name == "blea" else name
        return subprocess.CompletedProcess(args, 0, f"{prefix} 1.0.0\n", "")

    def test_project_lock_is_auto_selected_before_workstation_config(self) -> None:
        project = self.root / "project"
        project_lock = project / ".embedded" / "toolchain-lock.json"
        project_lock.parent.mkdir(parents=True)
        project_lock.write_bytes(self.lock.read_bytes())
        with (
            mock.patch.object(doctor.Path, "cwd", return_value=project),
            mock.patch.object(
                doctor.station_config, "config_path", return_value=self.root / "missing"
            ),
            mock.patch.dict(doctor.os.environ, {}, clear=True),
            mock.patch.object(doctor.subprocess, "run", side_effect=self.ready),
            mock.patch.object(
                doctor, "check_plugin_layout", return_value={"ok": True, "errors": []}
            ),
            mock.patch("builtins.print") as output,
        ):
            code = doctor.main(["--strict", "--json"])
        self.assertEqual(code, 0)
        report = json.loads(output.call_args.args[0])
        self.assertEqual(report["component_lock_source"], "project")
        self.assertEqual(report["component_lock_path"], str(project_lock.resolve()))

    def test_workstation_lock_is_auto_selected_when_project_lock_is_absent(
        self,
    ) -> None:
        config = self.root / "station.json"
        doctor.station_config.select(config, self.lock, False)
        with (
            mock.patch.object(doctor.Path, "cwd", return_value=self.root / "project"),
            mock.patch.object(
                doctor.station_config, "config_path", return_value=config
            ),
            mock.patch.dict(doctor.os.environ, {}, clear=True),
            mock.patch.object(doctor.subprocess, "run", side_effect=self.ready),
            mock.patch.object(
                doctor, "check_plugin_layout", return_value={"ok": True, "errors": []}
            ),
            mock.patch("builtins.print") as output,
        ):
            code = doctor.main(["--strict", "--json"])
        self.assertEqual(code, 0)
        report = json.loads(output.call_args.args[0])
        self.assertEqual(report["component_lock_source"], "workstation")
        self.assertTrue(report["component_lock_used"])

    def test_no_auto_lock_preserves_ambient_resolution(self) -> None:
        with (
            mock.patch.object(doctor.Path, "cwd", return_value=self.root),
            mock.patch.object(
                doctor.station_config,
                "config_path",
                side_effect=AssertionError("must not inspect station config"),
            ),
            mock.patch.object(doctor, "build_report") as build,
            mock.patch("builtins.print"),
        ):
            build.return_value = {"complete": True, "ok": True}
            code = doctor.main(["--no-auto-lock", "--json"])
        self.assertEqual(code, 0)
        self.assertIsNone(build.call_args.args[3])


if __name__ == "__main__":
    unittest.main()
