"""Real PostgreSQL evidence links on the existing canonical H1 source question."""
from concurrent.futures import ThreadPoolExecutor
import importlib
import json
import unittest
from unittest.mock import patch
from threading import Barrier

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from alembic.util.exc import CommandError

from http_support import running_server
from oi_api.app import create_app
from oi_api.database import Database
from oi_api.migrate import migrate
from open_intelligence.postgres_registry import PostgresPatientRegistry
from test_patients import TOKEN_A, TOKEN_B, request
from test_source_versions import SourceVersionFixture, ORIGINAL, AMENDED
import test_source_questions as questions


class QuestionEvidencePostgresTests(SourceVersionFixture):
    world = questions.SourceQuestionHTTPTests.world
    model_path = staticmethod(questions.SourceQuestionHTTPTests.model_path)
    path = staticmethod(questions.SourceQuestionHTTPTests.path)
    preflight = questions.SourceQuestionHTTPTests.preflight
    prepared = questions.SourceQuestionHTTPTests.prepared
    save = questions.SourceQuestionHTTPTests.save

    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend([
            "composer_context_read", "question_create", "question_read",
            "evidence_read", "evidence_link",
        ])
        self.write()
        self.catalog = importlib.import_module("oi_api.evidence_catalog")
        self.seed()

    def seed(self, records=None):
        with Database(self.settings).registry_connection() as connection:
            registry = PostgresPatientRegistry(connection, lambda *args: False)
            self.catalog.seed_fictional_records(
                registry, records if records is not None else self.catalog.fictional_records(),
                recorded_by="FIXTURE-AUTHOR",
            )

    def revise_rights(self, record_id="FICT-RECORD-CONTINUITY", version="1", **changes):
        with Database(self.settings).registry_connection() as connection:
            registry = PostgresPatientRegistry(connection, lambda *args: False)
            self.catalog.append_rights_decision(
                registry, record_id, version, recorded_by="FIXTURE-REVIEWER",
                permissions=changes.pop("permissions", {"metadata": {"store": "allowed", "display": "allowed"}}),
                revoked=changes.pop("revoked", False), superseded=changes.pop("superseded", False),
                reason="Independent synthetic rights scenario", **changes,
            )

    def question(self, base):
        patient = self.setup_case(base)
        source = self.ingest(base, patient)[1]["source_id"]
        prepared = self.prepared(base, patient, source)
        code, saved, _ = self.save(base, patient, prepared)
        self.assertEqual(code, 201)
        return patient, prepared, saved["question_id"]

    @staticmethod
    def evidence_path(patient, question, case="CASE-ALPHA"):
        return f"/v1/patients/{patient}/cases/{case}/questions/{question}"

    def search(self, base, patient, question, query="continuity", **kwargs):
        return request(base, self.evidence_path(patient, question) + "/evidence-search",
                       token=kwargs.pop("token", TOKEN_A),
                       body={"synthetic": True, "query": query, **kwargs})

    def link(self, base, patient, prepared, question, record, **overrides):
        payload = {
            "synthetic": True, "request_key": "LINK-ONE", "citation": record["citation"],
            "expected_metadata_sha256": record["metadata_sha256"],
            "source_snapshot_contract": "oi.pg-source-world-model/1",
            "expected_source_snapshot_sha256": prepared["source_snapshot_sha256"],
            "expected_preflight_sha256": prepared["preflight_sha256"],
        }
        payload.update(overrides)
        return request(base, self.evidence_path(patient, question) + "/evidence-links",
                       token=TOKEN_A, body=payload)

    def links(self, base, patient, question, case="CASE-ALPHA", token=TOKEN_A):
        return request(base, self.evidence_path(patient, question, case) + "/evidence-links", token=token)

    def test_search_link_exact_retry_restart_and_amended_history(self):
        with running_server(create_app(self.settings)) as base:
            patient, prepared, question = self.question(base)
            code, found, _ = self.search(base, patient, question)
            self.assertEqual(code, 200)
            self.assertEqual(len(found["records"]), 1)
            record = found["records"][0]
            self.assertEqual(record["citation"], "FICT-RECORD-CONTINUITY@1")
            self.assertEqual(record["availability"], "metadata_only")
            self.assertFalse(found["content_appraised"])
            self.assertFalse(found["model_executed"])
            code, linked, _ = self.link(base, patient, prepared, question, record)
            self.assertEqual((code, linked["duplicate"]), (201, False))
            self.assertEqual(self.link(base, patient, prepared, question, record)[:2],
                             (200, {**linked, "duplicate": True}))
            history = self.links(base, patient, question)[1]
            self.assertEqual(history["links"][0]["record"], record)
            self.assertEqual(self.ingest(base, patient, AMENDED)[0], 201)
            stale = self.links(base, patient, question)[1]
            self.assertEqual(stale["source_context_state"], "source_reassessment_required")
            self.assertEqual(stale["links"], history["links"])
            self.assertEqual(self.link(base, patient, prepared, question, record,
                                       request_key="NEW-AFTER-AMENDMENT")[0], 409)
        with running_server(create_app(self.settings)) as restarted:
            self.assertEqual(self.links(restarted, patient, question)[1]["links"], history["links"])

    def test_explicit_rights_revocation_redacts_cached_metadata_but_preserves_link_identity(self):
        with running_server(create_app(self.settings)) as base:
            patient, prepared, question = self.question(base)
            record = self.search(base, patient, question)[1]["records"][0]
            linked = self.link(base, patient, prepared, question, record)[1]
            self.revise_rights(revoked=True)
            self.assertEqual(self.search(base, patient, question)[1]["records"], [])
            history = self.links(base, patient, question)[1]
            row = history["links"][0]
            self.assertEqual((row["link_id"], row["citation"]), (linked["link_id"], record["citation"]))
            self.assertEqual((row["status"], row["record"]), ("rights_restricted", None))
            self.assertNotIn(record["title"], json.dumps(history))
            self.assertEqual(self.link(base, patient, prepared, question, record,
                                       request_key="LINK-REVOKED")[0], 404)

    def test_unknown_display_and_store_rights_never_reveal_matching_titles(self):
        with running_server(create_app(self.settings)) as base:
            patient, _, question = self.question(base)
            for permissions in ({}, {"metadata": {"store": "allowed"}},
                                {"metadata": {"display": "allowed"}}):
                with self.subTest(permissions=permissions):
                    self.revise_rights(permissions=permissions)
                    code, result, _ = self.search(base, patient, question)
                    self.assertEqual((code, result["records"]), (200, []))

    def test_scoped_metadata_and_question_cannot_cross_patient_or_organization(self):
        with running_server(create_app(self.settings)) as base:
            patient, _, question = self.question(base)
            records = self.catalog.fictional_records()
            from dataclasses import replace
            self.seed([replace(records[0], id="FICT-SCOPED-OTHER", title="Forbidden scope canary",
                               terms=("forbidden",), case_id="CASE-BETA", organization="ORG-BETA")])
            self.assertEqual(self.search(base, patient, question, "forbidden")[1]["records"], [])
            self.assertEqual(self.links(base, patient, question, token=TOKEN_B)[0], 404)
            self.assertEqual(self.links(base, patient, question, case="CASE-BETA")[0], 404)
            other = self.setup_case(base, case="CASE-GAMMA", key="CREATE-GAMMA", source_subject="SUBJECT-GAMMA")
            self.assertEqual(self.links(base, other, question, case="CASE-GAMMA")[0], 404)

    def test_explicit_grants_bad_citation_hash_and_changed_retry_are_denied(self):
        with running_server(create_app(self.settings)) as base:
            patient, prepared, question = self.question(base)
            record = self.search(base, patient, question)[1]["records"][0]
            self.assertEqual(self.link(base, patient, prepared, question, record,
                                       expected_metadata_sha256="0" * 64)[0], 409)
            self.assertEqual(self.link(base, patient, prepared, question, record,
                                       citation="FICT-RECORD-CONTINUITY@999")[0], 404)
            self.assertEqual(self.link(base, patient, prepared, question, record)[0], 201)
            self.assertEqual(self.link(base, patient, prepared, question, record,
                                       expected_metadata_sha256="1" * 64)[0], 409)
            self.creds[0]["actions"].remove("evidence_read"); self.write()
            self.assertEqual(self.search(base, patient, question)[0], 404)
            self.assertEqual(self.links(base, patient, question)[0], 404)

    def test_concurrent_exact_link_retry_creates_one_link_and_one_event(self):
        with running_server(create_app(self.settings)) as base:
            patient, prepared, question = self.question(base)
            record = self.search(base, patient, question)[1]["records"][0]
            with ThreadPoolExecutor(max_workers=2) as pool:
                replies = list(pool.map(lambda _: self.link(base, patient, prepared, question, record), range(2)))
            self.assertEqual(sorted(reply[0] for reply in replies), [200, 201])
            self.assertEqual(len({reply[1]["link_id"] for reply in replies}), 1)
            self.assertEqual(len(self.links(base, patient, question)[1]["links"]), 1)
            with self.engine.connect() as connection:
                self.assertEqual(connection.execute(text(
                    "SELECT count(*) FROM identity.identity_domain_events "
                    "WHERE event_type='evidence.citation.linked'"
                )).scalar_one(), 1)

    def test_concurrent_changed_intents_in_two_cases_return_conflict_without_duplicate_effect(self):
        with running_server(create_app(self.settings)) as base:
            patient, first, q1 = self.question(base)
            record = self.search(base, patient, q1)[1]["records"][0]
            self.assertEqual(request(base, f"/v1/patients/{patient}/case-bindings", token=TOKEN_A, body={
                "synthetic": True, "case_id": "CASE-BETA", "source_organization": "ORG-INSTITUTION",
                "source_system": "SYS-SYNTH", "source_subject_ref": "SUBJECT-BETA", "review_ref": "REVIEW-BETA",
            })[0], 201)
            source = self.ingest(base, patient, ORIGINAL.replace("CASE-ALPHA", "CASE-BETA"), case="CASE-BETA")[1]["source_id"]
            world = request(base, self.model_path(patient, "CASE-BETA"), token=TOKEN_A)[1]
            second = self.preflight(base, patient, source, world["snapshot_fingerprint"], case="CASE-BETA")[1]
            q2 = self.save(base, patient, second, case="CASE-BETA", request_key="QUESTION-BETA")[1]["question_id"]
            gate = Barrier(2)
            fetchone = PostgresPatientRegistry._fetchone
            def both_absent(registry, sql, values=()):
                result = fetchone(registry, sql, values)
                if ("SELECT link_id,intent_sha256" in sql and "request_key" in sql
                        and values[-1] == "RACING-INTENT" and result is None):
                    gate.wait(timeout=5)
                return result
            def submit(args):
                qid, case, prepared = args
                return request(base, self.evidence_path(patient, qid, case) + "/evidence-links", token=TOKEN_A, body={
                    "synthetic": True, "request_key": "RACING-INTENT", "citation": record["citation"],
                    "expected_metadata_sha256": record["metadata_sha256"],
                    "source_snapshot_contract": "oi.pg-source-world-model/1",
                    "expected_source_snapshot_sha256": prepared["source_snapshot_sha256"],
                    "expected_preflight_sha256": prepared["preflight_sha256"],
                })
            with patch.object(PostgresPatientRegistry, "_fetchone", both_absent), ThreadPoolExecutor(max_workers=2) as pool:
                replies = list(pool.map(submit, ((q1, "CASE-ALPHA", first), (q2, "CASE-BETA", second))))
            self.assertEqual(sorted(value[0] for value in replies), [201, 409])
            with self.engine.connect() as connection:
                self.assertEqual(connection.execute(text(
                    "SELECT count(*) FROM investigation.question_evidence_links"
                )).scalar_one(), 1)

    def test_prepared_json_and_mid_response_authority_failure_roll_back_link(self):
        from oi_api import evidence_routes
        with running_server(create_app(self.settings)) as base:
            patient, prepared, question = self.question(base)
            record = self.search(base, patient, question)[1]["records"][0]
            with patch.object(evidence_routes, "_prepare", side_effect=ValueError("synthetic encoder failure")):
                code, data, _ = self.link(base, patient, prepared, question, record)
                self.assertEqual(code, 503)
                self.assertNotIn("encoder", json.dumps(data))
            self.assertEqual(self.links(base, patient, question)[1]["links"], [])
            original = evidence_routes._prepare
            def revoke_after_prepare(model, value, **kwargs):
                response = original(model, value, **kwargs)
                self.creds[0]["actions"].remove("evidence_link"); self.write()
                return response
            with patch.object(evidence_routes, "_prepare", side_effect=revoke_after_prepare):
                self.assertEqual(self.link(base, patient, prepared, question, record)[0], 404)
            self.assertEqual(self.links(base, patient, question)[1]["links"], [])

    def test_metadata_and_link_history_are_immutable_and_wrong_version_terms_do_not_match(self):
        from dataclasses import replace
        first = self.catalog.fictional_records()[0]
        self.seed([replace(first, version="2", title="New unrelated topic", terms=("unrelated",))])
        with running_server(create_app(self.settings)) as base:
            patient, prepared, question = self.question(base)
            hits = self.search(base, patient, question, "continuity")[1]["records"]
            self.assertEqual([item["version"] for item in hits], ["1"])
            self.link(base, patient, prepared, question, hits[0])
        for statement in (
            "UPDATE investigation.evidence_catalog_records SET title='changed'",
            "DELETE FROM investigation.question_evidence_links",
            "UPDATE investigation.evidence_rights_decisions SET revoked=true",
        ):
            with self.subTest(statement=statement), self.assertRaises(DBAPIError):
                with self.engine.begin() as connection:
                    connection.execute(text(statement))

    def test_reseeding_never_restores_revoked_rights_and_populated_downgrade_is_blocked(self):
        self.revise_rights(revoked=True)
        self.seed()
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text(
                "SELECT revoked FROM investigation.evidence_rights_decisions "
                "WHERE record_id='FICT-RECORD-CONTINUITY' ORDER BY revision DESC LIMIT 1"
            )).scalar_one(), True)
            before = connection.execute(text("SELECT count(*) FROM investigation.evidence_rights_decisions")).scalar_one()
        with self.assertRaises(CommandError):
            migrate(self.admin, "downgrade", "0009_question_followthrough")
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT version_num FROM public.alembic_version")).scalar_one(),
                             "0010_question_evidence")
            self.assertEqual(connection.execute(text("SELECT count(*) FROM investigation.evidence_rights_decisions")).scalar_one(), before)

    def test_audit_failure_withholds_disclosure_and_rolls_back_citation(self):
        with running_server(create_app(self.settings)) as base:
            patient, prepared, question = self.question(base)
            record = self.search(base, patient, question)[1]["records"][0]
            append_event = PostgresPatientRegistry.append_event
            def reject_source_receipt(registry, subject, event_type, **metadata):
                if event_type == "source.read_authorized":
                    raise RuntimeError("Private synthetic receipt failure")
                return append_event(registry, subject, event_type, **metadata)
            with patch.object(PostgresPatientRegistry, "append_event", reject_source_receipt):
                for operation in (
                    lambda: self.search(base, patient, question),
                    lambda: self.links(base, patient, question),
                    lambda: self.link(base, patient, prepared, question, record),
                ):
                    code, result, _ = operation()
                    self.assertEqual(code, 503)
                    self.assertNotIn(record["title"], json.dumps(result))
                    self.assertNotIn("Private", json.dumps(result))
            self.assertEqual(self.links(base, patient, question)[1]["links"], [])

    def test_rights_change_after_source_audit_withholds_prepared_json_and_rolls_back(self):
        with running_server(create_app(self.settings)) as base:
            patient, prepared, question = self.question(base)
            record = self.search(base, patient, question)[1]["records"][0]
            append_event = PostgresPatientRegistry.append_event
            def revise_after_audit(registry, subject, event_type, **metadata):
                result = append_event(registry, subject, event_type, **metadata)
                if event_type == "source.read_authorized":
                    self.catalog._rights_locked(registry, "FICT-RECORD-CONTINUITY", "1",
                        permissions={}, revoked=True, superseded=False, recorded_by="FIXTURE-AUDIT-TAIL",
                        reason="Synthetic same-transaction callback after prepared disclosure")
                return result
            # The first search has a rights dependency. An empty history has
            # none, so use search and fresh link paths for this regression.
            with patch.object(PostgresPatientRegistry, "append_event", revise_after_audit):
                for operation in (
                    lambda: self.search(base, patient, question),
                    lambda: self.link(base, patient, prepared, question, record),
                ):
                    code, result, _ = operation()
                    self.assertEqual(code, 404)
                    self.assertNotIn(record["title"], json.dumps(result))
            self.assertEqual(self.links(base, patient, question)[1]["links"], [])
            self.assertEqual(self.search(base, patient, question)[1]["records"], [record])

    def test_catalog_disclosure_holds_rights_row_lock_through_actual_encoding(self):
        from oi_api import evidence_routes
        with running_server(create_app(self.settings)) as base:
            patient, _, question = self.question(base)
            prepare = evidence_routes._prepare
            inspected = []
            def inspect_lock(model, value, **options):
                response = prepare(model, value, **options)
                with self.assertRaises(DBAPIError) as blocked:
                    with self.engine.begin() as connection:
                        connection.execute(text("SELECT record_id FROM investigation.evidence_catalog_records "
                            "WHERE record_id='FICT-RECORD-CONTINUITY' AND version='1' FOR UPDATE NOWAIT"))
                self.assertEqual(blocked.exception.orig.args[0]["C"], "55P03")
                inspected.append(True)
                return response
            with patch.object(evidence_routes, "_prepare", inspect_lock):
                self.assertEqual(self.search(base, patient, question)[0], 200)
            self.assertEqual(inspected, [True])
