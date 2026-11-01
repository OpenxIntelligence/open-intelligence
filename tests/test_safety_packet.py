"""Guard tests for the submission safety packet.

These assert load-bearing repository invariants the packet relies on:
no third-party package manager files, only the two pinned CI actions,
no externally fetched web resources, and synthetic markers on every
example file. They read the repository itself, so a merge that breaks
an invariant fails here rather than silently invalidating the packet.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

KNOWN_ACTIONS = {"actions/checkout@v4", "actions/setup-python@v5"}


class SafetyPacketTest(unittest.TestCase):
    def test_no_package_manager_files(self):
        for name in ("requirements.txt", "pyproject.toml", "package.json",
                     "package-lock.json", "Pipfile", "Pipfile.lock"):
            self.assertFalse((ROOT / name).exists(), f"unexpected {name}")

    def test_workflows_pin_only_known_actions(self):
        uses = set()
        for workflow in (ROOT / ".github/workflows").glob("*.yml"):
            for line in workflow.read_text(encoding="utf-8").splitlines():
                match = re.search(r"uses:\s*(\S+)", line)
                if match:
                    uses.add(match.group(1))
        self.assertTrue(uses, "no actions found in workflows")
        self.assertEqual(uses, KNOWN_ACTIONS, f"unexpected actions: {uses}")

    def test_web_has_no_externally_fetched_resources(self):
        html = (ROOT / "web/index.html").read_text(encoding="utf-8")
        for match in re.finditer(r'<(?:script|link)[^>]+(?:src|href)="([^"]+)"', html):
            url = match.group(1)
            self.assertFalse(url.startswith("http"),
                             f"external web resource: {url}")
        css = (ROOT / "web/style.css").read_text(encoding="utf-8")
        self.assertNotIn("@import", css)

    def test_example_files_carry_synthetic_markers(self):
        examples = sorted((ROOT / "examples/synthetic").glob("*.txt"))
        self.assertTrue(examples, "no synthetic example files found")
        for path in examples:
            first = path.read_text(encoding="utf-8").splitlines()[0]
            self.assertTrue(first.startswith("OI-SYNTHETIC-"),
                            f"{path.name} missing synthetic marker: {first!r}")
        fixture = (ROOT / "examples/synthetic/crossref-metadata-fixture.json").read_text(encoding="utf-8")
        self.assertIn("10.5555/oi-synthetic-001", fixture)

    def test_packet_files_exist(self):
        packet = ROOT / "docs/safety-packet"
        for name in ("SBOM.md", "NOTICE.md", "DATA_RIGHTS.md",
                     "ASSET_CATALOG.md", "README.md"):
            self.assertTrue((packet / name).is_file(), f"missing {name}")


if __name__ == "__main__":
    unittest.main()
