from __future__ import annotations

import subprocess
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


if __name__ == "__main__":
    unittest.main()
