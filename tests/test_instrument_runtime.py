from __future__ import annotations

import copy
import json
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import instrument_runtime as runtime
from scripts import toolkit_doctor as doctor

ROOT = Path(__file__).resolve().parents[1]


class InstrumentRuntimeTests(unittest.TestCase):
    def fixture(self, root, layout="windows"):
        site = root / (
            "Lib/site-packages"
            if layout == "windows"
            else "lib/python3.11/site-packages"
        )
        python = root / ("Scripts/python.exe" if layout == "windows" else "bin/python")
        python.parent.mkdir(parents=True)
        python.write_bytes(b"DO NOT EXECUTE OR READ INTERPRETER")
        (root / "pyvenv.cfg").write_text("version = 3.11.15\n")
        pin = copy.deepcopy(runtime.load_pin())
        for component in pin["components"].values():
            for item in component["files"]:
                path = site / item["path"]
                path.parent.mkdir(parents=True, exist_ok=True)
                raw = b"raise AssertionError('selected components must never be imported')\n"
                path.write_bytes(raw)
                item.update(size=len(raw), sha256=runtime.files.digest(raw))
        return site, pin

    def inspect(self, root, pin, selected=None, *, candidate=True):
        with (
            mock.patch.object(runtime, "load_pin", return_value=pin),
            mock.patch.object(
                subprocess, "run", side_effect=AssertionError("no execution")
            ),
            mock.patch.object(
                subprocess, "Popen", side_effect=AssertionError("no execution")
            ),
            mock.patch.object(
                socket, "socket", side_effect=AssertionError("no network")
            ),
        ):
            return runtime.inspect_environment(root, selected, candidate=candidate)

    def test_both_layouts_check_74_files_without_importing_or_execution(self):
        for layout in ("windows", "posix"):
            with self.subTest(layout=layout), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                _, pin = self.fixture(root, layout)
                before = {
                    str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()
                }
                result = self.inspect(root, pin)
                self.assertTrue(result["ok"], result)
                self.assertEqual(result["layout"], layout)
                self.assertEqual(result["resolution_source"], "pinned_local_candidates")
                self.assertEqual(
                    sum(c["verified_files"] for c in result["components"]), 74
                )
                self.assertEqual(
                    {c["name"]: c["version"] for c in result["components"]},
                    {
                        "lab-instruments": "0.8.0",
                        "hil-runner": "0.9.0",
                        "embedded-trace": "0.9.0",
                    },
                )
                for field in (
                    "hardware_access",
                    "executables_started",
                    "native_evaluation_performed",
                    "vendor_sdk_verified",
                    "physical_instrument_verified",
                    "component_cli_verified",
                    "bytecode_verified",
                    "interpreter_authenticated",
                    "release_attestation_verified",
                ):
                    self.assertIs(result[field], False)
                self.assertTrue(
                    all(
                        c["distribution_status"] == "local_candidate"
                        for c in result["components"]
                    )
                )
                self.assertTrue(
                    all(
                        "source_ref" not in c and "url" not in c["wheel"]
                        for c in result["components"]
                    )
                )
                self.assertEqual(
                    before,
                    {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()},
                )

    def test_explicit_candidate_is_required_before_pin_or_environment_reads(self):
        with mock.patch.object(
            runtime, "load_pin", side_effect=AssertionError("must not read pin")
        ):
            for candidate in (False, 1, "true"):
                result = runtime.inspect_environment(
                    Path("absent"), candidate=candidate
                )
                self.assertFalse(result["ok"])
                self.assertIn("--candidate", result["errors"][0])

    def test_partial_selection_does_not_require_unselected_components(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site, pin = self.fixture(root)
            for name in ("hil-runner", "embedded-trace"):
                path = site / pin["components"][name]["files"][0]["path"]
                path.unlink()
            result = self.inspect(root, pin, ["lab-instruments"])
            self.assertTrue(result["ok"])
            self.assertEqual(len(result["components"]), 1)
            self.assertFalse(self.inspect(root, pin)["ok"])
            for selected in ([], ["unknown"], ["lab-instruments", "lab-instruments"]):
                self.assertFalse(self.inspect(root, pin, selected)["ok"])

    def test_changed_missing_and_extra_payloads_fail_without_fallback(self):
        for mode in (
            "changed",
            "missing",
            "extra-file",
            "extra-directory",
            "cache-data",
        ):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                site, pin = self.fixture(root)
                source = site / "lab_instruments/logic_reports.py"
                if mode == "changed":
                    source.write_bytes(b"changed")
                elif mode == "missing":
                    source.unlink()
                elif mode == "extra-directory":
                    (source.parent / "unlisted").mkdir()
                elif mode == "cache-data":
                    cache = source.parent / "__pycache__"
                    cache.mkdir()
                    (cache / "unlisted.txt").write_bytes(b"data")
                else:
                    (source.parent / "unlisted.py").write_bytes(b"data")
                result = self.inspect(root, pin)
                self.assertFalse(result["ok"])
                self.assertEqual(result["status"], "invalid_runtime")

    def test_bytecode_is_not_claimed_verified_and_inventory_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site, pin = self.fixture(root)
            cache = site / "lab_instruments/__pycache__"
            cache.mkdir()
            (cache / "sentinel.pyc").write_bytes(b"never imported")
            result = self.inspect(root, pin)
            self.assertTrue(result["ok"])
            self.assertIs(result["bytecode_verified"], False)
            for index in range(260):
                (cache / f"extra{index}.pyc").write_bytes(b"data")
            self.assertFalse(self.inspect(root, pin)["ok"])

    def test_ambiguous_layout_and_bad_python_declarations_fail(self):
        for mode in ("both-layouts", "old", "duplicate", "relative"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                _, pin = self.fixture(root)
                if mode == "both-layouts":
                    (root / "lib/python3.11/site-packages").mkdir(parents=True)
                elif mode == "old":
                    (root / "pyvenv.cfg").write_text("version = 3.10.1\n")
                elif mode == "duplicate":
                    (root / "pyvenv.cfg").write_text(
                        "version = 3.11.15\nversion_info = 3.13.13\n"
                    )
                else:
                    root = Path("relative")
                self.assertFalse(self.inspect(root, pin)["ok"])

    def test_pin_rejects_publication_claims_drift_unsafe_or_duplicate_files(self):
        for mode in (
            "published",
            "url",
            "ref",
            "drop-component",
            "drop-file",
            "duplicate",
            "traverse",
            "bool-size",
            "size-limit",
            "project",
            "version",
            "revision",
            "wheel-name",
            "wheel-hash",
            "old-schema",
        ):
            with self.subTest(mode=mode):
                pin = copy.deepcopy(runtime.load_pin())
                component = pin["components"]["lab-instruments"]
                if mode == "published":
                    component["status"] = "published"
                elif mode == "url":
                    component["wheel"]["url"] = "https://example.invalid/candidate"
                elif mode == "ref":
                    component["source_ref"] = "refs/tags/v0.8.0"
                elif mode == "drop-component":
                    pin["components"].pop("hil-runner")
                elif mode == "drop-file":
                    component["files"].pop()
                elif mode == "duplicate":
                    component["files"][-1] = component["files"][0]
                elif mode == "traverse":
                    component["files"][0]["path"] = "../outside.py"
                elif mode == "bool-size":
                    component["files"][0]["size"] = True
                elif mode == "size-limit":
                    component["files"][0]["size"] = 1048577
                elif mode == "project":
                    component["project"] = "other"
                elif mode == "version":
                    component["version"] = "0.9.0"
                elif mode == "revision":
                    component["source_revision"] = "unknown"
                elif mode == "wheel-name":
                    component["wheel"]["name"] = "other.whl"
                elif mode == "wheel-hash":
                    component["wheel"]["sha256"] = "invalid"
                else:
                    pin["schema_version"] = "invalid"
                with self.assertRaises(ValueError):
                    runtime.parse_pin(json.dumps(pin).encode())
        with self.assertRaises(ValueError):
            runtime.parse_pin(b'{"components":{},"components":{}}')

    def test_default_doctor_skips_instruments_and_explicit_failure_propagates(self):
        with (
            mock.patch.object(
                doctor, "check_plugin_layout", return_value={"ok": True, "errors": []}
            ),
            mock.patch.object(
                runtime,
                "inspect_environment",
                side_effect=AssertionError("not requested"),
            ),
        ):
            result = doctor.build_report([], 1, ROOT)
        self.assertTrue(result["complete"])
        self.assertNotIn("instruments", result)
        with mock.patch.object(
            doctor, "check_plugin_layout", return_value={"ok": True, "errors": []}
        ):
            result = doctor.build_report(
                [],
                1,
                ROOT,
                instrument_environment=ROOT / "absent",
                instrument_candidate=True,
            )
        self.assertFalse(result["ok"])
        self.assertFalse(result["complete"])
        self.assertIn("instruments: invalid_runtime", result["errors"])
        self.assertIn("[FAIL] Instrument", doctor.render_human(result))

    def test_doctor_validates_pair_before_native_checks(self):
        with mock.patch.object(
            doctor, "check_component", side_effect=AssertionError("no native command")
        ):
            for arguments in (
                {"instrument_candidate": True},
                {"instrument_environment": ROOT},
                {"instrument_environment": ROOT, "instrument_candidate": 1},
            ):
                with self.assertRaises(ValueError):
                    doctor.build_report(doctor.COMPONENTS, 1, ROOT, **arguments)
        for args in (
            ["--instrument-candidate"],
            ["--instrument-environment", str(ROOT)],
        ):
            with self.assertRaises(SystemExit) as error, mock.patch("sys.stderr"):
                doctor.parse_args(args)
            self.assertEqual(error.exception.code, 2)

    def test_successful_optional_doctor_retains_static_qualification(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, pin = self.fixture(root)
            with (
                mock.patch.object(runtime, "load_pin", return_value=pin),
                mock.patch.object(
                    doctor,
                    "check_plugin_layout",
                    return_value={"ok": True, "errors": []},
                ),
                mock.patch.object(
                    subprocess, "run", side_effect=AssertionError("no executable")
                ),
            ):
                result = doctor.build_report(
                    [], 1, ROOT, instrument_environment=root, instrument_candidate=True
                )
            self.assertTrue(result["complete"])
            self.assertIs(result["instruments"]["component_cli_verified"], False)

    def test_script_entry_failure_is_json_and_creates_no_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "missing"
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "scripts/instrument_runtime.py"),
                    "inspect",
                    str(target),
                    "--candidate",
                    "--json",
                ],
                capture_output=True,
                check=False,
                timeout=10,
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            value = json.loads(result.stdout)
            self.assertFalse(value["ok"])
            self.assertIs(value["executables_started"], False)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
