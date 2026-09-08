from __future__ import annotations

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

    def test_existing_output_is_never_replaced(self) -> None:
        output = self.create()
        before = output.read_bytes()
        with self.assertRaisesRegex(component_lock.LockError, "already exists"):
            component_lock.create(output, self.executables, 1.0)
        self.assertEqual(output.read_bytes(), before)

    def test_hash_drift_is_rejected(self) -> None:
        output = self.create()
        Path(self.executables["baud"]).write_bytes(b"changed")
        with self.assertRaisesRegex(component_lock.LockError, "hash differs"):
            component_lock.inspect(output)

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
