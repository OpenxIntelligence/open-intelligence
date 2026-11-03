"""Contract tests for the issue 114 fictional actor gate.

These tests cover the pure gate in src/open_intelligence/actor_gate.py
only. They do not claim the gate is wired to the HTTP routes: on main
at 2451983 the HTTP handler has no actor check, so wiring the gate to
routes is a separate, later step, and must not break the existing
no-actor local demo tests until that wiring is designed.
"""

import unittest

from open_intelligence.actor_gate import check


class TestActorGate(unittest.TestCase):
    def test_clinician_can_read_alpha(self):
        result = check("clinician-01", "CASE-ALPHA", "read")
        self.assertTrue(result["allowed"])
        self.assertEqual(result["reason"], "allowed")

    def test_navigator_can_investigate_alpha(self):
        result = check("navigator-01", "CASE-ALPHA", "investigate")
        self.assertTrue(result["allowed"])
        self.assertEqual(result["reason"], "allowed")

    def test_unknown_actor_denied(self):
        result = check("actor-nope", "CASE-ALPHA", "read")
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "unknown_actor")

    def test_navigator_wrong_case_denied(self):
        result = check("navigator-01", "CASE-BETA", "read")
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "wrong_case")

    def test_unknown_case_denied(self):
        result = check("clinician-01", "CASE-NOPE", "read")
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "wrong_case")

    def test_revoked_actor_denied(self):
        result = check("clinician-revoked", "CASE-ALPHA", "read")
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "revoked_actor")

    def test_navigator_review_purpose_denied(self):
        result = check("navigator-01", "CASE-ALPHA", "review")
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "denied_purpose")

    def test_empty_actor_denied(self):
        result = check("", "CASE-ALPHA", "read")
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "invalid_input")


if __name__ == "__main__":
    unittest.main()
