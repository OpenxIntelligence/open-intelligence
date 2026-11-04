"""Compatibility checks for direct historical-schema migration fixtures."""
import unittest

from oi_api.question_passages import QuestionPassages


class HistoricalSchemaRegistry:
    _transaction_active = True

    def __init__(self):
        self.queries = []

    def _fetchone(self, statement, parameters=None):
        self.queries.append((statement, parameters))
        if statement == "SELECT to_regclass('investigation.question_passage_revisions')":
            return (None,)
        raise AssertionError(f"unexpected query: {statement}")

    def _fetchall(self, statement, parameters=None):
        raise AssertionError("historical schema must not query an absent passage table")


CONTEXT = {
    "patient_id": "PAT-FICTIONAL",
    "case_id": "CASE-FICTIONAL",
    "organization": "ORG-FICTIONAL",
    "question_id": "QUESTION-" + "A" * 32,
    "purpose": "operations",
    "actor": "ACTOR-FICTIONAL",
}


class QuestionPassageSchemaCompatibility(unittest.TestCase):
    def test_historical_schema_without_passage_table_has_empty_manual_metadata(self):
        registry = HistoricalSchemaRegistry()

        actual = QuestionPassages(registry).metadata_locked(CONTEXT)

        self.assertEqual(actual, {
            "revision_id": None,
            "revision": 0,
            "attached_by": None,
            "attached_at": None,
            "references": [],
            "state": "current_unreviewed",
        })
        self.assertEqual(registry.queries, [
            ("SELECT to_regclass('investigation.question_passage_revisions')", None),
        ])

    def test_historical_revision_lookup_never_treats_an_absent_owner_as_empty(self):
        with self.assertRaisesRegex(RuntimeError, "revision unavailable"):
            QuestionPassages(HistoricalSchemaRegistry()).metadata_locked(
                CONTEXT, revision_id="PASSAGES-" + "B" * 32)


if __name__ == "__main__":
    unittest.main()
