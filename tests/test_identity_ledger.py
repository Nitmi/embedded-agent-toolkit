from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from scripts import validate_identity_ledger as validator

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "docs" / "examples" / "esp32s3-identity-ledger-2026-09-03.json"


class IdentityLedgerValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.example = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def test_bundled_example_is_valid(self) -> None:
        report = validator.validate_ledger(self.example)

        self.assertTrue(report["ok"], report["errors"])
        self.assertGreaterEqual(report["source_count"], 1)
        self.assertGreaterEqual(report["claim_count"], 1)

    def test_duplicate_source_id_is_rejected(self) -> None:
        ledger = copy.deepcopy(self.example)
        ledger["sources"].append(copy.deepcopy(ledger["sources"][0]))

        report = validator.validate_ledger(ledger)

        self.assertFalse(report["ok"])
        self.assertIn("duplicate source id", "\n".join(report["errors"]))

    def test_invalid_source_hash_is_rejected(self) -> None:
        ledger = copy.deepcopy(self.example)
        ledger["sources"][0]["sha256"] = "ABC"

        report = validator.validate_ledger(ledger)

        self.assertFalse(report["ok"])
        self.assertIn("64 lowercase hexadecimal", "\n".join(report["errors"]))

    def test_observed_claim_requires_source_references(self) -> None:
        ledger = copy.deepcopy(self.example)
        claim = next(item for item in ledger["claims"] if item["state"] == "observed")
        claim.pop("source_ids", None)

        report = validator.validate_ledger(ledger)

        self.assertFalse(report["ok"])
        self.assertIn("source_ids", "\n".join(report["errors"]))

    def test_unknown_source_reference_is_rejected(self) -> None:
        ledger = copy.deepcopy(self.example)
        claim = next(item for item in ledger["claims"] if item["state"] == "observed")
        claim["source_ids"] = ["missing_evidence"]

        report = validator.validate_ledger(ledger)

        self.assertFalse(report["ok"])
        self.assertIn("unknown source", "\n".join(report["errors"]))

    def test_inferred_claim_requires_assumptions(self) -> None:
        ledger = copy.deepcopy(self.example)
        claim = next(item for item in ledger["claims"] if item["state"] == "inferred")
        claim.pop("assumptions", None)

        report = validator.validate_ledger(ledger)

        self.assertFalse(report["ok"])
        self.assertIn("assumptions", "\n".join(report["errors"]))

    def test_rejected_claim_requires_contradiction(self) -> None:
        ledger = copy.deepcopy(self.example)
        claim = next(item for item in ledger["claims"] if item["state"] == "rejected")
        claim.pop("contradiction", None)

        report = validator.validate_ledger(ledger)

        self.assertFalse(report["ok"])
        self.assertIn("contradiction", "\n".join(report["errors"]))

    def test_unknown_claim_requires_explanation(self) -> None:
        ledger = copy.deepcopy(self.example)
        claim = next(item for item in ledger["claims"] if item["state"] == "unknown")
        claim.pop("reason", None)
        claim.pop("required_evidence", None)

        report = validator.validate_ledger(ledger)

        self.assertFalse(report["ok"])
        self.assertIn("unknown state", "\n".join(report["errors"]))


if __name__ == "__main__":
    unittest.main()
