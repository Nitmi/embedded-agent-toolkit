#!/usr/bin/env python3
"""Inspect a pinned HIL Runner installation without importing or starting it."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path, PurePosixPath

sys.dont_write_bytecode = True
SCHEMA = "embedded-agent-toolkit.hil-runtime-inspection.v1"
PIN_SCHEMA = "embedded-agent-toolkit.hil-runtime.v1"
HASH = re.compile(r"[0-9a-f]{64}")
PIN_PATH = Path(__file__).resolve().parents[1] / "hil-runtime.json"


class RuntimeErrorDetail(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeErrorDetail(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def reparse(path: Path) -> bool:
    return path.is_symlink() or getattr(path, "is_junction", lambda: False)()


def read(path: Path, maximum: int = 1024 * 1024) -> bytes:
    require(not reparse(path) and path.is_file(), f"Not a regular file: {path}")
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
            "managed_debugger",
        },
        "Pin fields differ",
    )
    version = pin["version"]
    require(
        pin["schema_version"] == PIN_SCHEMA and pin["repository"] == "Nitmi/hil-runner",
        "Pin identity differs",
    )
    require(
        isinstance(version, str)
        and re.fullmatch(r"\d+\.\d+\.\d+", version) is not None,
        "Invalid pinned version",
    )
    require(
        isinstance(pin["source_revision"], str)
        and re.fullmatch(r"[0-9a-f]{40}", pin["source_revision"]) is not None,
        "Invalid source revision",
    )
    wheel = pin["wheel"]
    expected_name = f"embedded_hil_runner-{version}-py3-none-any.whl"
    require(
        isinstance(wheel, dict)
        and set(wheel) == {"name", "url", "sha256"}
        and wheel["name"] == expected_name
        and wheel["url"]
        == f"https://github.com/Nitmi/hil-runner/releases/download/v{version}/{expected_name}"
        and isinstance(wheel["sha256"], str)
        and HASH.fullmatch(wheel["sha256"]) is not None,
        "Invalid wheel pin",
    )
    debugger = pin["managed_debugger"]
    require(
        isinstance(debugger, dict)
        and set(debugger) == {"version", "sha256"}
        and isinstance(debugger["version"], str)
        and re.fullmatch(r"\d+\.\d+\.\d+", debugger["version"]) is not None
        and isinstance(debugger["sha256"], str)
        and HASH.fullmatch(debugger["sha256"]) is not None,
        "Invalid debugger requirement",
    )
    files = pin["files"]
    require(isinstance(files, list) and 1 <= len(files) <= 64, "Invalid file inventory")
    seen = set()
    total = 0
    for item in files:
        require(
            isinstance(item, dict) and set(item) == {"path", "size", "sha256"},
            "Invalid payload entry",
        )
        name = item["path"]
        require(
            isinstance(name, str)
            and len(name) <= 256
            and all(
                part not in ("", ".", "..")
                and not part.endswith(".")
                and re.fullmatch(r"[A-Za-z0-9_.-]+", part) is not None
                and re.fullmatch(
                    r"(?i)(CON|PRN|AUX|NUL|COM[0-9]+|LPT[0-9]+)(?:\..*)?", part
                )
                is None
                for part in name.split("/")
            )
            and "\\" not in name
            and ":" not in name
            and not PurePosixPath(name).is_absolute()
            and name.startswith(
                ("hil_runner/", f"embedded_hil_runner-{version}.dist-info/")
            ),
            "Invalid payload path",
        )
        require(name.casefold() not in seen, "Duplicate payload path")
        seen.add(name.casefold())
        require(
            type(item["size"]) is int
            and 0 <= item["size"] <= 1024 * 1024
            and isinstance(item["sha256"], str)
            and HASH.fullmatch(item["sha256"]) is not None,
            "Invalid payload identity",
        )
        total += item["size"]
    require(
        total <= 4 * 1024 * 1024
        and "hil_runner/__init__.py" in seen
        and "hil_runner/managed.py" in seen
        and f"embedded_hil_runner-{version}.dist-info/metadata" in seen,
        "Incomplete payload pin",
    )
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
        # Managed native HIL currently uses Windows. Other layouts are not inferred.
        site = root / "Lib/site-packages"
        contained(site, root)
        require(site.is_dir(), "Expected a Windows venv Lib/site-packages directory")
        python = root / "Scripts/python.exe"
        contained(python, root)
        python_hash = digest(read(python, 64 * 1024 * 1024))
        cfg = root / "pyvenv.cfg"
        contained(cfg, root)
        configuration = read(cfg, 16384).decode("utf-8")
        versions = re.findall(
            r"(?m)^version(?:_info)?\s*=\s*(\d+)\.(\d+)\.(\d+)\s*$", configuration
        )
        require(
            len(versions) == 1 and tuple(map(int, versions[0][:2])) >= (3, 11),
            "Environment must declare Python 3.11+",
        )
        for item in pin["files"]:
            path = site / item["path"]
            contained(path, root)
            data = read(path)
            require(
                len(data) == item["size"] and digest(data) == item["sha256"],
                f"Installed payload differs: {item['path']}",
            )
        expected_paths = {item["path"] for item in pin["files"]}
        for index, path in enumerate((site / "hil_runner").rglob("*")):
            require(index < 256, "Package file inventory exceeds limit")
            contained(path, root)
            if path.is_dir():
                continue
            relative = path.relative_to(site).as_posix()
            require(
                relative in expected_paths
                or (path.parent.name == "__pycache__" and path.suffix == ".pyc"),
                f"Unexpected HIL package file: {relative}",
            )
        return {
            **base,
            "ok": True,
            "status": "payload_verified",
            "errors": [],
            "environment": str(root),
            "version": pin["version"],
            "source_revision": pin["source_revision"],
            "wheel": pin["wheel"],
            "verified_files": len(pin["files"]),
            "python": str(python),
            "python_sha256": python_hash,
            "python_version_claim": ".".join(versions[0]),
            "resolution_source": "pinned_distribution",
            "managed_debugger": pin["managed_debugger"],
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
        else (f"HIL Runner {result.get('version', '')}: {result['status']}")
    )
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
