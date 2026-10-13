from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import test_test_contract as fixtures

from scripts import rtt_evidence

ROOT = Path(__file__).resolve().parents[1]


class RttReaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.case = fixtures.TestContractTests()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.root = self.case.root

    def prepare(self, payload: bytes = b"READY\n") -> Path:
        chunks = [
            payload[index : index + 4096] for index in range(0, len(payload), 4096)
        ]
        return self.prepare_chunks(chunks)

    def prepare_chunks(self, chunks: list[bytes]) -> Path:
        contract, self.capture, self.records = self.case.prepare_rtt(chunks)
        self.capture["data"]["plan"]["limits"]["maximum_bytes"] = (
            rtt_evidence.MAX_PAYLOAD_BYTES
        )
        self.summary = Path(contract["stages"][1]["evidence_output"])
        self.artifact = Path(self.capture["data"]["evidence"]["path"])
        self.save()
        return self.summary

    def save(self) -> None:
        self.artifact.write_bytes(
            b"".join((json.dumps(row) + "\n").encode() for row in self.records)
        )
        self.capture["data"]["evidence"].update(
            size=self.artifact.stat().st_size,
            sha256=hashlib.sha256(self.artifact.read_bytes()).hexdigest(),
        )
        self.case.write_json(self.summary, self.capture)

    def test_utf8_crlf_split_across_chunks_and_partial_tail(self) -> None:
        summary = self.prepare_chunks([b"READY \xe4", b"\xb8", b"\xad\r", b"\n\nTAIL"])
        report = rtt_evidence.read_report(summary, "preview")
        self.assertTrue(report["ok"], report["errors"])
        lines = report["preview"]["lines"]
        self.assertEqual([line["text"] for line in lines], ["READY 中", "", "TAIL"])
        self.assertEqual([line["terminator"] for line in lines], ["crlf", "lf", None])
        self.assertEqual(
            [(line["cursor"], line["next_cursor"]) for line in lines],
            [(0, 11), (11, 12), (12, 16)],
        )
        self.assertFalse(lines[-1]["complete"])
        self.assertEqual(lines[0]["first_chunk"]["sequence"], 0)
        self.assertEqual(lines[0]["last_chunk"]["sequence"], 3)
        self.assertTrue(report["preview"]["timestamps_are_chunk_observations"])

    def test_paging_uses_capture_byte_offsets_and_marks_midline_start(self) -> None:
        summary = self.prepare(b"one\ntwo\nlast")
        first = rtt_evidence.read_report(summary, "preview", max_lines=1)["preview"]
        self.assertEqual(first["next_cursor"], 4)
        self.assertTrue(first["has_more"])
        second = rtt_evidence.read_report(summary, "preview", cursor=4, max_lines=1)[
            "preview"
        ]
        self.assertEqual(second["lines"][0]["text"], "two")
        self.assertFalse(second["lines"][0]["initial_fragment"])
        fragment = rtt_evidence.read_report(summary, "preview", cursor=1)["preview"][
            "lines"
        ][0]
        self.assertTrue(fragment["initial_fragment"])
        self.assertEqual(fragment["text"], "ne")

    def test_binary_export_is_lossless_without_replacement_decoding(self) -> None:
        payload = b"\x00\xff\xe4\n"
        summary = self.prepare(payload)
        preview = rtt_evidence.read_report(summary, "preview")["preview"]["lines"][0]
        self.assertFalse(preview["utf8_valid"])
        self.assertIsNone(preview["text"])
        self.assertEqual(preview["data_hex"], "00ffe4")
        output = self.root / "payload.bin"
        report = rtt_evidence.read_report(summary, "extract", output=output)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(output.read_bytes(), payload)
        self.assertEqual(
            report["output"]["sha256"], hashlib.sha256(payload).hexdigest()
        )

    def test_empty_capture_preview_and_export(self) -> None:
        summary = self.prepare(b"")
        preview = rtt_evidence.read_report(summary, "preview")
        self.assertTrue(preview["ok"])
        self.assertEqual(preview["preview"]["lines"], [])
        self.assertFalse(preview["preview"]["has_more"])
        output = self.root / "empty.bin"
        self.assertTrue(
            rtt_evidence.read_report(summary, "extract", output=output)["ok"]
        )
        self.assertEqual(output.read_bytes(), b"")

    def test_truncated_utf8_preview_does_not_split_a_character(self) -> None:
        summary = self.prepare("中中A\nnext\n".encode())
        preview = rtt_evidence.read_report(
            summary, "preview", max_lines=1, max_line_bytes=4
        )["preview"]
        line = preview["lines"][0]
        self.assertTrue(line["truncated"])
        self.assertTrue(line["complete"])
        self.assertTrue(line["utf8_valid"])
        self.assertEqual(line["text"], "中")
        self.assertEqual(line["preview_bytes"], 3)
        self.assertEqual(preview["next_cursor"], 8)
        self.assertTrue(preview["has_more"])

    def test_invalid_utf8_beyond_prefix_is_not_called_valid(self) -> None:
        summary = self.prepare(b"good-prefix\xff\n")
        line = rtt_evidence.read_report(summary, "preview", max_line_bytes=4)[
            "preview"
        ]["lines"][0]
        self.assertFalse(line["utf8_valid"])
        self.assertEqual(line["data_hex"], b"good".hex())
        self.assertTrue(line["truncated"])

    def test_preview_total_byte_and_line_bounds(self) -> None:
        summary = self.prepare((b"a" * 4096 + b"\n") * 6)
        preview = rtt_evidence.read_report(
            summary, "preview", max_lines=100, max_line_bytes=4096
        )["preview"]
        self.assertEqual(len(preview["lines"]), 4)
        self.assertEqual(sum(line["preview_bytes"] for line in preview["lines"]), 16384)
        self.assertTrue(preview["has_more"])
        cases = [
            {"cursor": -1},
            {"cursor": 24583},
            {"max_lines": 0},
            {"max_lines": 101},
            {"max_line_bytes": 0},
            {"max_line_bytes": 4097},
        ]
        for options in cases:
            with self.subTest(options=options):
                result = rtt_evidence.read_report(summary, "preview", **options)
                self.assertFalse(result["ok"])
                self.assertNotIn("preview", result)

    def test_existing_and_native_output_paths_are_not_overwritten(self) -> None:
        summary = self.prepare()
        existing = self.root / "existing.bin"
        existing.write_bytes(b"keep")
        for path in (existing, self.summary, self.artifact):
            before = path.read_bytes()
            result = rtt_evidence.read_report(summary, "extract", output=path)
            self.assertFalse(result["ok"])
            self.assertEqual(path.read_bytes(), before)
            self.assertNotIn("output", result)

    def test_corrupt_artifact_rejected_before_output_or_preview(self) -> None:
        summary = self.prepare()
        self.artifact.write_bytes(
            self.artifact.read_bytes().replace(b"5245414459", b"4641494c45")
        )
        output = self.root / "must-not-exist.bin"
        for mode in ("inspect", "preview", "extract"):
            result = rtt_evidence.read_report(summary, mode, output=output)
            self.assertFalse(result["ok"])
            self.assertNotIn("integrity", result)
            self.assertNotIn("preview", result)
        self.assertFalse(output.exists())

    def test_failed_cleanup_cannot_be_exported(self) -> None:
        summary = self.prepare()
        self.capture["data"]["disconnected"] = False
        self.save()
        output = self.root / "bad-cleanup.bin"
        self.assertFalse(
            rtt_evidence.read_report(summary, "extract", output=output)["ok"]
        )
        self.assertFalse(output.exists())

    def test_summary_rejects_duplicate_nonfinite_and_oversized_input(self) -> None:
        summary = self.prepare()
        original = summary.read_bytes()
        for raw in (
            original.replace(b'"ok": true', b'"ok": true, "ok": true'),
            original.replace(b'"elapsed_ms": 1000', b'"elapsed_ms": NaN'),
            b" " * (rtt_evidence.MAX_SUMMARY_BYTES + 1),
        ):
            with self.subTest(size=len(raw)):
                summary.write_bytes(raw)
                self.assertFalse(rtt_evidence.read_report(summary)["ok"])

    def test_relative_artifact_path_and_input_hashes_preserved(self) -> None:
        summary = self.prepare()
        self.capture["data"]["evidence"]["path"] = os.path.relpath(
            self.artifact, summary.parent
        )
        self.case.write_json(summary, self.capture)
        before = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (summary, self.artifact)
        }
        with patch("subprocess.run", side_effect=AssertionError("unexpected process")):
            result = rtt_evidence.read_report(summary, "preview")
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["summary"]["sha256"], before[summary])
        self.assertEqual(result["integrity"]["sha256"], before[self.artifact])
        self.assertFalse(result["hardware_access"])
        self.assertFalse(result["executables_started"])
        self.assertFalse(result["runtime_firmware_identity_verified"])
        self.assertTrue(result["source_execution_not_performed"])
        for path, expected in before.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected)
        self.assertFalse(
            any(
                key.startswith("_")
                for key in rtt_evidence.check_capture(self.capture, summary.parent)
            )
        )

    def test_export_uses_verified_snapshot_not_a_second_artifact_read(self) -> None:
        summary = self.prepare(b"original\n")
        snapshot = self.artifact.read_bytes()
        resolved_artifact = self.artifact.resolve(strict=True)
        original_open = Path.open
        reads = []

        def open_file(path, mode="r", *args, **kwargs):
            if path == resolved_artifact and mode == "rb":
                reads.append(path)
                with original_open(path, "wb") as handle:
                    handle.write(b"changed after snapshot")
                return io.BytesIO(snapshot)
            return original_open(path, mode, *args, **kwargs)

        output = self.root / "snapshot.bin"
        with patch.object(Path, "open", open_file):
            result = rtt_evidence.read_report(summary, "extract", output=output)
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(len(reads), 1)
        self.assertEqual(self.artifact.read_bytes(), b"changed after snapshot")
        self.assertEqual(output.read_bytes(), b"original\n")
        self.assertEqual(
            result["integrity"]["sha256"], hashlib.sha256(snapshot).hexdigest()
        )

    def test_oversized_valid_iso_timestamp_cannot_amplify_a_preview(self) -> None:
        summary = self.prepare(b"\n" * 100)
        stamp = "2026-10-12T00:00:00." + "1" * 10000 + "Z"
        for record in self.records:
            record["timestamp"] = stamp
        self.capture["data"].update(started_at=stamp, finished_at=stamp)
        self.save()
        result = rtt_evidence.read_report(summary, "preview", max_lines=100)
        self.assertFalse(result["ok"])
        self.assertNotIn("preview", result)
        self.assertIn("timestamp length", result["errors"][0])

    def test_cli_json_exit_codes_and_terminal_control_escaping(self) -> None:
        summary = self.prepare(b"\x1b[31mred\n")
        cli = ROOT / "scripts/rtt_evidence.py"
        environment = {**os.environ, "PATH": "", "PYTHONDONTWRITEBYTECODE": "1"}
        result = subprocess.run(
            [sys.executable, str(cli), "preview", str(summary), "--json"],
            capture_output=True,
            check=False,
            timeout=15,
            env=environment,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout)["preview"]["lines"][0]["text"], "\x1b[31mred"
        )
        text = subprocess.run(
            [sys.executable, str(cli), "preview", str(summary)],
            capture_output=True,
            check=False,
            timeout=15,
            env=environment,
        )
        self.assertEqual(text.returncode, 0)
        self.assertNotIn(b"\x1b", text.stdout)
        self.assertIn(b"\\u001b", text.stdout)
        self.artifact.write_bytes(b"corrupt\n")
        failure = subprocess.run(
            [sys.executable, str(cli), "inspect", str(summary), "--json"],
            capture_output=True,
            check=False,
            timeout=15,
            env=environment,
        )
        self.assertEqual(failure.returncode, 2)
        self.assertFalse(json.loads(failure.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()
