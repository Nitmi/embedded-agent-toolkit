"""Offline integrity checks for embedded-debugger 0.2.4 RTT evidence.

Preserve native files. This module starts no executable and performs no hardware
access. Payload integrity is distinct from project-specific runtime acceptance.
"""

from __future__ import annotations

import argparse
import codecs
import hashlib
import json
import re
import sys
from bisect import bisect_right
from datetime import datetime
from pathlib import Path
from typing import Any

MAX_ARTIFACT_BYTES = 16 * 1024 * 1024
MAX_PAYLOAD_BYTES = 1024 * 1024
MAX_CHUNKS = 4096
MAX_SUMMARY_BYTES = 256 * 1024
MAX_PREVIEW_BYTES = 16 * 1024
READ_SCHEMA = "embedded-agent-toolkit.rtt-read.v1"
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
    require(isinstance(value, str) and len(value) <= 40, "invalid timestamp length")
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        require(
            stamp.utcoffset() is not None and stamp.utcoffset().total_seconds() == 0,
            "timestamp must be UTC",
        )
    except ValueError as error:
        raise EvidenceError(f"invalid timestamp: {value}") from error


def _check_capture(value: Any, base: Path, *, retain: bool = False) -> dict[str, Any]:
    """Validate one artifact read; retain bytes privately only for offline views."""
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
        retained = bytearray()
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
            if retain:
                retained.extend(decoded)
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
        if retain:
            result["_payload"] = bytes(retained)
            result["_chunks"] = [
                {
                    key: chunk[key]
                    for key in (
                        "sequence",
                        "cursor",
                        "next_cursor",
                        "timestamp",
                        "elapsed_ms",
                    )
                }
                for chunk in chunks
            ]
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


def check_capture(value: Any, base: Path) -> dict[str, Any]:
    """Return bounded integrity metadata without native payload or file writes."""
    return _check_capture(value, base)


def _read_summary(path: Path) -> tuple[dict, dict]:
    resolved = path.resolve(strict=True)
    require(resolved.is_file(), "summary must be a regular file")
    with resolved.open("rb") as handle:
        raw = handle.read(MAX_SUMMARY_BYTES + 1)
    require(len(raw) <= MAX_SUMMARY_BYTES, "RTT summary too large")
    value = obj(
        json.loads(
            raw.decode("utf-8"), object_pairs_hook=_unique, parse_constant=_nonfinite
        ),
        "summary",
    )
    return value, {
        "path": str(resolved),
        "size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def _preview(
    payload: bytes, chunks: list[dict], cursor: int, max_lines: int, max_line_bytes: int
) -> dict:
    integer(cursor, "cursor", 0, len(payload))
    integer(max_lines, "max_lines", 1, 100)
    integer(max_line_bytes, "max_line_bytes", 1, 4096)
    starts = [chunk["cursor"] for chunk in chunks]
    lines = []
    budget = MAX_PREVIEW_BYTES
    start = cursor
    while start < len(payload) and len(lines) < max_lines and budget > 0:
        newline = payload.find(b"\n", start)
        end = newline + 1 if newline >= 0 else len(payload)
        content_end = end - 1 if newline >= 0 else end
        crlf = newline >= 0 and content_end > start and payload[content_end - 1] == 13
        if crlf:
            content_end -= 1
        content = payload[start:content_end]
        prefix = content[: min(max_line_bytes, budget)]
        budget -= len(prefix)
        valid_utf8 = True
        text = None
        try:
            content.decode("utf-8", errors="strict")
            # The bounded prefix can end inside a valid multi-byte character.
            text = codecs.getincrementaldecoder("utf-8")().decode(prefix, final=False)
        except UnicodeDecodeError:
            valid_utf8 = False
        first = chunks[bisect_right(starts, start) - 1]
        last = chunks[bisect_right(starts, end - 1) - 1]
        line = {
            "cursor": start,
            "next_cursor": end,
            "content_bytes": len(content),
            "complete": newline >= 0,
            "terminator": "crlf" if crlf else "lf" if newline >= 0 else None,
            "initial_fragment": start > 0 and payload[start - 1] != 10,
            "utf8_valid": valid_utf8,
            "text": text,
            "preview_bytes": len(text.encode("utf-8")) if valid_utf8 else len(prefix),
            "truncated": len(content)
            > (len(text.encode("utf-8")) if valid_utf8 else len(prefix)),
            "first_chunk": first,
            "last_chunk": last,
        }
        if not valid_utf8:
            line["data_hex"] = prefix.hex()
        lines.append(line)
        start = end
    return {
        "lines": lines,
        "cursor": cursor,
        "next_cursor": start,
        "has_more": start < len(payload),
        "max_lines": max_lines,
        "max_line_bytes": max_line_bytes,
        "preview_byte_budget": MAX_PREVIEW_BYTES,
        "timestamps_are_chunk_observations": True,
    }


