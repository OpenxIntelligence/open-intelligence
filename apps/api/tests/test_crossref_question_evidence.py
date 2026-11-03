"""DOI-only H1 provenance and authority; independently authored fixtures only."""
import asyncio
from copy import deepcopy
from dataclasses import replace
import importlib
import json
import unittest
from unittest.mock import patch

from sqlalchemy import text
from http_support import running_server
from oi_api.app import create_app
from oi_api.config import Settings, ConfigurationError
from oi_api.request_limits import PatientRequestLimit
from test_patients import TOKEN_A, TOKEN_B, request
from test_source_versions import SourceVersionFixture, AMENDED
import test_source_questions as questions
import test_question_evidence_postgres as existing_evidence

DOI = "10.5555/oi-independent-bibliography"
BODY = {"synthetic": True, "public_doi_acknowledged": True, "doi": DOI}


def projected(title="Independent fictional protocol bibliography", retrieved_at="2026-11-03T16:00:00+00:00"):
    from tools.crossref_metadata import project_work
    return project_work({"status": "ok", "message": {
        "DOI": DOI, "title": [title], "container-title": ["Invented Engineering Journal"],
        "issued": {"date-parts": [[2026]]}, "type": "journal-article",
        "author": [{"given": "Ari", "family": "Invented"}],
        "abstract": "DO NOT RETAIN COPYRIGHTED ABSTRACT",
    }}, DOI, retrieved_at=retrieved_at)


class CrossrefBoundaryTests(unittest.TestCase):
    def test_lookup_default_disabled_and_exact_configuration(self):
        self.assertFalse(Settings.from_env({}).crossref_enabled)
        self.assertTrue(Settings.from_env({"OI_API_CROSSREF_ENABLED": "true"}).crossref_enabled)
        for value in ("1", "yes", "TRUE", "unknown"):
            with self.subTest(value=value), self.assertRaises(ConfigurationError):
                Settings.from_env({"OI_API_CROSSREF_ENABLED": value})
        with self.assertRaises(ConfigurationError):
            Settings(crossref_enabled="true")

    def test_new_lookup_needs_auth_before_provider_or_database(self):
        calls = []
        with running_server(create_app(Settings.from_env({}), crossref_fetcher=lambda doi: calls.append(doi))) as base:
            code, body, _ = request(base, "/v1/patients/PAT-FICTION/cases/CASE-ALPHA/questions/QUESTION-" + "A"*32 + "/evidence-doi", body=BODY)
            self.assertEqual(code, 401)
        self.assertEqual(calls, [])

    def test_exact_acknowledgement_doi_and_unknown_fields(self):
        from oi_api.evidence_contracts import EvidenceDoiLookup
        self.assertEqual(EvidenceDoiLookup(**{**BODY, "doi": DOI.upper()}).doi, DOI)
        for field, value in (("synthetic", 1), ("public_doi_acknowledged", "true"),
                             ("doi", "patient narrative"), ("doi", DOI + "?patient=x"),
                             ("doi", "10.5555/" + "a"*194)):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                EvidenceDoiLookup(**{**BODY, field: value})
        with self.assertRaises(ValueError):
            EvidenceDoiLookup(**BODY, question="Do not forward")

    def test_lookup_body_limit_covers_chunked_payload(self):
        sent = []
        async def app(scope, receive, send): sent.append("UNBOUNDED")
        async def receive(): return {"type": "http.request", "body": b"x"*17000, "more_body": False}
        async def send(message): sent.append(message)
        asyncio.run(PatientRequestLimit(app)({"type": "http", "method": "POST",
            "path": "/v1/patients/PAT-FICTION/cases/CASE-ALPHA/questions/QUESTION-X/evidence-doi",
            "headers": []}, receive, send))
        self.assertNotIn("UNBOUNDED", sent)
        self.assertEqual(sent[0]["status"], 413)

    def test_crossref_native_identity_is_scoped_without_weakening_fictional_contract(self):
        from open_intelligence.evidence_catalog import EvidenceRecord, record_fingerprint
        record = EvidenceRecord(id=DOI, source_kind="crossref", version="a"*64,
            title="Fictional protocol bibliography", terms=(), licence="Factual metadata only",
            link="https://doi.org/10.5555%2Foi-independent-bibliography",
            permissions={"metadata": {"store": "allowed", "display": "allowed"}})
        self.assertEqual(len(record_fingerprint(record)), 64)
        with self.assertRaises(ValueError):
            record_fingerprint(replace(record, source_kind="fictional"))


