from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

LEDGER_SCHEMA_VERSION = "embedded-agent-toolkit.identity-ledger.v1"
VALIDATION_SCHEMA_VERSION = "embedded-agent-toolkit.identity-ledger-validation.v1"
EVIDENCE_STATES = frozenset(
    {"observed", "documented", "inferred", "rejected", "unknown"}
)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _require_string(value: object, field: str, errors: list[str]) -> str | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} must be a non-empty string")
        return None
    return value


def _validate_sources(value: object, errors: list[str]) -> tuple[int, set[str]]:
    if not isinstance(value, list) or not value:
        errors.append("sources must be a non-empty array")
        return 0, set()

    identifiers: list[str] = []
    for index, source in enumerate(value):
        prefix = f"sources[{index}]"
        if not isinstance(source, dict):
            errors.append(f"{prefix} must be an object")
            continue
        source_id = _require_string(source.get("id"), f"{prefix}.id", errors)
        if source_id is not None:
            identifiers.append(source_id)
        _require_string(source.get("tool"), f"{prefix}.tool", errors)
        _require_string(source.get("path"), f"{prefix}.path", errors)
        digest = _require_string(source.get("sha256"), f"{prefix}.sha256", errors)
        if digest is not None and SHA256_PATTERN.fullmatch(digest) is None:
            errors.append(
                f"{prefix}.sha256 must be 64 lowercase hexadecimal characters"
            )
        if not isinstance(source.get("point_in_time"), bool):
            errors.append(f"{prefix}.point_in_time must be a boolean")

    for source_id, count in Counter(identifiers).items():
        if count > 1:
            errors.append(f"duplicate source id: {source_id}")
    return len(value), set(identifiers)


def _validate_source_references(
    value: object,
    prefix: str,
    known_source_ids: set[str],
    required: bool,
    errors: list[str],
) -> None:
    if value is None and not required:
        return
    if (
        not isinstance(value, list)
        or (required and not value)
        or not all(isinstance(item, str) and item.strip() for item in value)
    ):
        requirement = "a non-empty string array" if required else "a string array"
        errors.append(f"{prefix}.source_ids must be {requirement}")
        return
    duplicates = sorted(
        source_id for source_id, count in Counter(value).items() if count > 1
    )
    for source_id in duplicates:
        errors.append(f"{prefix}.source_ids contains duplicate id: {source_id}")
    for source_id in sorted(set(value) - known_source_ids):
        errors.append(f"{prefix}.source_ids references unknown source: {source_id}")


def _validate_claims(
    value: object, known_source_ids: set[str], errors: list[str]
) -> tuple[int, Counter[str]]:
    if not isinstance(value, list) or not value:
        errors.append("claims must be a non-empty array")
        return 0, Counter()

    identifiers: list[str] = []
    states: Counter[str] = Counter()
    for index, claim in enumerate(value):
        prefix = f"claims[{index}]"
        if not isinstance(claim, dict):
            errors.append(f"{prefix} must be an object")
            continue
        claim_id = _require_string(claim.get("id"), f"{prefix}.id", errors)
        if claim_id is not None:
            identifiers.append(claim_id)
        _require_string(claim.get("claim"), f"{prefix}.claim", errors)
        state = _require_string(claim.get("state"), f"{prefix}.state", errors)
        if state is None:
            continue
        states[state] += 1
        if state not in EVIDENCE_STATES:
            errors.append(f"{prefix}.state is not a supported evidence state: {state}")
            continue
        _validate_source_references(
            claim.get("source_ids"),
            prefix,
            known_source_ids,
            required=state != "unknown",
            errors=errors,
        )
        if state == "inferred":
            assumptions = claim.get("assumptions")
            if (
                not isinstance(assumptions, list)
                or not assumptions
                or not all(
                    isinstance(item, str) and item.strip() for item in assumptions
                )
            ):
                errors.append(f"{prefix}.assumptions must be a non-empty string array")
        elif state == "rejected":
            _require_string(
                claim.get("contradiction"), f"{prefix}.contradiction", errors
            )
        elif state == "unknown" and not any(
            isinstance(claim.get(field), str) and claim[field].strip()
            for field in ("reason", "required_evidence")
        ):
            errors.append(
                f"{prefix} must explain unknown state with reason or required_evidence"
            )

    for claim_id, count in Counter(identifiers).items():
        if count > 1:
            errors.append(f"duplicate claim id: {claim_id}")
    return len(value), states


def validate_ledger(data: object) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(data, dict):
        errors.append("ledger root must be an object")
        return {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "ok": False,
            "ledger_schema_version": None,
            "source_count": 0,
            "claim_count": 0,
            "state_counts": {},
            "errors": errors,
        }

    ledger_schema_version = data.get("schema_version")
    if ledger_schema_version != LEDGER_SCHEMA_VERSION:
        errors.append(f"schema_version must equal {LEDGER_SCHEMA_VERSION}")
    _require_string(data.get("mode"), "mode", errors)
    _require_string(data.get("question"), "question", errors)
    source_count, source_ids = _validate_sources(data.get("sources"), errors)
    claim_count, state_counts = _validate_claims(data.get("claims"), source_ids, errors)

    next_experiment = data.get("next_experiment")
    if not isinstance(next_experiment, dict):
        errors.append("next_experiment must be an object")
    else:
        _require_string(
            next_experiment.get("authorization"),
            "next_experiment.authorization",
            errors,
        )

    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "ok": not errors,
        "ledger_schema_version": ledger_schema_version,
        "source_count": source_count,
        "claim_count": claim_count,
        "state_counts": dict(sorted(state_counts.items())),
        "errors": errors,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate an Embedded Agent Toolkit identity ledger without accessing hardware."
    )
    parser.add_argument("ledger", type=Path)
    parser.add_argument(
        "--json", action="store_true", help="emit a versioned JSON result"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        data = json.loads(args.ledger.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        report = {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "ok": False,
            "ledger_schema_version": None,
            "source_count": 0,
            "claim_count": 0,
            "state_counts": {},
            "errors": [f"unable to load ledger: {error}"],
        }
    else:
        report = validate_ledger(data)

    report["path"] = str(args.ledger.resolve())
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["ok"]:
        print(
            f"Identity ledger valid: {report['source_count']} sources, "
            f"{report['claim_count']} claims"
        )
    else:
        print("Identity ledger invalid", file=sys.stderr)
        for error in report["errors"]:
            print(f"- {error}", file=sys.stderr)
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
