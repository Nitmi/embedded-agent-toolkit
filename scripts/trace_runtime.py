#!/usr/bin/env python3
"""Inspect a pinned Embedded Trace environment without importing or starting it."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path

sys.dont_write_bytecode = True
SCHEMA = "embedded-agent-toolkit.trace-runtime-inspection.v1"
PIN_SCHEMA = "embedded-agent-toolkit.trace-runtime.v1"
PIN_PATH = Path(__file__).resolve().parents[1] / "trace-runtime.json"
HASH = re.compile(r"[0-9a-f]{64}")
LEGACY_PACKAGE_FILES = {
    "embedded_trace/" + name
    for name in (
        "__init__.py",
        "__main__.py",
        "adapters.py",
        "cli.py",
        "clock.py",
        "common.py",
        "framing.py",
        "query.py",
        "timeline.py",
        "schemas/input.v1.schema.json",
        "schemas/result.v1.schema.json",
        "schemas/timeline.v1.schema.json",
    )
}
PACKAGE_FILES = LEGACY_PACKAGE_FILES | {
    "embedded_trace/" + name
    for name in (
        "report.py",
        "simulation.py",
        "instrument.py",
        "waveform.py",
        "load.py",
        "load_protocol.py",
        "thermal.py",
        "thermal_protocol.py",
        "schemas/instrument-report.schema.json",
        "schemas/waveform-report.schema.json",
        "schemas/load-report.schema.json",
        "schemas/thermal-report.schema.json",
    )
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def reparse(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & 0x400
    )


def read(path: Path, maximum: int = 1024 * 1024) -> bytes:
    require(
        not reparse(path) and stat.S_ISREG(path.lstat().st_mode),
        f"Not a regular file: {path}",
    )
    with path.open("rb") as stream:
        data = stream.read(maximum + 1)
    require(len(data) <= maximum, f"File exceeds size limit: {path}")
    return data


def unique(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate pin field")
        result[key] = value
    return result


def parse_pin(data: bytes) -> dict:
    require(len(data) <= 32768, "Pin file exceeds size limit")
    pin = json.loads(data, object_pairs_hook=unique)
    require(
        isinstance(pin, dict)
        and set(pin)
        == {
            "schema_version",
            "repository",
            "version",
            "source_revision",
            "wheel",
            "files",
        },
        "Pin fields differ",
    )
    version = pin["version"]
    require(
        pin["schema_version"] == PIN_SCHEMA
        and pin["repository"] == "Nitmi/embedded-trace",
        "Pin identity differs",
    )
    require(
        isinstance(version, str) and version in ("0.1.0", "0.13.1", "0.14.0"),
        "Unsupported pinned Trace version",
    )
    require(
        isinstance(pin["source_revision"], str)
        and re.fullmatch(r"[0-9a-f]{40}", pin["source_revision"]) is not None,
        "Invalid source revision",
    )
    wheel = pin["wheel"]
    name = f"embedded_trace-{version}-py3-none-any.whl"
    require(
        isinstance(wheel, dict)
        and set(wheel) == {"name", "url", "sha256"}
        and wheel["name"] == name
        and wheel["url"]
        == f"https://github.com/Nitmi/embedded-trace/releases/download/v{version}/{name}"
        and isinstance(wheel["sha256"], str)
        and HASH.fullmatch(wheel["sha256"]) is not None,
        "Invalid wheel pin",
    )
    package_files = LEGACY_PACKAGE_FILES if version == "0.1.0" else PACKAGE_FILES
    expected = package_files | {
        f"embedded_trace-{version}.dist-info/" + leaf
        for leaf in ("METADATA", "WHEEL", "entry_points.txt", "licenses/LICENSE")
    }
    files = pin["files"]
    require(
        isinstance(files, list) and len(files) == len(expected),
        "Incomplete payload pin",
    )
    seen = set()
    total = 0
    for item in files:
        require(
            isinstance(item, dict) and set(item) == {"path", "size", "sha256"},
            "Invalid payload entry",
        )
        path = item["path"]
        require(
            isinstance(path, str) and path in expected and path not in seen,
            "Invalid/duplicate payload path",
        )
        seen.add(path)
        require(
            type(item["size"]) is int
            and 0 <= item["size"] <= 1024 * 1024
            and isinstance(item["sha256"], str)
            and HASH.fullmatch(item["sha256"]) is not None,
            "Invalid payload identity",
        )
        total += item["size"]
    require(seen == expected and total <= 4 * 1024 * 1024, "Incomplete payload pin")
    return pin


def load_pin() -> dict:
    return parse_pin(read(PIN_PATH, 32768))


def contained(path: Path, root: Path) -> None:
    require(path.is_relative_to(root), "Path escapes environment")
    for part in (path, *path.parents):
        require(not reparse(part), f"Reparse point in environment: {part}")
        if part == root:
            break
    require(path.resolve().is_relative_to(root), "Resolved path escapes environment")


def inspect_environment(environment: Path) -> dict:
    base = {
        "schema_version": SCHEMA,
        "environment": str(environment),
        "scope": "host_only_installed_payload_inspection",
        "executables_started": False,
        "hardware_access": False,
        "authorization_granted": False,
        "interpreter_version_verified": False,
        "interpreter_authenticated": False,
        "bytecode_verified": False,
    }
    try:
        pin = load_pin()
        require(
            environment.is_absolute()
            and not str(environment).startswith(("\\\\", "//")),
            "Use an absolute local environment directory",
        )
        require(
            not reparse(environment) and environment.is_dir(),
            "Invalid environment directory",
        )
        root = environment.resolve()
        cfg = root / "pyvenv.cfg"
        contained(cfg, root)
        configuration = read(cfg, 16384).decode("utf-8")
        versions = re.findall(
            r"(?m)^version(?:_info)?\s*=\s*([0-9]+)\.([0-9]+)\.([0-9]+)\s*$",
            configuration,
        )
        require(
            len(versions) == 1 and tuple(map(int, versions[0][:2])) >= (3, 11),
            "Environment must declare Python 3.11+",
        )
        major, minor, _ = versions[0]
        layouts = [
            (root / "Lib/site-packages", root / "Scripts/python.exe", "windows"),
            (
                root / f"lib/python{major}.{minor}/site-packages",
                root / "bin/python",
                "posix",
            ),
        ]
        selected = [
            (site, python, label)
            for site, python, label in layouts
            if site.exists() or site.is_symlink()
        ]
        require(len(selected) == 1, "Expected one Windows or POSIX venv layout")
        site, python, layout = selected[0]
        contained(site, root)
        require(site.is_dir(), "Missing site-packages directory")
        # POSIX venv interpreters are normally symlinks. Inspect their directory
        # entry only: do not follow, read, authenticate or start that interpreter.
        contained(python.parent, root)
        mode = python.lstat().st_mode
        require(
            stat.S_ISREG(mode) or (layout == "posix" and stat.S_ISLNK(mode)),
            "Missing interpreter entry",
        )
        for item in pin["files"]:
            path = site / item["path"]
            contained(path, root)
            raw = read(path)
            require(
                len(raw) == item["size"] and digest(raw) == item["sha256"],
                f"Installed payload differs: {item['path']}",
            )
        package_files = {
            item["path"]
            for item in pin["files"]
            if item["path"].startswith("embedded_trace/")
        }
        pending = [site / "embedded_trace"]
        count = 0
        while pending:
            with os.scandir(pending.pop()) as entries:
                for entry in entries:
                    count += 1
                    require(count <= 256, "Package file inventory exceeds limit")
                    path = Path(entry.path)
                    contained(path, root)
                    relative = path.relative_to(site).as_posix()
                    if entry.is_dir(follow_symlinks=False):
                        require(
                            relative
                            in {
                                "embedded_trace/schemas",
                                "embedded_trace/__pycache__",
                                "embedded_trace/schemas/__pycache__",
                            },
                            f"Unexpected Trace package directory: {relative}",
                        )
                        pending.append(path)
                    else:
                        require(
                            stat.S_ISREG(path.lstat().st_mode),
                            "Nonregular package entry",
                        )
                        require(
                            relative in package_files
                            or (
                                path.parent.name == "__pycache__"
                                and path.suffix == ".pyc"
                            ),
                            f"Unexpected Trace package file: {relative}",
                        )
        return {
            **base,
            "ok": True,
            "status": "payload_verified",
            "errors": [],
            "environment": str(root),
            "layout": layout,
            "version": pin["version"],
            "source_revision": pin["source_revision"],
            "wheel": pin["wheel"],
            "verified_files": len(pin["files"]),
            "python": str(python),
            "python_version_claim": ".".join(versions[0]),
            "resolution_source": "pinned_distribution",
        }
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as error:
        return {
            **base,
            "ok": False,
            "status": "invalid_runtime",
            "errors": [str(error)[:1024]],
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["inspect"])
    parser.add_argument("environment", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = inspect_environment(args.environment)
    print(
        json.dumps(result, indent=2)
        if args.json
        else f"Embedded Trace: {result['status']}"
    )
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
