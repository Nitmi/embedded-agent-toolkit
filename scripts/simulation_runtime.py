#!/usr/bin/env python3
"""Inspect optional simulation Python payloads; never import or execute them."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from pathlib import Path

sys.dont_write_bytecode = True
if __package__:
    from . import trace_runtime as files
else:
    import trace_runtime as files

PIN_PATH = Path(__file__).resolve().parents[1] / "simulation-runtime.json"
CANDIDATE_PIN_PATH = Path(__file__).resolve().parents[1] / "simulation-candidates.json"
SCHEMA = "embedded-agent-toolkit.simulation-runtime-inspection.v1"
SPECS = {
    "sim-runner": (
        "sim_runner",
        "embedded_sim_runner",
        "0.7.0",
        {
            "__init__.py",
            "__main__.py",
            "backend.py",
            "cli.py",
            "common.py",
            "inspect.py",
            "plan.py",
            "process.py",
            "qemu.py",
            "qemu_flash.py",
            "qemu_s3.py",
            "flash_image.py",
            "gpio_timer.py",
            "gpio_fault.py",
            "esp_wasm.py",
            "run.py",
            "winjob.py",
            "assets/esp32c3-uart.json",
            "assets/esp32c3-idf-flash.json",
            "assets/esp32s3-idf-flash.json",
            "assets/esp32c3-esp-wasm.json",
            "assets/esp_wasm_runner.mjs",
            "assets/nrf52840-uart.repl",
            "assets/nrf52840-gpio-timer.repl",
        },
    ),
    "hil-runner": (
        "hil_runner",
        "embedded_hil_runner",
        "0.8.0",
        {
            "__init__.py",
            "__main__.py",
            "child.py",
            "cli.py",
            "common.py",
            "lease.py",
            "managed.py",
            "managed_plan.py",
            "selection.py",
            "server.py",
            "simulation.py",
            "winjob.py",
            "schemas/managed-plan.schema.json",
            "schemas/managed-result.schema.json",
            "schemas/managed-spec.schema.json",
            "schemas/result.schema.json",
            "schemas/simulation-plan.schema.json",
            "schemas/simulation-report.schema.json",
            "schemas/simulation-spec.schema.json",
        },
    ),
    "embedded-trace": (
        "embedded_trace",
        "embedded_trace",
        "0.8.0",
        {
            "__init__.py",
            "__main__.py",
            "adapters.py",
            "cli.py",
            "clock.py",
            "common.py",
            "framing.py",
            "query.py",
            "report.py",
            "simulation.py",
            "timeline.py",
            "schemas/input.v1.schema.json",
            "schemas/result.v1.schema.json",
            "schemas/timeline.v1.schema.json",
        },
    ),
}
CANDIDATE_VERSIONS = {
    "sim-runner": "0.7.0",
    "hil-runner": "0.8.0",
    "embedded-trace": "0.8.0",
}
CANDIDATE_SPECS = {
    name: (
        package,
        distribution,
        CANDIDATE_VERSIONS[name],
        names
        | (
            {
                "esp_wasm.py",
                "assets/esp32c3-esp-wasm.json",
                "assets/esp_wasm_runner.mjs",
            }
            if name == "sim-runner"
            else set()
        ),
    )
    for name, (package, distribution, _, names) in SPECS.items()
}


def payload_paths(name: str, *, candidate: bool = False) -> set[str]:
    package, distribution, version, names = (CANDIDATE_SPECS if candidate else SPECS)[
        name
    ]
    return {f"{package}/{leaf}" for leaf in names} | {
        f"{distribution}-{version}.dist-info/{leaf}"
        for leaf in ("METADATA", "WHEEL", "entry_points.txt", "licenses/LICENSE")
    }


def parse_pin(data: bytes, *, candidate: bool = False) -> dict:
    files.require(len(data) <= 65536, "Simulation pin exceeds size limit")
    pin = json.loads(data, object_pairs_hook=files.unique)
    files.require(
        isinstance(pin, dict)
        and set(pin) == {"schema_version", "components"}
        and pin["schema_version"]
        == (
            "embedded-agent-toolkit.simulation-candidates.v1"
            if candidate
            else "embedded-agent-toolkit.simulation-runtime.v2"
        )
        and isinstance(pin["components"], dict)
        and set(pin["components"]) == set(SPECS),
        "Invalid simulation pin identity",
    )
    for name, item in pin["components"].items():
        _, distribution, version, _ = (CANDIDATE_SPECS if candidate else SPECS)[name]
        files.require(
            isinstance(item, dict)
            and set(item)
            == {
                "repository",
                "version",
                "source_revision",
                "status",
                "wheel",
                "files",
            }
            | (set() if candidate else {"source_ref"})
            and item["repository"] == f"Nitmi/{name}"
            and item["version"] == version
            and item["status"] == ("local_candidate" if candidate else "published")
            and (candidate or item["source_ref"] == f"refs/tags/v{version}")
            and isinstance(item["source_revision"], str)
            and re.fullmatch(r"[0-9a-f]{40}", item["source_revision"]) is not None,
            "Invalid simulation component identity",
        )
        wheel = item["wheel"]
        files.require(
            isinstance(wheel, dict)
            and set(wheel) == {"name", "sha256"} | (set() if candidate else {"url"})
            and wheel["name"] == f"{distribution}-{version}-py3-none-any.whl"
            and (
                candidate
                or wheel["url"]
                == f"https://github.com/Nitmi/{name}/releases/download/v{version}/{wheel['name']}"
            )
            and isinstance(wheel["sha256"], str)
            and files.HASH.fullmatch(wheel["sha256"]) is not None,
            "Invalid simulation wheel identity",
        )
        expected = payload_paths(name, candidate=candidate)
        inventory = item["files"]
        files.require(
            isinstance(inventory, list) and len(inventory) == len(expected),
            "Incomplete simulation payload inventory",
        )
        seen = set()
        for entry in inventory:
            files.require(
                isinstance(entry, dict) and set(entry) == {"path", "size", "sha256"},
                "Invalid simulation payload entry",
            )
            path = entry["path"]
            files.require(
                isinstance(path, str) and path in expected and path not in seen,
                "Invalid/duplicate simulation payload path",
            )
            seen.add(path)
            files.require(
                type(entry["size"]) is int
                and 0 <= entry["size"] <= 1024 * 1024
                and isinstance(entry["sha256"], str)
                and files.HASH.fullmatch(entry["sha256"]) is not None,
                "Invalid simulation payload digest/size",
            )
        files.require(
            sum(entry["size"] for entry in inventory) <= 4 * 1024 * 1024,
            "Simulation payload exceeds size limit",
        )
    return pin


def load_pin(*, candidate: bool = False) -> dict:
    return parse_pin(
        files.read(CANDIDATE_PIN_PATH if candidate else PIN_PATH, 65536),
        candidate=candidate,
    )


def inspect_package(
    site: Path, root: Path, name: str, pin: dict, *, candidate: bool = False
) -> dict:
    verify_payload(
        site,
        root,
        SPECS[name][0],
        payload_paths(name, candidate=candidate),
        pin["files"],
    )
    return {
        "name": name,
        "version": pin["version"],
        "status": "payload_verified",
        "repository": pin["repository"],
        "source_ref": pin.get("source_ref"),
        "source_revision": pin["source_revision"],
        "wheel": pin["wheel"],
        "distribution_status": pin["status"],
        "verified_files": len(pin["files"]),
    }


def verify_payload(
    site: Path, root: Path, package: str, expected: set[str], inventory: list
) -> None:
    """Shared bounded file checks; never import a selected installed package."""
    for item in inventory:
        path = site / item["path"]
        files.contained(path, root)
        raw = files.read(path)
        files.require(
            len(raw) == item["size"] and files.digest(raw) == item["sha256"],
            f"Installed payload differs: {item['path']}",
        )
    directories = {
        str(Path(path).parent).replace("\\", "/")
        for path in expected
        if path.startswith(package + "/")
    }
    directories |= {path + "/__pycache__" for path in tuple(directories)}
    pending = [site / package]
    count = 0
    while pending:
        with os.scandir(pending.pop()) as entries:
            for entry in entries:
                count += 1
                files.require(count <= 256, "Package inventory exceeds limit")
                path = Path(entry.path)
                files.contained(path, root)
                relative = path.relative_to(site).as_posix()
                if entry.is_dir(follow_symlinks=False):
                    files.require(
                        relative in directories,
                        f"Unexpected package directory: {relative}",
                    )
                    pending.append(path)
                else:
                    files.require(
                        stat.S_ISREG(path.lstat().st_mode)
                        and (
                            relative in expected
                            or (
                                path.parent.name == "__pycache__"
                                and path.suffix == ".pyc"
                            )
                        ),
                        f"Unexpected package file: {relative}",
                    )


def environment_layout(environment: Path) -> tuple:
    """Read a venv layout/declaration without following its interpreter entry."""
    files.require(
        environment.is_absolute() and not str(environment).startswith(("\\\\", "//")),
        "Use an absolute local environment directory",
    )
    files.contained(environment, Path(environment.anchor))
    root = environment.resolve()
    cfg = root / "pyvenv.cfg"
    files.contained(cfg, root)
    configuration = files.read(cfg, 16384).decode("utf-8")
    versions = re.findall(
        r"(?m)^version(?:_info)?\s*=\s*([0-9]+)\.([0-9]+)\.([0-9]+)\s*$", configuration
    )
    files.require(
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
    available = [
        (site, python, label)
        for site, python, label in layouts
        if site.exists() or site.is_symlink()
    ]
    files.require(len(available) == 1, "Expected one Windows or POSIX venv layout")
    site, python, layout = available[0]
    files.contained(site, root)
    files.contained(python.parent, root)
    mode = python.lstat().st_mode
    files.require(
        stat.S_ISREG(mode) or (layout == "posix" and stat.S_ISLNK(mode)),
        "Missing interpreter entry",
    )
    return root, site, python, layout, versions[0]


def inspect_environment(
    environment: Path, selected: list[str] | None = None, *, candidate: bool = False
) -> dict:
    base = {
        "schema_version": SCHEMA,
        "environment": str(environment),
        "scope": "host_only_installed_payload_inspection",
        "executables_started": False,
        "hardware_access": False,
        "authorization_granted": False,
        "physical_board_verified": False,
        "backend_runtime_verified": False,
        "interpreter_version_verified": False,
        "interpreter_authenticated": False,
        "bytecode_verified": False,
        "release_attestation_verified": False,
        "candidate_mode": candidate,
    }
    try:
        pin = load_pin(candidate=candidate)
        names = selected if selected is not None else list(SPECS)
        files.require(
            bool(names) and len(names) == len(set(names)) and set(names) <= set(SPECS),
            "Invalid component selection",
        )
        root, site, python, layout, version = environment_layout(environment)
        results = [
            inspect_package(
                site, root, name, pin["components"][name], candidate=candidate
            )
            for name in names
        ]
        return {
            **base,
            "ok": True,
            "status": "payload_verified",
            "errors": [],
            "components": results,
            "environment": str(root),
            "layout": layout,
            "python": str(python),
            "python_version_claim": ".".join(version),
            "resolution_source": "pinned_local_candidates"
            if candidate
            else "pinned_releases",
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
    parser.add_argument("--component", action="append", choices=list(SPECS))
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--candidate",
        action="store_true",
        help="explicitly select bundled local candidate pins; no release/authenticity claim",
    )
    args = parser.parse_args()
    result = inspect_environment(
        args.environment, args.component, candidate=args.candidate
    )
    print(
        json.dumps(result, indent=2)
        if args.json
        else f"Simulation payload: {result['status']}"
    )
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
