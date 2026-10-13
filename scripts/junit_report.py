"""Render fresh offline contract evaluation as bounded JUnit XML."""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

SCHEMA = "embedded-agent-toolkit.test-junit.v1"
MAX_CASES = 263  # Contract gate + 66 inputs + 64 stages + 128 assertions + 4 cleanup.
MAX_DIAGNOSTIC_CHARS = 4096
MAX_XML_BYTES = 4 * 1024 * 1024


class JunitError(ValueError):
    pass


def new_output(path: Path) -> Path:
    """Refuse existing outputs, including dangling links, before evaluation."""
    try:
        candidate = path.expanduser()
        if candidate.exists() or candidate.is_symlink():
            raise JunitError(f"output already exists: {candidate}")
        if candidate.suffix.lower() != ".xml":
            raise JunitError("JUnit output must have an .xml extension")
        resolved = candidate.resolve(strict=False)
        if not resolved.parent.is_dir():
            raise JunitError(f"output parent does not exist: {resolved.parent}")
        return resolved
    except (OSError, ValueError, RuntimeError) as error:
        if isinstance(error, JunitError):
            raise
        raise JunitError(f"invalid JUnit output path: {error}") from error


def _diagnostic(value: Any) -> str:
    # JSON escaping keeps XML 1.0 control characters and lone surrogates as
    # visible literal escapes. ElementTree then escapes markup characters.
    text = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True)
    if len(text) > MAX_DIAGNOSTIC_CHARS:
        return (
            text[:MAX_DIAGNOSTIC_CHARS]
            + "\n[diagnostic truncated; retain native evidence]"
        )
    return text


def render(evaluation: dict[str, Any]) -> tuple[bytes, dict[str, int]]:
    """Consume the evaluator's fresh result, never an arbitrary report file."""
    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite", name="embedded." + evaluation["board_id"])
    properties = ET.SubElement(suite, "properties")
    values = {
        "contract_sha256": evaluation["contract"]["sha256"],
        "run_sha256": evaluation["run"]["sha256"],
        "scope": evaluation["scope"],
        "complete": str(evaluation["complete"]).lower(),
        "source_execution_not_performed": "true",
        "hardware_access": "false",
        "executables_started": "false",
        "authorization_granted": "false",
        "execution_supported": "false",
    }
    for name, value in values.items():
        ET.SubElement(properties, "property", name=name, value=value)
    counts = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    names = set()

    def case(category: str, name: str, outcome: str | None, details: dict) -> None:
        key = (category, name)
        if key in names:
            raise JunitError("JUnit testcase identity is duplicated")
        names.add(key)
        counts["tests"] += 1
        if counts["tests"] > MAX_CASES:
            raise JunitError("JUnit report exceeds the contract testcase limit")
        item = ET.SubElement(
            suite, "testcase", classname=suite.get("name") + "." + category, name=name
        )
        diagnostic = _diagnostic(details)
        if outcome:
            tag = "failure" if outcome == "failures" else "error"
            counts[outcome] += 1
            problem = ET.SubElement(item, tag, type="evidence." + category)
            problem.text = diagnostic
        else:
            ET.SubElement(item, "system-out").text = diagnostic

    contract = evaluation["contract"]
    case(
        "contract",
        "inputs-current",
        None if contract["current"] else "errors",
        {
            "path": contract["path"],
            "sha256": contract["sha256"],
            "current": contract["current"],
        },
    )
    for check in contract["input_checks"]:
        case(
            "inputs",
            check["kind"] + "." + check["id"],
            None if check["current"] else "errors",
            check,
        )
    for stage in evaluation["stages"]:
        case(
            "stages",
            stage["id"],
            None if stage["evidence"]["current"] else "errors",
            stage,
        )
    for assertion in evaluation["assertions"]:
        outcome = (
            None
            if assertion["passed"]
            else "failures"
            if assertion["evaluated"]
            else "errors"
        )
        case("assertions", assertion["id"], outcome, assertion)
    for cleanup in evaluation["cleanup"]:
        outcome = (
            None
            if cleanup["passed"]
            else "failures"
            if cleanup["evaluated"]
            else "errors"
        )
        case("cleanup", cleanup["resource"], outcome, cleanup)
    if evaluation["ok"] != (counts["failures"] == 0 and counts["errors"] == 0):
        raise JunitError("JUnit outcomes differ from the native evaluation result")
    for name, count in counts.items():
        root.set(name, str(count))
        suite.set(name, str(count))
    # No test durations or execution timestamps are inferred from offline reads.
    ET.indent(root, space="  ")
    payload = ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n"
    if len(payload) > MAX_XML_BYTES:
        raise JunitError("JUnit output exceeds 4 MiB")
    return payload, counts


def export(evaluation: dict[str, Any], destination: Path) -> dict[str, Any]:
    payload, counts = render(evaluation)
    try:
        with destination.open("xb") as handle:
            handle.write(payload)
    except FileExistsError as error:
        raise JunitError(f"output already exists: {destination}") from error
    except OSError as error:
        raise JunitError(
            f"unable to write JUnit output {destination}: {error}"
        ) from error
    return {
        "schema_version": SCHEMA,
        "operation": "junit",
        "ok": evaluation["ok"],
        "status": evaluation["status"],
        "complete": evaluation["complete"],
        "scope": evaluation["scope"],
        "contract": {
            key: evaluation["contract"][key] for key in ("path", "sha256", "current")
        },
        "run": evaluation["run"],
        "board_id": evaluation["board_id"],
        "junit": {
            "path": str(destination),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "size_bytes": len(payload),
            **counts,
        },
        "evaluation_summary": evaluation["summary"],
        "authorization_granted": False,
        "execution_supported": False,
        "source_execution_not_performed": True,
        "hardware_access": False,
        "executables_started": False,
        "errors": evaluation["errors"],
    }
