"""Regression contract for task-grouped navigation in the synthetic case workspace."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GROUPS = {
    "Overview": ("overview", "patient-mission", "changes-since-review", "patient-view"),
    "Journey": ("timeline",),
    "Record": ("assertions", "sources", "import"),
    "Investigations": ("investigations", "evidence", "bibliography", "options"),
    "Care and work": ("incoming-board", "activity"),
}


class WorkspaceNavigationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        cls.css = (ROOT / "web" / "style.css").read_text(encoding="utf-8")

    def test_five_task_groups_keep_all_original_case_destinations(self):
        navigation = re.search(
            r'<nav id="workspace-nav" aria-label="Workspace sections">(.*?)</nav>',
            self.html,
            re.DOTALL,
        )
        self.assertIsNotNone(navigation)
        groups = re.findall(
            r'<div class="nav-group" aria-label="([^"]+)">(.*?)</div>',
            navigation.group(1),
            re.DOTALL,
        )
        self.assertEqual([name for name, _ in groups], list(GROUPS))
        all_destinations = []
        for name, content in groups:
            destinations = re.findall(r'<a href="#([^"]+)">', content)
            self.assertEqual(tuple(destinations), GROUPS[name])
            for dest in destinations:
                self.assertRegex(self.html, rf'\bid="{re.escape(dest)}"')
            all_destinations.extend(destinations)
        self.assertEqual(len(all_destinations), 14)
        self.assertEqual(len(all_destinations), len(set(all_destinations)))

    def test_navigation_keeps_live_links_and_readable_context(self):
        self.assertIn('class="section-menu" open', self.html)
        self.assertIn('aria-label="Workspace sections"', self.html)
        self.assertIn('.nav-group-title', self.css)
        self.assertIn('href="#patient-view"', self.html)
        self.assertIn('FICTIONAL DEMO DATA — not a real patient', self.html)


if __name__ == "__main__":
    unittest.main()
