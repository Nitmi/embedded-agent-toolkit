#!/usr/bin/env python3
"""Read-only host readiness check for Embedded Agent Toolkit."""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

if __package__:
    from . import component_lock
else:
    import component_lock

SCHEMA_VERSION = "embedded-agent-toolkit.doctor.v2"
PLUGIN_NAME = "embedded-agent-toolkit"
WARNING_STATUSES = frozenset({"not_found"})


@dataclass(frozen=True)
class Component:
    name: str
    executable: str
    environment_variable: str
    version_pattern: str
    install_hint: str


COMPONENTS = (
    Component(
        name="baud",
        executable="baud",
        environment_variable="EMBEDDED_AGENT_BAUD",
        version_pattern=r"baud\s+([^\s]+)",
        install_hint="uv tool install git+https://github.com/Nitmi/baud-cli",
    ),
    Component(
        name="blea",
        executable="ble",
        environment_variable="EMBEDDED_AGENT_BLE",
        version_pattern=r"ble\s+([^\s]+)",
        install_hint="uv tool install git+https://github.com/Nitmi/blea",
    ),
    Component(
        name="embedded-debugger",
        executable="embedded-debugger",
        environment_variable="EMBEDDED_AGENT_DEBUGGER",
        version_pattern=r"embedded-debugger\s+([^\s]+)",
        install_hint=(
            "cargo install --git https://github.com/Nitmi/embedded-debugger "
            "embedded-debugger"
        ),
    ),
)


def resolve_executable(
    component: Component, locked: dict[str, str] | None = None
) -> tuple[str | None, str, str]:
    override = os.environ.get(component.environment_variable)
    if locked is not None:
        if override:
            return None, override, "lock_environment_conflict"
        return locked["path"], locked["path"], "component_lock"
    requested = override or component.executable
    if override:
        candidate = Path(override).expanduser()
        if candidate.is_file():
            return str(candidate.resolve()), requested, "environment_override"
        return None, requested, "environment_override"
    return shutil.which(requested), requested, "path"


def check_component(
    component: Component, timeout: float, locked: dict[str, str] | None = None
) -> dict[str, object]:
    executable, requested, resolution_source = resolve_executable(component, locked)
    base: dict[str, object] = {
        "name": component.name,
        "requested_executable": requested,
        "resolution_source": resolution_source,
        "environment_variable": component.environment_variable,
        "install_hint": component.install_hint,
        "fallback_hint": (
            f"Use the installed {component.name} integration, or set "
            f"{component.environment_variable} to one exact executable path."
        ),
    }
    if executable is None:
        status = (
            "invalid_environment_override"
            if resolution_source == "environment_override"
            else (
                "environment_conflicts_with_component_lock"
                if resolution_source == "lock_environment_conflict"
                else "not_found"
            )
        )
        return {
            **base,
            "ok": False,
            "severity": "warning" if status in WARNING_STATUSES else "error",
            "status": status,
            "executable": None,
            "version": None,
        }

    if locked is not None:
        actual_hash = component_lock.sha256(Path(executable))
        if actual_hash != locked["sha256"]:
            return {
                **base,
                "ok": False,
                "severity": "error",
                "status": "component_lock_hash_mismatch",
                "executable": executable,
                "version": None,
                "expected_sha256": locked["sha256"],
                "actual_sha256": actual_hash,
            }
    try:
        completed = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            check=False,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {
            **base,
            "ok": False,
            "severity": "error",
            "status": "timeout",
            "executable": executable,
            "version": None,
        }
    except OSError as error:
        return {
            **base,
            "ok": False,
            "severity": "error",
            "status": "launch_error",
            "executable": executable,
            "version": None,
            "error": str(error),
        }

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    match = re.fullmatch(component.version_pattern, stdout)
    if completed.returncode != 0:
        status = "nonzero_exit"
    elif match is None:
        status = "unexpected_version_output"
    elif locked is not None and match.group(1) != locked["version"]:
        status = "component_lock_version_mismatch"
    else:
        status = "ready"
    return {
        **base,
        "ok": status == "ready",
        "severity": "info" if status == "ready" else "error",
        "status": status,
        "executable": executable,
        "version": match.group(1) if match else None,
        "exit_code": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
        **({"sha256": locked["sha256"]} if locked is not None else {}),
    }


def load_json_object(path: Path, errors: list[str]) -> dict[str, object] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"missing {path.name}: {path}")
        return None
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"cannot read {path.name}: {error}")
        return None
    if not isinstance(payload, dict):
        errors.append(f"{path.name} must contain a JSON object")
        return None
    return payload


def base_plugin_version(version: object) -> str | None:
    if not isinstance(version, str):
        return None
    return version.split("+codex.", 1)[0]


