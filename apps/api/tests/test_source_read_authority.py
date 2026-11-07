"""Real PG16/HTTP disclosure regressions; independently fictional originals."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from unittest.mock import patch

from sqlalchemy import text

from oi_api.app import create_app
from oi_api.sources import PostgresSourceVersions
from open_intelligence.postgres_registry import PostgresPatientRegistry
from http_support import running_server
from test_patients import TOKEN_A, request
from test_source_versions import ORIGINAL, SourceVersionFixture


class SourceReadAuthorityTests(SourceVersionFixture):
    def read_events(self):
        with self.engine.connect() as connection:
            return connection.execute(text(
                "SELECT event_type,metadata_json FROM identity.identity_domain_events "
                "WHERE event_type IN ('source.read_authorized','source.original_read_authorized') ORDER BY id"
            )).all()

    def test_successful_reads_commit_reference_only_receipts_before_disclosure(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            source = self.ingest(base, patient)[1]["source_id"]
            index_status, index, _ = request(base, self.url(patient), token=TOKEN_A)
            raw_status, original, _ = request(base, self.url(patient) + "/" + source, token=TOKEN_A)
            self.assertEqual((index_status, raw_status), (200, 200))
            receipts = [index["access_receipt_id"], original["access_receipt_id"]]
            self.assertEqual(len(set(receipts)), 2)
            self.assertTrue(all(value.startswith("ACCESS-") for value in receipts))
            self.assertEqual(original["original_text"].encode("utf-8"), ORIGINAL.encode("utf-8"))
        events = self.read_events()
        self.assertEqual([row[0] for row in events], ["source.read_authorized", "source.original_read_authorized"])
        self.assertEqual([row[1]["receipt_id"] for row in events], receipts)
        materialized = {key: value for key, value in index.items() if key != "access_receipt_id"}
        digest = hashlib.sha256(json.dumps(materialized, sort_keys=True, ensure_ascii=False,
                                            separators=(",", ":")).encode("utf-8")).hexdigest()
        self.assertEqual(events[0][1]["snapshot_sha256"], digest)
        self.assertEqual(events[1][1]["source_id"], source)
        self.assertEqual(events[1][1]["sha256"], original["sha256"])
        self.assertNotIn("Fictional café", json.dumps([row[1] for row in events]))
        self.assertNotIn(TOKEN_A, json.dumps([row[1] for row in events]))

    def test_read_audit_failure_withholds_both_index_and_original(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            source = self.ingest(base, patient)[1]["source_id"]
            with self.engine.begin() as connection:
                connection.exec_driver_sql("""CREATE FUNCTION identity.reject_read_receipt() RETURNS trigger
                    LANGUAGE plpgsql AS $$ BEGIN
                    IF NEW.event_type IN ('source.read_authorized','source.original_read_authorized') THEN
                    RAISE EXCEPTION 'PRIVATE-READ-AUDIT-FAILURE'; END IF; RETURN NEW; END; $$;""")
                connection.exec_driver_sql("CREATE TRIGGER reject_read_receipt BEFORE INSERT ON identity.identity_domain_events "
                                           "FOR EACH ROW EXECUTE FUNCTION identity.reject_read_receipt()")
            for path in (self.url(patient), self.url(patient) + "/" + source):
                status, result, _ = request(base, path, token=TOKEN_A)
                self.assertEqual((status, result), (503, {"detail": "Patient registry unavailable"}))
            self.assertEqual(self.read_events(), [])

    def test_changed_authority_during_original_read_withholds_bytes_and_receipt(self):
        fetch = PostgresPatientRegistry._fetchone
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            source = self.ingest(base, patient)[1]["source_id"]
            initial = json.loads(json.dumps(self.creds))
            changes = [
                ({"actions": ["patient_read", "source_read"]}, 404),
                ({"patient_ids": []}, 404),
                ({"actor": "ACTOR-CHANGED"}, 404),
                ({"organization": "ORG-CHANGED"}, 404),
                ({"purpose": "research"}, 404),
                ({"expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()}, 401),
            ]
            for change, expected in changes:
                with self.subTest(change=list(change)):
                    self.creds = json.loads(json.dumps(initial))
                    self.write()
                    def alter(registry, sql, params=()):
                        value = fetch(registry, sql, params)
                        if "SELECT raw,sha256" in sql:
                            self.creds[0].update(change)
                            self.write()
                        return value
                    with patch.object(PostgresPatientRegistry, "_fetchone", alter):
                        status, result, _ = request(base, self.url(patient) + "/" + source, token=TOKEN_A)
                    self.assertEqual(status, expected)
                    self.assertNotIn("original_text", result)
                    self.assertEqual(self.read_events(), [])

    def test_revocation_or_provider_failure_during_index_read_withholds_findings(self):
        sources = PostgresSourceVersions._sources
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            self.ingest(base, patient)
            initial = json.loads(json.dumps(self.creds))
            for corrupt, expected in ((False, 401), (True, 503)):
                self.creds = json.loads(json.dumps(initial))
                self.write()
                def withdraw(owner, case):
                    value = sources(owner, case)
                    if corrupt:
                        self.access.write_text("PRIVATE-PROVIDER-FAILURE")
                    else:
                        self.creds.clear()
                        self.write()
                    return value
                with patch.object(PostgresSourceVersions, "_sources", withdraw):
                    status, result, _ = request(base, self.url(patient), token=TOKEN_A)
                self.assertEqual(status, expected)
                self.assertNotIn("source_reported_assertions", result)
                self.assertNotIn("PRIVATE-PROVIDER-FAILURE", json.dumps(result))
                self.assertEqual(self.read_events(), [])

    def test_binding_purpose_must_match_authorized_source_operation(self):
        with running_server(create_app(self.settings)) as base:
            self.creds[0]["purpose"] = "research"
            self.write()
            patient = self.setup_case(base)
            status, imported, _ = self.ingest(base, patient)
            self.assertEqual(status, 201)
            source = imported["source_id"]
            with self.engine.connect() as connection:
                self.assertEqual(connection.execute(text(
                    "SELECT count(*) FROM coordination.source_event_outbox"
                )).scalar_one(), 0)
            self.creds[0]["purpose"] = "operations"
            self.write()
            for path in (self.url(patient), self.url(patient) + "/" + source):
                self.assertEqual(request(base, path, token=TOKEN_A)[0], 404)
            self.assertEqual(self.ingest(base, patient)[0], 404)
            self.assertEqual(self.read_events(), [])
            self.creds[0]["purpose"] = "research"
            self.write()
            self.assertEqual(request(base, self.url(patient), token=TOKEN_A)[0], 200)

    def test_denied_patient_action_and_suspension_do_not_read_sources(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            self.ingest(base, patient)
            self.creds[0]["actions"].remove("source_read")
            self.write()
            with patch.object(PostgresSourceVersions, "_sources", side_effect=AssertionError("must not read")):
                self.assertEqual(request(base, self.url(patient), token=TOKEN_A)[0], 404)
            self.creds[0]["actions"].append("source_read")
            self.write()
            with self.engine.begin() as connection:
                connection.execute(text("UPDATE identity.identity_patients SET status='suspended',revision=revision+1 WHERE patient_id=:p"), {"p": patient})
            with patch.object(PostgresSourceVersions, "_sources", side_effect=AssertionError("must not read")):
                self.assertEqual(request(base, self.url(patient), token=TOKEN_A)[0], 404)
            self.assertEqual(self.read_events(), [])

    def test_self_consistent_wrong_context_and_hash_corruption_are_unavailable(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            for index, corrupted in enumerate(("declared_case", "hash"), start=1):
                source_id = "SRC-" + str(index) * 32
                document = "DOC-CORRUPT-" + str(index)
                raw = ORIGINAL.replace("DOC-ONE", document)
                if corrupted == "declared_case":
                    raw = raw.replace("Patient: CASE-ALPHA", "Patient: CASE-BETA")
                digest = hashlib.sha256(raw.encode("utf-8")).hexdigest() if corrupted != "hash" else "0" * 64
                with self.engine.begin() as connection:
                    connection.execute(text("""INSERT INTO clinical_source.source_versions
                        (source_id,case_id,document_id,version,sha256,raw,kind,event_date,
                         issued_at,specimen_id,state,supersedes_id)
                        VALUES (:id,'CASE-ALPHA',:document,1,:digest,:raw,'pathology',
                         '2026-01-10','2026-01-11','SPECIMEN-ONE','current',NULL)"""),
                        {"id": source_id, "document": document, "digest": digest, "raw": raw.encode("utf-8")})
                status, result, _ = request(base, self.url(patient) + "/" + source_id, token=TOKEN_A)
                self.assertEqual((status, result), (503, {"detail": "Patient registry unavailable"}), corrupted)
                self.assertEqual(self.read_events(), [])
