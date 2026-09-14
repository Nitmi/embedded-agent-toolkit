from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from scripts import test_contract

ROOT = Path(__file__).resolve().parents[1]


class TestContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.selection_path = self.root / "selection.json"
        self.firmware = self.root / "application.hex"
        self.firmware.write_bytes(b":00000001FF\n")
        self.selection = {
            "schema_version": test_contract.SELECTION_SCHEMA,
            "ok": True,
            "status": "selected",
            "board_id": "nrf52840-dk",
            "required_transports": ["debug", "serial"],
            "bindings": [
                {
                    "transport": "debug",
                    "selector_id": "onboard-jlink",
                    "observation_id": "probe-list-jlink",
                    "selector_identity": {"probe_selector": "1366:1061:001050275757"},
                    "observed_identity": {
                        "probe_selector": "1366:1061:001050275757",
                        "serial_number": "001050275757",
                    },
                    "source": {
                        "path": "evidence/probes-list.json",
                        "sha256": "b" * 64,
                        "point_in_time": True,
                    },
                },
                {
                    "transport": "serial",
                    "selector_id": "onboard-uart",
                    "observation_id": "baud-list-com11",
                    "selector_identity": {
                        "usb_vid": "1366",
                        "usb_pid": "1061",
                        "usb_serial": "001050275757",
                    },
                    "observed_identity": {
                        "port": "COM11",
                        "usb_vid": "1366",
                        "usb_pid": "1061",
                        "usb_serial": "001050275757",
                        "pnp_interface": "MI_00",
                    },
                    "source": {
                        "path": "evidence/baud-list.json",
                        "sha256": "a" * 64,
                        "point_in_time": True,
                    },
                },
            ],
            "inputs": {
                "registry": {"path": "registry.json", "sha256": "c" * 64},
                "observations": {
                    "path": "observations.json",
                    "sha256": "d" * 64,
                },
            },
            "authorization": {"granted": False, "allowed_operations": []},
            "hardware_access": False,
            "executables_started": False,
        }
        self.write_json(self.selection_path, self.selection)
        self.spec_path = self.root / "test-spec.json"
        self.spec = self.flash_spec()
        self.write_json(self.spec_path, self.spec)

    @staticmethod
    def write_json(path: Path, value: object) -> None:
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    def flash_spec(self) -> dict:
        return {
            "schema_version": test_contract.SPEC_SCHEMA,
            "name": "nrf52840-dk-flash-smoke",
            "selection": self.selection_path.name,
            "debug_target": "nRF52840_xxAA",
            "resources": [
                {
                    "id": "application",
                    "kind": "firmware",
                    "path": self.firmware.name,
                    "sha256": test_contract.sha256(self.firmware),
                }
            ],
            "stages": [
                {
                    "id": "flash-plan",
                    "operation": "embedded-debugger.flash-plan",
                    "inputs": ["application"],
                    "requires": [],
                    "declared_effects": [
                        "hardware_discovery",
                        "host_process_start",
                    ],
                    "timeout_seconds": 30,
                    "max_retries": 0,
                    "evidence_output": "evidence/flash-plan.json",
                },
                {
                    "id": "flash-execute",
                    "operation": "embedded-debugger.flash-execute",
                    "inputs": ["application"],
                    "requires": ["flash-plan"],
                    "declared_effects": [
                        "debug_attach",
                        "flash_erase",
                        "flash_write",
                        "hardware_discovery",
                        "host_process_start",
                        "memory_read",
                        "register_read",
                        "target_halt",
                        "target_reset",
                        "target_resume",
                        "target_state_may_change",
                    ],
                    "timeout_seconds": 120,
                    "max_retries": 0,
                    "evidence_output": "evidence/flash-execute.json",
                },
            ],
            "assertions": [
                {
                    "id": "flash-ok",
                    "stage": "flash-execute",
                    "json_pointer": "/ok",
                    "operator": "equals",
                    "expected": True,
                }
            ],
            "cleanup": [
                {
                    "resource": "debug",
                    "required_state": "disconnected",
                    "timeout_seconds": 5,
                },
                {
                    "resource": "target",
                    "required_state": "running",
                    "timeout_seconds": 5,
                },
            ],
        }

    def discovery_spec(self) -> dict:
        selection = copy.deepcopy(self.selection)
        selection["required_transports"] = ["ble", "debug", "serial"]
        selection["bindings"] = [
            {
                "transport": "ble",
                "selector_id": "advertised-service",
                "observation_id": "ble-scan-device",
                "selector_identity": {
                    "service_uuid": "12345678-1234-5678-1234-56789abcdef0"
                },
                "observed_identity": {
                    "identifier": "id:AA:BB:CC:DD:EE:FF",
                    "service_uuid": "12345678-1234-5678-1234-56789abcdef0",
                },
                "source": {
                    "path": "evidence/ble-scan.json",
                    "sha256": "e" * 64,
                    "point_in_time": True,
                },
            },
            *selection["bindings"],
        ]
        self.write_json(self.selection_path, selection)
        return {
            "schema_version": test_contract.SPEC_SCHEMA,
            "name": "nrf52840-dk-discovery",
            "selection": self.selection_path.name,
            "debug_target": None,
            "resources": [],
            "stages": [
                {
                    "id": "serial-list",
                    "operation": "baud.list",
                    "inputs": [],
                    "requires": [],
                    "declared_effects": ["hardware_discovery", "host_process_start"],
                    "timeout_seconds": 10,
                    "max_retries": 0,
                    "evidence_output": "evidence/baud-list.json",
                },
                {
                    "id": "ble-doctor",
                    "operation": "blea.doctor",
                    "inputs": [],
                    "requires": [],
                    "declared_effects": ["ble_scan", "host_process_start"],
                    "timeout_seconds": 10,
                    "max_retries": 0,
                    "evidence_output": "evidence/ble-doctor.json",
                },
                {
                    "id": "probe-list",
                    "operation": "embedded-debugger.probes-list",
                    "inputs": [],
                    "requires": [],
                    "declared_effects": ["hardware_discovery", "host_process_start"],
                    "timeout_seconds": 10,
                    "max_retries": 0,
                    "evidence_output": "evidence/probes-list.json",
                },
            ],
            "assertions": [
                {
                    "id": "serial-number",
                    "stage": "serial-list",
                    "json_pointer": "/ports/0/serial_number",
                    "operator": "equals",
                    "expected": "001050275757",
                },
                {
                    "id": "adapter-ready",
                    "stage": "ble-doctor",
                    "json_pointer": "/adapter_available",
                    "operator": "equals",
                    "expected": True,
                },
                {
                    "id": "probe-selector",
                    "stage": "probe-list",
                    "json_pointer": "/data/probes/0/id",
                    "operator": "equals",
                    "expected": "1366:1061:001050275757",
                },
            ],
            "cleanup": [],
        }

    def save_spec(self, value: dict) -> None:
        self.write_json(self.spec_path, value)

    def prepare_evaluation(
        self,
        *,
        flash_ok: bool = True,
        debug_state: str = "disconnected",
        target_state: str = "running",
    ) -> tuple[Path, Path, Path]:
        contract_path = self.root / "contract.json"
        test_contract.compile_report(self.spec_path, contract_path)
        contract = test_contract.load_json(contract_path, "contract")
        evidence_dir = self.root / "evidence"
        evidence_dir.mkdir()
        plan = evidence_dir / "flash-plan.json"
        execute = evidence_dir / "flash-execute.json"
        self.write_json(plan, {"ok": True, "ranges": ["0x00000000-0x00000fff"]})
        self.write_json(
            execute,
            {
                "ok": flash_ok,
                "cleanup": {"debug": debug_state, "target": target_state},
            },
        )
        run_path = self.root / "run.json"
        run = {
            "schema_version": test_contract.RUN_SCHEMA,
            "contract_sha256": test_contract.sha256(contract_path),
            "stage_evidence": [
                {
                    "stage": "flash-plan",
                    "path": contract["stages"][0]["evidence_output"],
                    "sha256": test_contract.sha256(plan),
                },
                {
                    "stage": "flash-execute",
                    "path": contract["stages"][1]["evidence_output"],
                    "sha256": test_contract.sha256(execute),
                },
            ],
            "cleanup_evidence": [
                {
                    "resource": "debug",
                    "path": str(execute),
                    "sha256": test_contract.sha256(execute),
                    "json_pointer": "/cleanup/debug",
                },
                {
                    "resource": "target",
                    "path": str(execute),
                    "sha256": test_contract.sha256(execute),
                    "json_pointer": "/cleanup/target",
                },
            ],
            "authorization": {
                "granted": False,
                "allowed_operations": [],
                "manifest_is_authorization": False,
            },
        }
        self.write_json(run_path, run)
        return contract_path, run_path, execute

    def test_compile_binds_selection_firmware_effects_and_no_authorization(
        self,
    ) -> None:
        contract = test_contract.compile_contract(self.spec_path)

        self.assertEqual(contract["board"]["id"], "nrf52840-dk")
        self.assertEqual(contract["debug_target"], "nRF52840_xxAA")
        self.assertEqual(contract["resources"][0]["path"], str(self.firmware.resolve()))
        self.assertEqual(contract["stages"][1]["risk"], "persistent-write")
        self.assertEqual(
            [binding["component"] for binding in contract["bindings"]],
            ["embedded-debugger", "baud"],
        )
        self.assertEqual(
            contract["authorization"],
            {
                "granted": False,
                "allowed_operations": [],
                "contract_is_authorization": False,
                "native_component_gates_preserved": True,
            },
        )
        self.assertFalse(contract["execution_supported"])
        self.assertFalse(contract["hardware_access"])
        self.assertFalse(contract["executables_started"])
        forbidden = {"command", "argv", "confirm", "confirm_digest"}

        def keys(value: object) -> set[str]:
            if isinstance(value, dict):
                return set(value) | set().union(
                    *(keys(item) for item in value.values())
                )
            if isinstance(value, list):
                return set().union(*(keys(item) for item in value))
            return set()

        self.assertFalse(keys(contract) & forbidden)

    def test_compile_report_refuses_to_overwrite(self) -> None:
        output = self.root / "contract.json"
        first = test_contract.compile_report(self.spec_path, output)

        self.assertTrue(first["ok"])
        with self.assertRaisesRegex(test_contract.ContractError, "already exists"):
            test_contract.compile_report(self.spec_path, output)

    def test_discovery_operations_compile_as_observation_only(self) -> None:
        self.save_spec(self.discovery_spec())

        contract = test_contract.compile_contract(self.spec_path)

        self.assertEqual(
            [stage["component"] for stage in contract["stages"]],
            ["baud", "blea", "embedded-debugger"],
        )
        self.assertEqual(
            [stage["risk"] for stage in contract["stages"]],
            ["hardware-observation"] * 3,
        )
        forbidden = {
            "serial_open",
            "ble_connect",
            "debug_attach",
            "target_state_may_change",
        }
        self.assertFalse(
            forbidden
            & {
                effect
                for stage in contract["stages"]
                for effect in stage["declared_effects"]
            }
        )

    def test_ble_doctor_declares_its_short_scan(self) -> None:
        spec = self.discovery_spec()
        spec["stages"][1]["declared_effects"] = ["host_process_start"]

        report = test_contract.validate_spec(spec)

        self.assertFalse(report["ok"])
        self.assertIn("ble_scan", "\n".join(report["errors"]))

    def test_discovery_operations_reject_active_effects(self) -> None:
        for index, effect in (
            (0, "serial_open"),
            (1, "ble_connect"),
            (2, "debug_attach"),
        ):
            with self.subTest(effect=effect):
                spec = self.discovery_spec()
                spec["stages"][index]["declared_effects"].append(effect)
                spec["stages"][index]["declared_effects"].sort()

                report = test_contract.validate_spec(spec)

                self.assertFalse(report["ok"])
                self.assertIn(effect, "\n".join(report["errors"]))

    def test_discovery_requires_each_selected_transport(self) -> None:
        spec = self.discovery_spec()
        selection = test_contract.load_json(self.selection_path, "selection")
        selection["required_transports"] = ["debug", "serial"]
        selection["bindings"] = selection["bindings"][1:]
        self.write_json(self.selection_path, selection)
        self.save_spec(spec)

        with self.assertRaisesRegex(test_contract.ContractError, "required transports"):
            test_contract.compile_contract(self.spec_path)

    def test_discovery_native_evidence_evaluates_without_translation(self) -> None:
        self.save_spec(self.discovery_spec())
        contract_path = self.root / "discovery-contract.json"
        test_contract.compile_report(self.spec_path, contract_path)
        contract = test_contract.load_json(contract_path, "contract")
        evidence_dir = self.root / "evidence"
        evidence_dir.mkdir()
        evidence = [
            {
                "ok": True,
                "ports": [
                    {
                        "device": "COM11",
                        "vid": 0x1366,
                        "pid": 0x1061,
                        "serial_number": "001050275757",
                    }
                ],
            },
            {
                "ok": True,
                "operation": "doctor",
                "backend": "BleakBackend",
                "adapter_available": True,
                "devices_observed": 1,
            },
            {
                "schema_version": "1.0",
                "ok": True,
                "operation": "probes.list",
                "data": {
                    "backend": "probe-rs",
                    "probes": [
                        {
                            "id": "1366:1061:001050275757",
                            "vendor_id": 0x1366,
                            "product_id": 0x1061,
                            "serial": "001050275757",
                            "accessible": True,
                        }
                    ],
                },
            },
        ]
        entries = []
        for stage, payload in zip(contract["stages"], evidence, strict=True):
            path = Path(stage["evidence_output"])
            self.write_json(path, payload)
            entries.append(
                {
                    "stage": stage["id"],
                    "path": str(path),
                    "sha256": test_contract.sha256(path),
                }
            )
        run_path = self.root / "discovery-run.json"
        self.write_json(
            run_path,
            {
                "schema_version": test_contract.RUN_SCHEMA,
                "contract_sha256": test_contract.sha256(contract_path),
                "stage_evidence": entries,
                "cleanup_evidence": [],
                "authorization": {
                    "granted": False,
                    "allowed_operations": [],
                    "manifest_is_authorization": False,
                },
            },
        )

        report = test_contract.evaluate_contract(contract_path, run_path)

        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["summary"]["stage_evidence_current"], 3)
        self.assertEqual(report["summary"]["assertions_passed"], 3)
        self.assertEqual(report["summary"]["cleanup_passed"], 0)

    def test_evaluate_passes_hash_bound_evidence_and_cleanup(self) -> None:
        contract, run, _ = self.prepare_evaluation()
        output = self.root / "report.json"

        report = test_contract.evaluate_report(contract, run, output)

        self.assertTrue(report["ok"])
        self.assertTrue(report["complete"])
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["scope"], "host_only_evidence_evaluation")
        self.assertEqual(report["summary"]["assertions_passed"], 1)
        self.assertEqual(report["summary"]["cleanup_passed"], 2)
        self.assertFalse(report["authorization_granted"])
        self.assertFalse(report["execution_supported"])
        self.assertTrue(report["source_execution_not_performed"])
        self.assertFalse(report["hardware_access"])
        self.assertFalse(report["executables_started"])
        self.assertEqual(test_contract.load_json(output, "report"), report)

    def test_evaluate_reports_failed_assertion_and_cleanup(self) -> None:
        contract, run, _ = self.prepare_evaluation(
            flash_ok=False, target_state="halted"
        )
        output = self.root / "failed-report.json"

        report = test_contract.evaluate_report(contract, run, output)

        self.assertFalse(report["ok"])
        self.assertTrue(report["complete"])
        self.assertEqual(report["status"], "failed")
        self.assertFalse(report["assertions"][0]["passed"])
        self.assertFalse(report["cleanup"][1]["passed"])
        self.assertIn("assertion flash-ok did not pass", report["errors"])
        self.assertIn("cleanup state for target did not pass", report["errors"])
        self.assertEqual(test_contract.load_json(output, "report"), report)

    def test_evaluate_marks_drifted_evidence_incomplete(self) -> None:
        contract, run, execute = self.prepare_evaluation()
        execute.write_text('{"ok": false}\n', encoding="utf-8")

        report = test_contract.evaluate_contract(contract, run)

        self.assertFalse(report["ok"])
        self.assertFalse(report["complete"])
        execute_stage = next(
            stage for stage in report["stages"] if stage["id"] == "flash-execute"
        )
        self.assertFalse(execute_stage["evidence"]["current"])
        self.assertIn("SHA-256 differs", execute_stage["evidence"]["error"])
        self.assertFalse(report["assertions"][0]["evaluated"])

    def test_evaluate_rejects_stage_evidence_path_not_bound_by_contract(self) -> None:
        contract, run_path, _ = self.prepare_evaluation()
        run = test_contract.load_json(run_path, "run")
        alternate = self.root / "alternate.json"
        self.write_json(alternate, {"ok": True})
        run["stage_evidence"][1]["path"] = str(alternate)
        run["stage_evidence"][1]["sha256"] = test_contract.sha256(alternate)
        self.write_json(self.root / "alternate-run.json", run)

        with self.assertRaisesRegex(
            test_contract.ContractError, "differs from contract"
        ):
            test_contract.evaluate_contract(contract, self.root / "alternate-run.json")

    def test_evaluate_report_refuses_to_overwrite(self) -> None:
        contract, run, _ = self.prepare_evaluation()
        output = self.root / "report.json"
        test_contract.evaluate_report(contract, run, output)

        with self.assertRaisesRegex(test_contract.ContractError, "already exists"):
            test_contract.evaluate_report(contract, run, output)

    def test_evaluate_cli_writes_machine_readable_report(self) -> None:
        contract, run, _ = self.prepare_evaluation()
        output = self.root / "report.json"
        stdout = io.StringIO()

        with redirect_stdout(stdout):
            exit_code = test_contract.main(
                [
                    "evaluate",
                    str(contract),
                    "--run",
                    str(run),
                    "--output",
                    str(output),
                    "--json",
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertTrue(json.loads(stdout.getvalue())["ok"])
        self.assertTrue(test_contract.load_json(output, "report")["ok"])

    def test_json_pointer_and_assertion_types_are_strict(self) -> None:
        document = {"a/b": {"~key": [1, True, "ready"]}, "object": {"ok": 1}}

        self.assertEqual(
            test_contract._resolve_pointer(document, "/a~1b/~0key/2"), "ready"
        )
        self.assertFalse(test_contract._json_equal(1, True))
        self.assertTrue(test_contract._assertion_passes([1, 2], "contains", 2)[0])
        self.assertTrue(
            test_contract._assertion_passes(document["object"], "contains", "ok")[0]
        )
        with self.assertRaisesRegex(test_contract.ContractError, "array index"):
            test_contract._resolve_pointer(["value"], "/01")
        self.assertEqual(
            test_contract._actual_summary("x" * 2048),
            {"type": "string", "size": 2048},
        )

    def test_nonfinite_evidence_json_is_rejected(self) -> None:
        evidence = self.root / "evidence.json"
        evidence.write_text('{"value": NaN}\n', encoding="utf-8")

        with self.assertRaisesRegex(test_contract.ContractError, "non-finite"):
            test_contract.load_json_value(evidence, "evidence")

    def test_wrong_firmware_hash_fails_before_output(self) -> None:
        spec = copy.deepcopy(self.spec)
        spec["resources"][0]["sha256"] = "0" * 64
        self.save_spec(spec)

        with self.assertRaisesRegex(test_contract.ContractError, "SHA-256 differs"):
            test_contract.compile_contract(self.spec_path)

    def test_flash_execute_cannot_hide_write_effect(self) -> None:
        spec = copy.deepcopy(self.spec)
        spec["stages"][1]["declared_effects"].remove("flash_write")

        report = test_contract.validate_spec(spec)

        self.assertFalse(report["ok"])
        self.assertIn("flash_write", "\n".join(report["errors"]))

    def test_state_changing_stage_must_not_retry(self) -> None:
        spec = copy.deepcopy(self.spec)
        spec["stages"][1]["max_retries"] = 1

        report = test_contract.validate_spec(spec)

        self.assertFalse(report["ok"])
        self.assertIn("must equal 0", "\n".join(report["errors"]))

    def test_flash_execute_requires_matching_plan_dependency(self) -> None:
        spec = copy.deepcopy(self.spec)
        spec["stages"][1]["requires"] = []

        report = test_contract.validate_spec(spec)

        self.assertFalse(report["ok"])
        self.assertIn(
            "earlier embedded-debugger.flash-plan", "\n".join(report["errors"])
        )

    def test_selection_must_cover_stage_transport(self) -> None:
        selection = copy.deepcopy(self.selection)
        selection["required_transports"] = ["serial"]
        selection["bindings"] = [selection["bindings"][1]]
        self.write_json(self.selection_path, selection)

        with self.assertRaisesRegex(test_contract.ContractError, "required transports"):
            test_contract.compile_contract(self.spec_path)

    def test_authorizing_selection_is_rejected(self) -> None:
        selection = copy.deepcopy(self.selection)
        selection["authorization"]["granted"] = True
        self.write_json(self.selection_path, selection)

        with self.assertRaisesRegex(
            test_contract.ContractError, "granted must equal false"
        ):
            test_contract.compile_contract(self.spec_path)

    def test_unknown_command_field_is_rejected(self) -> None:
        spec = copy.deepcopy(self.spec)
        spec["stages"][0]["command"] = "embedded-debugger flash plan"

        report = test_contract.validate_spec(spec)

        self.assertFalse(report["ok"])
        self.assertIn("command is not allowed", "\n".join(report["errors"]))

    def test_missing_nullable_expected_field_is_rejected(self) -> None:
        spec = copy.deepcopy(self.spec)
        del spec["assertions"][0]["expected"]

        report = test_contract.validate_spec(spec)

        self.assertFalse(report["ok"])
        self.assertIn("expected is required", "\n".join(report["errors"]))

    def test_empty_json_pointer_selects_document_root(self) -> None:
        spec = copy.deepcopy(self.spec)
        spec["assertions"][0]["json_pointer"] = ""

        report = test_contract.validate_spec(spec)

        self.assertTrue(report["ok"], report["errors"])

    def test_inspect_detects_resource_drift(self) -> None:
        output = self.root / "contract.json"
        test_contract.compile_report(self.spec_path, output)
        self.firmware.write_bytes(b"changed")

        report = test_contract.inspect_contract(output)

        self.assertFalse(report["ok"])
        resource = next(
            item for item in report["input_checks"] if item["id"] == "application"
        )
        self.assertFalse(resource["current"])

    def test_runtime_accept_requires_matching_inspect_stage(self) -> None:
        runtime = self.root / "runtime.json"
        runtime.write_text("{}\n", encoding="utf-8")
        spec = {
            "schema_version": test_contract.SPEC_SCHEMA,
            "name": "runtime-smoke",
            "selection": self.selection_path.name,
            "debug_target": "nRF52840_xxAA",
            "resources": [
                {
                    "id": "runtime",
                    "kind": "debugger-runtime-contract",
                    "path": runtime.name,
                    "sha256": test_contract.sha256(runtime),
                }
            ],
            "stages": [
                {
                    "id": "runtime-accept",
                    "operation": "embedded-debugger.runtime-accept",
                    "inputs": ["runtime"],
                    "requires": [],
                    "declared_effects": sorted(
                        test_contract.OPERATION_POLICIES[
                            "embedded-debugger.runtime-accept"
                        ].minimum_effects
                    ),
                    "timeout_seconds": 30,
                    "max_retries": 0,
                    "evidence_output": "evidence/runtime.json",
                }
            ],
            "assertions": [],
            "cleanup": [
                {
                    "resource": "serial",
                    "required_state": "closed",
                    "timeout_seconds": 5,
                },
                {
                    "resource": "debug",
                    "required_state": "disconnected",
                    "timeout_seconds": 5,
                },
                {
                    "resource": "target",
                    "required_state": "running",
                    "timeout_seconds": 5,
                },
            ],
        }

        report = test_contract.validate_spec(spec)

        self.assertFalse(report["ok"])
        self.assertIn(
            "earlier embedded-debugger.runtime-inspect", "\n".join(report["errors"])
        )

    def test_duplicate_json_fields_are_rejected(self) -> None:
        duplicate = self.root / "duplicate.json"
        duplicate.write_text('{"name":"first","name":"second"}\n', encoding="utf-8")

        with self.assertRaisesRegex(
            test_contract.ContractError, "duplicate JSON field"
        ):
            test_contract.load_json(duplicate, "fixture")

    def test_published_schemas_and_example_are_valid_json(self) -> None:
        for name in (
            "test-spec.schema.json",
            "test-contract.schema.json",
            "test-run.schema.json",
            "test-report.schema.json",
        ):
            schema = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
            self.assertEqual(
                schema["$schema"], "https://json-schema.org/draft/2020-12/schema"
            )
        contract_schema = json.loads(
            (ROOT / "schemas" / "test-contract.schema.json").read_text(encoding="utf-8")
        )
        compiled_resource = contract_schema["$defs"]["compiledResource"]
        self.assertNotIn("allOf", compiled_resource)
        self.assertEqual(
            set(compiled_resource["required"]),
            {"id", "kind", "path", "sha256", "size"},
        )
        operations = set(
            json.loads(
                (ROOT / "schemas" / "test-spec.schema.json").read_text(encoding="utf-8")
            )["$defs"]["operation"]["enum"]
        )
        self.assertTrue(
            {
                "baud.list",
                "blea.doctor",
                "embedded-debugger.probes-list",
            }.issubset(operations)
        )
        for name in ("esp32s3-test-spec.json", "esp32s3-discovery-test-spec.json"):
            example = json.loads(
                (ROOT / "docs" / "examples" / name).read_text(encoding="utf-8")
            )
            self.assertTrue(test_contract.validate_spec(example)["ok"])


if __name__ == "__main__":
    unittest.main()
