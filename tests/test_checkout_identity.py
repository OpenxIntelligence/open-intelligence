"""Exercise verification against real Git state, without network or project data."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "verify_checkout.py"


class CheckoutIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Fictional verification fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        (self.root / "source.txt").write_text("original\n")
        self.git("add", "source.txt")
        self.git("commit", "-qm", "Fixture source")
        self.head = self.git("rev-parse", "HEAD")
        self.tree = self.git("rev-parse", "HEAD^{tree}")

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True).strip()

    def verify(self, expected):
        return subprocess.run([sys.executable, str(SCRIPT), "--expected-head", expected],
                              cwd=self.root, text=True, capture_output=True)

    def test_clean_proposed_revision_reports_its_actual_commit_and_tree(self):
        result = self.verify(self.head)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {
            "commit": self.head, "tree": self.tree, "tracked_tree_clean": True})

    def test_a_different_commit_is_rejected_even_when_the_tree_is_identical(self):
        self.git("commit", "--allow-empty", "-qm", "Different revision, identical files")
        self.assertEqual(self.git("rev-parse", "HEAD^{tree}"), self.tree)
        result = self.verify(self.head)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not match", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_unstaged_and_staged_changes_cannot_be_attributed_to_the_commit(self):
        (self.root / "source.txt").write_text("changed\n")
        for staged in (False, True):
            with self.subTest(staged=staged):
                if staged:
                    self.git("add", "source.txt")
                result = self.verify(self.head)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("tracked changes", result.stderr)
                self.assertEqual(result.stdout, "")

    def test_missing_abbreviated_or_option_like_revision_is_rejected(self):
        for expected in ("", self.head[:7], "--help", "main"):
            with self.subTest(expected=expected):
                result = self.verify(expected)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
