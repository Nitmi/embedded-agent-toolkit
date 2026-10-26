#!/usr/bin/env python3
"""Inspect selected published or explicit candidate instrument payloads offline."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True
if __package__:
    from . import simulation_runtime as payloads
else:
    import simulation_runtime as payloads

files = payloads.files
PIN_PATH = Path(__file__).resolve().parents[1] / "instrument-runtime.json"
CANDIDATE_PIN_PATH = PIN_PATH.with_name("instrument-candidates.json")
SCHEMA = "embedded-agent-toolkit.instrument-runtime-inspection.v1"
CANDIDATE_SPECS = {
    "lab-instruments": (
        "lab_instruments",
        "lab_instruments",
        "0.8.0",
        {
            "__init__.py",
            "__main__.py",
            "_worker.py",
            "_scope_worker.py",
            "bus_logic.py",
            "capture.py",
            "cli.py",
            "common.py",
            "dwf.py",
            "lease.py",
            "logic.py",
            "logic_checks.py",
            "logic_reports.py",
            "plan.py",
            "scpi.py",
            "sdl.py",
            "sdl_plan.py",
            "sds.py",
            "sds_plan.py",
            "sds_wave.py",
            "sds_wire.py",
            "thermal.py",
            "thermal_frame.py",
            "thermal_plan.py",
        },
    ),
    "hil-runner": (
        "hil_runner",
        "embedded_hil_runner",
        "0.9.0",
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
            "instrument.py",
            "schemas/managed-plan.schema.json",
            "schemas/managed-result.schema.json",
            "schemas/managed-spec.schema.json",
            "schemas/result.schema.json",
            "schemas/simulation-plan.schema.json",
            "schemas/simulation-report.schema.json",
            "schemas/simulation-spec.schema.json",
            "schemas/instrument-spec.schema.json",
            "schemas/instrument-report.schema.json",
        },
    ),
    "embedded-trace": (
        "embedded_trace",
        "embedded_trace",
        "0.9.0",
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
            "instrument.py",
            "schemas/input.v1.schema.json",
            "schemas/result.v1.schema.json",
            "schemas/timeline.v1.schema.json",
            "schemas/instrument-report.schema.json",
        },
    ),
}
PUBLISHED_VERSIONS = {
    "lab-instruments": "0.9.0",
    "hil-runner": "0.10.0",
    "embedded-trace": "0.10.0",
}
WAVEFORM_FILES = {
    "lab-instruments": {"waveform.py"},
    "hil-runner": {
        "waveform.py",
        "schemas/waveform-spec.schema.json",
        "schemas/waveform-report.schema.json",
    },
    "embedded-trace": {"waveform.py", "schemas/waveform-report.schema.json"},
}
SPECS = {
    name: (
        package,
        distribution,
        PUBLISHED_VERSIONS[name],
        names | WAVEFORM_FILES[name],
    )
    for name, (package, distribution, _, names) in CANDIDATE_SPECS.items()
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
    files.require(type(candidate) is bool, "Invalid instrument candidate mode")
    files.require(len(data) <= 65536, "Instrument pin exceeds size limit")
    pin = json.loads(data, object_pairs_hook=files.unique)
    files.require(
        isinstance(pin, dict)
        and set(pin) == {"schema_version", "components"}
        and pin["schema_version"]
        == (
            "embedded-agent-toolkit.instrument-candidates.v1"
            if candidate
            else "embedded-agent-toolkit.instrument-runtime.v1"
        )
        and isinstance(pin["components"], dict)
        and set(pin["components"]) == set(SPECS),
        "Invalid instrument pin",
    )
    for name, item in pin["components"].items():
        _, distribution, version, _ = (CANDIDATE_SPECS if candidate else SPECS)[name]
        files.require(
            isinstance(item, dict)
            and set(item)
            == {"project", "version", "source_revision", "status", "wheel", "files"}
            | (set() if candidate else {"repository", "source_ref"})
            and item["project"] == distribution.replace("_", "-")
            and item["version"] == version
            and item["status"] == ("local_candidate" if candidate else "published")
            and (
                candidate
                or (
                    item["repository"] == f"Nitmi/{name}"
                    and item["source_ref"] == f"refs/tags/v{version}"
                )
            )
            and isinstance(item["source_revision"], str)
            and re.fullmatch(r"[0-9a-f]{40}", item["source_revision"]),
            "Invalid instrument component identity",
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
            and files.HASH.fullmatch(wheel["sha256"]),
            "Invalid instrument wheel identity",
        )
        inventory = item["files"]
        expected = payload_paths(name, candidate=candidate)
        files.require(
            isinstance(inventory, list) and len(inventory) == len(expected),
            "Incomplete instrument inventory",
        )
        seen = set()
        for entry in inventory:
            files.require(
                isinstance(entry, dict) and set(entry) == {"path", "size", "sha256"},
                "Invalid instrument payload entry",
            )
            path = entry["path"]
            files.require(
                isinstance(path, str) and path in expected and path not in seen,
                "Invalid/duplicate instrument payload path",
            )
            seen.add(path)
            files.require(
                type(entry["size"]) is int
                and 0 <= entry["size"] <= 1048576
                and isinstance(entry["sha256"], str)
                and files.HASH.fullmatch(entry["sha256"]),
                "Invalid instrument payload size/digest",
            )
        files.require(
            seen == expected and sum(item["size"] for item in inventory) <= 4 * 1048576,
            "Instrument package exceeds byte limit",
        )
    return pin


def load_pin(*, candidate: bool = False) -> dict:
    files.require(type(candidate) is bool, "Invalid instrument candidate mode")
    return parse_pin(
        files.read(CANDIDATE_PIN_PATH if candidate else PIN_PATH, 65536),
        candidate=candidate,
    )


def inspect_environment(
    environment: Path, selected: list[str] | None = None, *, candidate: bool = False
) -> dict:
    base = {
        "schema_version": SCHEMA,
        "environment": str(environment),
        "scope": "host_only_installed_payload_inspection",
        "candidate_mode": candidate,
        **{
            key: False
            for key in (
                "executables_started",
                "hardware_access",
                "authorization_granted",
                "physical_instrument_verified",
                "vendor_sdk_verified",
                "component_cli_verified",
                "native_evaluation_performed",
                "interpreter_version_verified",
                "interpreter_authenticated",
                "bytecode_verified",
                "release_attestation_verified",
            )
        },
    }
    try:
        files.require(type(candidate) is bool, "Invalid instrument candidate mode")
        names = selected if selected is not None else list(SPECS)
        files.require(
            bool(names) and len(names) == len(set(names)) and set(names) <= set(SPECS),
            "Invalid instrument component selection",
        )
        pin = load_pin(candidate=candidate)
        root, site, python, layout, version = payloads.environment_layout(environment)
        results = []
        for name in names:
            package = SPECS[name][0]
            item = pin["components"][name]
            payloads.verify_payload(
                site,
                root,
                package,
                payload_paths(name, candidate=candidate),
                item["files"],
            )
            results.append(
                {
                    "name": name,
                    "version": item["version"],
                    "project": item["project"],
                    "status": "payload_verified",
                    "source_revision": item["source_revision"],
                    **(
                        {}
                        if candidate
                        else {
                            "repository": item["repository"],
                            "source_ref": item["source_ref"],
                        }
                    ),
                    "wheel": item["wheel"],
                    "distribution_status": item["status"],
                    "verified_files": len(item["files"]),
                }
            )
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
            "resolution_source": (
                "pinned_local_candidates" if candidate else "pinned_releases"
            ),
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
    parser.add_argument(
        "--candidate",
        action="store_true",
        help="explicitly select the bundled local candidates",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = inspect_environment(
        args.environment, args.component, candidate=args.candidate
    )
    print(
        json.dumps(result, indent=2)
        if args.json
        else f"Instrument payload: {result['status']}"
    )
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
