"""Focused audit-tail regression; real PostgreSQL cases live in the sibling suite.

The source lookup and connection are explicit doubles in this unit test. It
exercises the real evidence transaction coordinator and source receipt ordering,
not persistence, SQL lock behavior or clinical authorization.
"""
import unittest
from unittest.mock import patch

from open_intelligence.patient_registry import PatientRegistryDenied
from open_intelligence.postgres_registry import PostgresPatientRegistry
from oi_api.question_evidence import PostgresQuestionEvidence
from oi_api.source_questions import PostgresSourceQuestions
from oi_api.sources import PostgresSourceVersions


class EvidenceAuditTailTests(unittest.TestCase):
    def test_rights_change_during_source_receipt_withholds_prepared_response(self):
        class Connection:
            autocommit = False
            committed = 0
            rolled_back = 0
            def commit(self): self.committed += 1
            def rollback(self): self.rolled_back += 1

        connection = Connection()
        registry = PostgresPatientRegistry(connection, lambda *args: True)
        rights = {"latest": "DECISION-ONE"}
        qid = "QUESTION-" + "A" * 32

        def prepare(question, scope, dependencies):
            dependencies[("FICT-ONE", "1")] = rights["latest"]
            return b"fictional metadata prepared before the audit callback"

        def source_read(owner, patient, case, **options):
            response = options["prepare_response"]({"access_receipt_id": "ACCESS-" + "B" * 32})
            owner._read_receipt(patient, case, actor="ACTOR-ONE", purpose="operations",
                                binding_revision=1, event="source.read_authorized",
                                receipt_id="ACCESS-" + "B" * 32,
                                recheck_authority=options["recheck_authority"])
            return response

        def audit_callback(*args, **kwargs):
            rights["latest"] = "DECISION-TWO"

        with patch.object(PostgresSourceVersions, "list_locked", source_read), \
                patch.object(PostgresSourceQuestions, "project_locked", return_value=[{
                    "question_id": qid, "source_context_state": "current_unreviewed_question"}]), \
                patch.object(registry, "append_event", side_effect=audit_callback), \
                patch.object(registry, "_fetchone", side_effect=lambda *args: (rights["latest"],)):
            with self.assertRaises(PatientRegistryDenied):
                PostgresQuestionEvidence(registry)._run(
                    "PAT-" + "C" * 32, "CASE-ONE", qid, organization="ORG-ONE",
                    actor="ACTOR-ONE", purpose="operations", operation=prepare,
                    recheck_authority=lambda: None, prepare_response=None)
        self.assertEqual((connection.committed, connection.rolled_back), (0, 1))
