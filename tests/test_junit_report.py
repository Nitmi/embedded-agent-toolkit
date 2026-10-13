from __future__ import annotations

import copy
import hashlib
import io
import json
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import test_test_contract as contract_fixtures

from scripts import junit_report, test_contract

ROOT = Path(__file__).resolve().parents[1]


class JunitReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = contract_fixtures.TestContractTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.output = self.root / "result.xml"

    def prepare(self, **options):
        return self.fixture.prepare_evaluation(**options)

    def cli(self, contract, run, output=None, *, machine=True):
        out, err = io.StringIO(), io.StringIO()
        arguments = [
            "junit",
            str(contract),
            "--run",
            str(run),
            "--output",
            str(output or self.output),
        ]
        if machine:
            arguments.append("--json")
        with redirect_stdout(out), redirect_stderr(err):
            result = test_contract.main(arguments)
        return result, out.getvalue(), err.getvalue()

    def assert_counts(self, report):
        tree = ET.fromstring(self.output.read_bytes())
        cases = tree.findall("./testsuite/testcase")
        expected = {
            "tests": len(cases),
            "failures": len(tree.findall("./testsuite/testcase/failure")),
            "errors": len(tree.findall("./testsuite/testcase/error")),
            "skipped": len(tree.findall("./testsuite/testcase/skipped")),
        }
        for key, value in expected.items():
            self.assertEqual(int(tree.get(key)), value)
            self.assertEqual(int(tree.find("testsuite").get(key)), value)
            self.assertEqual(report["junit"][key], value)
        self.assertEqual(
            report["junit"]["sha256"],
            hashlib.sha256(self.output.read_bytes()).hexdigest(),
        )
        self.assertEqual(report["junit"]["size_bytes"], self.output.stat().st_size)
        self.assertEqual(
            len({(item.get("classname"), item.get("name")) for item in cases}),
            len(cases),
        )
        self.assertTrue(all(item.get("time") is None for item in cases))
        return tree

    def test_passing_export_binds_contract_run_hashes_without_processes(self):
        contract, run, _ = self.prepare()
        with mock.patch("subprocess.run", side_effect=AssertionError("no component")):
            report = test_contract.junit_export(contract, run, self.output)
        self.assertTrue(report["ok"] and report["complete"])
        self.assertEqual(report["schema_version"], junit_report.SCHEMA)
        self.assertEqual(report["contract"]["sha256"], test_contract.sha256(contract))
        self.assertEqual(report["run"]["sha256"], test_contract.sha256(run))
        self.assertEqual(report["junit"]["failures"], 0)
        self.assertEqual(report["junit"]["errors"], 0)
        tree = self.assert_counts(report)
        categories = {
            item.get("classname").rsplit(".", 1)[-1]
            for item in tree.findall("./testsuite/testcase")
        }
        self.assertEqual(
            categories, {"contract", "inputs", "stages", "assertions", "cleanup"}
        )
        properties = {
            item.get("name"): item.get("value")
            for item in tree.findall("./testsuite/properties/property")
        }
        self.assertEqual(properties["contract_sha256"], report["contract"]["sha256"])
        self.assertEqual(properties["scope"], "host_only_evidence_evaluation")
        self.assertEqual(properties["source_execution_not_performed"], "true")
        for field in (
            "authorization_granted",
            "execution_supported",
            "hardware_access",
            "executables_started",
        ):
            self.assertIs(report[field], False)
            self.assertEqual(properties[field], "false")

    def test_failed_assertion_and_cleanup_write_failures_and_exit_nonzero(self):
        contract, run, _ = self.prepare(flash_ok=False, target_state="halted")
        code, output, error = self.cli(contract, run)
        self.assertEqual(code, 2)
        self.assertEqual(error, "")
        report = json.loads(output)
        self.assertFalse(report["ok"])
        self.assertTrue(report["complete"])
        self.assertEqual(report["junit"]["failures"], 2)
        self.assertEqual(report["junit"]["errors"], 0)
        failures = self.assert_counts(report).findall("./testsuite/testcase/failure")
        self.assertTrue(
            any('"actual_state": "halted"' in item.text for item in failures)
        )

    def test_missing_evidence_and_unevaluated_assertions_are_errors_not_skips(self):
        contract, run, execute = self.prepare()
        execute.unlink()
        code, output, _ = self.cli(contract, run)
        self.assertEqual(code, 2)
        report = json.loads(output)
        self.assertFalse(report["complete"])
        self.assertGreater(report["junit"]["errors"], 0)
        self.assertEqual(report["junit"]["skipped"], 0)
        tree = self.assert_counts(report)
        self.assertIsNotNone(
            tree.find("./testsuite/testcase[@name='flash-execute']/error")
        )
        self.assertIsNotNone(tree.find("./testsuite/testcase[@name='flash-ok']/error"))

    def test_current_input_drift_cannot_be_hidden_by_passing_evidence(self):
        contract, run, _ = self.prepare()
        self.fixture.firmware.write_bytes(b"changed")
        report = test_contract.junit_export(contract, run, self.output)
        self.assertFalse(report["ok"] or report["complete"])
        self.assertEqual(report["evaluation_summary"]["assertions_passed"], 1)
        tree = self.assert_counts(report)
        self.assertIsNotNone(
            tree.find("./testsuite/testcase[@name='inputs-current']/error")
        )

    def test_missing_pointer_and_wrong_cleanup_type_are_errors(self):
        contract, run_path, execute = self.prepare()
        evidence = json.loads(execute.read_text())
        evidence.pop("ok")
        evidence["cleanup"]["target"] = 1
        self.fixture.write_json(execute, evidence)
        run = json.loads(run_path.read_text())
        for row in run["stage_evidence"] + run["cleanup_evidence"]:
            if Path(row["path"]).resolve() == execute.resolve():
                # Exercise equivalent spellings, including Windows short paths.
                row["path"] = str(execute.parent / ".." / "evidence" / execute.name)
                row["sha256"] = test_contract.sha256(execute)
        self.fixture.write_json(run_path, run)
        report = test_contract.junit_export(contract, run_path, self.output)
        self.assertGreaterEqual(report["junit"]["errors"], 2)
        self.assert_counts(report)

    def test_existing_output_stops_before_reading_inputs_and_is_preserved(self):
        self.output.write_bytes(b"original")
        with mock.patch.object(
            test_contract, "evaluate_contract", side_effect=AssertionError
        ):
            code, output, _ = self.cli(self.root / "absent", self.root / "absent")
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output)["status"], "invalid")
        self.assertEqual(self.output.read_bytes(), b"original")

    def test_exclusive_write_catches_creation_after_preflight(self):
        contract, run, _ = self.prepare()
        original = test_contract.evaluate_contract

        def evaluation(*args):
            value = original(*args)
            self.output.write_bytes(b"concurrent")
            return value

        with mock.patch.object(
            test_contract, "evaluate_contract", side_effect=evaluation
        ):
            code, output, _ = self.cli(contract, run)
        self.assertEqual(code, 2)
        self.assertNotIn("junit", json.loads(output))
        self.assertEqual(self.output.read_bytes(), b"concurrent")

    def test_invalid_contract_or_run_does_not_create_xml(self):
        contract, run, _ = self.prepare()
        value = json.loads(run.read_text())
        value["contract_sha256"] = "0" * 64
        self.fixture.write_json(run, value)
        code, output, _ = self.cli(contract, run)
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output)["status"], "invalid")
        self.assertFalse(self.output.exists())

    def test_markup_controls_unicode_and_lone_surrogates_remain_well_formed(self):
        contract, run, _ = self.prepare()
        evaluation = test_contract.evaluate_contract(contract, run)
        diagnostic = "中文 <failure/> & \x00 \ud800"
        evaluation["assertions"][0]["actual"] = {"type": "string", "value": diagnostic}
        payload, counts = junit_report.render(evaluation)
        tree = ET.fromstring(payload)
        text = tree.find("./testsuite/testcase[@name='flash-ok']/system-out").text
        actual = json.loads(text)
        self.assertEqual(actual["actual"]["value"], diagnostic)
        self.assertIsNone(tree.find("./testsuite/testcase/failure"))
        self.assertEqual(counts["failures"], 0)

    def test_diagnostics_are_bounded_and_truncation_is_visible(self):
        contract, run, _ = self.prepare()
        evaluation = test_contract.evaluate_contract(contract, run)
        evaluation["assertions"][0]["expected"] = "X" * 10000
        payload, _ = junit_report.render(evaluation)
        text = (
            ET.fromstring(payload)
            .find("./testsuite/testcase[@name='flash-ok']/system-out")
            .text
        )
        self.assertIn("diagnostic truncated", text)
        self.assertLess(len(text), 4200)

    def test_limits_reject_without_writing_and_do_not_allow_empty_green_report(self):
        contract, run, _ = self.prepare()
        evaluation = test_contract.evaluate_contract(contract, run)
        for field, value in (("MAX_CASES", 1), ("MAX_XML_BYTES", 1)):
            with (
                self.subTest(field=field),
                mock.patch.object(junit_report, field, value),
            ):
                with self.assertRaises(junit_report.JunitError):
                    junit_report.export(evaluation, self.output)
                self.assertFalse(self.output.exists())
        inconsistent = copy.deepcopy(evaluation)
        inconsistent["ok"] = False
        with self.assertRaisesRegex(junit_report.JunitError, "outcomes differ"):
            junit_report.render(inconsistent)

    def test_distinct_categories_preserve_same_named_stage_and_assertion(self):
        contract, run, _ = self.prepare()
        evaluation = test_contract.evaluate_contract(contract, run)
        evaluation["assertions"][0]["id"] = evaluation["stages"][0]["id"]
        payload, counts = junit_report.render(evaluation)
        self.assertEqual(
            len(ET.fromstring(payload).findall("./testsuite/testcase")), counts["tests"]
        )
        evaluation["assertions"].append(copy.deepcopy(evaluation["assertions"][0]))
        with self.assertRaisesRegex(junit_report.JunitError, "duplicated"):
            junit_report.render(evaluation)

    def test_repeated_exports_are_deterministic_and_inputs_unchanged(self):
        contract, run, _ = self.prepare()
        before = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in self.root.rglob("*")
            if path.is_file()
        }
        first = test_contract.junit_export(contract, run, self.output)
        second = test_contract.junit_export(contract, run, self.root / "second.xml")
        self.assertEqual(first["junit"]["sha256"], second["junit"]["sha256"])
        for path, digest in before.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)

    def test_invalid_extension_or_missing_parent_has_structured_error(self):
        for output in (self.root / "result.json", self.root / "absent/result.xml"):
            with self.subTest(output=output):
                code, value, _ = self.cli(
                    self.root / "absent", self.root / "absent", output
                )
                self.assertEqual(code, 2)
                result = json.loads(value)
                self.assertEqual(result["schema_version"], junit_report.SCHEMA)
                self.assertEqual(result["status"], "invalid")
                self.assertFalse(output.exists())

    def test_cli_text_and_actual_subprocess_exit_agree_with_xml(self):
        contract, run, _ = self.prepare(flash_ok=False)
        code, _, error = self.cli(contract, run, machine=False)
        self.assertEqual(code, 2)
        self.assertIn("Test evidence failed", error)
        command = [
            sys.executable,
            "-B",
            str(ROOT / "scripts/test_contract.py"),
            "junit",
            str(contract),
            "--run",
            str(run),
            "--output",
            str(self.root / "subprocess.xml"),
            "--json",
        ]
        result = subprocess.run(
            command, cwd=self.root, capture_output=True, timeout=15, text=True
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)["junit"]["failures"], 1)
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
