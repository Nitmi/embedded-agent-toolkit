#!/usr/bin/env python3
"""Select and inspect one hash-bound workstation component lock."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

sys.dont_write_bytecode = True

if __package__:
    from . import component_lock
else:
    import component_lock

SCHEMA = "embedded-agent-toolkit.station-config.v1"
CONFIG_ENV = "EMBEDDED_AGENT_TOOLKIT_STATION_CONFIG"
MAX_CONFIG_BYTES = 16 * 1024


class StationConfigError(ValueError):
    pass


def default_config_path() -> Path:
    override = os.environ.get(CONFIG_ENV)
    if override:
        path = Path(override).expanduser()
        if not path.is_absolute():
            raise StationConfigError(f"{CONFIG_ENV} must be an absolute path")
        return path
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "embedded-agent-toolkit" / "station.json"
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "embedded-agent-toolkit" / "station.json"


def config_path(value: Path | None) -> Path:
    selected = value.expanduser() if value is not None else default_config_path()
    if not selected.is_absolute():
        raise StationConfigError("station config path must be absolute")
    return selected


def parse(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise StationConfigError(f"station config is not a regular file: {path}")
    data = path.read_bytes()
    if not data or len(data) > MAX_CONFIG_BYTES:
        raise StationConfigError("station config is empty or oversized")
    try:
        payload = json.loads(data, object_pairs_hook=component_lock.unique_object)
    except (UnicodeError, json.JSONDecodeError, component_lock.LockError) as error:
        raise StationConfigError(f"invalid station config JSON: {error}") from error
    if not isinstance(payload, dict) or set(payload) != {
        "schema_version",
        "component_lock",
    }:
        raise StationConfigError("station config fields differ")
    if payload["schema_version"] != SCHEMA:
        raise StationConfigError("unsupported station config schema")
    selected = payload["component_lock"]
    if not isinstance(selected, dict) or set(selected) != {"path", "sha256"}:
        raise StationConfigError("station component lock fields differ")
    lock_value = selected["path"]
    expected_hash = selected["sha256"]
    if not isinstance(lock_value, str) or not Path(lock_value).is_absolute():
        raise StationConfigError("station component lock path must be absolute")
    lock_path = Path(lock_value)
    if not isinstance(expected_hash, str) or not component_lock.HASH.fullmatch(
        expected_hash
    ):
        raise StationConfigError("invalid station component lock hash")
    if lock_path.is_symlink() or not lock_path.is_file():
        raise StationConfigError(f"station component lock is unavailable: {lock_path}")
    actual_hash = component_lock.sha256(lock_path)
    if actual_hash != expected_hash:
        raise StationConfigError("station component lock hash differs")
    try:
        components = component_lock.parse_lock(lock_path)
    except (component_lock.LockError, OSError) as error:
        raise StationConfigError(f"invalid station component lock: {error}") from error
    return {
        "config": str(path.resolve()),
        "component_lock": str(lock_path.resolve()),
        "component_lock_sha256": actual_hash,
        "components": components,
    }


def inspect(path: Path) -> dict[str, object]:
    return {
        "schema_version": SCHEMA,
        "ok": True,
        "operation": "inspect",
        **parse(path),
        "executables_started": False,
        "hardware_access": False,
    }


def select(path: Path, lock_path: Path, replace: bool) -> dict[str, object]:
    if lock_path.is_symlink() or not lock_path.is_file():
        raise StationConfigError(f"component lock is not a regular file: {lock_path}")
    try:
        components = component_lock.parse_lock(lock_path)
    except (component_lock.LockError, OSError) as error:
        raise StationConfigError(f"invalid component lock: {error}") from error
    resolved_lock = lock_path.resolve()
    lock_hash = component_lock.sha256(resolved_lock)
    status = "selected"
    if path.exists() or path.is_symlink():
        current = parse(path)
        if (
            current["component_lock"] == str(resolved_lock)
            and current["component_lock_sha256"] == lock_hash
        ):
            status = "already_selected"
        elif not replace:
            raise StationConfigError(
                "station config already selects another lock; compare locks and use --replace"
            )
    if status == "selected":
        payload = {
            "schema_version": SCHEMA,
            "component_lock": {"path": str(resolved_lock), "sha256": lock_hash},
        }
        data = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            descriptor, name = tempfile.mkstemp(
                prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
            )
            temporary = Path(name)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
            if os.name != "nt":
                temporary.chmod(0o600)
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        parse(path)
    return {
        "schema_version": SCHEMA,
        "ok": True,
        "operation": "select",
        "status": status,
        "config": str(path.resolve()),
        "component_lock": str(resolved_lock),
        "component_lock_sha256": lock_hash,
        "components": components,
        "executables_started": False,
        "hardware_access": False,
        "path_modified": False,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="override station config path")
    commands = parser.add_subparsers(dest="operation", required=True)
    selector = commands.add_parser("select")
    selector.add_argument("component_lock", type=Path)
    selector.add_argument("--replace", action="store_true")
    selector.add_argument("--json", action="store_true")
    inspector = commands.add_parser("inspect")
    inspector.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        path = config_path(args.config)
        report = (
            select(path, args.component_lock, args.replace)
            if args.operation == "select"
            else inspect(path)
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except (StationConfigError, OSError) as error:
        print(
            json.dumps(
                {
                    "schema_version": SCHEMA,
                    "ok": False,
                    "operation": args.operation,
                    "error": str(error),
                    "executables_started": False,
                    "hardware_access": False,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
