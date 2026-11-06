"""Actual HTTP and PostgreSQL exercises for durable laboratory inspection membership."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
import json
from unittest.mock import patch

from alembic.util.exc import CommandError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from http_support import running_server
from oi_api import evidence_catalog, laboratory_snapshot_routes
from oi_api.app import create_app
from oi_api.database import Database
from oi_api.migrate import migrate
from open_intelligence.postgres_registry import PostgresPatientRegistry
from test_patients import TOKEN_A, TOKEN_B, request
from test_source_versions import SourceVersionFixture
import test_laboratory_metadata_citations as catalog


class LaboratoryInspectionSnapshotTests(SourceVersionFixture):
    expect = catalog.LaboratoryMetadataCitationTests.expect
    scope = catalog.LaboratoryMetadataCitationTests.scope
    import_lab = catalog.LaboratoryMetadataCitationTests.import_lab
    prepare = catalog.LaboratoryMetadataCitationTests.prepare
    saved = catalog.LaboratoryMetadataCitationTests.saved
    find = catalog.LaboratoryMetadataCitationTests.find
    command = staticmethod(catalog.LaboratoryMetadataCitationTests.command)

    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend(("question_create", "composer_context_read", "question_read",
            "evidence_read", "evidence_link", "review_packet_read", "laboratory_snapshot_create"))
        self.write()
        self.catalog = Database(self.settings)
        self.addCleanup(self.catalog.close)
        with self.catalog.registry_connection() as connection:
            evidence_catalog.seed_fictional_records(PostgresPatientRegistry(connection),
                evidence_catalog.fictional_records(), recorded_by="FIXTURE-AUTHOR")

    def fixture(self, base):
        _, case = self.scope(base)
        source = self.import_lab(base, case, value=Decimal("4.20"))
        question, anchor = self.saved(base, case, source)
        report = question + "/source-citation-report"
        payload = {"synthetic": True, "request_key": "FICTIONAL-SNAPSHOT-ONE",
                   "expected_report_sha256": self.expect(200, base, report + "/versioned")["report_sha256"]}
        return case, source, question, anchor, report, payload

    def rights(self, *, withdrawn):
        with self.catalog.registry_connection() as conn:
            evidence_catalog.append_rights_decision(PostgresPatientRegistry(conn), "FICT-RECORD-CONTINUITY", "1",
                permissions={"metadata": {"store": "allowed", "display": "denied" if withdrawn else "allowed"}},
                revoked=withdrawn, superseded=False, recorded_by="FICTIONAL-AUTHOR",
                reason="Fictional capture visibility boundary")

    def test_exact_capture_reopen_after_new_links_amendment_and_rights_changes(self):
        with running_server(create_app(self.settings)) as base:
            case, source, question, anchor, report, command = self.fixture(base)
            history = report + "/snapshots"
            self.assertEqual(self.expect(200, base, history)["snapshots"], [])
            start = Barrier(2)
            def capture():
                start.wait(timeout=5)
                return request(base, history, body=command, token=TOKEN_A)[:2]
            with ThreadPoolExecutor(max_workers=2) as pool:
                requests = [pool.submit(capture) for _ in range(2)]
                replay, created = sorted((r.result() for r in requests), key=lambda r: r[0])
            empty = created[1]
            self.assertEqual(created[0], 201)
            self.assertEqual(empty["duplicate"], False)
            self.assertEqual(replay, (200, {**empty, "duplicate": True}))
            self.assertEqual(len(self.expect(200, base, history)["snapshots"]), 1)
            with self.engine.connect() as db:
                events = db.execute(text("""
                    SELECT count(*) FROM identity.identity_domain_events
                    WHERE event_type='investigation.laboratory_snapshot.captured'
                      AND metadata_json->>'snapshot_id'=:snapshot
                """), {"snapshot": empty["snapshot_id"]}).scalar_one()
            self.assertEqual(events, 1)
            # An independently authorized actor can read the history but cannot
            # use the first actor's key to claim an idempotent write receipt.
            for key in ("organization", "actions", "patient_ids"):
                self.creds[1][key] = self.creds[0][key]
            self.write()
            self.assertEqual(len(self.expect(200, base, history, token=TOKEN_B)["snapshots"]), 1)
            self.expect(409, base, history, command, token=TOKEN_B)
            self.assertEqual(self.expect(200, base, history + "/" + empty["snapshot_id"])["inspection"]["report_sha256"],
                             empty["captured_report_sha256"])
            metadata = self.find(base, question, anchor)
            self.expect(201, base, question + "/evidence-links", self.command(metadata, anchor, "CITE-FOR-SNAPSHOT"))
            self.expect(409, base, history, command | {"request_key": "STALE-HASH"})
            current = self.expect(200, base, report + "/versioned")
            full_command = command | {"request_key":"FULL-SNAPSHOT", "expected_report_sha256":current["report_sha256"]}
            self.expect(409, base, history, full_command | {"request_key":command["request_key"]})
            full = self.expect(201, base, history, full_command)
            self.rights(withdrawn=True)
            withdrawn = self.expect(200, base, report + "/versioned")
            self.expect(409, base, history, full_command | {"request_key":"STALE-RIGHTS"})
            masked = self.expect(201, base, history, command | {"request_key":"MASKED-SNAPSHOT",
                                                                 "expected_report_sha256":withdrawn["report_sha256"]})
            redacted = self.expect(200, base, history + "/" + full["snapshot_id"])["inspection"]
            self.assertIsNone(redacted["citations"]["links"][0]["record"])
            self.assertNotIn(metadata["title"], json.dumps(redacted))
            self.assertEqual(self.expect(200, base, history, full_command), full | {"duplicate":True})
            # A direct database write cannot promote a restricted captured link,
            # even if the attacker names the latest legitimate rights decision.
            with self.assertRaisesRegex(DBAPIError, "OI-LAB-SNAPSHOT-RIGHTS"):
                with self.engine.begin() as conn:
                    conn.execute(text("""INSERT INTO investigation.laboratory_inspection_snapshots
                        SELECT (jsonb_populate_record(NULL::investigation.laboratory_inspection_snapshots,
                            to_jsonb(s) || jsonb_build_object('snapshot_id','LAB-SNAPSHOT-'||repeat('E',32),
                            'request_key','FORGED-VISIBILITY','manifest',jsonb_set(s.manifest,'{links,0,status}',
                            to_jsonb('available'::text))))).*
                        FROM investigation.laboratory_inspection_snapshots s WHERE s.snapshot_id=:id"""),
                        {"id":masked["snapshot_id"]})
            self.rights(withdrawn=False)
            was_masked = self.expect(200, base, history + "/" + masked["snapshot_id"])["inspection"]
            self.assertEqual(was_masked["report_sha256"], masked["captured_report_sha256"])
            self.assertIsNone(was_masked["citations"]["links"][0]["record"])
            self.import_lab(base, case, value=Decimal("5.10"), previous=source["source_id"])
            old = self.expect(200, base, history + "/" + empty["snapshot_id"])
            self.assertEqual(old["snapshot"]["captured_source_context_state"], "current_unreviewed_question")
            self.assertEqual(old["inspection"]["reported_result"]["value_text"], "4.20")
            self.assertEqual(old["inspection"]["citations"]["links"], [])
            self.assertEqual(old["inspection"]["citations"]["source_context_state"], "source_reassessment_required")
            self.assertNotEqual(old["inspection"]["report_sha256"], empty["captured_report_sha256"])
            self.assertEqual([item["citation_count"] for item in self.expect(200, base, history)["snapshots"]], [0,1,1])
            self.creds[0]["actions"].remove("laboratory_snapshot_create")
            self.write()
            self.expect(404, base, history, full_command)
            self.expect(200, base, history + "/" + full["snapshot_id"])
            self.creds[0]["actions"].remove("evidence_read")
            self.write()
            self.expect(404, base, history)
            self.expect(404, base, history + "/" + full["snapshot_id"])

    def test_late_denial_rolls_back_prepared_capture_and_audits(self):
        with running_server(create_app(self.settings)) as base:
            _, _, _, _, report, command = self.fixture(base)
            def counts():
                with self.engine.connect() as conn:
                    return tuple(conn.execute(text("""SELECT
                        (SELECT count(*) FROM investigation.laboratory_inspection_snapshots),
                        (SELECT count(*) FROM identity.identity_domain_events)
                    """)).one())
            before = counts()
            encode = laboratory_snapshot_routes._prepare
            def withdraw_after_encoding(*args, **kwargs):
                response = encode(*args, **kwargs)
                self.creds[0]["actions"].remove("laboratory_snapshot_create")
                self.write()
                return response
            with patch.object(laboratory_snapshot_routes, "_prepare", side_effect=withdraw_after_encoding):
                self.expect(404, base, report + "/snapshots", command)
            self.assertEqual(counts(), before)

    def test_0024_upgrade_downgrade_guard_and_foreign_manifest_rejection(self):
        migrate(self.admin, "downgrade", "0024_fhir_coded_results")
        migrate(self.admin, "upgrade", "head")
        with running_server(create_app(self.settings)) as base:
            _, _, _, _, report, command = self.fixture(base)
            self.expect(201, base, report + "/snapshots", command)
        for sql in ("UPDATE investigation.laboratory_inspection_snapshots SET actor=actor",
                    "DELETE FROM investigation.laboratory_inspection_snapshots",
                    "TRUNCATE investigation.laboratory_inspection_snapshots"):
            with self.subTest(sql=sql), self.assertRaisesRegex(DBAPIError, "HISTORY-IMMUTABLE"):
                with self.engine.begin() as conn:
                    conn.execute(text(sql))
        with self.assertRaisesRegex(DBAPIError, "OI-LAB-SNAPSHOT-ANCHOR"):
            with self.engine.begin() as conn:
                conn.execute(text("""INSERT INTO investigation.laboratory_inspection_snapshots
                    SELECT (jsonb_populate_record(NULL::investigation.laboratory_inspection_snapshots,
                        to_jsonb(s) || jsonb_build_object('snapshot_id','LAB-SNAPSHOT-'||repeat('D',32),
                        'request_key','FORGED-ORIGINAL','manifest',jsonb_set(s.manifest,'{anchor,source_version}','99')))).*
                    FROM investigation.laboratory_inspection_snapshots s"""))
        # Even an authentic old receipt and valid identifiers cannot attest
        # a new capture in another transaction, or a fabricated freshness label.
        for state in ("current_unreviewed_question", "source_reassessment_required"):
            with self.subTest(state=state), self.assertRaisesRegex(DBAPIError, "OI-LAB-SNAPSHOT-INSPECTION-REQUIRED"):
                with self.engine.begin() as conn:
                    conn.execute(text("""INSERT INTO investigation.laboratory_inspection_snapshots
                        SELECT (jsonb_populate_record(NULL::investigation.laboratory_inspection_snapshots,
                            to_jsonb(s) || jsonb_build_object('snapshot_id','LAB-SNAPSHOT-'||repeat('F',32),
                            'request_key','FORGED-INSPECTION','manifest',
                            jsonb_set(s.manifest,'{source_context_state}',to_jsonb(CAST(:state AS text)))))).*
                        FROM investigation.laboratory_inspection_snapshots s"""), {"state":state})
        with self.assertRaisesRegex(CommandError, "Stored laboratory inspection snapshots"):
            migrate(self.admin, "downgrade", "0024_fhir_coded_results")
