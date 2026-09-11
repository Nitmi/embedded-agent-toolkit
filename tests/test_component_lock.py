from __future__ import annotations

import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import component_lock


class ComponentLockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.executables = {}
        for name in component_lock.SPECS:
            path = self.root / f"{name}.exe"
            path.write_bytes(f"fixture {name}".encode())
            self.executables[name] = str(path)

    def completed(self, args, **_kwargs):
        outputs = {
            "baud": "baud 0.1.0\n",
            "blea": "ble 0.6.4\n",
            "embedded-debugger": "embedded-debugger 0.2.0\n",
            "board-registry": "board-registry 0.1.0\n",
        }
        return subprocess.CompletedProcess(args, 0, outputs[Path(args[0]).stem], "")

    def create(self) -> Path:
        output = self.root / "toolchain-lock.json"
        with mock.patch.object(
            component_lock.subprocess, "run", side_effect=self.completed
        ):
            result = component_lock.create(output, self.executables, 1.0)
        self.assertTrue(result["ok"])
        return output

    def test_create_and_offline_inspect_bind_every_executable(self) -> None:
        output = self.create()
        with mock.patch.object(
            component_lock.subprocess, "run", side_effect=AssertionError("must not run")
        ):
            result = component_lock.inspect(output)
        self.assertFalse(result["executables_started"])
        self.assertEqual(set(result["components"]), set(component_lock.SPECS))

    def test_legacy_v1_core_lock_remains_readable(self) -> None:
        output = self.create()
        payload = json.loads(output.read_bytes())
        payload["schema_version"] = component_lock.LEGACY_SCHEMA
        output.write_text(json.dumps(payload), encoding="utf-8")

        result = component_lock.inspect(output)
        self.assertEqual(result["schema_version"], component_lock.LEGACY_SCHEMA)
        self.assertEqual(set(result["components"]), set(component_lock.SPECS))

    def test_v2_lock_can_bind_optional_board_registry(self) -> None:
        registry = self.root / "board-registry.exe"
        registry.write_bytes(b"fixture board-registry")
        selections = {**self.executables, "board-registry": str(registry)}
        output = self.root / "optional-lock.json"
        with mock.patch.object(
            component_lock.subprocess, "run", side_effect=self.completed
        ):
            result = component_lock.create(output, selections, 1.0)

        self.assertEqual(result["schema_version"], component_lock.SCHEMA)
        self.assertEqual(result["components"]["board-registry"]["version"], "0.1.0")
        self.assertTrue(
            Path(component_lock.parse_lock(output)["board-registry"]["path"]).samefile(
                registry
            )
        )

    def test_existing_output_is_never_replaced(self) -> None:
        output = self.create()
        before = output.read_bytes()
        with self.assertRaisesRegex(component_lock.LockError, "already exists"):
            component_lock.create(output, self.executables, 1.0)
        self.assertEqual(output.read_bytes(), before)

    def test_failed_post_write_validation_removes_new_output(self) -> None:
        output = self.root / "toolchain-lock.json"
        with (
            mock.patch.object(
                component_lock.subprocess, "run", side_effect=self.completed
            ),
            mock.patch.object(
                component_lock,
                "parse_lock",
                side_effect=component_lock.LockError("validation failed"),
            ),
            self.assertRaisesRegex(component_lock.LockError, "validation failed"),
        ):
            component_lock.create(output, self.executables, 1.0)
        self.assertFalse(output.exists())

    def test_hash_drift_is_rejected(self) -> None:
        output = self.create()
        Path(self.executables["baud"]).write_bytes(b"changed")
        with self.assertRaisesRegex(component_lock.LockError, "hash differs"):
            component_lock.inspect(output)

    def test_compare_reports_exact_changed_fields_without_execution(self) -> None:
        base = self.create()
        candidate = self.root / "candidate-lock.json"
        payload = json.loads(base.read_bytes())
        replacement = self.root / "replacement-baud.exe"
        replacement.write_bytes(b"replacement baud")
        payload["components"]["baud"] = {
            "path": str(replacement.resolve()),
            "sha256": component_lock.sha256(replacement),
            "version": "0.2.0",
        }
        candidate.write_text(json.dumps(payload), encoding="utf-8")

        with mock.patch.object(
            component_lock.subprocess, "run", side_effect=AssertionError("must not run")
        ):
            report = component_lock.compare(base, candidate)

        self.assertFalse(report["identical"])
        self.assertEqual(report["change_count"], 1)
        self.assertEqual(
            report["changes"]["baud"]["changed_fields"],
            ["path", "version", "sha256"],
        )
        self.assertFalse(report["executables_started"])
        self.assertFalse(report["hardware_access"])

    def test_compare_identical_locks_has_no_changes(self) -> None:
        lock = self.create()
        report = component_lock.compare(lock, lock)
        self.assertTrue(report["identical"])
        self.assertEqual(report["changes"], {})

    def test_compare_reports_optional_component_presence(self) -> None:
        base = self.create()
        registry = self.root / "board-registry.exe"
        registry.write_bytes(b"fixture board-registry")
        candidate = self.root / "candidate-with-registry.json"
        with mock.patch.object(
            component_lock.subprocess, "run", side_effect=self.completed
        ):
            component_lock.create(
                candidate,
                {**self.executables, "board-registry": str(registry)},
                1.0,
            )

        report = component_lock.compare(base, candidate)
        self.assertEqual(
            report["changes"]["board-registry"]["changed_fields"], ["presence"]
        )
        self.assertIsNone(report["changes"]["board-registry"]["before"])
        self.assertEqual(
            report["changes"]["board-registry"]["after"]["version"], "0.1.0"
        )

    def test_compare_cli_is_structured_with_or_without_json_flag(self) -> None:
        lock = self.create()
        for extra in ([], ["--json"]):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = component_lock.main(["compare", str(lock), str(lock), *extra])
            self.assertEqual(code, 0)
            self.assertTrue(json.loads(output.getvalue())["identical"])

    def test_relative_path_and_duplicate_json_field_are_rejected(self) -> None:
        output = self.create()
        payload = json.loads(output.read_bytes())
        payload["components"]["baud"]["path"] = "baud.exe"
        output.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(component_lock.LockError, "must be absolute"):
            component_lock.inspect(output)
        output.write_text(
            '{"schema_version":"x","schema_version":"x","components":{}}',
            encoding="utf-8",
        )
        with self.assertRaisesRegex(component_lock.LockError, "duplicate JSON"):
            component_lock.inspect(output)


if __name__ == "__main__":
    unittest.main()
