from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import component_lock, station_config


class StationConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.config = self.root / "config" / "station.json"
        self.lock = self.root / "toolchain-lock.json"
        components = {}
        for name in component_lock.SPECS:
            executable = self.root / f"{name}.exe"
            executable.write_bytes(name.encode("ascii"))
            components[name] = {
                "path": str(executable.resolve()),
                "sha256": component_lock.sha256(executable),
                "version": "1.0.0",
            }
        self.lock.write_text(
            json.dumps(
                {"schema_version": component_lock.SCHEMA, "components": components}
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_select_and_inspect_bind_lock_without_starting_executables(self) -> None:
        with mock.patch.object(
            component_lock.subprocess, "run", side_effect=AssertionError("must not run")
        ):
            selected = station_config.select(self.config, self.lock, False)
            inspected = station_config.inspect(self.config)
        self.assertEqual(selected["status"], "selected")
        self.assertFalse(selected["executables_started"])
        self.assertFalse(inspected["hardware_access"])
        self.assertEqual(inspected["component_lock"], str(self.lock.resolve()))
        self.assertEqual(
            inspected["component_lock_sha256"],
            hashlib.sha256(self.lock.read_bytes()).hexdigest(),
        )

    def test_select_is_idempotent_and_requires_replace_for_another_lock(self) -> None:
        station_config.select(self.config, self.lock, False)
        repeated = station_config.select(self.config, self.lock, False)
        self.assertEqual(repeated["status"], "already_selected")
        other = self.root / "other-lock.json"
        payload = json.loads(self.lock.read_text(encoding="utf-8"))
        payload["components"]["baud"]["version"] = "2.0.0"
        other.write_text(json.dumps(payload), encoding="utf-8")
        with self.assertRaisesRegex(station_config.StationConfigError, "--replace"):
            station_config.select(self.config, other, False)
        replaced = station_config.select(self.config, other, True)
        self.assertEqual(replaced["component_lock"], str(other.resolve()))

    def test_modified_selected_lock_is_rejected(self) -> None:
        station_config.select(self.config, self.lock, False)
        self.lock.write_bytes(self.lock.read_bytes() + b"\n")
        with self.assertRaisesRegex(station_config.StationConfigError, "hash differs"):
            station_config.inspect(self.config)

    def test_default_path_override_must_be_absolute(self) -> None:
        with (
            mock.patch.dict(
                station_config.os.environ,
                {station_config.CONFIG_ENV: "relative.json"},
                clear=True,
            ),
            self.assertRaisesRegex(station_config.StationConfigError, "absolute"),
        ):
            station_config.default_config_path()


if __name__ == "__main__":
    unittest.main()
