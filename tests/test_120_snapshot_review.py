"""Contract tests for the issue 120 snapshot review record.

These tests cover the pure record in
src/open_intelligence/snapshot_review.py only. They do not claim the
record is wired to the store, the HTTP routes, or the existing demo
acknowledgement: on main at 2451983, snapshot review is demo
acknowledgement only, and wiring this record is a separate, later step.
"""

import unittest

from open_intelligence.snapshot_review import review_snapshot


class TestSnapshotReview(unittest.TestCase):
    def test_draft_accepted_with_basis_and_provenance(self):
        result = review_snapshot("draft", "accepted", "Source version matches the cited finding.", 3)
        self.assertTrue(result["allowed"])
        self.assertEqual(result["reason"], "accepted")
        self.assertEqual(result["record"]["provenance_source_version_id"], 3)

    def test_draft_rejected_with_basis_and_provenance(self):
        result = review_snapshot("draft", "rejected", "Quotation does not match the source version.", 2)
        self.assertTrue(result["allowed"])
        self.assertEqual(result["reason"], "rejected")

    def test_stale_snapshot_denied(self):
        result = review_snapshot("stale", "accepted", "Source version matches the cited finding.", 3)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "not_draft")

    def test_already_reviewed_snapshot_denied(self):
        result = review_snapshot("reviewed_in_demo", "accepted", "Source version matches the cited finding.", 3)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "not_draft")

    def test_invalid_action_denied(self):
        result = review_snapshot("draft", "approve", "Source version matches the cited finding.", 3)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "invalid_action")

    def test_short_basis_denied(self):
        result = review_snapshot("draft", "accepted", "Too short", 3)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "invalid_basis")

    def test_missing_provenance_denied(self):
        result = review_snapshot("draft", "accepted", "Source version matches the cited finding.", 0)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "invalid_provenance")


if __name__ == "__main__":
    unittest.main()
