from __future__ import annotations

import copy
import json
import tempfile
import unittest
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

    def save_spec(self, value: dict) -> None:
        self.write_json(self.spec_path, value)

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
        for name in ("test-spec.schema.json", "test-contract.schema.json"):
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
        example = json.loads(
            (ROOT / "docs" / "examples" / "esp32s3-test-spec.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(test_contract.validate_spec(example)["ok"])


if __name__ == "__main__":
    unittest.main()
