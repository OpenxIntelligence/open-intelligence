"""Bounded historical migration fallback for canonical question passages.

The live application requires the latest Alembic head. These pure tests only
exercise direct synthetic migration-fixture preparation on older published heads.
No patient data, SQL write or external connector is involved.
"""
import unittest

from oi_api.question_passages import QuestionPassages


class _LegacyRegistry:
    def __init__(self, *revisions, active=True):
        self._transaction_active = active
        self.revisions = revisions

    def _fetchone(self, query, parameters=None):
        if "to_regclass('investigation.question_passage_revisions')" not in query:
            raise AssertionError("Unexpected query in historical fixture")
        return (None,)

    def _fetchall(self, query, parameters=None):
        if "FROM public.alembic_version" not in query:
            raise AssertionError("Unexpected query in historical fixture")
        return [(revision,) for revision in self.revisions]


class QuestionPassagesHistoricalSchemaTests(unittest.TestCase):
    def test_image_only_published_0012_may_seed_empty_manual_context(self):
        result = QuestionPassages(_LegacyRegistry("0012_image_report_convergence")).metadata_locked({})
        self.assertEqual(result, {
            "revision_id": None, "revision": 0, "attached_by": None,
            "attached_at": None, "references": [], "state": "current_unreviewed",
        })

    def test_unknown_revision_is_never_silently_treated_as_no_manual_context(self):
        with self.assertRaisesRegex(RuntimeError, "Question passage owner unavailable"):
            QuestionPassages(_LegacyRegistry("0012_unrecognized_history")).metadata_locked({})

    def test_two_unjoined_historical_heads_do_not_get_a_synthetic_current_context(self):
        owner = QuestionPassages(_LegacyRegistry(
            "0012_image_report_convergence", "0012_reviewed_documents"))
        with self.assertRaisesRegex(RuntimeError, "Question passage owner unavailable"):
            owner.metadata_locked({})

    def test_explicit_historical_reference_and_missing_transaction_fail_closed(self):
        owner = QuestionPassages(_LegacyRegistry("0012_image_report_convergence"))
        with self.assertRaisesRegex(RuntimeError, "Question passage owner unavailable"):
            owner.metadata_locked({}, revision_id="PASSAGES-0123456789ABCDEF0123456789ABCDEF")
        with self.assertRaisesRegex(Exception, "requires a transaction"):
            QuestionPassages(_LegacyRegistry("0012_image_report_convergence", active=False)).metadata_locked({})


if __name__ == "__main__":
    unittest.main()