def check_plugin_layout(plugin_root: Path) -> dict[str, object]:
    errors: list[str] = []
    codex_manifest = load_json_object(
        plugin_root / ".codex-plugin" / "plugin.json", errors
    )
    portable_manifest = load_json_object(plugin_root / "plugin.json", errors)

    for label, manifest in (
        ("Codex manifest", codex_manifest),
        ("portable manifest", portable_manifest),
    ):
        if manifest is None:
            continue
        if manifest.get("name") != PLUGIN_NAME:
            errors.append(f"{label} name must be {PLUGIN_NAME}")
        if not isinstance(manifest.get("version"), str):
            errors.append(f"{label} must contain a string version")
        if manifest.get("skills") != "./skills/":
            errors.append(f"{label} skills must point to ./skills/")
        if "mcpServers" in manifest:
            errors.append(f"{label} must not register component MCP servers")

    for filename in (".mcp.json", "mcp.json"):
        if (plugin_root / filename).exists():
            errors.append(f"orchestration plugin must not contain active {filename}")

    if codex_manifest and portable_manifest:
        codex_version = base_plugin_version(codex_manifest.get("version"))
        portable_version = base_plugin_version(portable_manifest.get("version"))
        if codex_version != portable_version:
            errors.append("plugin manifest base versions do not match")

    return {
        "ok": not errors,
        "plugin_root": str(plugin_root.resolve()),
        "errors": errors,
        "component_mcp_registered": False,
        "component_mcp_reason": "component plugins own MCP server lifecycles",
    }


def build_report(
    selected_components: Sequence[Component],
    timeout: float,
    plugin_root: Path,
    locked_components: dict[str, dict[str, str]] | None = None,
) -> dict[str, object]:
    component_results = [
        check_component(
            component,
            timeout,
            locked_components.get(component.name) if locked_components else None,
        )
        for component in selected_components
    ]
    layout = check_plugin_layout(plugin_root)
    warnings = [
        f"{result['name']}: {result['status']}"
        for result in component_results
        if result["status"] in WARNING_STATUSES
    ]
    errors = [
        f"{result['name']}: {result['status']}"
        for result in component_results
        if not result["ok"] and result["status"] not in WARNING_STATUSES
    ]
    errors.extend(layout["errors"])
    complete = layout["ok"] and all(result["ok"] for result in component_results)
    ok = layout["ok"] and not errors
    if not ok:
        status = "error"
    elif complete:
        status = "ready"
    else:
        status = "ready_with_warnings"
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": ok,
        "complete": complete,
        "status": status,
        "warnings": warnings,
        "errors": errors,
        "scope": "host_only_no_hardware_access",
        "component_lock_used": locked_components is not None,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "components": component_results,
        "plugin": layout,
    }


def render_human(report: dict[str, object]) -> str:
    lines = ["Embedded Agent Toolkit doctor", "Scope: host only; no hardware access"]
    for result in report["components"]:  # type: ignore[union-attr]
        if result["ok"]:
            marker = "OK"
        elif result["status"] in WARNING_STATUSES:
            marker = "WARN"
        else:
            marker = "FAIL"
        detail = result.get("version") or result["status"]
        lines.append(f"[{marker}] {result['name']}: {detail}")
        if not result["ok"]:
            lines.append(f"       remedy: {result['install_hint']}")
            lines.append(f"       fallback: {result['fallback_hint']}")
    plugin = report["plugin"]
    marker = "OK" if plugin["ok"] else "FAIL"  # type: ignore[index]
    lines.append(f"[{marker}] plugin layout")
    for error in plugin["errors"]:  # type: ignore[index,union-attr]
        lines.append(f"       {error}")
    if not report["ok"]:
        lines.append("Not ready")
    elif report["complete"]:
        lines.append("Ready")
    else:
        lines.append("Ready with warnings")
    return "\n".join(lines)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit one JSON result")
    parser.add_argument(
        "--component-lock",
        type=Path,
        help="authoritative exact component lock; environment overrides then fail",
    )
    parser.add_argument(
        "--component",
        action="append",
        choices=[component.name for component in COMPONENTS],
        help="check only this component; repeat to select more than one",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="per-version-command timeout in seconds (0.1..30; default: 5)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="return exit code 2 unless every selected CLI is directly available",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if not 0.1 <= args.timeout <= 30:
        print("--timeout must be between 0.1 and 30 seconds", file=sys.stderr)
        return 2
    names = set(args.component or [])
    selected = [
        component for component in COMPONENTS if not names or component.name in names
    ]
    plugin_root = Path(__file__).resolve().parent.parent
    try:
        locked_components = (
            component_lock.parse_lock(args.component_lock)
            if args.component_lock is not None
            else None
        )
    except (component_lock.LockError, OSError) as error:
        print(f"invalid component lock: {error}", file=sys.stderr)
        return 2
    report = build_report(selected, args.timeout, plugin_root, locked_components)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_human(report))
    passed = report["complete"] if args.strict else report["ok"]
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
