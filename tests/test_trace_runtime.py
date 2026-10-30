from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import toolkit_doctor as doctor
from scripts import trace_runtime as trace

ROOT = Path(__file__).resolve().parents[1]


class TraceInspectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.environment = Path(temporary.name) / "environment"
        self.site = self.environment / "Lib/site-packages"
        self.site.mkdir(parents=True)
        python = self.environment / "Scripts/python.exe"
        python.parent.mkdir()
        python.write_bytes(b"not executable; never start or import this fixture")
        (self.environment / "pyvenv.cfg").write_text("version = 3.11.15\n")
        self.pin = trace.load_pin()
        for item in self.pin["files"]:
            path = self.site / item["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = ("synthetic fixture: " + item["path"]).encode()
            if item["path"] == "embedded_trace/__init__.py":
                raw = b"raise AssertionError('must not import inspected code')\n"
            path.write_bytes(raw)
            item.update(size=len(raw), sha256=trace.digest(raw))
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(trace, "load_pin", return_value=self.pin).start()

    def test_inspection_does_not_execute_import_or_authorize(self):
        with mock.patch.object(
            subprocess, "run", side_effect=AssertionError("no process")
        ):
            report = trace.inspect_environment(self.environment)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["status"], "payload_verified")
        self.assertEqual(report["verified_files"], 28)
        for key in (
            "hardware_access",
            "executables_started",
            "authorization_granted",
            "interpreter_version_verified",
            "interpreter_authenticated",
            "bytecode_verified",
        ):
            self.assertIs(report[key], False)

    def test_same_launcher_does_not_hide_changed_code(self):
        path = self.site / "embedded_trace/cli.py"
        path.write_bytes(path.read_bytes() + b"drift")
        report = trace.inspect_environment(self.environment)
        self.assertFalse(report["ok"])
        self.assertIn("Installed payload differs", report["errors"][0])

    def test_missing_schema_is_a_failure(self):
        (self.site / "embedded_trace/schemas/input.v1.schema.json").unlink()
        self.assertFalse(trace.inspect_environment(self.environment)["ok"])

    def test_metadata_is_part_of_payload_identity(self):
        (self.site / "embedded_trace-0.15.0.dist-info/entry_points.txt").write_bytes(
            b"wrong CLI"
        )
        self.assertFalse(trace.inspect_environment(self.environment)["ok"])

    def test_unreviewed_importable_module_is_rejected(self):
        (self.site / "embedded_trace/cli.pyd").write_bytes(b"unreviewed extension")
        report = trace.inspect_environment(self.environment)
        self.assertFalse(report["ok"])
        self.assertIn("Unexpected Trace package file", report["errors"][0])

    def test_unreviewed_package_directory_is_rejected(self):
        (self.site / "embedded_trace/extra").mkdir()
        self.assertFalse(trace.inspect_environment(self.environment)["ok"])

    def test_generated_bytecode_is_explicitly_outside_identity_claim(self):
        cache = self.site / "embedded_trace/__pycache__"
        cache.mkdir()
        (cache / "cli.cpython-311.pyc").write_bytes(b"generated, not authenticated")
        report = trace.inspect_environment(self.environment)
        self.assertTrue(report["ok"], report)
        self.assertIs(report["bytecode_verified"], False)

    def test_source_size_is_bounded(self):
        (self.site / "embedded_trace/cli.py").write_bytes(b"x" * (1024 * 1024 + 1))
        report = trace.inspect_environment(self.environment)
        self.assertFalse(report["ok"])
        self.assertIn("size limit", report["errors"][0])

    def test_package_walk_is_bounded_even_with_generated_cache(self):
        cache = self.site / "embedded_trace/__pycache__"
        cache.mkdir()
        for index in range(260):
            (cache / f"cli.{index}.pyc").write_bytes(b"generated")
        report = trace.inspect_environment(self.environment)
        self.assertFalse(report["ok"])
        self.assertIn("inventory exceeds limit", report["errors"][0])

    def test_payload_symlink_is_rejected(self):
        source = self.site / "embedded_trace/cli.py"
        outside = self.environment.parent / "outside.py"
        outside.write_bytes(source.read_bytes())
        source.unlink()
        try:
            source.symlink_to(outside)
        except OSError:
            self.skipTest("Symlink creation unavailable")
        self.assertFalse(trace.inspect_environment(self.environment)["ok"])

    def test_posix_layout_is_supported_without_executing_interpreter(self):
        other = self.environment / "lib/python3.11/site-packages"
        other.parent.mkdir(parents=True)
        self.site.rename(other)
        (self.environment / "bin").mkdir()
        (self.environment / "bin/python").write_bytes(b"not an executable")
        report = trace.inspect_environment(self.environment)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["layout"], "posix")

    def test_ambiguous_site_layout_is_rejected(self):
        (self.environment / "lib/python3.11/site-packages").mkdir(parents=True)
        self.assertFalse(trace.inspect_environment(self.environment)["ok"])

    def test_declared_python_versions_are_checked_without_starting_python(self):
        for cfg, valid in (
            ("version_info = 3.13.13\n", True),
            ("version = 3.10.9\n", False),
            ("version = 3.11.15\nversion_info = 3.12.10\n", False),
        ):
            with self.subTest(cfg=cfg):
                (self.environment / "pyvenv.cfg").write_text(cfg)
                self.assertEqual(
                    trace.inspect_environment(self.environment)["ok"], valid
                )

    def test_relative_environment_is_not_searched(self):
        self.assertFalse(trace.inspect_environment(Path("relative"))["ok"])

    def doctor_report(self):
        with (
            mock.patch.object(
                doctor, "check_plugin_layout", return_value={"ok": True, "errors": []}
            ),
            mock.patch.object(
                subprocess, "run", side_effect=AssertionError("no process")
            ),
        ):
            return doctor.build_report([], 1, ROOT, trace_environment=self.environment)

    def test_doctor_accepts_explicit_payload_without_requiring_a_debugger(self):
        result = self.doctor_report()
        self.assertTrue(result["ok"] and result["complete"], result)
        self.assertEqual(
            result["embedded_trace"]["resolution_source"], "pinned_distribution"
        )
        self.assertEqual(result["components"], [])
        self.assertIn("[OK] Embedded Trace", doctor.render_human(result))

    def test_explicit_drift_makes_doctor_incomplete_and_error(self):
        (self.site / "embedded_trace/cli.py").write_bytes(b"drift")
        result = self.doctor_report()
        self.assertFalse(result["ok"] or result["complete"])
        self.assertIn("embedded-trace: invalid_runtime", result["errors"])
        self.assertIn("[FAIL] Embedded Trace", doctor.render_human(result))


