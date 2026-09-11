#!/usr/bin/env python3
"""Create, inspect, or compare exact Toolkit component locks."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

LEGACY_SCHEMA = "embedded-agent-toolkit.component-lock.v1"
SCHEMA = "embedded-agent-toolkit.component-lock.v2"
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
OPTIONAL_SPECS = {
    "board-registry": (
        "board-registry",
        re.compile(r"board-registry\s+([^\s]+)"),
    ),
}
ALL_SPECS = {**SPECS, **OPTIONAL_SPECS}


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


def lock_schema(path: Path) -> str:
    try:
        payload = json.loads(path.read_bytes(), object_pairs_hook=unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise LockError(f"invalid component lock JSON: {error}") from error
    if not isinstance(payload, dict) or not isinstance(
        payload.get("schema_version"), str
    ):
        raise LockError("component lock schema is missing")
    return payload["schema_version"]


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
    schema = payload["schema_version"]
    if schema not in {LEGACY_SCHEMA, SCHEMA}:
        raise LockError("unsupported component lock schema")
    components = payload["components"]
    names = set(components) if isinstance(components, dict) else set()
    valid_inventory = (
        names == set(SPECS)
        if schema == LEGACY_SCHEMA
        else (set(SPECS) <= names <= set(ALL_SPECS))
    )
    if not isinstance(components, dict) or not valid_inventory:
        raise LockError("component lock inventory differs")
    normalized = {}
    for name, record in components.items():
        if name not in ALL_SPECS:
            raise LockError(f"unsupported component: {name}")
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
    components = parse_lock(path)
    return {
        "schema_version": lock_schema(path),
        "ok": True,
        "lock": str(path.resolve()),
        "components": components,
        "executables_started": False,
        "hardware_access": False,
    }


def compare(base_path: Path, candidate_path: Path) -> dict[str, object]:
    base = parse_lock(base_path)
    candidate = parse_lock(candidate_path)
    changes = {}
    for name in ALL_SPECS:
        if name not in base or name not in candidate:
            if base.get(name) != candidate.get(name):
                changes[name] = {
                    "changed_fields": ["presence"],
                    "before": base.get(name),
                    "after": candidate.get(name),
                }
            continue
        fields = [
            field
            for field in ("path", "version", "sha256")
            if base[name][field] != candidate[name][field]
        ]
        if fields:
            changes[name] = {
                "changed_fields": fields,
                "before": base[name],
                "after": candidate[name],
            }
    return {
        "schema_version": SCHEMA,
        "ok": True,
        "operation": "compare",
        "base_lock": str(base_path.resolve()),
        "candidate_lock": str(candidate_path.resolve()),
        "identical": not changes,
        "change_count": len(changes),
        "changes": changes,
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
    expected_command, pattern = ALL_SPECS[name]
    match = pattern.fullmatch(completed.stdout.strip())
    if completed.returncode != 0 or match is None or completed.stderr.strip():
        raise LockError(f"unexpected {expected_command} version result")
    return {"path": str(path), "sha256": sha256(path), "version": match.group(1)}


def create(
    output: Path, selections: dict[str, str], timeout: float
) -> dict[str, object]:
    if output.exists() or output.is_symlink():
        raise LockError("component lock output already exists")
    names = set(selections)
    if not set(SPECS) <= names <= set(ALL_SPECS):
        raise LockError(
            "component selections must contain every core component and only known optional components"
        )
    components = {
        name: identify(name, selections[name], timeout)
        for name in ALL_SPECS
        if name in selections
    }
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
    creator.add_argument("--board-registry")
    creator.add_argument("--timeout", type=float, default=5.0)
    creator.add_argument("--json", action="store_true")
    inspector = commands.add_parser("inspect")
    inspector.add_argument("lock", type=Path)
    inspector.add_argument("--json", action="store_true")
    comparator = commands.add_parser("compare")
    comparator.add_argument("base", type=Path)
    comparator.add_argument("candidate", type=Path)
    comparator.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.operation == "create":
            if not 0.1 <= args.timeout <= 30:
                raise LockError("--timeout must be between 0.1 and 30 seconds")
            selections = {
                "baud": args.baud,
                "blea": args.blea,
                "embedded-debugger": args.debugger,
            }
            if args.board_registry is not None:
                selections["board-registry"] = args.board_registry
            result = create(args.output, selections, args.timeout)
        elif args.operation == "inspect":
            result = inspect(args.lock)
        else:
            result = compare(args.base, args.candidate)
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
        if args.operation == "compare":
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(result["lock"])
    else:
        print(result["error"], file=sys.stderr)
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
