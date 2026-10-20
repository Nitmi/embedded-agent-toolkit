from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class InstalledScriptTests(unittest.TestCase):
    def test_standalone_bootstrap_rejects_setup_before_resolving_github_cli(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "bootstrap.py"
            shutil.copy2(ROOT / "scripts" / "bootstrap.py", script)
            environment = os.environ.copy()
            environment.pop("PYTHONDONTWRITEBYTECODE", None)
            for arguments, error in (
                (["--component-lock", "lock.json", "--timeout", "90"], "30 seconds"),
                (["--lock-output", "new.json"], "required together"),
                (["--component-install-root", "components"], "requires --lock-output"),
            ):
                with self.subTest(arguments=arguments):
                    result = subprocess.run(
                        [
                            sys.executable,
                            str(script),
                            "--install-root",
                            str(root / "install"),
                            "--gh",
                            str(root / "absent-gh"),
                            *arguments,
                            "--json",
                        ],
                        cwd=root,
                        capture_output=True,
                        encoding="utf-8",
                        check=False,
                        env=environment,
                        timeout=15,
                    )
                    self.assertEqual(result.returncode, 2, result.stderr)
                    report = json.loads(result.stdout)
                    self.assertFalse(report["ok"])
                    self.assertFalse(report["hardware_access"])
                    self.assertIn(error, report["error"])
                    self.assertEqual(
                        {path.name for path in root.iterdir()}, {"bootstrap.py"}
                    )

    def test_entry_points_do_not_create_bytecode_cache(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            install = Path(directory)
            scripts = install / "scripts"
            scripts.mkdir()
            for name in (
                "component_install.py",
                "component_lock.py",
                "release.py",
                "station_config.py",
                "test_contract.py",
                "junit_report.py",
                "rtt_evidence.py",
                "toolkit_doctor.py",
                "hil_runtime.py",
                "trace_runtime.py",
            ):
                shutil.copy2(ROOT / "scripts" / name, scripts / name)
            shutil.copy2(
                ROOT / "component-catalog.json", install / "component-catalog.json"
            )

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
                [sys.executable, str(scripts / "station_config.py"), "--help"],
                [sys.executable, str(scripts / "test_contract.py"), "--help"],
                [sys.executable, str(scripts / "rtt_evidence.py"), "--help"],
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