class TracePinAndCliTests(unittest.TestCase):
    def test_all_three_routes_select_the_same_complete_trace_payload(self):
        from scripts import instrument_runtime, simulation_runtime

        standalone = trace.load_pin()
        for runtime in (simulation_runtime, instrument_runtime):
            selected = runtime.load_pin()["components"]["embedded-trace"]
            for field in ("version", "source_revision", "wheel", "files"):
                self.assertEqual(standalone[field], selected[field])
        self.assertEqual(standalone["version"], "0.15.0")

    def test_audited_legacy_layout_remains_valid_but_cannot_hide_new_files(self):
        legacy = copy.deepcopy(trace.load_pin())
        legacy["version"] = "0.1.0"
        wheel = "embedded_trace-0.1.0-py3-none-any.whl"
        legacy["wheel"].update(
            name=wheel,
            url="https://github.com/Nitmi/embedded-trace/releases/download/v0.1.0/"
            + wheel,
        )
        legacy["files"] = [
            dict(
                item,
                path=item["path"].replace("-0.15.0.dist-info/", "-0.1.0.dist-info/"),
            )
            for item in legacy["files"]
            if item["path"] in trace.LEGACY_PACKAGE_FILES
            or ".dist-info/" in item["path"]
        ]
        self.assertEqual(len(legacy["files"]), 16)
        self.assertEqual(trace.parse_pin(json.dumps(legacy).encode()), legacy)
        legacy["files"].append(
            next(
                item
                for item in trace.load_pin()["files"]
                if item["path"] == "embedded_trace/thermal.py"
            )
        )
        with self.assertRaises(ValueError):
            trace.parse_pin(json.dumps(legacy).encode())

    def test_semver_alone_cannot_select_an_unaudited_payload_layout(self):
        pin = copy.deepcopy(trace.load_pin())
        pin["version"] = "0.13.2"
        with self.assertRaisesRegex(ValueError, "Unsupported pinned Trace version"):
            trace.parse_pin(json.dumps(pin).encode())

    def test_audited_previous_trace_layout_can_still_be_selected_explicitly(self):
        pin = copy.deepcopy(trace.load_pin())
        pin["version"] = "0.13.1"
        wheel = "embedded_trace-0.13.1-py3-none-any.whl"
        pin["wheel"].update(
            name=wheel,
            url="https://github.com/Nitmi/embedded-trace/releases/download/v0.13.1/"
            + wheel,
        )
        for item in pin["files"]:
            item["path"] = item["path"].replace(
                "-0.15.0.dist-info/", "-0.13.1.dist-info/"
            )
        self.assertEqual(trace.parse_pin(json.dumps(pin).encode()), pin)
        pin["files"].append(
            {"path": "embedded_trace/unreviewed.py", "size": 0, "sha256": "0" * 64}
        )
        with self.assertRaises(ValueError):
            trace.parse_pin(json.dumps(pin).encode())

    def test_pin_cannot_drop_payloads_redirect_or_override_runtime_paths(self):
        original = trace.load_pin()
        for mode in ("drop", "duplicate", "traverse", "redirect", "bad-size"):
            with self.subTest(mode=mode):
                pin = copy.deepcopy(original)
                if mode == "drop":
                    pin["files"].pop()
                elif mode == "duplicate":
                    pin["files"][-1] = pin["files"][0]
                elif mode == "traverse":
                    pin["files"][0]["path"] = "../escape.py"
                elif mode == "redirect":
                    pin["wheel"]["url"] = "https://example.invalid/other.whl"
                else:
                    pin["files"][0]["size"] = True
                with self.assertRaises(ValueError):
                    trace.parse_pin(json.dumps(pin).encode())

    def test_duplicate_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            trace.parse_pin(b'{"version":"0.1.0","version":"0.2.0"}')

    def test_cli_missing_environment_is_json_without_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "scripts/trace_runtime.py"),
                    "inspect",
                    str(missing),
                    "--json",
                ],
                capture_output=True,
                check=False,
                timeout=5,
            )
            self.assertEqual(completed.returncode, 2, completed.stderr)
            self.assertFalse(completed.stderr)
            self.assertIs(json.loads(completed.stdout)["executables_started"], False)
            self.assertFalse(missing.exists())

    def test_default_doctor_does_not_search_for_trace(self):
        with (
            mock.patch.object(
                trace,
                "inspect_environment",
                side_effect=AssertionError("not requested"),
            ),
            mock.patch.object(
                doctor, "check_plugin_layout", return_value={"ok": True, "errors": []}
            ),
        ):
            result = doctor.build_report([], 1, ROOT)
        self.assertTrue(result["ok"])
        self.assertNotIn("embedded_trace", result)

    def test_cli_selection_is_explicit(self):
        args = doctor.parse_args(["--trace-environment", str(ROOT), "--json"])
        self.assertEqual(args.trace_environment, ROOT)

    def test_bundled_example_keeps_exact_native_input_hashes(self):
        fixture = ROOT / "docs/examples/trace"
        spec = json.loads((fixture / "input.json").read_bytes())
        for item in spec["sources"]:
            self.assertEqual(
                trace.digest((fixture / item["path"]).read_bytes()), item["sha256"]
            )
