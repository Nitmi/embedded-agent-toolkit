from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACTION = re.compile(r"uses:\s+([^\s]+)")
PINNED = re.compile(r"[^@\s]+@[0-9a-f]{40}$")


class WorkflowTests(unittest.TestCase):
    def workflow(self, name: str) -> str:
        return (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")

    def test_all_external_actions_are_pinned_to_commits(self) -> None:
        for name in ("ci.yml", "release-attestation.yml"):
            actions = ACTION.findall(self.workflow(name))
            self.assertTrue(actions, name)
            for action in actions:
                with self.subTest(workflow=name, action=action):
                    self.assertRegex(action, PINNED)

    def test_provenance_workflow_has_narrow_permissions_and_tag_binding(self) -> None:
        workflow = self.workflow("release-attestation.yml")
        for permission in (
            "contents: read",
            "id-token: write",
            "attestations: write",
            "artifact-metadata: write",
        ):
            self.assertIn(permission, workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("pull_request:", workflow)
        self.assertIn("- 'v*.*.*'", workflow)
        self.assertIn("check-tag --tag", workflow)
        self.assertIn(
            "actions/attest@a1948c3f048ba23858d222213b7c278aabede763", workflow
        )
        self.assertIn("Release builds differ", workflow)
        self.assertIn("--output-dir build/release-a", workflow)
        self.assertIn("--output-dir build/release-b", workflow)
        self.assertNotIn("--output-dir dist-a", workflow)


if __name__ == "__main__":
    unittest.main()
