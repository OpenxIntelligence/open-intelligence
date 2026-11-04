"""Contract tests for the issue 118 Composer lifecycle.

These tests cover the pure lifecycle in
src/open_intelligence/composer_lifecycle.py only. They do not claim
the lifecycle is wired to the store, the HTTP routes, the rights
broker, or any model call: on main at 2451983, Composer investigation
is prompt building and output validation only, and wiring this
lifecycle is a separate, later step.
"""

import unittest

from open_intelligence.composer_lifecycle import ComposerInvestigation


def make():
    return ComposerInvestigation("FINDING-ALPHA", "What does this finding show?", [1, 2])


class TestComposerLifecycle(unittest.TestCase):
    def test_starts_running_and_produces_receipt(self):
        inv = make()
        self.assertEqual(inv.state, "running")
        result = inv.next_steps(["Review the cited source version."])
        self.assertTrue(result["allowed"])
        self.assertEqual(len(result["receipt"]), 64)

    def test_add_evidence_while_running(self):
        inv = make()
        result = inv.add_evidence(3)
        self.assertTrue(result["allowed"])
        self.assertIn(3, inv.evidence_ids)

    def test_amendment_marks_stale_and_blocks_next_steps(self):
        inv = make()
        inv.amend_source(1)
        self.assertEqual(inv.state, "stale")
        result = inv.next_steps(["Review the cited source version."])
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "cannot_produce_next_steps_when_stale")

    def test_revalidate_after_amendment_restores_running(self):
        inv = make()
        inv.amend_source(1)
        result = inv.revalidate(4)
        self.assertTrue(result["allowed"])
        self.assertEqual(inv.state, "running")

    def test_hold_blocks_and_release_restores(self):
        inv = make()
        held = inv.hold("Awaiting independent review of the evidence.")
        self.assertTrue(held["allowed"])
        self.assertEqual(inv.state, "held")
        blocked = inv.next_steps(["Review the cited source version."])
        self.assertFalse(blocked["allowed"])
        released = inv.release()
        self.assertTrue(released["allowed"])
        self.assertEqual(inv.state, "running")

    def test_short_hold_reason_denied(self):
        inv = make()
        result = inv.hold("Too short")
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "invalid_hold_reason")

    def test_amend_uncited_source_denied(self):
        inv = make()
        result = inv.amend_source(99)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "source_not_cited")

    def test_empty_finding_denied(self):
        with self.assertRaises(ValueError):
            ComposerInvestigation("", "What does this finding show?", [1])


if __name__ == "__main__":
    unittest.main()
