from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class InstalledScriptTests(unittest.TestCase):
    def test_entry_points_do_not_create_bytecode_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            install = Path(directory)
            scripts = install / "scripts"
            scripts.mkdir()
            for name in (
                "component_install.py",
                "component_lock.py",
                "release.py",
                "toolkit_doctor.py",
            ):
                shutil.copy2(ROOT / "scripts" / name, scripts / name)
            shutil.copy2(ROOT / "component-catalog.json", install / "component-catalog.json")

            environment = os.environ.copy()
            environment.pop("PYTHONDONTWRITEBYTECODE", None)
            commands = (
                [
                    sys.executable,
                    str(scripts / "component_install.py"),
                    "plan",
                    "--install-root",
                    str(install / "components"),
                    "--platform",
                    "windows-x86_64",
                    "--json",
                ],
                [sys.executable, str(scripts / "release.py"), "--help"],
                [sys.executable, str(scripts / "toolkit_doctor.py"), "--help"],
            )
            for command in commands:
                result = subprocess.run(
                    command,
                    cwd=install,
                    capture_output=True,
                    check=False,
                    encoding="utf-8",
                    env=environment,
                    timeout=15,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

            self.assertFalse((scripts / "__pycache__").exists())


if __name__ == "__main__":
    unittest.main()
