"""Exact authored passage resolution for the synthetic human review handoff."""
from datetime import date, datetime, timezone
import hashlib
import unittest
from unittest.mock import Mock

from open_intelligence.patient_registry import PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError
from open_intelligence.postgres_registry import PostgresPatientRegistry
from open_intelligence.store import parse_synthetic_evidence
from oi_api.authored_evidence import PostgresQuestionEvidence
from oi_api.composer_preflight import PostgresSourceComposerPreflight
from oi_api.evidence_report import canonical_hash
from test_authored_evidence_postgres import EvidenceFixture, SUPPORT_QUOTE, SUPPORT_STATEMENT, evidence_text, permissions
from test_question_source_brief import fictional_brief_inputs, fictional_source_index


class AssessmentHandoffTests(unittest.TestCase):
    """Only persistence is doubled. Parse stored originals and resolve the real source preflight."""
    def setUp(self):
        self.registry = Mock(spec=PostgresPatientRegistry)
        self.registry._transaction_active = True
        self.owner = PostgresQuestionEvidence(self.registry)
        self.source_index = fictional_source_index()
        _, self.item, _ = fictional_brief_inputs()
        self.scope = dict(organization="ORG-ALPHA", actor="REVIEWER", purpose="operations")
        self.author = "AUTHOR-ONE"
        prepared = PostgresSourceComposerPreflight(self.registry).preview_locked(
            self.item["patient_id"], self.item["case_id"], source_id=self.item["source_id"],
            source_line=self.item["source_line"], question=self.item["question"],
            expected_source_snapshot_sha256=self.item["source_snapshot_sha256"],
            source_index=self.source_index, **self.scope)
        self.item["preflight_sha256"] = prepared["preflight_sha256"]

        self.statement = "🧪 A fictional café passage with invented observations."
        self.quote = "café passage"
        self.raw = evidence_text(statement=self.statement).encode("utf-8")
        parsed = parse_synthetic_evidence(self.raw)
        rights = permissions(export="unknown")
        self.content_sha = hashlib.sha256(self.raw).hexdigest()
        self.rights_sha = canonical_hash(rights)
        now = datetime(2026, 11, 5, tzinfo=timezone.utc)
        self.eid = "EVIDENCE-" + "A" * 32
        self.aid = "ASSESSMENT-" + "B" * 32
        self.qid = self.item["question_id"]
        self.versions = [(self.eid, parsed.evidence_key, 1, self.content_sha, parsed.statement_line, "full_text",
                          self.rights_sha, rights, parsed.title, date.fromisoformat(parsed.issued_at),
                          self.statement, now, self.raw, None)]
        self.assessments = [(self.aid, self.qid, self.eid, self.content_sha, self.rights_sha,
                             self.item["source_snapshot_sha256"], self.item["preflight_sha256"], "context",
                             "limited", self.quote, self.statement.index(self.quote), "A fictional comparison.",
                             self.author, now, 1)]
        self.withdrawals = []
        original_payload = dict(synthetic=True, request_key="ASSESS-ONE", evidence_id=self.eid,
                                evidence_sha256=self.content_sha, rights_sha256=self.rights_sha, quote=self.quote,
                                expected_source_snapshot_sha256=self.item["source_snapshot_sha256"],
                                expected_preflight_sha256=self.item["preflight_sha256"], relation="context",
                                applicability="limited", rationale="A fictional comparison.")
        self.intent = canonical_hash(dict(patient_id=self.item["patient_id"], case_id=self.item["case_id"],
                                         question_id=self.qid, organization="ORG-ALPHA", actor=self.author,
                                         purpose="operations", operation="assess", payload=original_payload))
        self.registry._fetchall.side_effect = self.rows
        self.registry._fetchone.side_effect = self.one

    def rows(self, sql, params):
        scope = (self.item["patient_id"], self.item["case_id"], "ORG-ALPHA")
        if "case_evidence_versions" in sql:
            self.assertEqual(params, scope)
            return self.versions
        if "case_evidence_withdrawals" in sql:
            self.assertEqual(params, scope)
            return self.withdrawals
        self.assertIn("question_evidence_assessments", sql)
        self.assertEqual(params, (*scope, self.qid))
        return self.assessments

    def one(self, sql, params):
        if "evidence_command_origins" in sql:
            self.assertEqual(params[-3:], (self.qid, "assess", self.aid))
            return ("ASSESS-ONE", self.intent, None, "not_applicable", None, self.author, "operations")
        self.assertIn("evidence_commands", sql)
        return (self.intent, {"assessment_id": self.aid, "question_id": self.qid},
                "ORG-ALPHA", self.author, "operations")

    def verify(self):
        return self.owner.verify_review_assessment_locked(self.item, self.aid,
                                                          source_index=self.source_index, **self.scope)

    def test_literal_proof_contains_only_source_references_and_unicode_offsets(self):
        proof, recheck = self.verify()
        self.assertEqual(proof, dict(assessment_id=self.aid, evidence_id=self.eid, evidence_version=1,
                                     evidence_sha256=self.content_sha, rights_sha256=self.rights_sha,
                                     statement_line=6, quote_start=14, quote_length=12,
                                     quote_sha256=hashlib.sha256(self.quote.encode("utf-8")).hexdigest()))
        recheck()
        self.assertEqual({call.args[2] for call in self.registry._allow.call_args_list},
                         {"patient_read", "source_read", "question_read", "authored_evidence_read"})
        self.registry._allow.side_effect = PatientRegistryDenied("revoked")
        with self.assertRaises(PatientRegistryDenied):
            recheck()

    def test_superseding_comparison_and_withdrawn_family_prevent_return(self):
        _, recheck = self.verify()
        self.withdrawals.append(("WITHDRAWAL-" + "D" * 32, self.eid, "Fictional rights withdrawn."))
        with self.assertRaises(PatientRegistryDenied):
            recheck()
        self.withdrawals.clear()
        self.assessments.append(("ASSESSMENT-" + "E" * 32, *self.assessments[0][1:-1], 2))
        with self.assertRaises(PatientRegistryConflict):
            self.verify()

    def test_missing_assessment_and_stale_source_preflight_fail_closed(self):
        self.aid = "ASSESSMENT-" + "D" * 32
        with self.assertRaises(PatientRegistryDenied):
            self.verify()
        self.source_index = fictional_source_index(state="pending")
        with self.assertRaises(PatientRegistryConflict):
            self.verify()

    def test_altered_literal_from_same_original_still_fails_the_creating_intent(self):
        other = "invented observations"
        row = list(self.assessments[0])
        row[9:11] = [other, self.statement.index(other)]
        self.assessments[0] = tuple(row)
        with self.assertRaisesRegex(RuntimeError, "original command"):
            self.verify()

    def test_corrupt_preserved_bytes_or_quote_offset_stop_verification(self):
        row = self.versions[0]
        self.versions[0] = (*row[:-2], self.raw.replace(b"fictional", b"invented"), None)
        with self.assertRaisesRegex(RuntimeError, "evidence integrity"):
            self.verify()
        self.versions[0] = row
        assessment = list(self.assessments[0])
        assessment[10] += 1
        self.assessments[0] = tuple(assessment)
        with self.assertRaisesRegex(RuntimeError, "comparison integrity"):
            self.verify()

    def test_no_separate_transaction_or_unscoped_review(self):
        self.scope["purpose"] = "research"
        with self.assertRaises(PatientRegistryDenied):
            self.verify()
        self.registry._transaction_active = False
        with self.assertRaises(PatientRegistryError):
            self.verify()
        self.registry._fetchall.assert_not_called()
        self.registry._fetchone.assert_not_called()


