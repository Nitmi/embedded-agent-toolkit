from __future__ import annotations

import contextlib
import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import simulation_runtime as sim
from scripts import toolkit_doctor as doctor

ROOT = Path(__file__).resolve().parents[1]


class SimulationRuntimeTests(unittest.TestCase):
    def fixture(self, root, layout="windows", *, candidate=False):
        site = root / (
            "Lib/site-packages"
            if layout == "windows"
            else "lib/python3.11/site-packages"
        )
        python = root / ("Scripts/python.exe" if layout == "windows" else "bin/python")
        python.parent.mkdir(parents=True)
        python.write_bytes(b"DO NOT EXECUTE")
        (root / "pyvenv.cfg").write_text("version = 3.11.15\n")
        pin = copy.deepcopy(sim.load_pin(candidate=candidate))
        for component in pin["components"].values():
            for item in component["files"]:
                path = site / item["path"]
                path.parent.mkdir(parents=True, exist_ok=True)
                raw = b"raise AssertionError('must not import')\n"
                path.write_bytes(raw)
                item.update(size=len(raw), sha256=sim.files.digest(raw))
        return site, pin

    def inspect(self, root, pin, selected=None, *, candidate=False):
        with (
            mock.patch.object(sim, "load_pin", return_value=pin),
            mock.patch.object(
                subprocess, "run", side_effect=AssertionError("must not execute")
            ),
            mock.patch.object(
                subprocess, "Popen", side_effect=AssertionError("must not execute")
            ),
        ):
            return sim.inspect_environment(root, selected, candidate=candidate)

    def test_candidate_requires_explicit_selection_and_has_no_release_identity(self):
        candidate = sim.load_pin(candidate=True)
        published = sim.load_pin()
        with self.assertRaises(ValueError):
            sim.parse_pin(json.dumps(candidate).encode())
        with self.assertRaises(ValueError):
            sim.parse_pin(json.dumps(published).encode(), candidate=True)
        for layout in ("windows", "posix"):
            with self.subTest(layout=layout), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                _, pin = self.fixture(root, layout, candidate=True)
                result = self.inspect(root, pin, candidate=True)
                self.assertTrue(result["ok"], result)
                self.assertIs(result["candidate_mode"], True)
                self.assertEqual(result["resolution_source"], "pinned_local_candidates")
                self.assertEqual(
                    sum(c["verified_files"] for c in result["components"]), 66
                )
                for component in result["components"]:
                    self.assertEqual(
                        component["version"], sim.CANDIDATE_VERSIONS[component["name"]]
                    )
                    self.assertEqual(
                        component["distribution_status"], "local_candidate"
                    )
                    self.assertIsNone(component["source_ref"])
                    self.assertNotIn("url", component["wheel"])
                for flag in (
                    "executables_started",
                    "hardware_access",
                    "release_attestation_verified",
                    "backend_runtime_verified",
                ):
                    self.assertIs(result[flag], False)

    def test_candidate_cannot_claim_published_status_tag_or_url_and_binds_full_inventory(
        self,
    ):
        original = sim.load_pin(candidate=True)
        for mutation in (
            "status",
            "ref",
            "url",
            "version",
            "drop",
            "duplicate",
            "path",
            "bool-size",
            "revision",
            "wheel",
        ):
            with self.subTest(mutation=mutation):
                pin = copy.deepcopy(original)
                item = pin["components"]["sim-runner"]
                if mutation == "status":
                    item["status"] = "published"
                elif mutation == "ref":
                    item["source_ref"] = "refs/tags/v0.6.0"
                elif mutation == "url":
                    item["wheel"]["url"] = "https://example.invalid/future.whl"
                elif mutation == "version":
                    item["version"] = "0.5.0"
                elif mutation == "drop":
                    item["files"].pop()
                elif mutation == "duplicate":
                    item["files"][-1] = item["files"][0]
                elif mutation == "path":
                    item["files"][0]["path"] = "../escape.py"
                elif mutation == "bool-size":
                    item["files"][0]["size"] = True
                elif mutation == "revision":
                    item["source_revision"] = "main"
                else:
                    item["wheel"]["sha256"] = "invalid"
                with self.assertRaises(ValueError):
                    sim.parse_pin(json.dumps(pin).encode(), candidate=True)

    def test_candidate_new_module_missing_drift_and_extra_bytes_are_rejected(self):
        for change in ("missing", "drift", "extra"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                site, pin = self.fixture(root, candidate=True)
                target = site / "sim_runner/gpio_fault.py"
                if change == "missing":
                    target.unlink()
                elif change == "drift":
                    target.write_bytes(b"changed")
                else:
                    (target.parent / "extra_fault.py").write_bytes(b"unexpected")
                self.assertFalse(self.inspect(root, pin, candidate=True)["ok"])

    def test_candidate_doctor_requires_environment_before_checking_components(self):
        with (
            mock.patch.object(
                doctor, "check_component", side_effect=AssertionError("not selected")
            ),
            self.assertRaises(ValueError),
        ):
            doctor.build_report(doctor.COMPONENTS, 1, ROOT, simulation_candidate=True)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            doctor.parse_args(["--simulation-candidate"])
        self.assertTrue(
            doctor.parse_args(
                ["--simulation-candidate", "--simulation-environment", str(ROOT)]
            ).simulation_candidate
        )
        with (
            mock.patch.object(
                doctor, "check_plugin_layout", return_value={"ok": True, "errors": []}
            ),
            mock.patch.object(
                sim, "inspect_environment", return_value={"ok": True}
            ) as inspector,
        ):
            result = doctor.build_report(
                [], 1, ROOT, simulation_environment=ROOT, simulation_candidate=True
            )
        self.assertTrue(result["complete"])
        inspector.assert_called_once_with(ROOT, candidate=True)

    def test_windows_and_posix_payloads_are_checked_without_starting_interpreter(self):
        for layout in ("windows", "posix"):
            with self.subTest(layout=layout), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                site, pin = self.fixture(root, layout)
                # Interpreter bytes are not authenticated/read; fake file is sufficient.
                original = sim.files.read

                def no_python_read(path, *args, original=original):
                    self.assertNotIn(path.name, ("python", "python.exe"))
                    return original(path, *args)

                with mock.patch.object(sim.files, "read", side_effect=no_python_read):
                    report = self.inspect(root, pin)
                self.assertTrue(report["ok"], report)
                self.assertEqual(report["layout"], layout)
                self.assertEqual(report["resolution_source"], "pinned_releases")
                self.assertEqual(
                    sum(x["verified_files"] for x in report["components"]), 65
                )
                for flag in (
                    "executables_started",
                    "hardware_access",
                    "authorization_granted",
                    "physical_board_verified",
                    "backend_runtime_verified",
                    "interpreter_authenticated",
                    "release_attestation_verified",
                ):
                    self.assertIs(report[flag], False)
                for component in report["components"]:
                    selected = pin["components"][component["name"]]
                    self.assertEqual(component["distribution_status"], "published")
                    for key in ("repository", "source_ref", "source_revision", "wheel"):
                        self.assertEqual(component[key], selected[key])
                self.assertFalse(list(site.rglob("__pycache__")))

    def test_selected_missing_changed_or_extra_package_bytes_fail(self):
        for name in sim.SPECS:
            for change in (
                "missing",
                "drift",
                "extra",
                "directory",
                "bad-cfg",
                "bad-python",
            ):
                with (
                    self.subTest(name=name, change=change),
                    tempfile.TemporaryDirectory() as tmp,
                ):
                    root = Path(tmp)
                    site, pin = self.fixture(root)
                    package = site / sim.SPECS[name][0]
                    if change == "missing":
                        (package / "__init__.py").unlink()
                    elif change == "drift":
                        (package / "__init__.py").write_bytes(b"changed")
                    elif change == "extra":
                        (package / "surprise.py").write_bytes(b"extra")
                    elif change == "directory":
                        (package / "unexpected").mkdir()
                    elif change == "bad-cfg":
                        (root / "pyvenv.cfg").write_text("version = 3.10.0\n")
                    else:
                        (root / "Scripts/python.exe").unlink()
                    report = self.inspect(root, pin, [name])
                    self.assertFalse(report["ok"], report)
                    self.assertIs(report["executables_started"], False)

    def test_explicit_subset_ignores_absent_unselected_distribution(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site, pin = self.fixture(root)
            (site / "hil_runner/__init__.py").unlink()
            self.assertTrue(self.inspect(root, pin, ["embedded-trace"])["ok"])
            self.assertFalse(self.inspect(root, pin)["ok"])

    def test_generated_bytecode_is_not_claimed_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site, pin = self.fixture(root)
            cache = site / "sim_runner/__pycache__"
            cache.mkdir()
            (cache / "cli.cpython-311.pyc").write_bytes(b"unverified")
            report = self.inspect(root, pin)
            self.assertTrue(report["ok"], report)
            self.assertIs(report["bytecode_verified"], False)
            (cache / "hidden.py").write_bytes(b"unexpected")
            self.assertFalse(self.inspect(root, pin)["ok"])

    def test_linked_payload_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            site, pin = self.fixture(root)
            original = site / "sim_runner/__init__.py"
            target = root / "outside.py"
            target.write_bytes(original.read_bytes())
            original.unlink()
            try:
                original.symlink_to(target)
            except OSError:
                self.skipTest("Symlink privilege unavailable")
            self.assertFalse(self.inspect(root, pin)["ok"])

    def test_pin_rejects_incomplete_redirected_and_malformed_identities(self):
        original = sim.load_pin()
        for mode in (
            "drop-component",
            "drop-file",
            "duplicate",
            "traverse",
            "bool-size",
            "version",
            "url",
            "candidate",
            "ref",
            "revision",
            "repository",
            "wheel-name",
            "wheel-hash",
            "missing-ref",
            "old-schema",
        ):
            with self.subTest(mode=mode):
                pin = copy.deepcopy(original)
                item = pin["components"]["sim-runner"]
                if mode == "drop-component":
                    pin["components"].pop("hil-runner")
                elif mode == "drop-file":
                    item["files"].pop()
                elif mode == "duplicate":
                    item["files"][-1] = item["files"][0]
                elif mode == "traverse":
                    item["files"][0]["path"] = "../escape.py"
                elif mode == "bool-size":
                    item["files"][0]["size"] = True
                elif mode == "version":
                    item["version"] = "0.1.0"
                elif mode == "url":
                    item["wheel"]["url"] = "https://example.invalid"
                elif mode == "candidate":
                    item["status"] = "local_candidate"
                elif mode == "ref":
                    item["source_ref"] = "refs/heads/main"
                elif mode == "revision":
                    item["source_revision"] = "not-a-commit"
                elif mode == "repository":
                    item["repository"] = "other/sim-runner"
                elif mode == "wheel-name":
                    item["wheel"]["name"] = "other.whl"
                elif mode == "wheel-hash":
                    item["wheel"]["sha256"] = "not-a-hash"
                elif mode == "missing-ref":
                    item.pop("source_ref")
                else:
                    pin["schema_version"] = (
                        "embedded-agent-toolkit.simulation-runtime.v1"
                    )
                with self.assertRaises(ValueError):
                    sim.parse_pin(json.dumps(pin).encode())
        with self.assertRaises(ValueError):
            sim.parse_pin(b'{"components":{},"components":{}}')

    def test_release_urls_cannot_redirect_across_repository_version_or_asset(self):
        for name in sim.SPECS:
            for suffix in ("?download=1", "#other", "/extra"):
                with self.subTest(name=name, suffix=suffix):
                    pin = copy.deepcopy(sim.load_pin())
                    pin["components"][name]["wheel"]["url"] += suffix
                    with self.assertRaises(ValueError):
                        sim.parse_pin(json.dumps(pin).encode())
            for old, new in (
                (f"Nitmi/{name}", "Nitmi/other"),
                ("releases/download/v", "releases/download/other-v"),
                ("https://", "http://"),
            ):
                with self.subTest(name=name, replacement=new):
                    pin = copy.deepcopy(sim.load_pin())
                    item = pin["components"][name]
                    item["wheel"]["url"] = item["wheel"]["url"].replace(old, new)
                    with self.assertRaises(ValueError):
                        sim.parse_pin(json.dumps(pin).encode())

    def test_cli_failure_is_json_and_does_not_write_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "scripts/simulation_runtime.py"),
                    "inspect",
                    str(missing),
                    "--json",
                ],
                capture_output=True,
                check=False,
                timeout=5,
            )
            self.assertEqual(completed.returncode, 2, completed.stderr)
            report = json.loads(completed.stdout)
            self.assertIs(report["executables_started"], False)
            self.assertFalse(missing.exists())

    def test_default_doctor_does_not_inspect_and_explicit_failure_propagates(self):
        with (
            mock.patch.object(
                doctor, "check_plugin_layout", return_value={"ok": True, "errors": []}
            ),
            mock.patch.object(
                sim, "inspect_environment", side_effect=AssertionError("not requested")
            ),
        ):
            result = doctor.build_report([], 1, ROOT)
        self.assertTrue(result["complete"])
        self.assertNotIn("simulation", result)
        with mock.patch.object(
            doctor, "check_plugin_layout", return_value={"ok": True, "errors": []}
        ):
            result = doctor.build_report(
                [], 1, ROOT, simulation_environment=ROOT / "absent"
            )
        self.assertFalse(result["ok"])
        self.assertFalse(result["complete"])
        self.assertIn("simulation: invalid_runtime", result["errors"])
        self.assertIn("[FAIL] Simulation", doctor.render_human(result))
        self.assertEqual(
            doctor.parse_args(
                ["--simulation-environment", str(ROOT)]
            ).simulation_environment,
            ROOT,
        )


if __name__ == "__main__":
    unittest.main()
