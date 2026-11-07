"""A human return binds the exact saved inspection that was reopened, with current rights."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from threading import Barrier
import unittest
from unittest.mock import patch

from alembic.util.exc import CommandError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from http_support import running_server
from oi_api.app import create_app
from oi_api.config import Settings
from oi_api.migrate import migrate
from oi_api.request_limits import PatientRequestLimit
from open_intelligence.postgres_registry import PostgresPatientRegistry
from test_patients import TOKEN_A, TOKEN_B, request
from test_source_versions import SourceVersionFixture
import test_laboratory_inspection_snapshots as snapshot_fixtures

REASON = "Please independently verify this fictional specimen result and the permitted citations."
PREFIX = "/v1/patients/{patient_id}/cases/{case_id}/composer/laboratory-questions/{question_id}/source-citation-report/snapshots/{snapshot_id}/review-returns"


class LaboratoryReviewContractTests(unittest.TestCase):
    def test_return_contract_binds_saved_and_reopened_hashes(self):
        schema = create_app(Settings.from_env({})).openapi()
        self.assertTrue(PREFIX in schema["paths"], "The typed inspection review endpoint is missing")
        for method in ("get", "post"):
            self.assertEqual(schema["paths"][PREFIX][method]["security"], [{"SyntheticFixture": []}])
        models = schema["components"]["schemas"]
        self.assertEqual(set(models["ReturnLaboratoryInspection"]["required"]), {
            "synthetic", "request_key", "expected_queue_fingerprint", "expected_captured_report_sha256",
            "expected_report_sha256", "reason"})
        self.assertEqual(models["LaboratoryReviewHistory"]["properties"]["contract"]["const"],
                         "oi.laboratory-inspection-review-returns/1")
        self.assertEqual(models["LaboratoryReturnHistory"]["properties"]["action"]["const"], "returned")
        self.assertEqual(models["LaboratoryReviewHistory"]["additionalProperties"], False)

    def test_return_body_is_bounded_before_parsing(self):
        async def run(declared):
            seen = []
            async def app(scope, receive, send):
                seen.append("reached application")
            parts = iter([{"type":"http.request", "body":b"x" * 9000,"more_body":True},
                          {"type":"http.request", "body":b"x" * 9000,"more_body":False}])
            async def receive():
                return next(parts)
            async def send(message):
                seen.append(message)
            headers = [(b"content-length", b"18000")] if declared else []
            await PatientRequestLimit(app)({"type":"http", "method":"POST", "path":PREFIX,
                                           "headers":headers}, receive, send)
            self.assertNotIn("reached application", seen)
            self.assertEqual(seen[0]["status"], 413)
            self.assertEqual(json.loads(seen[1]["body"]), {"detail":"Request body too large"})
        for declared in (True, False):
            asyncio.run(run(declared))


class LaboratoryReviewReturnTests(SourceVersionFixture):
    expect = snapshot_fixtures.LaboratoryInspectionSnapshotTests.expect
    scope = snapshot_fixtures.LaboratoryInspectionSnapshotTests.scope
    import_lab = snapshot_fixtures.LaboratoryInspectionSnapshotTests.import_lab
    prepare = snapshot_fixtures.LaboratoryInspectionSnapshotTests.prepare
    saved = snapshot_fixtures.LaboratoryInspectionSnapshotTests.saved
    find = snapshot_fixtures.LaboratoryInspectionSnapshotTests.find
    command = staticmethod(snapshot_fixtures.LaboratoryInspectionSnapshotTests.command)
    fixture = snapshot_fixtures.LaboratoryInspectionSnapshotTests.fixture
    rights = snapshot_fixtures.LaboratoryInspectionSnapshotTests.rights

    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend(("question_create", "composer_context_read", "question_read",
            "evidence_read", "evidence_link", "review_packet_read", "laboratory_snapshot_create"))
        from oi_api.database import Database
        from oi_api import evidence_catalog
        self.catalog = Database(self.settings)
        self.addCleanup(self.catalog.close)
        with self.catalog.registry_connection() as connection:
            evidence_catalog.seed_fictional_records(PostgresPatientRegistry(connection),
                evidence_catalog.fictional_records(), recorded_by="FIXTURE-AUTHOR")
        self.creds[0]["actions"].extend(("review_queue_read", "review_return"))
        self.write()

    def start(self, base):
        case, source, question, anchor, report, capture = self.fixture(base)
        metadata = self.find(base, question, anchor)
        self.expect(201, base, question + "/evidence-links", self.command(metadata, anchor, "CITE-TO-RETURN"))
        capture["expected_report_sha256"] = self.expect(200, base, report + "/versioned")["report_sha256"]
        snapshot = self.expect(201, base, report + "/snapshots", capture)
        path = report + "/snapshots/" + snapshot["snapshot_id"] + "/review-returns"
        queue = self.expect(200, base, path)
        return case, source, question, path, queue

    @staticmethod
    def payload(queue, key="RETURN-LAB-ONE"):
        return {"synthetic":True, "request_key":key, "expected_queue_fingerprint":queue["queue_fingerprint"],
                "expected_captured_report_sha256":queue["captured_report_sha256"],
                "expected_report_sha256":queue["current_report_sha256"], "reason":REASON}

    def counts(self):
        with self.engine.connect() as conn:
            return tuple(conn.execute(text("""SELECT
                (SELECT count(*) FROM investigation.question_review_receipts),
                (SELECT count(*) FROM investigation.laboratory_review_origins),
                (SELECT count(*) FROM identity.identity_domain_events)
            """)).one())

    def test_return_same_view_concurrency_retry_amendment_and_legacy_queue(self):
        with running_server(create_app(self.settings)) as base:
            case, source, question, path, queue = self.start(base)
            payload = self.payload(queue)
            self.assertEqual(queue["review_state"], "awaiting_independent_verification")
            barrier = Barrier(2)
            def create():
                barrier.wait(timeout=5)
                return request(base, path, token=TOKEN_A, body=payload)[:2]
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(create) for _ in range(2)]
                replay, saved = sorted((f.result() for f in futures), key=lambda r:r[0])
            self.assertEqual(saved[0], 201)
            self.assertEqual(replay, (200, saved[1] | {"duplicate":True}))
            queue = self.expect(200, base, path)
            self.assertEqual(queue["return_count"], 1)
            self.assertEqual(queue["prior_return_count"], 0)
            self.assertEqual(queue["review_state"], "returned_for_independent_verification")
            self.assertEqual(queue["current_return_receipt_id"], saved[1]["receipt_id"])
            self.assertFalse(queue["clinical_approval"])
            self.expect(409, base, path, payload | {"reason":"Different requested verification reason."})
            text_queue = self.expect(200, base, case + "/review-queue")
            self.assertEqual(text_queue["receipts"], [])
            self.assertEqual(text_queue["items"], [])
            old_receipt = queue["receipts"][0]
            self.import_lab(base, case, value=5, previous=source["source_id"])
            self.expect(409, base, path, payload | {"request_key":"STALE-BEFORE-REOPEN"})
            changed = self.expect(200, base, path)
            self.assertEqual(changed["source_context_state"], "source_reassessment_required")
            self.assertEqual(changed["review_state"], "source_reassessment_required")
            self.assertEqual(changed["return_count"], 0)
            self.assertEqual(changed["prior_return_count"], 1)
            self.assertEqual(changed["receipts"], [old_receipt])
            self.assertEqual(self.expect(200, base, path, payload), saved[1] | {"duplicate":True})
            self.expect(201, base, path, self.payload(changed, "RETURN-AFTER-REOPEN"))
            reassessed = self.expect(200, base, path)
            self.assertEqual(reassessed["review_state"], "source_reassessment_required")
            self.assertEqual(reassessed["return_count"], 1)
            self.assertEqual(reassessed["prior_return_count"], 1)
            self.assertFalse(reassessed["reviewer_identity_verified"])

    def test_rights_change_requires_reopen_and_records_visible_hash(self):
        with running_server(create_app(self.settings)) as base:
            _, _, _, path, queue = self.start(base)
            first = self.payload(queue)
            self.rights(withdrawn=True)
            self.expect(409, base, path, first)
            hidden = self.expect(200, base, path)
            self.assertNotEqual(hidden["current_report_sha256"], queue["current_report_sha256"])
            self.assertEqual(hidden["captured_report_sha256"], queue["captured_report_sha256"])
            self.expect(201, base, path, self.payload(hidden))
            row = self.expect(200, base, path)["receipts"][0]
            self.assertEqual(row["report_sha256"], hidden["current_report_sha256"])
            self.assertEqual(row["captured_report_sha256"], queue["captured_report_sha256"])
            self.rights(withdrawn=False)
            visible = self.expect(200, base, path)
            self.assertEqual(visible["return_count"], 0)
            self.assertEqual(visible["prior_return_count"], 1)
            self.assertEqual(visible["receipts"], [row])

    def test_independent_grants_actor_scope_and_late_denial_rollback(self):
        from oi_api import laboratory_review_routes
        with running_server(create_app(self.settings)) as base:
            _, _, _, path, queue = self.start(base)
            payload = self.payload(queue)
            self.expect(404, base, path, token=TOKEN_B)
            for key in ("organization", "actions", "patient_ids"):
                self.creds[1][key] = list(self.creds[0][key]) if isinstance(self.creds[0][key],list) else self.creds[0][key]
            self.write()
            self.expect(201, base, path, payload)
            self.expect(200, base, path, token=TOKEN_B)
            self.expect(409, base, path, payload, token=TOKEN_B)
            for action in ("review_return", "evidence_read", "review_packet_read", "source_read", "question_read"):
                self.creds[0]["actions"].remove(action)
                self.write()
                self.expect(404, base, path, payload)
                self.creds[0]["actions"].append(action)
                self.write()
            before = self.counts()
            original = laboratory_review_routes._prepare
            def revoke(*args, **kwargs):
                result = original(*args, **kwargs)
                self.creds[0]["actions"].remove("review_return")
                self.write()
                return result
            with patch.object(laboratory_review_routes,"_prepare",side_effect=revoke):
                self.expect(404, base, path, payload | {"request_key":"DENIED-AFTER-ENCODE"})
            self.assertEqual(self.counts(), before)

    def test_populated_snapshot_upgrade_origin_immutability_and_downgrade_guard(self):
        with running_server(create_app(self.settings)) as base:
            _, _, _, path, _ = self.start(base)

        # All these populated tables were already owned by the predecessor.
        # The additive review origin starts empty and may be removed safely.
        tables = ("clinical_source.source_versions", "clinical_source.fhir_laboratory_sources",
                  "clinical_source.fhir_laboratory_observations", "investigation.source_questions",
                  "investigation.laboratory_question_anchors", "investigation.question_evidence_links",
                  "investigation.laboratory_citation_anchors", "investigation.laboratory_inspection_snapshots",
                  "investigation.evidence_catalog_records", "investigation.evidence_rights_decisions",
                  "investigation.question_review_receipts", "identity.identity_domain_events")
        def preserved_rows():
            with self.engine.connect() as conn:
                return {table: conn.execute(text(
                    "SELECT to_jsonb(t) FROM " + table + " t ORDER BY to_jsonb(t)::text"
                )).scalars().all() for table in tables}

        captured = preserved_rows()
        self.assertEqual(len(captured["investigation.laboratory_inspection_snapshots"]), 1)
        self.assertEqual(len(captured["investigation.question_evidence_links"]), 1)
        self.assertEqual(captured["investigation.question_review_receipts"], [])
        migrate(self.admin,"downgrade","0025_lab_inspection_snapshots")
        self.assertEqual(preserved_rows(), captured)
        with self.engine.connect() as conn:
            prior = conn.execute(text("SELECT tgname FROM pg_trigger WHERE tgrelid='investigation.question_review_receipts'::regclass AND NOT tgisinternal")).scalars().all()
        self.assertIn("oi_anchor_text_question_required", prior)
        migrate(self.admin,"upgrade","head")
        # Compare before an application read adds its expected access receipt.
        self.assertEqual(preserved_rows(), captured)
        with self.engine.connect() as conn:
            after = conn.execute(text("SELECT tgname FROM pg_trigger WHERE tgrelid='investigation.question_review_receipts'::regclass AND NOT tgisinternal")).scalars().all()
        self.assertIn("oi_anchor_text_question_required", after)
        self.assertIn("oi_laboratory_review_insert", after)
        with running_server(create_app(self.settings)) as base:
            queue = self.expect(200, base, path)
            original = captured["investigation.laboratory_inspection_snapshots"][0]
            self.assertEqual(queue["snapshot_id"], original["snapshot_id"])
            self.assertEqual(queue["captured_report_sha256"], original["captured_report_sha256"])
            self.expect(201, base, path, self.payload(queue))
        for sql in ("UPDATE investigation.laboratory_review_origins SET report_sha256=report_sha256",
                    "DELETE FROM investigation.laboratory_review_origins",
                    "TRUNCATE investigation.laboratory_review_origins"):
            with self.subTest(sql=sql), self.assertRaisesRegex(DBAPIError,"HISTORY-IMMUTABLE"):
                with self.engine.begin() as conn:
                    conn.execute(text(sql))
        with self.assertRaisesRegex(CommandError,"Stored laboratory review"):
            migrate(self.admin,"downgrade","0025_lab_inspection_snapshots")

    def test_old_reopen_event_cannot_attest_a_new_direct_return(self):
        with running_server(create_app(self.settings)) as base:
            _, _, _, path, queue = self.start(base)
            self.expect(201, base, path, self.payload(queue))
        with self.assertRaisesRegex(DBAPIError, "OI-LAB-REVIEW-REOPEN-REQUIRED"):
            with self.engine.begin() as conn:
                conn.execute(text("""INSERT INTO investigation.laboratory_review_origins
                    SELECT (jsonb_populate_record(NULL::investigation.laboratory_review_origins,
                    to_jsonb(o) || jsonb_build_object('receipt_id','REVIEW-'||repeat('F',32),
                    'source_access_receipt_id','ACCESS-'||repeat('F',32)))).*
                    FROM investigation.laboratory_review_origins o"""))
                conn.execute(text("""INSERT INTO investigation.question_review_receipts
                    SELECT (jsonb_populate_record(NULL::investigation.question_review_receipts,
                    to_jsonb(r) || jsonb_build_object('receipt_id','REVIEW-'||repeat('F',32),
                    'request_key','FORGED-PAST-REOPEN'))).*
                    FROM investigation.question_review_receipts r"""))
        with self.assertRaisesRegex(DBAPIError, "OI-LAB-REVIEW-ORIGIN-REQUIRED"):
            with self.engine.begin() as conn:
                conn.execute(text("""INSERT INTO investigation.question_review_receipts
                    SELECT (jsonb_populate_record(NULL::investigation.question_review_receipts,
                    to_jsonb(r) || jsonb_build_object('receipt_id','REVIEW-'||repeat('E',32),
                    'request_key','FORGED-NO-ORIGIN'))).*
                    FROM investigation.question_review_receipts r"""))

    def test_rights_change_and_audit_failure_roll_back_return_and_reopen_receipts(self):
        from oi_api import evidence_catalog
        with running_server(create_app(self.settings)) as base:
            _, _, _, path, queue = self.start(base)
            before = self.counts()
            original = PostgresPatientRegistry.append_event
            def change_rights(registry, patient, event, **details):
                original(registry, patient, event, **details)
                if event == "investigation.review.returned_for_verification":
                    evidence_catalog._rights_locked(registry, "FICT-RECORD-CONTINUITY", "1",
                        permissions={"metadata":{"store":"allowed","display":"denied"}},
                        revoked=True, superseded=False, recorded_by="FICTIONAL-AUTHOR",
                        reason="Fictional mid-return rights change")
            with patch.object(PostgresPatientRegistry,"append_event",new=change_rights):
                self.expect(404, base, path, self.payload(queue, "LATE-RIGHTS"))
            self.assertEqual(self.counts(), before)
            def fail_audit(registry, patient, event, **details):
                original(registry, patient, event, **details)
                if event == "source.read_authorized":
                    raise RuntimeError("Injected final audit failure")
            with patch.object(PostgresPatientRegistry,"append_event",new=fail_audit):
                self.expect(503, base, path, self.payload(queue, "AUDIT-FAILURE"))
            self.assertEqual(self.counts(), before)

    def test_return_body_rejects_extra_authority_and_wrong_saved_digest(self):
        with running_server(create_app(self.settings)) as base:
            _, _, _, path, queue = self.start(base)
            payload = self.payload(queue)
            self.expect(422, base, path, payload | {"clinical_approval":True})
            self.expect(404, base, path, payload | {"synthetic":False})
            self.expect(409, base, path, payload | {"expected_captured_report_sha256":"0"*64})
            self.expect(409, base, path, payload | {"expected_report_sha256":"0"*64})
            self.assertEqual(self.expect(200, base, path)["receipts"], [])

    def _source_change_during_reopen(self, *, write):
        with running_server(create_app(self.settings)) as base:
            patient, case = self.scope(base)
            status, other, _ = self.ingest(base, patient)
            self.assertEqual(status, 201, other)
            source = self.import_lab(base, case)
            question, _ = self.saved(base, case, source)
            report = question + "/source-citation-report"
            current = self.expect(200, base, report + "/versioned")
            snapshot = self.expect(201, base, report + "/snapshots", {
                "synthetic":True, "request_key":"SNAPSHOT-WITH-OTHER-SOURCE",
                "expected_report_sha256":current["report_sha256"]})
            path = report + "/snapshots/" + snapshot["snapshot_id"] + "/review-returns"
            queue = self.expect(200, base, path)
            self.assertEqual(queue["source_context_state"], "current_unreviewed_question")
            before = self.counts()
            original = PostgresPatientRegistry.append_event
            changed = []
            def supersede_other_source(registry, subject, event, **details):
                original(registry, subject, event, **details)
                if event == "investigation.laboratory_snapshot.reopened":
                    # This state-only transition is allowed by the source owner's
                    # immutable-original guard. The selected lab source stays current.
                    changed.append(registry._execute(
                        "UPDATE clinical_source.source_versions SET state='superseded' WHERE source_id=%s",
                        (other["source_id"],)))
            with patch.object(PostgresPatientRegistry,"append_event",new=supersede_other_source):
                self.expect(404, base, path, self.payload(queue, "RETURN-SOURCE-CHANGED") if write else None)
            self.assertEqual(changed, [1])
            self.assertEqual(self.counts(), before)
            with self.engine.connect() as conn:
                state = conn.execute(text("SELECT state FROM clinical_source.source_versions WHERE source_id=:id"),
                                     {"id":other["source_id"]}).scalar_one()
            self.assertEqual(state, "current")

    def test_source_change_during_reopen_rolls_back_history_read(self):
        self._source_change_during_reopen(write=False)

    def test_source_change_during_reopen_rolls_back_new_return(self):
        self._source_change_during_reopen(write=True)