class StoredAssessmentHandoffTests(EvidenceFixture):
    def test_locked_handoff_matches_the_inspected_packet_and_refuses_a_withdrawal(self):
        from http_support import running_server
        from oi_api.app import create_app
        from oi_api.database import Database
        from oi_api.question_review_returns import PostgresQuestionReviewReturns
        from oi_api.sources import PostgresSourceVersions

        with running_server(create_app(self.settings)) as base:
            patient, question, _ = self.start(base)
            status, imported, _ = self.imported(base, patient, question)
            self.assertEqual(status, 201, imported)
            packet = self.packet(base, patient, question)
            proposal = self.assessment_body(packet, imported["evidence_id"])
            status, assessment, _ = self.assessed(base, patient, question, proposal)
            self.assertEqual(status, 201, assessment)
            case = packet["case_id"]
            scope = dict(organization="ORG-ALPHA", actor="INDEPENDENT-REVIEWER", purpose="operations")
            database = Database(self.admin)
            self.addCleanup(database.close)

            def authorized(actor, subject, action, purpose):
                return (actor, subject, purpose) == (scope["actor"], patient, "operations") and action in {
                    "patient_read", "source_read", "question_read", "authored_evidence_read"
                }

            def verify():
                with database.registry_connection() as conn:
                    registry = PostgresPatientRegistry(conn, authorized)
                    def prepare(index):
                        items, _ = PostgresQuestionReviewReturns(registry)._read_locked(
                            patient, case, scope["organization"], index)
                        item, = [i for i in items if i["question_id"] == question]
                        proof, check = PostgresQuestionEvidence(registry).verify_review_assessment_locked(
                            item, assessment["assessment_id"], source_index=index, **scope)
                        check()
                        return proof
                    with registry.transaction():
                        return PostgresSourceVersions(registry).list_locked(
                            patient, case, prepare_response=prepare, recheck_authority=lambda: None, **scope)

            proof = verify()
            self.assertEqual((proof["evidence_sha256"], proof["rights_sha256"], proof["evidence_version"]),
                             (proposal["evidence_sha256"], proposal["rights_sha256"], imported["version"]))
            self.assertEqual((proof["quote_sha256"], proof["quote_start"], proof["quote_length"]),
                             (hashlib.sha256(SUPPORT_QUOTE.encode()).hexdigest(),
                              SUPPORT_STATEMENT.index(SUPPORT_QUOTE), len(SUPPORT_QUOTE)))
            status, result, _ = self.withdrawn(base, patient, question, imported["evidence_id"])
            self.assertEqual(status, 201, result)
            with self.assertRaises(PatientRegistryDenied):
                verify()
