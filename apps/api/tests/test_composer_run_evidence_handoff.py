"""Exact completed-run handoff to the canonical review owner. Real PG16 + HTTP."""
import hashlib
import json
from unittest.mock import patch
import unittest

from sqlalchemy import text
from http_support import running_server
from oi_api.app import create_app
from oi_api import evidence_catalog, evidence_routes
from open_intelligence.postgres_registry import PostgresPatientRegistry
from oi_api.database import Database
import test_composer_runs_postgres as runs
import test_question_evidence_postgres as metadata
import test_authored_evidence_postgres as authored
import test_source_versions as sources
from test_patients import request, TOKEN_A


class HandoffContracts(unittest.TestCase):
    def test_both_input_shapes_are_disjoint_and_reject_content_and_approval(self):
        from pydantic import TypeAdapter, ValidationError
        from oi_api.evidence_contracts import RunEvidenceReview, RunQuoteReview
        inputs = TypeAdapter(RunQuoteReview | RunEvidenceReview)
        base = dict(synthetic=True, expected_result_sha256="0"*64)
        quote = dict(**base, verification="exact_authored_quote", assessment_id="ASSESSMENT-"+"A"*32,
                     expected_evidence_sha256="1"*64, expected_quote_sha256="2"*64)
        metadata_only = dict(**base, verification="exact_version_metadata_only", link_id="EVIDENCE-LINK-"+"B"*32,
                             citation="FICT-EXAMPLE@2", expected_metadata_sha256="3"*64)
        for good in (quote, metadata_only):
            self.assertEqual(inputs.validate_python(good).model_dump(), good)
            for extra in ({"quote":"not allowed"}, {"clinical_approval":True},
                          {"verification":"clinical_support"}, {"synthetic":False}):
                with self.assertRaises(ValidationError):
                    inputs.validate_python({**good, **extra})
        with self.assertRaises(ValidationError):
            inputs.validate_python({**quote, **metadata_only})
        route = next(v for k, v in create_app().openapi()["paths"].items() if k.endswith("/verification-return"))
        self.assertEqual(route["post"]["security"], [{"SyntheticFixture": []}])