def read_report(
    summary: Path,
    operation: str = "inspect",
    *,
    cursor: int = 0,
    max_lines: int = 40,
    max_line_bytes: int = 1024,
    output: Path | None = None,
) -> dict[str, Any]:
    """Inspect, preview or explicitly export one fully verified saved capture."""
    report: dict[str, Any] = {
        "schema_version": READ_SCHEMA,
        "operation": operation,
        "ok": False,
        "scope": "host_only_rtt_evidence",
        "hardware_access": False,
        "executables_started": False,
        "source_execution_not_performed": True,
        "runtime_firmware_identity_verified": False,
        "errors": [],
    }
    try:
        require(operation in {"inspect", "preview", "extract"}, "unknown operation")
        value, source = _read_summary(summary)
        report["summary"] = source
        result = _check_capture(value, Path(source["path"]).parent, retain=True)
        require(result["ok"], result.get("error", "invalid RTT capture"))
        payload = result.pop("_payload")
        chunks = result.pop("_chunks")
        report["integrity"] = result
        data = value["data"]
        report["capture"] = {
            "capture_id": data["capture_id"],
            "backend": data["plan"]["backend"],
            "probe_id": data["plan"]["probe_id"],
            "target": data["plan"]["target"],
            "selection": data["plan"]["selection"],
            "stop_reason": data["stop_reason"],
            "channel_stopped": data["channel_stopped"],
            "disconnected": data["disconnected"],
        }
        if operation == "preview":
            report["preview"] = _preview(
                payload, chunks, cursor, max_lines, max_line_bytes
            )
        elif operation == "extract":
            require(output is not None, "extract requires an explicit output path")
            destination = output.resolve()
            require(
                destination not in {Path(source["path"]), Path(result["path"])},
                "output must not replace native evidence",
            )
            with destination.open("xb") as handle:
                handle.write(payload)
                handle.flush()
            report["output"] = {
                "path": str(destination),
                "size": len(payload),
                "sha256": result["payload_sha256"],
                "encoding": "binary",
                "derived_from_verified_capture": True,
            }
        report["ok"] = True
    except (
        EvidenceError,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        RecursionError,
    ) as error:
        report["errors"].append(str(error) or type(error).__name__)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect saved RTT evidence without hardware access."
    )
    commands = parser.add_subparsers(dest="operation", required=True)
    for name in ("inspect", "preview", "extract"):
        command = commands.add_parser(name)
        command.add_argument(
            "summary", type=Path, help="unchanged native capture summary JSON"
        )
        command.add_argument("--json", action="store_true")
        if name == "preview":
            command.add_argument("--cursor", type=int, default=0)
            command.add_argument("--max-lines", type=int, default=40)
            command.add_argument("--max-line-bytes", type=int, default=1024)
        if name == "extract":
            command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = read_report(
        args.summary,
        args.operation,
        cursor=getattr(args, "cursor", 0),
        max_lines=getattr(args, "max_lines", 40),
        max_line_bytes=getattr(args, "max_line_bytes", 1024),
        output=getattr(args, "output", None),
    )
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    elif not report["ok"]:
        print("RTT evidence invalid: " + "; ".join(report["errors"]), file=sys.stderr)
    else:
        integrity = report["integrity"]
        print(
            f"RTT evidence verified: {integrity['bytes_captured']} bytes / {integrity['chunk_count']} chunks"
        )
        if args.operation == "preview":
            for line in report["preview"]["lines"]:
                # JSON string escaping keeps untrusted terminal control bytes inert.
                text = json.dumps(
                    line.get("text") if line["utf8_valid"] else line["data_hex"],
                    ensure_ascii=True,
                )
                flags = (" truncated" if line["truncated"] else "") + (
                    " incomplete" if not line["complete"] else ""
                )
                print(f"[{line['cursor']}:{line['next_cursor']}){flags} {text}")
            print(
                f"Next cursor: {report['preview']['next_cursor']}; more: {report['preview']['has_more']}"
            )
        elif args.operation == "extract":
            print(
                f"Payload: {report['output']['path']}\nSHA-256: {report['output']['sha256']}"
            )
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
