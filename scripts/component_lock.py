#!/usr/bin/env python3
"""Create or inspect an exact Embedded Agent Toolkit component lock."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

SCHEMA = "embedded-agent-toolkit.component-lock.v1"
MAX_LOCK_BYTES = 64 * 1024
HASH = re.compile(r"[0-9a-f]{64}")
SPECS = {
    "baud": ("baud", re.compile(r"baud\s+([^\s]+)")),
    "blea": ("ble", re.compile(r"ble\s+([^\s]+)")),
    "embedded-debugger": (
        "embedded-debugger",
        re.compile(r"embedded-debugger\s+([^\s]+)"),
    ),
}


class LockError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise LockError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def regular_executable(path_value: object) -> Path:
    if not isinstance(path_value, str) or not path_value or len(path_value) > 4096:
        raise LockError("component path must be a bounded string")
    path = Path(path_value)
    if not path.is_absolute():
        raise LockError("component path must be absolute")
    if path.is_symlink() or not path.is_file():
        raise LockError(f"component path is not a regular file: {path}")
    return path.resolve()


def parse_lock(path: Path) -> dict[str, dict[str, str]]:
    if path.is_symlink() or not path.is_file():
        raise LockError(f"component lock is not a regular file: {path}")
    data = path.read_bytes()
    if not data or len(data) > MAX_LOCK_BYTES:
        raise LockError("component lock is empty or oversized")
    try:
        payload = json.loads(data, object_pairs_hook=unique_object)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise LockError(f"invalid component lock JSON: {error}") from error
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version",
        "components",
    }:
        raise LockError("component lock fields differ")
    if payload["schema_version"] != SCHEMA:
        raise LockError("unsupported component lock schema")
    components = payload["components"]
    if not isinstance(components, dict) or set(components) != set(SPECS):
        raise LockError("component lock inventory differs")
    normalized = {}
    for name, record in components.items():
        if not isinstance(record, dict) or set(record) != {"path", "sha256", "version"}:
            raise LockError(f"component lock record differs: {name}")
        executable = regular_executable(record["path"])
        digest = record["sha256"]
        version = record["version"]
        if not isinstance(digest, str) or not HASH.fullmatch(digest):
            raise LockError(f"invalid component hash: {name}")
        if not isinstance(version, str) or not version or len(version) > 128:
            raise LockError(f"invalid component version: {name}")
        if sha256(executable) != digest:
            raise LockError(f"component hash differs: {name}")
        normalized[name] = {
            "path": str(executable),
            "sha256": digest,
            "version": version,
        }
    return normalized


def inspect(path: Path) -> dict[str, object]:
    return {
        "schema_version": SCHEMA,
        "ok": True,
        "lock": str(path.resolve()),
        "components": parse_lock(path),
        "executables_started": False,
        "hardware_access": False,
    }


def identify(name: str, path_value: str, timeout: float) -> dict[str, str]:
    path = regular_executable(path_value)
    completed = subprocess.run(
        [str(path), "--version"],
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    expected_command, pattern = SPECS[name]
    match = pattern.fullmatch(completed.stdout.strip())
    if completed.returncode != 0 or match is None or completed.stderr.strip():
        raise LockError(f"unexpected {expected_command} version result")
    return {"path": str(path), "sha256": sha256(path), "version": match.group(1)}


def create(
    output: Path, selections: dict[str, str], timeout: float
) -> dict[str, object]:
    if output.exists() or output.is_symlink():
        raise LockError("component lock output already exists")
    components = {name: identify(name, selections[name], timeout) for name in SPECS}
    data = (
        json.dumps(
            {"schema_version": SCHEMA, "components": components},
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as stream:
        stream.write(data)
    try:
        parse_lock(output)
    except Exception:
        output.unlink(missing_ok=True)
        raise
    return {
        "schema_version": SCHEMA,
        "ok": True,
        "lock": str(output.resolve()),
        "lock_sha256": hashlib.sha256(data).hexdigest(),
        "components": components,
        "executables_started": True,
        "executed_command": "--version only",
        "hardware_access": False,
        "path_modified": False,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    creator = commands.add_parser("create")
    creator.add_argument("--output", type=Path, required=True)
    creator.add_argument("--baud", required=True)
    creator.add_argument("--blea", required=True)
    creator.add_argument("--debugger", required=True)
    creator.add_argument("--timeout", type=float, default=5.0)
    creator.add_argument("--json", action="store_true")
    inspector = commands.add_parser("inspect")
    inspector.add_argument("lock", type=Path)
    inspector.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.operation == "create":
            if not 0.1 <= args.timeout <= 30:
                raise LockError("--timeout must be between 0.1 and 30 seconds")
            result = create(
                args.output,
                {
                    "baud": args.baud,
                    "blea": args.blea,
                    "embedded-debugger": args.debugger,
                },
                args.timeout,
            )
        else:
            result = inspect(args.lock)
    except (LockError, OSError, subprocess.SubprocessError) as error:
        result = {
            "schema_version": SCHEMA,
            "ok": False,
            "operation": args.operation,
            "hardware_access": False,
            "error": str(error),
        }
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["ok"]:
        print(result["lock"])
    else:
        print(result["error"], file=sys.stderr)
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