class CrossrefPostgresTests(SourceVersionFixture):
    world = questions.SourceQuestionHTTPTests.world
    model_path = staticmethod(questions.SourceQuestionHTTPTests.model_path)
    path = staticmethod(questions.SourceQuestionHTTPTests.path)
    preflight = questions.SourceQuestionHTTPTests.preflight
    prepared = questions.SourceQuestionHTTPTests.prepared
    save = questions.SourceQuestionHTTPTests.save
    question = existing_evidence.QuestionEvidencePostgresTests.question
    evidence_path = staticmethod(existing_evidence.QuestionEvidencePostgresTests.evidence_path)
    link = existing_evidence.QuestionEvidencePostgresTests.link
    links = existing_evidence.QuestionEvidencePostgresTests.links
    revise_rights = existing_evidence.QuestionEvidencePostgresTests.revise_rights

    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend(["composer_context_read", "question_create", "question_read",
                                       "evidence_read", "evidence_link", "evidence_lookup"])
        self.write()
        self.settings = replace(self.settings, crossref_enabled=True)
        self.catalog = importlib.import_module("oi_api.evidence_catalog")

    def lookup(self, base, patient, question, *, token=TOKEN_A, case="CASE-ALPHA", body=None):
        return request(base, self.evidence_path(patient, question, case) + "/evidence-doi",
                       token=token, body=BODY if body is None else body)

    def counts(self):
        with self.engine.connect() as c:
            return tuple(c.execute(text("SELECT count(*) FROM investigation."+name)).scalar_one()
                         for name in ("evidence_catalog_records", "crossref_metadata_projections", "crossref_retrieval_receipts", "question_evidence_links"))

    def test_default_off_no_grant_wrong_scope_and_invalid_payload_make_no_provider_call(self):
        calls = []
        fetch = lambda doi: (calls.append(doi), projected())[1]
        with running_server(create_app(replace(self.settings, crossref_enabled=False), crossref_fetcher=fetch)) as base:
            patient, _, question = self.question(base)
            self.assertEqual(self.lookup(base, patient, question)[0], 403)
        with running_server(create_app(self.settings, crossref_fetcher=fetch)) as base:
            self.assertEqual(self.lookup(base, patient, question, token=TOKEN_B)[0], 404)
            self.assertEqual(self.lookup(base, patient, question, case="CASE-BETA")[0], 404)
            self.assertEqual(self.lookup(base, patient, question, body={**BODY, "patient_text": "NEVER SEND"})[0], 422)
            self.creds[0]["actions"].remove("evidence_lookup"); self.write()
            self.assertEqual(self.lookup(base, patient, question)[0], 404)
        self.assertEqual(calls, [])
        self.assertEqual(self.counts(), (0, 0, 0, 0))

    def test_import_retains_only_projection_exact_version_first_retrieval_and_link_retry(self):
        calls = []
        def fetch(doi):
            calls.append(doi)
            return projected(retrieved_at="2026-11-03T16:00:0%d+00:00" % len(calls))
        with running_server(create_app(self.settings, crossref_fetcher=fetch)) as base:
            patient, prepared, question = self.question(base)
            code, result, _ = self.lookup(base, patient, question)
            self.assertEqual(code, 200, result)
            self.assertEqual(result["query"], DOI)
            record = result["records"][0]
            self.assertEqual(record["id"], DOI)
            self.assertEqual(record["source_kind"], "crossref")
            self.assertEqual(record["version"], record["bibliography"]["projection_sha256"])
            self.assertNotIn("COPYRIGHTED", json.dumps(result))
            self.assertEqual(self.counts(), (1, 1, 1, 0))
            self.assertEqual(self.lookup(base, patient, question)[1]["records"][0], record)
            self.assertEqual(self.counts(), (1, 1, 2, 0))
            code, receipt, _ = self.link(base, patient, prepared, question, record)
            self.assertEqual(code, 201)
            self.assertEqual(self.link(base, patient, prepared, question, record)[:2], (200, {**receipt, "duplicate": True}))
            self.assertEqual(self.links(base, patient, question)[1]["links"][0]["record"], record)
        with running_server(create_app(self.settings, crossref_fetcher=fetch)) as base:
            self.assertEqual(self.links(base, patient, question)[1]["links"][0]["record"], record)
        self.assertEqual(calls, [DOI, DOI])

    def test_provider_runs_without_canonical_database_lock_and_source_amendment_denies_commit(self):
        def fetch(doi):
            self.assertEqual(doi, DOI)
            self.assertEqual(self.ingest(base, patient, AMENDED)[0], 201)
            return projected()
        with running_server(create_app(self.settings, crossref_fetcher=fetch)) as base:
            patient, _, question = self.question(base)
            self.assertEqual(self.lookup(base, patient, question)[0], 409)
        self.assertEqual(self.counts(), (0, 0, 0, 0))

    def test_provider_auth_revocation_and_invalid_provider_response_never_persist_or_disclose(self):
        def revoked(doi):
            self.creds[0]["actions"].remove("evidence_lookup"); self.write()
            return projected()
        with running_server(create_app(self.settings, crossref_fetcher=revoked)) as base:
            patient, _, question = self.question(base)
            self.assertEqual(self.lookup(base, patient, question)[0], 404)
        self.assertEqual(self.counts(), (0, 0, 0, 0))
        self.creds[0]["actions"].append("evidence_lookup"); self.write()
        bad = projected(); bad["doi"] = "10.5555/wrong"
        with running_server(create_app(self.settings, crossref_fetcher=lambda doi: bad)) as base:
            code, result, _ = self.lookup(base, patient, question)
            self.assertEqual(code, 502)
            self.assertNotIn("wrong", json.dumps(result))
        self.assertEqual(self.counts(), (0, 0, 0, 0))

    def test_rights_withdrawal_blocks_same_and_changed_version_without_resurrection(self):
        responses = [projected(), projected(title="Changed fictional projection")]
        with running_server(create_app(self.settings, crossref_fetcher=lambda doi: responses[0])) as base:
            patient, prepared, question = self.question(base)
            record = self.lookup(base, patient, question)[1]["records"][0]
            self.assertEqual(self.link(base, patient, prepared, question, record)[0], 201)
            self.revise_rights(DOI, record["version"], revoked=True)
            self.assertEqual(self.lookup(base, patient, question)[0], 404)
            responses[0] = responses[1]
            self.assertEqual(self.lookup(base, patient, question)[0], 404)
            history = self.links(base, patient, question)[1]
            self.assertEqual(history["links"][0]["record"], None)
            self.assertNotIn(record["title"], json.dumps(history))
        self.assertEqual(self.counts(), (1, 1, 1, 1))

    def test_encoding_or_final_authority_failure_rolls_back_metadata_and_retrieval(self):
        from oi_api import evidence_routes
        with running_server(create_app(self.settings, crossref_fetcher=lambda doi: projected())) as base:
            patient, _, question = self.question(base)
            original = evidence_routes._prepare
            def revoke_after_encode(model, value, **kw):
                response = original(model, value, **kw)
                self.creds[0]["actions"].remove("evidence_lookup"); self.write()
                return response
            with patch.object(evidence_routes, "_prepare", side_effect=revoke_after_encode):
                self.assertEqual(self.lookup(base, patient, question)[0], 404)
            self.assertEqual(self.counts(), (0, 0, 0, 0))
            self.creds[0]["actions"].append("evidence_lookup"); self.write()
            with patch.object(evidence_routes, "_prepare", side_effect=ValueError("private encoder")):
                code, result, _ = self.lookup(base, patient, question)
                self.assertEqual(code, 503)
                self.assertNotIn("private", json.dumps(result))
        self.assertEqual(self.counts(), (0, 0, 0, 0))


    def test_changed_projection_preserves_both_snapshots_without_rebinding_saved_link(self):
        state = [projected()]
        with running_server(create_app(self.settings, crossref_fetcher=lambda doi: state[0])) as base:
            patient, prepared, question = self.question(base)
            first = self.lookup(base, patient, question)[1]["records"][0]
            self.assertEqual(self.link(base, patient, prepared, question, first)[0], 201)
            state[0] = projected(title="Second independently authored bibliography snapshot")
            second = self.lookup(base, patient, question)[1]["records"][0]
            self.assertNotEqual(first["version"], second["version"])
            self.assertEqual(self.links(base, patient, question)[1]["links"][0]["record"], first)
            self.assertEqual(self.counts(), (2, 2, 2, 1))
            state[0] = projected(retrieved_at="2026-11-03T18:00:00+00:00")
            returned = self.lookup(base, patient, question)[1]["records"][0]
            self.assertEqual(returned, first)
            self.assertEqual(self.counts(), (2, 2, 3, 1))
            self.assertEqual(self.ingest(base, patient, AMENDED)[0], 201)
            self.assertEqual(self.lookup(base, patient, question)[0], 409)
            history = self.links(base, patient, question)[1]
            self.assertEqual(history["source_context_state"], "source_reassessment_required")
            self.assertEqual(history["links"][0]["record"], first)

    def test_rights_withdrawal_during_unlocked_fetch_and_restored_grant_never_silently_rebind(self):
        state = {"callback": None}
        def fetch(doi):
            if state["callback"]: state["callback"]()
            return projected(title="Changed independently authored provider metadata")
        with running_server(create_app(self.settings, crossref_fetcher=lambda doi: projected())) as base:
            patient, _, question = self.question(base)
            first = self.lookup(base, patient, question)[1]["records"][0]
        def withdraw_then_restore():
            self.revise_rights(DOI, first["version"], revoked=True)
            self.revise_rights(DOI, first["version"], revoked=False)
        state["callback"] = withdraw_then_restore
        with running_server(create_app(self.settings, crossref_fetcher=fetch)) as base:
            self.assertEqual(self.lookup(base, patient, question)[0], 404)
        self.assertEqual(self.counts(), (1, 1, 1, 0))

    def test_concurrent_lookups_share_immutable_snapshot_and_keep_both_honest_receipts(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        gate = Barrier(2)
        def fetch(doi):
            gate.wait(timeout=5)
            return projected()
        with running_server(create_app(self.settings, crossref_fetcher=fetch)) as base:
            patient, _, question = self.question(base)
            with ThreadPoolExecutor(max_workers=2) as pool:
                replies = list(pool.map(lambda _: self.lookup(base, patient, question), range(2)))
            self.assertEqual([reply[0] for reply in replies], [200, 200], replies)
            self.assertEqual(replies[0][1]["records"], replies[1][1]["records"])
        self.assertEqual(self.counts(), (1, 1, 2, 0))

    def test_new_projection_and_receipts_are_immutable_and_populated_downgrade_refuses_erasure(self):
        from alembic.util.exc import CommandError
        from sqlalchemy.exc import DBAPIError
        from oi_api.migrate import migrate
        with running_server(create_app(self.settings, crossref_fetcher=lambda doi: projected())) as base:
            patient, _, question = self.question(base)
            self.assertEqual(self.lookup(base, patient, question)[0], 200)
        for table in ("crossref_metadata_projections", "crossref_retrieval_receipts"):
            for sql in ("UPDATE investigation."+table+" SET acquisition_mode='provider_lookup'",
                        "DELETE FROM investigation."+table,
                        "TRUNCATE investigation."+table+" CASCADE"):
                with self.subTest(sql=sql), self.assertRaises(DBAPIError):
                    with self.engine.begin() as db: db.exec_driver_sql(sql)
        with self.assertRaises(CommandError):
            migrate(self.admin, "downgrade", "0011_evidence_convergence")
        self.assertEqual(self.counts(), (1, 1, 1, 0))

    def test_source_audit_tail_rights_change_withholds_encoded_metadata_and_rolls_back_receipt(self):
        from open_intelligence.postgres_registry import PostgresPatientRegistry
        with running_server(create_app(self.settings, crossref_fetcher=lambda doi: projected())) as base:
            patient, _, question = self.question(base)
            first = self.lookup(base, patient, question)[1]["records"][0]
            append_event = PostgresPatientRegistry.append_event
            state = {"retaining": False}
            def alter_at_tail(registry, subject, event_type, **metadata):
                if event_type == "evidence.metadata.retrieved": state["retaining"] = True
                result = append_event(registry, subject, event_type, **metadata)
                if event_type == "source.read_authorized" and state["retaining"]:
                    self.catalog._rights_locked(registry, DOI, first["version"], permissions={}, revoked=True,
                        superseded=False, recorded_by="FIXTURE-REVIEWER", reason="Synthetic audit-tail revocation")
                return result
            with patch.object(PostgresPatientRegistry, "append_event", alter_at_tail):
                code, body, _ = self.lookup(base, patient, question)
                self.assertEqual(code, 404)
                self.assertNotIn(first["title"], json.dumps(body))
        self.assertEqual(self.counts(), (1, 1, 1, 0))



class CrossrefProjectionContractTests(unittest.TestCase):
    def record(self):
        from oi_api.crossref_contract import selected_projection, digest, catalog_record, bibliography
        from open_intelligence.evidence_catalog import record_fingerprint
        selected = selected_projection(projected(), DOI)
        record = catalog_record(selected, digest(selected))
        return {"id": DOI, "citation": DOI+"@"+record.version, "version": record.version,
                "source_kind": "crossref", "title": record.title, "licence": record.licence,
                "link": record.link, "metadata_sha256": record_fingerprint(record),
                "availability": "metadata_only", "rights_status": "granted",
                "bibliography": bibliography(selected, projected()["source"]["retrieved_at"], "protocol_fixture")}

    def test_genuine_projection_shape_retains_fixture_mode_without_article_or_ai_rights(self):
        from oi_api.evidence_contracts import CrossrefEvidenceMetadata
        value = self.record()
        self.assertEqual(CrossrefEvidenceMetadata(**value).model_dump(mode="json"), value)
        self.assertEqual(value["bibliography"]["acquisition_mode"], "protocol_fixture")
        self.assertNotIn("abstract", json.dumps(value))

    def test_self_consistent_citation_cannot_hide_changed_authors_journal_dates_or_urls(self):
        from oi_api.evidence_contracts import CrossrefEvidenceMetadata
        changes = ({"authors": ["Forged author"]}, {"journal": "Different journal"},
                   {"retrieved_at": "not-a-date"}, {"record_url": "https://evil.invalid/"},
                   {"rights_basis": "https://evil.invalid/license"}, {"year": True},
                   {"projection_sha256": "a"*64}, {"acquisition_mode": "live_approved"},
                   {"authors": ["spoof\u202e"]}, {"unexpected_abstract": "COPYRIGHTED"})
        for change in changes:
            value = self.record(); value["bibliography"].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                CrossrefEvidenceMetadata(**value)

    def test_retrieval_time_is_not_publication_version_but_changed_projection_is(self):
        from oi_api.crossref_contract import selected_projection, digest
        first = selected_projection(projected(), DOI)
        again = selected_projection(projected(retrieved_at="2026-11-03T17:00:00+00:00"), DOI)
        changed = selected_projection(projected(title="Changed independently authored title"), DOI)
        self.assertEqual(digest(first), digest(again))
        self.assertNotEqual(digest(first), digest(changed))

    def test_injected_provider_must_honestly_identify_protocol_fixture_mode(self):
        with self.assertRaises(ValueError):
            create_app(Settings.from_env({}), crossref_fetcher=lambda doi: projected(), crossref_acquisition_mode="provider_lookup")
        with self.assertRaises(ValueError):
            create_app(Settings.from_env({}), crossref_acquisition_mode="protocol_fixture")
