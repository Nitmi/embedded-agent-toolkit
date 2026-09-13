#!/usr/bin/env python3
"""Compile and inspect non-authorizing embedded hardware-test contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

SPEC_SCHEMA = "embedded-agent-toolkit.test-spec.v1"
CONTRACT_SCHEMA = "embedded-agent-toolkit.test-contract.v1"
REPORT_SCHEMA = "embedded-agent-toolkit.test-contract-report.v1"
SELECTION_SCHEMA = "embedded-board-registry.selection.v1"
MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_NATIVE_INPUT_BYTES = 32 * 1024 * 1024
MAX_FIRMWARE_BYTES = 512 * 1024 * 1024
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
JSON_POINTER_PATTERN = re.compile(r"(?:/(?:[^~/]|~[01])*)*")
TRANSPORTS = frozenset({"serial", "debug", "ble"})
TRANSPORT_COMPONENTS = {
    "serial": "baud",
    "debug": "embedded-debugger",
    "ble": "blea",
}
IDENTITY_FIELDS = {
    "serial": frozenset({"port", "usb_vid", "usb_pid", "usb_serial", "pnp_interface"}),
    "debug": frozenset(
        {"probe_selector", "vendor_id", "product_id", "serial_number", "target"}
    ),
    "ble": frozenset({"identifier", "local_name", "service_uuid", "manufacturer_id"}),
}
RESOURCE_KINDS = frozenset(
    {
        "firmware",
        "baud-workflow",
        "blea-workflow",
        "debugger-runtime-contract",
    }
)
EFFECTS = frozenset(
    {
        "host_process_start",
        "hardware_discovery",
        "serial_open",
        "serial_transmit",
        "ble_scan",
        "ble_connect",
        "ble_write",
        "debug_attach",
        "target_state_may_change",
        "target_reset",
        "target_halt",
        "target_resume",
        "target_step",
        "register_read",
        "register_write",
        "memory_read",
        "memory_write",
        "flash_erase",
        "flash_write",
        "recover",
        "external_actuation",
    }
)
PERSISTENT_EFFECTS = frozenset(
    {"register_write", "memory_write", "flash_erase", "flash_write", "recover"}
)
EXTERNAL_EFFECTS = frozenset({"serial_transmit", "ble_write", "external_actuation"})
TARGET_CONTROL_EFFECTS = frozenset(
    {
        "debug_attach",
        "target_state_may_change",
        "target_reset",
        "target_halt",
        "target_resume",
        "target_step",
    }
)
HARDWARE_EFFECTS = EFFECTS - {"host_process_start"}
NON_RETRIABLE_EFFECTS = (
    PERSISTENT_EFFECTS | EXTERNAL_EFFECTS | TARGET_CONTROL_EFFECTS | {"ble_connect"}
)
CLEANUP_STATES = {
    "serial": frozenset({"closed"}),
    "ble": frozenset({"disconnected"}),
    "debug": frozenset({"disconnected"}),
    "target": frozenset({"running", "halted", "unchanged"}),
}


class ContractError(ValueError):
    pass


@dataclass(frozen=True)
class OperationPolicy:
    component: str
    required_transports: frozenset[str]
    input_kinds: tuple[str, ...]
    minimum_effects: frozenset[str]
    allowed_effects: frozenset[str]
    target_required: bool = False
    prerequisite_operation: str | None = None


def _effects(*values: str) -> frozenset[str]:
    return frozenset(values)


OPERATION_POLICIES = {
    "baud.monitor": OperationPolicy(
        "baud",
        frozenset({"serial"}),
        (),
        _effects("host_process_start", "serial_open"),
        _effects("host_process_start", "serial_open"),
    ),
    "baud.workflow": OperationPolicy(
        "baud",
        frozenset({"serial"}),
        ("baud-workflow",),
        _effects("host_process_start", "serial_open"),
        _effects(
            "host_process_start",
            "serial_open",
            "serial_transmit",
            "external_actuation",
        ),
    ),
    "blea.scan": OperationPolicy(
        "blea",
        frozenset({"ble"}),
        (),
        _effects("host_process_start", "ble_scan"),
        _effects("host_process_start", "ble_scan"),
    ),
    "blea.workflow": OperationPolicy(
        "blea",
        frozenset({"ble"}),
        ("blea-workflow",),
        _effects("host_process_start"),
        _effects(
            "host_process_start",
            "ble_scan",
            "ble_connect",
            "ble_write",
            "external_actuation",
        ),
    ),
    "embedded-debugger.probes-test": OperationPolicy(
        "embedded-debugger",
        frozenset({"debug"}),
        (),
        _effects(
            "host_process_start",
            "hardware_discovery",
            "debug_attach",
            "target_state_may_change",
        ),
        _effects(
            "host_process_start",
            "hardware_discovery",
            "debug_attach",
            "target_state_may_change",
        ),
        target_required=True,
    ),
    "embedded-debugger.flash-plan": OperationPolicy(
        "embedded-debugger",
        frozenset({"debug"}),
        ("firmware",),
        _effects("host_process_start", "hardware_discovery"),
        _effects("host_process_start", "hardware_discovery"),
        target_required=True,
    ),
    "embedded-debugger.flash-execute": OperationPolicy(
        "embedded-debugger",
        frozenset({"debug"}),
        ("firmware",),
        _effects(
            "host_process_start",
            "hardware_discovery",
            "debug_attach",
            "target_state_may_change",
            "target_reset",
            "target_halt",
            "target_resume",
            "register_read",
            "memory_read",
            "flash_erase",
            "flash_write",
        ),
        _effects(
            "host_process_start",
            "hardware_discovery",
            "debug_attach",
            "target_state_may_change",
            "target_reset",
            "target_halt",
            "target_resume",
            "register_read",
            "memory_read",
            "flash_erase",
            "flash_write",
        ),
        target_required=True,
        prerequisite_operation="embedded-debugger.flash-plan",
    ),
    "embedded-debugger.runtime-inspect": OperationPolicy(
        "embedded-debugger",
        frozenset(),
        ("debugger-runtime-contract",),
        _effects("host_process_start"),
        _effects("host_process_start"),
    ),
    "embedded-debugger.runtime-accept": OperationPolicy(
        "embedded-debugger",
        frozenset({"debug", "serial"}),
        ("debugger-runtime-contract",),
        _effects(
            "host_process_start",
            "serial_open",
            "debug_attach",
            "target_state_may_change",
            "target_reset",
            "target_halt",
            "target_resume",
            "register_read",
        ),
        _effects(
            "host_process_start",
            "serial_open",
            "debug_attach",
            "target_state_may_change",
            "target_reset",
            "target_halt",
            "target_resume",
            "register_read",
        ),
        target_required=True,
        prerequisite_operation="embedded-debugger.runtime-inspect",
    ),
}


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        size = path.stat().st_size
        if size > MAX_JSON_BYTES:
            raise ContractError(f"{label} exceeds {MAX_JSON_BYTES} bytes")
        value = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=unique_object
        )
    except ContractError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ContractError(f"unable to load {label} {path}: {error}") from error
    if not isinstance(value, dict):
        raise ContractError(f"{label} root must be an object")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise ContractError(f"unable to hash {path}: {error}") from error
    return digest.hexdigest()


def _reject_unknown(
    value: dict[str, Any], allowed: set[str], field: str, errors: list[str]
) -> None:
    for key in sorted(set(value) - allowed):
        errors.append(f"{field}.{key} is not allowed")
    for key in sorted(allowed - set(value)):
        errors.append(f"{field}.{key} is required")


def _string(value: object, field: str, errors: list[str]) -> str | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} must be a non-empty string")
        return None
    return value


def _json_pointer(value: object, field: str, errors: list[str]) -> str | None:
    if not isinstance(value, str):
        errors.append(f"{field} must be a string")
        return None
    if JSON_POINTER_PATTERN.fullmatch(value) is None:
        errors.append(f"{field} must be RFC 6901 syntax")
    return value


def _identifier(value: object, field: str, errors: list[str]) -> str | None:
    result = _string(value, field, errors)
    if result is not None and ID_PATTERN.fullmatch(result) is None:
        errors.append(f"{field} must match {ID_PATTERN.pattern}")
    return result


def _digest(value: object, field: str, errors: list[str]) -> str | None:
    result = _string(value, field, errors)
    if result is not None and SHA256_PATTERN.fullmatch(result) is None:
        errors.append(f"{field} must be a lowercase SHA-256")
    return result


def _integer(
    value: object, field: str, minimum: int, maximum: int, errors: list[str]
) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        errors.append(f"{field} must be an integer")
        return None
    if not minimum <= value <= maximum:
        errors.append(f"{field} must be between {minimum} and {maximum}")
    return value


def _string_array(
    value: object,
    field: str,
    errors: list[str],
    *,
    nonempty: bool = False,
    sorted_unique: bool = False,
) -> list[str]:
    if (
        not isinstance(value, list)
        or (nonempty and not value)
        or not all(isinstance(item, str) and item for item in value)
    ):
        requirement = "a non-empty string array" if nonempty else "a string array"
        errors.append(f"{field} must be {requirement}")
        return []
    if len(value) != len(set(value)):
        errors.append(f"{field} must contain unique values")
    if sorted_unique and value != sorted(set(value)):
        errors.append(f"{field} must be sorted and unique")
    return value


def _reference(value: object, field: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object")
        return
    _reject_unknown(value, {"path", "sha256"}, field, errors)
    _string(value.get("path"), f"{field}.path", errors)
    _digest(value.get("sha256"), f"{field}.sha256", errors)


def _identity(
    value: object, transport: str | None, field: str, errors: list[str]
) -> dict[str, str]:
    if not isinstance(value, dict) or not value:
        errors.append(f"{field} must be a non-empty object")
        return {}
    if transport not in TRANSPORTS:
        return {}
    for key in sorted(set(value) - IDENTITY_FIELDS[transport]):
        errors.append(f"{field}.{key} is not valid for transport {transport}")
    result: dict[str, str] = {}
    for key, item in value.items():
        checked = _string(item, f"{field}.{key}", errors)
        if checked is not None:
            result[key] = checked
    return result


def _validate_binding(value: object, field: str, errors: list[str]) -> str | None:
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object")
        return None
    _reject_unknown(
        value,
        {
            "transport",
            "selector_id",
            "observation_id",
            "selector_identity",
            "observed_identity",
            "source",
        },
        field,
        errors,
    )
    transport = _string(value.get("transport"), f"{field}.transport", errors)
    if transport is not None and transport not in TRANSPORTS:
        errors.append(f"{field}.transport must be one of {sorted(TRANSPORTS)}")
    _identifier(value.get("selector_id"), f"{field}.selector_id", errors)
    _identifier(value.get("observation_id"), f"{field}.observation_id", errors)
    selector = _identity(
        value.get("selector_identity"),
        transport,
        f"{field}.selector_identity",
        errors,
    )
    observed = _identity(
        value.get("observed_identity"),
        transport,
        f"{field}.observed_identity",
        errors,
    )
    if (
        selector
        and observed
        and not all(observed.get(key) == item for key, item in selector.items())
    ):
        errors.append(f"{field}.selector_identity does not match observed_identity")
    source = value.get("source")
    if not isinstance(source, dict):
        errors.append(f"{field}.source must be an object")
    else:
        _reject_unknown(
            source, {"path", "sha256", "point_in_time"}, f"{field}.source", errors
        )
        _string(source.get("path"), f"{field}.source.path", errors)
        _digest(source.get("sha256"), f"{field}.source.sha256", errors)
        if source.get("point_in_time") is not True:
            errors.append(f"{field}.source.point_in_time must equal true")
    return transport


def validate_selection(data: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["selection root must be an object"]
    _reject_unknown(
        data,
        {
            "schema_version",
            "ok",
            "status",
            "board_id",
            "required_transports",
            "bindings",
            "inputs",
            "authorization",
            "hardware_access",
            "executables_started",
        },
        "selection",
        errors,
    )
    if data.get("schema_version") != SELECTION_SCHEMA:
        errors.append(f"selection.schema_version must equal {SELECTION_SCHEMA}")
    if data.get("ok") is not True:
        errors.append("selection.ok must equal true")
    if data.get("status") != "selected":
        errors.append("selection.status must equal selected")
    _identifier(data.get("board_id"), "selection.board_id", errors)
    required = _string_array(
        data.get("required_transports"),
        "selection.required_transports",
        errors,
        nonempty=True,
        sorted_unique=True,
    )
    for item in required:
        if item not in TRANSPORTS:
            errors.append(f"selection.required_transports contains unsupported {item}")
    bindings = data.get("bindings")
    transports: list[str] = []
    if not isinstance(bindings, list) or not bindings:
        errors.append("selection.bindings must be a non-empty array")
    else:
        for index, binding in enumerate(bindings):
            transport = _validate_binding(
                binding, f"selection.bindings[{index}]", errors
            )
            if transport is not None:
                transports.append(transport)
    if transports != required:
        errors.append(
            "selection.bindings must contain exactly one binding per required transport in order"
        )
    inputs = data.get("inputs")
    if not isinstance(inputs, dict):
        errors.append("selection.inputs must be an object")
    else:
        _reject_unknown(
            inputs, {"registry", "observations"}, "selection.inputs", errors
        )
        _reference(inputs.get("registry"), "selection.inputs.registry", errors)
        _reference(inputs.get("observations"), "selection.inputs.observations", errors)
    authorization = data.get("authorization")
    if not isinstance(authorization, dict):
        errors.append("selection.authorization must be an object")
    else:
        _reject_unknown(
            authorization,
            {"granted", "allowed_operations"},
            "selection.authorization",
            errors,
        )
        if authorization.get("granted") is not False:
            errors.append("selection.authorization.granted must equal false")
        if authorization.get("allowed_operations") != []:
            errors.append("selection.authorization.allowed_operations must be empty")
    if data.get("hardware_access") is not False:
        errors.append("selection.hardware_access must equal false")
    if data.get("executables_started") is not False:
        errors.append("selection.executables_started must equal false")
    return errors


def _validate_resources(value: object, errors: list[str]) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list):
        errors.append("resources must be an array")
        return {}
    if len(value) > 64:
        errors.append("resources must contain at most 64 items")
    result: dict[str, dict[str, Any]] = {}
    identifiers: list[str] = []
    for index, resource in enumerate(value):
        field = f"resources[{index}]"
        if not isinstance(resource, dict):
            errors.append(f"{field} must be an object")
            continue
        _reject_unknown(resource, {"id", "kind", "path", "sha256"}, field, errors)
        identifier = _identifier(resource.get("id"), f"{field}.id", errors)
        kind = _string(resource.get("kind"), f"{field}.kind", errors)
        if kind is not None and kind not in RESOURCE_KINDS:
            errors.append(f"{field}.kind must be one of {sorted(RESOURCE_KINDS)}")
        _string(resource.get("path"), f"{field}.path", errors)
        _digest(resource.get("sha256"), f"{field}.sha256", errors)
        if identifier is not None:
            identifiers.append(identifier)
            result[identifier] = resource
    for identifier, count in Counter(identifiers).items():
        if count > 1:
            errors.append(f"duplicate resource id: {identifier}")
    return result


def _risk(effects: set[str] | frozenset[str]) -> str:
    if effects & PERSISTENT_EFFECTS:
        return "persistent-write"
    if effects & EXTERNAL_EFFECTS:
        return "external-interaction"
    if effects & TARGET_CONTROL_EFFECTS:
        return "target-control"
    if effects & HARDWARE_EFFECTS:
        return "hardware-observation"
    return "host-only"


def _validate_stages(
    value: object,
    resources: dict[str, dict[str, Any]],
    debug_target: str | None,
    errors: list[str],
) -> tuple[list[dict[str, Any]], set[str], set[str]]:
    if not isinstance(value, list) or not value:
        errors.append("stages must be a non-empty array")
        return [], set(), set()
    if len(value) > 64:
        errors.append("stages must contain at most 64 items")
    result: list[dict[str, Any]] = []
    identifiers: list[str] = []
    seen: dict[str, dict[str, Any]] = {}
    required_transports: set[str] = set()
    all_effects: set[str] = set()
    evidence_outputs: list[str] = []
    for index, stage in enumerate(value):
        field = f"stages[{index}]"
        if not isinstance(stage, dict):
            errors.append(f"{field} must be an object")
            continue
        _reject_unknown(
            stage,
            {
                "id",
                "operation",
                "inputs",
                "requires",
                "declared_effects",
                "timeout_seconds",
                "max_retries",
                "evidence_output",
            },
            field,
            errors,
        )
        identifier = _identifier(stage.get("id"), f"{field}.id", errors)
        operation = _string(stage.get("operation"), f"{field}.operation", errors)
        policy = OPERATION_POLICIES.get(operation or "")
        if operation is not None and policy is None:
            errors.append(
                f"{field}.operation must be one of {sorted(OPERATION_POLICIES)}"
            )
        inputs = _string_array(stage.get("inputs"), f"{field}.inputs", errors)
        requires = _string_array(stage.get("requires"), f"{field}.requires", errors)
        effects = _string_array(
            stage.get("declared_effects"),
            f"{field}.declared_effects",
            errors,
            nonempty=True,
            sorted_unique=True,
        )
        effect_set = set(effects)
        for effect in sorted(effect_set - EFFECTS):
            errors.append(f"{field}.declared_effects contains unsupported {effect}")
        timeout = _integer(
            stage.get("timeout_seconds"),
            f"{field}.timeout_seconds",
            1,
            86400,
            errors,
        )
        retries = _integer(
            stage.get("max_retries"), f"{field}.max_retries", 0, 3, errors
        )
        evidence = _string(
            stage.get("evidence_output"), f"{field}.evidence_output", errors
        )
        if evidence is not None:
            evidence_outputs.append(evidence)
        for resource_id in inputs:
            if resource_id not in resources:
                errors.append(
                    f"{field}.inputs references unknown resource {resource_id}"
                )
        for required in requires:
            if required not in seen:
                errors.append(
                    f"{field}.requires references unknown or later stage {required}"
                )
        if policy is not None:
            input_kinds = tuple(
                sorted(
                    str(resources[item].get("kind"))
                    for item in inputs
                    if item in resources
                )
            )
            if input_kinds != tuple(sorted(policy.input_kinds)):
                errors.append(
                    f"{field}.inputs must select resource kinds "
                    f"{list(policy.input_kinds)}"
                )
            missing = sorted(policy.minimum_effects - effect_set)
            unexpected = sorted(effect_set - policy.allowed_effects)
            if missing:
                errors.append(f"{field}.declared_effects is missing {missing}")
            if unexpected:
                errors.append(f"{field}.declared_effects does not allow {unexpected}")
            if policy.target_required and debug_target is None:
                errors.append(f"{field}.operation requires debug_target")
            if (
                retries is not None
                and retries != 0
                and effect_set & NON_RETRIABLE_EFFECTS
            ):
                errors.append(
                    f"{field}.max_retries must equal 0 for state-changing effects"
                )
            if policy.prerequisite_operation is not None:
                candidates = [
                    seen[item]
                    for item in requires
                    if item in seen
                    and seen[item].get("operation") == policy.prerequisite_operation
                    and seen[item].get("inputs") == inputs
                ]
                if not candidates:
                    errors.append(
                        f"{field} requires an earlier {policy.prerequisite_operation} "
                        "stage with the same inputs"
                    )
            required_transports.update(policy.required_transports)
        all_effects.update(effect_set)
        normalized = {
            "id": identifier,
            "operation": operation,
            "inputs": inputs,
            "requires": requires,
            "declared_effects": effects,
            "timeout_seconds": timeout,
            "max_retries": retries,
            "evidence_output": evidence,
        }
        result.append(normalized)
        if identifier is not None:
            identifiers.append(identifier)
            seen[identifier] = normalized
    for identifier, count in Counter(identifiers).items():
        if count > 1:
            errors.append(f"duplicate stage id: {identifier}")
    for evidence, count in Counter(evidence_outputs).items():
        if count > 1:
            errors.append(f"duplicate stage evidence_output: {evidence}")
    return result, required_transports, all_effects


def _validate_assertions(
    value: object, stage_ids: set[str], errors: list[str]
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        errors.append("assertions must be an array")
        return []
    if len(value) > 128:
        errors.append("assertions must contain at most 128 items")
    identifiers: list[str] = []
    result: list[dict[str, Any]] = []
    for index, assertion in enumerate(value):
        field = f"assertions[{index}]"
        if not isinstance(assertion, dict):
            errors.append(f"{field} must be an object")
            continue
        _reject_unknown(
            assertion,
            {"id", "stage", "json_pointer", "operator", "expected"},
            field,
            errors,
        )
        identifier = _identifier(assertion.get("id"), f"{field}.id", errors)
        stage = _identifier(assertion.get("stage"), f"{field}.stage", errors)
        if stage is not None and stage not in stage_ids:
            errors.append(f"{field}.stage references unknown stage {stage}")
        _json_pointer(assertion.get("json_pointer"), f"{field}.json_pointer", errors)
        operator = _string(assertion.get("operator"), f"{field}.operator", errors)
        if operator is not None and operator not in {
            "equals",
            "not_equals",
            "at_least",
            "at_most",
            "contains",
        }:
            errors.append(f"{field}.operator is unsupported")
        expected = assertion.get("expected")
        if isinstance(expected, (dict, list)):
            errors.append(f"{field}.expected must be a JSON scalar")
        if isinstance(expected, float) and not math.isfinite(expected):
            errors.append(f"{field}.expected must be finite")
        if operator in {"at_least", "at_most"} and (
            isinstance(expected, bool) or not isinstance(expected, (int, float))
        ):
            errors.append(f"{field}.expected must be numeric for {operator}")
        if identifier is not None:
            identifiers.append(identifier)
        result.append(assertion)
    for identifier, count in Counter(identifiers).items():
        if count > 1:
            errors.append(f"duplicate assertion id: {identifier}")
    return result


def _validate_cleanup(
    value: object, all_effects: set[str], errors: list[str]
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        errors.append("cleanup must be an array")
        return []
    resources: list[str] = []
    result: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        field = f"cleanup[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{field} must be an object")
            continue
        _reject_unknown(
            item, {"resource", "required_state", "timeout_seconds"}, field, errors
        )
        resource = _string(item.get("resource"), f"{field}.resource", errors)
        state = _string(item.get("required_state"), f"{field}.required_state", errors)
        _integer(
            item.get("timeout_seconds"),
            f"{field}.timeout_seconds",
            1,
            3600,
            errors,
        )
        if resource is not None:
            resources.append(resource)
            if resource not in CLEANUP_STATES:
                errors.append(
                    f"{field}.resource must be one of {sorted(CLEANUP_STATES)}"
                )
            elif state is not None and state not in CLEANUP_STATES[resource]:
                errors.append(
                    f"{field}.required_state must be one of "
                    f"{sorted(CLEANUP_STATES[resource])}"
                )
        result.append(item)
    for resource, count in Counter(resources).items():
        if count > 1:
            errors.append(f"duplicate cleanup resource: {resource}")
    required: set[str] = set()
    if "serial_open" in all_effects:
        required.add("serial")
    if "ble_connect" in all_effects:
        required.add("ble")
    if "debug_attach" in all_effects:
        required.add("debug")
    if all_effects & TARGET_CONTROL_EFFECTS:
        required.add("target")
    for missing in sorted(required - set(resources)):
        errors.append(f"cleanup must declare final state for {missing}")
    return result


def validate_spec(data: object) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return {"ok": False, "errors": ["spec root must be an object"]}
    _reject_unknown(
        data,
        {
            "schema_version",
            "name",
            "selection",
            "debug_target",
            "resources",
            "stages",
            "assertions",
            "cleanup",
        },
        "spec",
        errors,
    )
    if data.get("schema_version") != SPEC_SCHEMA:
        errors.append(f"schema_version must equal {SPEC_SCHEMA}")
    _identifier(data.get("name"), "name", errors)
    _string(data.get("selection"), "selection", errors)
    target_value = data.get("debug_target")
    debug_target = None
    if target_value is not None:
        debug_target = _string(target_value, "debug_target", errors)
    resources = _validate_resources(data.get("resources"), errors)
    stages, required_transports, all_effects = _validate_stages(
        data.get("stages"), resources, debug_target, errors
    )
    stage_ids = {item["id"] for item in stages if isinstance(item.get("id"), str)}
    _validate_assertions(data.get("assertions"), stage_ids, errors)
    _validate_cleanup(data.get("cleanup"), all_effects, errors)
    return {
        "ok": not errors,
        "errors": errors,
        "resources": resources,
        "stages": stages,
        "required_transports": required_transports,
        "all_effects": all_effects,
    }


def _resolve(path_value: str, base: Path, field: str, *, existing: bool) -> Path:
    candidate = Path(path_value).expanduser()
    if not candidate.is_absolute():
        candidate = base / candidate
    try:
        resolved = candidate.resolve(strict=existing)
    except OSError as error:
        raise ContractError(f"unable to resolve {field}: {error}") from error
    if existing and not resolved.is_file():
        raise ContractError(f"{field} must be an existing regular file: {resolved}")
    return resolved


def _check_resource_file(
    path: Path, expected_hash: str, kind: str, field: str
) -> tuple[str, int]:
    try:
        size = path.stat().st_size
    except OSError as error:
        raise ContractError(f"unable to inspect {field} {path}: {error}") from error
    maximum = MAX_FIRMWARE_BYTES if kind == "firmware" else MAX_NATIVE_INPUT_BYTES
    if size > maximum:
        raise ContractError(f"{field} exceeds {maximum} bytes")
    actual = sha256(path)
    if actual != expected_hash:
        raise ContractError(
            f"{field} SHA-256 differs: expected {expected_hash}, actual {actual}"
        )
    return actual, size


def compile_contract(spec_path: Path) -> dict[str, Any]:
    resolved_spec = _resolve(str(spec_path), Path.cwd(), "spec", existing=True)
    spec = load_json(resolved_spec, "test spec")
    validation = validate_spec(spec)
    if not validation["ok"]:
        raise ContractError("invalid test spec: " + "; ".join(validation["errors"]))
    base = resolved_spec.parent
    selection_path = _resolve(spec["selection"], base, "selection", existing=True)
    selection = load_json(selection_path, "board selection")
    selection_errors = validate_selection(selection)
    if selection_errors:
        raise ContractError("invalid board selection: " + "; ".join(selection_errors))
    selected_transports = set(selection["required_transports"])
    missing_transports = sorted(validation["required_transports"] - selected_transports)
    if missing_transports:
        raise ContractError(
            f"board selection does not bind required transports: {missing_transports}"
        )
    debug_target = spec["debug_target"]
    for binding in selection["bindings"]:
        if (
            binding["transport"] == "debug"
            and debug_target is not None
            and "target" in binding["observed_identity"]
            and binding["observed_identity"]["target"] != debug_target
        ):
            raise ContractError(
                "debug_target differs from the board selection observed target"
            )
    compiled_resources = []
    for resource in spec["resources"]:
        path = _resolve(
            resource["path"], base, f"resource {resource['id']}", existing=True
        )
        actual, size = _check_resource_file(
            path, resource["sha256"], resource["kind"], f"resource {resource['id']}"
        )
        compiled_resources.append(
            {
                "id": resource["id"],
                "kind": resource["kind"],
                "path": str(path),
                "sha256": actual,
                "size": size,
            }
        )
    compiled_stages = []
    for stage in spec["stages"]:
        policy = OPERATION_POLICIES[stage["operation"]]
        evidence = _resolve(
            stage["evidence_output"],
            base,
            f"stage {stage['id']} evidence_output",
            existing=False,
        )
        if evidence.exists() or evidence.is_symlink():
            raise ContractError(
                f"stage {stage['id']} evidence_output already exists: {evidence}"
            )
        compiled_stages.append(
            {
                **stage,
                "component": policy.component,
                "risk": _risk(set(stage["declared_effects"])),
                "evidence_output": str(evidence),
            }
        )
    bindings = [
        {**binding, "component": TRANSPORT_COMPONENTS[binding["transport"]]}
        for binding in selection["bindings"]
    ]
    contract = {
        "schema_version": CONTRACT_SCHEMA,
        "ok": True,
        "status": "compiled",
        "name": spec["name"],
        "source_spec": {"path": str(resolved_spec), "sha256": sha256(resolved_spec)},
        "board": {
            "id": selection["board_id"],
            "selection": {
                "path": str(selection_path),
                "sha256": sha256(selection_path),
                "schema_version": SELECTION_SCHEMA,
            },
            "required_transports": selection["required_transports"],
        },
        "bindings": bindings,
        "debug_target": debug_target,
        "resources": compiled_resources,
        "stages": compiled_stages,
        "assertions": spec["assertions"],
        "cleanup": spec["cleanup"],
        "authorization": {
            "granted": False,
            "allowed_operations": [],
            "contract_is_authorization": False,
            "native_component_gates_preserved": True,
        },
        "execution_supported": False,
        "hardware_access": False,
        "executables_started": False,
    }
    errors = validate_contract(contract)
    if errors:
        raise ContractError("compiler produced invalid contract: " + "; ".join(errors))
    return contract


def _compiled_reference(value: object, field: str, errors: list[str]) -> None:
    _reference(value, field, errors)


def validate_contract(data: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["contract root must be an object"]
    _reject_unknown(
        data,
        {
            "schema_version",
            "ok",
            "status",
            "name",
            "source_spec",
            "board",
            "bindings",
            "debug_target",
            "resources",
            "stages",
            "assertions",
            "cleanup",
            "authorization",
            "execution_supported",
            "hardware_access",
            "executables_started",
        },
        "contract",
        errors,
    )
    if data.get("schema_version") != CONTRACT_SCHEMA:
        errors.append(f"schema_version must equal {CONTRACT_SCHEMA}")
    if data.get("ok") is not True or data.get("status") != "compiled":
        errors.append("contract must have ok=true and status=compiled")
    _identifier(data.get("name"), "name", errors)
    _compiled_reference(data.get("source_spec"), "source_spec", errors)
    board = data.get("board")
    required_transports: list[str] = []
    if not isinstance(board, dict):
        errors.append("board must be an object")
    else:
        _reject_unknown(
            board, {"id", "selection", "required_transports"}, "board", errors
        )
        _identifier(board.get("id"), "board.id", errors)
        required_transports = _string_array(
            board.get("required_transports"),
            "board.required_transports",
            errors,
            nonempty=True,
            sorted_unique=True,
        )
        selection = board.get("selection")
        if not isinstance(selection, dict):
            errors.append("board.selection must be an object")
        else:
            _reject_unknown(
                selection,
                {"path", "sha256", "schema_version"},
                "board.selection",
                errors,
            )
            _string(selection.get("path"), "board.selection.path", errors)
            _digest(selection.get("sha256"), "board.selection.sha256", errors)
            if selection.get("schema_version") != SELECTION_SCHEMA:
                errors.append(
                    f"board.selection.schema_version must equal {SELECTION_SCHEMA}"
                )
    bindings = data.get("bindings")
    binding_transports: list[str] = []
    if not isinstance(bindings, list) or not bindings:
        errors.append("bindings must be a non-empty array")
    else:
        for index, binding in enumerate(bindings):
            field = f"bindings[{index}]"
            if not isinstance(binding, dict):
                errors.append(f"{field} must be an object")
                continue
            component = binding.get("component")
            native = {key: item for key, item in binding.items() if key != "component"}
            transport = _validate_binding(native, field, errors)
            if transport is not None:
                binding_transports.append(transport)
                if component != TRANSPORT_COMPONENTS.get(transport):
                    errors.append(f"{field}.component does not match transport")
    if binding_transports != required_transports:
        errors.append("bindings must match board.required_transports in order")
    target_value = data.get("debug_target")
    debug_target = None
    if target_value is not None:
        debug_target = _string(target_value, "debug_target", errors)
    resources_value = data.get("resources")
    spec_resources = []
    if not isinstance(resources_value, list):
        errors.append("resources must be an array")
        resources_value = []
    for index, resource in enumerate(resources_value):
        field = f"resources[{index}]"
        if not isinstance(resource, dict):
            errors.append(f"{field} must be an object")
            continue
        _reject_unknown(
            resource, {"id", "kind", "path", "sha256", "size"}, field, errors
        )
        _integer(resource.get("size"), f"{field}.size", 0, MAX_FIRMWARE_BYTES, errors)
        spec_resources.append(
            {key: resource.get(key) for key in ("id", "kind", "path", "sha256")}
        )
    resource_map = _validate_resources(spec_resources, errors)
    stages_value = data.get("stages")
    spec_stages = []
    if not isinstance(stages_value, list):
        errors.append("stages must be an array")
        stages_value = []
    for index, stage in enumerate(stages_value):
        field = f"stages[{index}]"
        if not isinstance(stage, dict):
            errors.append(f"{field} must be an object")
            continue
        _reject_unknown(
            stage,
            {
                "id",
                "operation",
                "component",
                "inputs",
                "requires",
                "declared_effects",
                "risk",
                "timeout_seconds",
                "max_retries",
                "evidence_output",
            },
            field,
            errors,
        )
        operation = stage.get("operation")
        policy = OPERATION_POLICIES.get(operation)
        if policy is not None and stage.get("component") != policy.component:
            errors.append(f"{field}.component does not match operation")
        effects = stage.get("declared_effects")
        if (
            isinstance(effects, list)
            and all(isinstance(item, str) for item in effects)
            and stage.get("risk") != _risk(set(effects))
        ):
            errors.append(f"{field}.risk does not match declared_effects")
        spec_stages.append(
            {
                key: stage.get(key)
                for key in (
                    "id",
                    "operation",
                    "inputs",
                    "requires",
                    "declared_effects",
                    "timeout_seconds",
                    "max_retries",
                    "evidence_output",
                )
            }
        )
    normalized_stages, used_transports, all_effects = _validate_stages(
        spec_stages, resource_map, debug_target, errors
    )
    if not used_transports.issubset(set(required_transports)):
        errors.append("board bindings do not cover every stage transport")
    stage_ids = {
        item["id"] for item in normalized_stages if isinstance(item.get("id"), str)
    }
    _validate_assertions(data.get("assertions"), stage_ids, errors)
    _validate_cleanup(data.get("cleanup"), all_effects, errors)
    authorization = data.get("authorization")
    expected_authorization = {
        "granted": False,
        "allowed_operations": [],
        "contract_is_authorization": False,
        "native_component_gates_preserved": True,
    }
    if authorization != expected_authorization:
        errors.append(
            "authorization must preserve the non-authorizing contract boundary"
        )
    if data.get("execution_supported") is not False:
        errors.append("execution_supported must equal false")
    if data.get("hardware_access") is not False:
        errors.append("hardware_access must equal false")
    if data.get("executables_started") is not False:
        errors.append("executables_started must equal false")
    return errors


def _current_input(
    kind: str, identifier: str, reference: dict[str, Any], expected_size: int | None
) -> tuple[dict[str, Any], str | None]:
    path = Path(reference["path"])
    expected = reference["sha256"]
    actual: str | None = None
    actual_size: int | None = None
    error: str | None = None
    try:
        resolved = path.resolve(strict=True)
        if not resolved.is_file():
            raise OSError("not a regular file")
        actual_size = resolved.stat().st_size
        actual = sha256(resolved)
    except (OSError, ContractError) as problem:
        error = str(problem)
    current = error is None and actual == expected
    if expected_size is not None:
        current = current and actual_size == expected_size
    check = {
        "kind": kind,
        "id": identifier,
        "path": str(path),
        "expected_sha256": expected,
        "actual_sha256": actual,
        "expected_size": expected_size,
        "actual_size": actual_size,
        "current": current,
    }
    if error is not None:
        check["error"] = error
    message = None
    if not current:
        message = f"{kind} {identifier} differs or is unavailable: {path}"
    return check, message


def inspect_contract(contract_path: Path) -> dict[str, Any]:
    resolved = _resolve(str(contract_path), Path.cwd(), "contract", existing=True)
    contract = load_json(resolved, "test contract")
    errors = validate_contract(contract)
    checks = []
    if not errors:
        references = [
            ("source-spec", "spec", contract["source_spec"], None),
            ("board-selection", "selection", contract["board"]["selection"], None),
        ]
        references.extend(
            (
                "resource",
                resource["id"],
                resource,
                resource["size"],
            )
            for resource in contract["resources"]
        )
        for kind, identifier, reference, expected_size in references:
            check, message = _current_input(kind, identifier, reference, expected_size)
            checks.append(check)
            if message is not None:
                errors.append(message)
    return {
        "schema_version": REPORT_SCHEMA,
        "operation": "inspect",
        "ok": not errors,
        "status": "valid" if not errors else "invalid_or_drifted",
        "contract": str(resolved),
        "contract_sha256": sha256(resolved),
        "board_id": contract.get("board", {}).get("id")
        if isinstance(contract.get("board"), dict)
        else None,
        "stage_count": len(contract.get("stages", []))
        if isinstance(contract.get("stages"), list)
        else 0,
        "input_checks": checks,
        "authorization_granted": False,
        "execution_supported": False,
        "hardware_access": False,
        "executables_started": False,
        "errors": errors,
    }


def _write_exclusive(path: Path, value: dict[str, Any]) -> Path:
    candidate = path.expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    resolved = candidate.resolve(strict=False)
    try:
        with resolved.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError as error:
        raise ContractError(f"output already exists: {resolved}") from error
    except OSError as error:
        raise ContractError(f"unable to write output {resolved}: {error}") from error
    return resolved


def compile_report(spec: Path, output: Path) -> dict[str, Any]:
    contract = compile_contract(spec)
    written = _write_exclusive(output, contract)
    return {
        "schema_version": REPORT_SCHEMA,
        "operation": "compile",
        "ok": True,
        "status": "compiled",
        "contract": str(written),
        "contract_sha256": sha256(written),
        "board_id": contract["board"]["id"],
        "stage_count": len(contract["stages"]),
        "resource_count": len(contract["resources"]),
        "risks": sorted({stage["risk"] for stage in contract["stages"]}),
        "authorization_granted": False,
        "execution_supported": False,
        "hardware_access": False,
        "executables_started": False,
        "errors": [],
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="operation", required=True)
    compile_parser = subparsers.add_parser(
        "compile", help="compile one strict test spec without executing components"
    )
    compile_parser.add_argument("spec", type=Path)
    compile_parser.add_argument("--output", type=Path, required=True)
    compile_parser.add_argument("--json", action="store_true")
    inspect_parser = subparsers.add_parser(
        "inspect", help="validate one contract and rehash all bound inputs"
    )
    inspect_parser.add_argument("contract", type=Path)
    inspect_parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def _render(report: dict[str, Any]) -> str:
    if report["ok"]:
        if report["operation"] == "compile":
            return (
                f"Test contract compiled: {report['contract']}\n"
                f"SHA-256: {report['contract_sha256']}\n"
                "Host only; execution and authorization are not provided."
            )
        return (
            f"Test contract valid: {report['contract']}\n"
            f"SHA-256: {report['contract_sha256']}\n"
            "All bound inputs are current; no component was executed."
        )
    return "Test contract invalid\n" + "\n".join(
        f"- {error}" for error in report["errors"]
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.operation == "compile":
            report = compile_report(args.spec, args.output)
        else:
            report = inspect_contract(args.contract)
    except ContractError as error:
        report = {
            "schema_version": REPORT_SCHEMA,
            "operation": args.operation,
            "ok": False,
            "status": "invalid",
            "authorization_granted": False,
            "execution_supported": False,
            "hardware_access": False,
            "executables_started": False,
            "errors": [str(error)],
        }
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        stream = sys.stdout if report["ok"] else sys.stderr
        print(_render(report), file=stream)
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