class RunEvidenceHandoff(sources.SourceVersionFixture):
    world = runs.ComposerRunsPostgresTests.world
    model_path = staticmethod(runs.ComposerRunsPostgresTests.model_path)
    path = staticmethod(runs.ComposerRunsPostgresTests.path)
    preflight = runs.ComposerRunsPostgresTests.preflight
    prepared = runs.ComposerRunsPostgresTests.prepared
    save = runs.ComposerRunsPostgresTests.save
    seed = runs.ComposerRunsPostgresTests.seed
    seeded_run = runs.ComposerRunsPostgresTests.seeded_run
    run_path = staticmethod(runs.ComposerRunsPostgresTests.run_path)
    enqueue = runs.ComposerRunsPostgresTests.enqueue
    work = runs.ComposerRunsPostgresTests.work
    status = runs.ComposerRunsPostgresTests.status
    evidence_path = staticmethod(metadata.QuestionEvidencePostgresTests.evidence_path)
    search = metadata.QuestionEvidencePostgresTests.search
    link = metadata.QuestionEvidencePostgresTests.link
    revise_rights = metadata.QuestionEvidencePostgresTests.revise_rights
    prefix = staticmethod(authored.EvidenceFixture.prefix)
    imported = authored.EvidenceFixture.imported
    packet = authored.EvidenceFixture.packet
    assessment_body = authored.EvidenceFixture.assessment_body
    assessed = authored.EvidenceFixture.assessed
    withdrawn = authored.EvidenceFixture.withdrawn

    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend(("composer_context_read", "question_create", "question_read",
            "source_brief_export", "review_return", "review_queue_read", "evidence_read", "evidence_link", *authored.ACTIONS))
        self.write()
        self.catalog = evidence_catalog

    def returns(self):
        with self.engine.connect() as c:
            return c.execute(text("SELECT metadata_json FROM identity.identity_domain_events "
                                  "WHERE event_type='investigation.review.returned_for_verification' ORDER BY id")).scalars().all()

    def test_catalog_requires_completed_actor_run_and_exact_current_link_even_on_retry(self):
        with Database(self.settings).registry_connection() as conn:
            evidence_catalog.seed_fictional_records(PostgresPatientRegistry(conn, lambda *args: False),
                evidence_catalog.fictional_records(), recorded_by="FIXTURE-AUTHOR")
        with running_server(create_app(self.settings)) as base:
            patient, q, prep, run = self.seeded_run(base)
            record = self.search(base, patient, q)[1]["records"][0]
            link = self.link(base, patient, prep, q, record)[1]
            intent = dict(synthetic=True, verification="exact_version_metadata_only", link_id=link["link_id"],
                citation=record["citation"], expected_metadata_sha256=record["metadata_sha256"], expected_result_sha256="0"*64)
            def send(**overrides):
                return request(base, self.run_path(patient, q, run, "/verification-return"), token=TOKEN_A,
                               body={**intent, **overrides})
            self.assertEqual(send()[0], 409)
            self.assertEqual(self.work(patient)["status"], "completed")
            intent["expected_result_sha256"] = self.status(base, patient, q, run)[1]["result_sha256"]
            self.assertEqual(send(citation="FICT-OTHER@1")[0], 409)
            self.assertEqual(send(link_id="EVIDENCE-LINK-"+"0"*32)[0], 404)
            self.assertEqual(self.returns(), [])
            code, result, headers = send()
            self.assertEqual((code, result["verification"], headers["Cache-Control"]), (201, "exact_version_metadata_only", "no-store"))
            self.assertEqual(send()[:2], (200, {**result, "duplicate":True}))
            event, = self.returns()
            self.assertEqual((event["receipt_id"], event["run_id"], event["evidence_link_id"], event["citation_version"]),
                             (result["receipt_id"], run, link["link_id"], record["version"]))
            self.revise_rights(revoked=True)
            code, denied, _ = send()
            self.assertEqual((code, set(denied)), (404, {"detail"}))
            self.assertNotIn(record["citation"], json.dumps(denied))
            self.assertEqual(self.returns(), [event])

    def test_exact_authored_quote_commits_one_real_review_and_late_denial_rolls_back(self):
        with running_server(create_app(self.settings)) as base:
            patient, q, _, run = self.seeded_run(base)
            self.assertEqual(self.work(patient)["status"], "completed")
            result_sha = self.status(base, patient, q, run)[1]["result_sha256"]
            code, record, _ = self.imported(base, patient, q)
            self.assertEqual(code, 201, record)
            item = self.assessment_body(self.packet(base, patient, q), record["evidence_id"])
            code, assessment, _ = self.assessed(base, patient, q, item)
            self.assertEqual(code, 201, assessment)
            intent = dict(synthetic=True, verification="exact_authored_quote", assessment_id=assessment["assessment_id"],
                          expected_evidence_sha256=item["evidence_sha256"], expected_result_sha256=result_sha,
                          expected_quote_sha256=hashlib.sha256(item["quote"].encode()).hexdigest())
            def send(**overrides):
                return request(base, self.run_path(patient, q, run, "/verification-return"), token=TOKEN_A,
                               body={**intent, **overrides})
            self.assertEqual(send(expected_quote_sha256="0"*64)[0], 409)
            prepare = evidence_routes._prepare
            def revoke(*args, **kwargs):
                response = prepare(*args, **kwargs)
                self.creds[0]["actions"].remove("authored_evidence_read")
                self.write()
                return response
            with patch.object(evidence_routes, "_prepare", side_effect=revoke):
                code, denied, _ = send()
            self.assertIn(code, (403, 404))
            self.assertEqual(set(denied), {"detail"})
            self.assertEqual(self.returns(), [])
            self.creds[0]["actions"].append("authored_evidence_read"); self.write()
            code, receipt, _ = send()
            self.assertEqual(code, 201, receipt)
            self.assertFalse(receipt["clinical_approval"])
            self.assertEqual((receipt["quote_sha256"], receipt["quote_length"], receipt["rights_sha256"]),
                (intent["expected_quote_sha256"], len(item["quote"]), item["rights_sha256"]))
            self.assertEqual(send()[:2], (200, {**receipt, "duplicate":True}))
            event, = self.returns()
            self.assertEqual((event["receipt_id"], event["assessment_id"], event["evidence_version"]),
                             (receipt["receipt_id"], intent["assessment_id"], 1))
            self.assertNotIn(item["quote"], json.dumps(event))
            queue = request(base, f"/v1/patients/{patient}/cases/CASE-ALPHA/review-queue", token=TOKEN_A)[1]
            self.assertEqual(queue["items"][0]["current_return_receipt_id"], receipt["receipt_id"])
            self.assertEqual(self.withdrawn(base, patient, q, record["evidence_id"])[0], 201)
            self.assertIn(send()[0], (403, 404, 409))
            self.assertEqual(self.ingest(base, patient, sources.AMENDED)[0], 201)
            self.assertEqual(send()[0], 409)
            self.assertEqual(self.returns(), [event])
