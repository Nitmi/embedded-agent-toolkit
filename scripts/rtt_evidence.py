"""Offline integrity checks for embedded-debugger 0.2.4 RTT evidence.

Preserve native files. This module starts no executable and performs no hardware
access. Payload integrity is distinct from project-specific runtime acceptance.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
MAX_PAYLOAD_BYTES = 1024 * 1024
MAX_CHUNKS = 4096
HEX = re.compile(r"[0-9a-f]*")
ADDRESS = re.compile(r"0x[0-9a-f]{8}")


class EvidenceError(ValueError):
    pass


def same(actual: Any, expected: Any) -> bool:
    """Compare JSON values without treating true as integer 1."""
    return json.dumps(actual, sort_keys=True) == json.dumps(expected, sort_keys=True)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise EvidenceError(message)


def obj(value: Any, field: str) -> dict:
    require(isinstance(value, dict), f"{field} must be an object")
    return value


def integer(value: Any, field: str, minimum: int, maximum: int) -> int:
    require(type(value) is int and minimum <= value <= maximum, f"invalid {field}")
    return value


def envelope(value: Any, operation: str) -> dict:
    document = obj(value, "envelope")
    require(document.get("schema_version") == "1.0", "invalid native envelope schema")
    require(document.get("ok") is True, "native operation did not succeed")
    require(document.get("operation") == operation, "unexpected native operation")
    return obj(document.get("data"), "data")


def validate_plan(value: Any) -> dict:
    plan = obj(value, "plan")
    require(
        plan.get("schema_version") == "embedded-debugger.rtt-plan.v1",
        "invalid RTT plan schema",
    )
    require(plan.get("operation") == "rtt.capture", "unexpected plan operation")
    require(
        plan.get("scope") == "host_only_rtt_planning"
        and plan.get("hardware_access") is False,
        "RTT planning must be host-only",
    )
    require(
        plan.get("protocol") == "segger_rtt_32bit_little_endian",
        "unsupported RTT protocol",
    )
    require(
        plan.get("hardware_acceptance_verified") is False,
        "unexpected plan hardware acceptance claim",
    )
    require(
        isinstance(plan.get("confirm_digest"), str)
        and re.fullmatch(r"[0-9a-f]{64}", plan["confirm_digest"]) is not None,
        "missing native plan digest",
    )
    backend = plan.get("backend")
    require(backend in {"replay", "probe-rs"}, "unsupported RTT backend")
    require(
        isinstance(plan.get("probe_id"), str) and bool(plan["probe_id"]),
        "missing exact probe",
    )
    target = obj(plan.get("target"), "target")
    selection = obj(plan.get("selection"), "selection")
    integer(selection.get("core"), "core", 0, 255)
    integer(selection.get("channel"), "channel", 0, 15)
    require(
        isinstance(selection.get("control_block"), str)
        and ADDRESS.fullmatch(selection["control_block"]) is not None,
        "invalid control-block address",
    )
    if backend == "probe-rs":
        require(
            target.get("name") == "nRF52840_xxAA" and selection["core"] == 0,
            "unsupported native RTT target/core",
        )
    expected_effects = {
        "target_ram_read": True,
        "target_rtt_read_cursor_write": True,
        "down_channel_write": False,
        "channel_mode_write": False,
        "reset_requested": False,
        "halt_requested": False,
        "resume_requested": False,
        "attach_may_affect_target": backend != "replay",
        "post_disconnect_core_state_verified": False,
    }
    require(same(plan.get("effects"), expected_effects), "unexpected RTT effects")
    limits = obj(plan.get("limits"), "limits")
    duration = integer(limits.get("duration_ms"), "duration_ms", 10, 60000)
    integer(limits.get("poll_interval_ms"), "poll_interval_ms", 1, min(1000, duration))
    integer(limits.get("maximum_bytes"), "maximum_bytes", 1, MAX_PAYLOAD_BYTES)
    require(
        type(plan.get("chunk_bytes_limit")) is int
        and plan["chunk_bytes_limit"] == 4096,
        "unexpected chunk byte limit",
    )
    require(
        type(plan.get("chunk_count_limit")) is int
        and plan["chunk_count_limit"] == MAX_CHUNKS,
        "unexpected chunk count limit",
    )
    return plan


def plan_from_envelope(value: Any) -> dict:
    return validate_plan(envelope(value, "rtt.plan"))


def _unique(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _nonfinite(value: str) -> None:
    raise EvidenceError(f"non-finite JSON number: {value}")


def _timestamp(value: Any) -> None:
    require(isinstance(value, str), "missing timestamp")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(
            stamp.utcoffset() is not None and stamp.utcoffset().total_seconds() == 0,
            "timestamp must be UTC",
        )
    except ValueError as error:
        raise EvidenceError(f"invalid timestamp: {value}") from error


def check_capture(value: Any, base: Path) -> dict[str, Any]:
    """Return a bounded integrity result; never return or rewrite native payload."""
    result: dict[str, Any] = {
        "ok": False,
        "path": None,
        "sha256": None,
        "size": None,
        "bytes_captured": None,
        "chunk_count": None,
        "payload_sha256": None,
    }
    try:
        data = envelope(value, "rtt.capture")
        require(
            data.get("schema_version") == "embedded-debugger.rtt-capture.v1",
            "invalid RTT capture schema",
        )
        require(data.get("scope") == "bounded_rtt_capture", "unexpected capture scope")
        require(
            data.get("complete") is True
            and data.get("channel_stopped") is True
            and data.get("disconnected") is True,
            "capture or cleanup incomplete",
        )
        plan = validate_plan(data.get("plan"))
        require(
            data.get("hardware_access") is (plan["backend"] != "replay"),
            "hardware scope mismatch",
        )
        session = obj(data.get("session"), "session")
        require(
            session.get("backend") == plan["backend"]
            and same(session.get("target"), plan["target"])
            and obj(session.get("probe"), "probe").get("id") == plan["probe_id"],
            "session identity differs from plan",
        )
        channel = obj(data.get("channel"), "channel")
        require(
            same(channel.get("selection"), plan["selection"])
            and same(channel.get("memory_scope"), plan.get("memory_scope")),
            "channel differs from plan",
        )
        total = integer(
            data.get("bytes_captured"),
            "bytes_captured",
            0,
            plan["limits"]["maximum_bytes"],
        )
        count = integer(data.get("chunk_count"), "chunk_count", 0, MAX_CHUNKS)
        require(
            type(data.get("next_cursor")) is int and data["next_cursor"] == total,
            "invalid final cursor",
        )
        elapsed = integer(data.get("elapsed_ms"), "elapsed_ms", 0, 2**64 - 1)
        reason = data.get("stop_reason")
        require(
            reason in {"byte_limit", "chunk_limit", "duration_limit"},
            "invalid stop reason",
        )
        require(
            reason != "byte_limit" or total == plan["limits"]["maximum_bytes"],
            "byte limit not reached",
        )
        require(
            reason != "chunk_limit" or count == MAX_CHUNKS, "chunk limit not reached"
        )
        require(
            reason != "duration_limit" or elapsed >= plan["limits"]["duration_ms"],
            "duration limit not reached",
        )
        reference = obj(data.get("evidence"), "evidence")
        require(reference.get("kind") == "rtt_jsonl", "unexpected artifact kind")
        require(
            isinstance(reference.get("path"), str) and bool(reference["path"]),
            "missing artifact path",
        )
        path = Path(reference["path"])
        if not path.is_absolute():
            path = base / path
        path = path.resolve(strict=True)
        require(path.is_file(), "artifact must be a regular file")
        result["path"] = str(path)
        with path.open("rb") as handle:
            raw = handle.read(MAX_ARTIFACT_BYTES + 1)
        require(len(raw) <= MAX_ARTIFACT_BYTES, "RTT artifact too large")
        result["size"] = len(raw)
        result["sha256"] = hashlib.sha256(raw).hexdigest()
        require(
            type(reference.get("size")) is int and reference["size"] == len(raw),
            "artifact size differs",
        )
        require(result["sha256"] == reference.get("sha256"), "artifact SHA-256 differs")
        require(raw.endswith(b"\n"), "incomplete JSONL record")
        lines = raw.splitlines()
        require(3 <= len(lines) <= MAX_CHUNKS + 3, "invalid JSONL record count")
        records = [
            obj(
                json.loads(
                    line.decode("utf-8"),
                    object_pairs_hook=_unique,
                    parse_constant=_nonfinite,
                ),
                "record",
            )
            for line in lines
        ]
        capture_id = data.get("capture_id")
        require(isinstance(capture_id, str) and bool(capture_id), "missing capture ID")
        previous_elapsed = 0
        for record in records:
            require(
                record.get("schema_version") == "embedded-debugger.rtt-evidence.v1"
                and record.get("capture_id") == capture_id,
                "record schema/capture ID mismatch",
            )
            _timestamp(record.get("timestamp"))
            previous_elapsed = integer(
                record.get("elapsed_ms"), "record elapsed_ms", previous_elapsed, elapsed
            )
        start, metadata, finish = records[0], records[1], records[-1]
        require(
            start.get("event") == "capture.started"
            and same(start.get("plan"), plan)
            and start.get("elapsed_ms") == 0
            and start.get("timestamp") == data.get("started_at"),
            "capture start differs from summary",
        )
        require(
            metadata.get("event") == "rtt.channel"
            and same(metadata.get("channel"), channel),
            "channel metadata differs from summary",
        )
        require(
            finish.get("event") == "capture.finished" and finish.get("ok") is True,
            "missing successful capture finish",
        )
        for field in (
            "bytes_captured",
            "chunk_count",
            "next_cursor",
            "payload_sha256",
            "stop_reason",
            "elapsed_ms",
        ):
            require(
                same(finish.get(field), data.get(field)),
                f"finish {field} differs from summary",
            )
        require(
            finish.get("timestamp") == data.get("finished_at"),
            "finish timestamp differs",
        )
        require(
            same(
                finish.get("cleanup"),
                {
                    "channel_stopped": True,
                    "disconnected": True,
                    "stop_error": None,
                    "disconnect_error": None,
                },
            ),
            "finish cleanup failed",
        )
        payload = hashlib.sha256()
        cursor = 0
        chunks = records[2:-1]
        require(len(chunks) == count, "chunk count differs")
        for sequence, chunk in enumerate(chunks):
            require(
                chunk.get("event") == "rtt.chunk" and chunk.get("encoding") == "hex",
                "invalid chunk event/encoding",
            )
            require(
                type(chunk.get("sequence")) is int and chunk["sequence"] == sequence,
                "chunk sequence discontinuity",
            )
            require(
                type(chunk.get("cursor")) is int and chunk["cursor"] == cursor,
                "chunk cursor discontinuity",
            )
            encoded = chunk.get("data")
            require(
                isinstance(encoded, str)
                and len(encoded) <= 8192
                and HEX.fullmatch(encoded) is not None,
                "invalid chunk hex",
            )
            decoded = bytes.fromhex(encoded)
            length = integer(chunk.get("length"), "chunk length", 1, 4096)
            require(len(decoded) == length, "chunk length differs")
            cursor += length
            require(
                cursor <= total
                and type(chunk.get("next_cursor")) is int
                and chunk["next_cursor"] == cursor,
                "invalid chunk next_cursor",
            )
            payload.update(decoded)
        require(cursor == total, "payload byte count differs")
        require(
            payload.hexdigest() == data.get("payload_sha256"), "payload SHA-256 differs"
        )
        result.update(
            ok=True,
            bytes_captured=cursor,
            chunk_count=count,
            payload_sha256=payload.hexdigest(),
        )
    except (
        EvidenceError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        RecursionError,
    ) as error:
        result["error"] = str(error) or type(error).__name__
    return result
