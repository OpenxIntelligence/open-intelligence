"""Exercise existing-source review navigation without adding runtime dependencies."""
from pathlib import Path
import subprocess
import unittest


class QuestionReviewTests(unittest.TestCase):
    def test_question_scoped_review_handoff(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(['node', '--test', 'tests/question_review.test.js'],
                                cwd=root, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
