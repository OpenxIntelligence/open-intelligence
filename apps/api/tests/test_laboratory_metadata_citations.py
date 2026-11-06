"""Real PostgreSQL/HTTP proof for fictional metadata cited by an exact lab question."""
from concurrent.futures import ThreadPoolExecutor
import json
from unittest.mock import patch

from sqlalchemy import text

from http_support import running_server
from oi_api.app import create_app
from oi_api import evidence_catalog
from oi_api.database import Database
from open_intelligence.postgres_registry import PostgresPatientRegistry
from test_laboratory_fhir_r4 import OBS
from test_patients import TOKEN_A, TOKEN_B, request
from test_source_versions import SourceVersionFixture
import test_durable_laboratory_questions as laboratory


SEARCH = {"synthetic": True, "query": "continuity"}


class LaboratoryMetadataCitationTests(SourceVersionFixture):
    expect = laboratory.DurableLaboratoryQuestionHTTPTests.expect
    scope = laboratory.DurableLaboratoryQuestionHTTPTests.scope
    import_lab = laboratory.DurableLaboratoryQuestionHTTPTests.import_lab
    prepare = laboratory.DurableLaboratoryQuestionHTTPTests.prepare

    def setUp(self):
        super().setUp()
        for actor in self.creds:
            actor["actions"].extend(("question_read", "question_create", "composer_context_read",
                                     "evidence_read", "evidence_link"))
        self.write()
        self.catalog_db = Database(self.settings)
        self.addCleanup(self.catalog_db.close)
        with self.catalog_db.registry_connection() as conn:
            evidence_catalog.seed_fictional_records(
                PostgresPatientRegistry(conn), evidence_catalog.fictional_records(), recorded_by="FIXTURE-AUTHOR")

    def saved(self, base, case_path, source, reference=OBS, key="QUESTION-ONE"):
        preview, command = self.prepare(base, case_path, source["source_id"], reference)
        qid = self.expect(201, base, case_path + laboratory.LAB_HISTORY,
                          {**command, "request_key": key})["question_id"]
        anchor = {"source_id": source["source_id"], "source_version": source["version"],
                  "source_sha256": source["original_sha256"], "observation_reference": reference,
                  "source_snapshot_sha256": preview["source_snapshot_sha256"],
                  "preflight_sha256": preview["preflight_sha256"]}
        return case_path + laboratory.LAB_HISTORY + "/" + qid, anchor

    def find(self, base, path, anchor):
        found = self.expect(200, base, path + "/evidence-search", SEARCH)
        self.assertEqual(found["question_id"], path.split("/")[-1])
        self.assertEqual(found["question_anchor"], anchor)
        self.assertEqual(found["source_context_state"], "current_unreviewed_question")
        self.assertTrue(found["synthetic"])
        self.assertTrue(all(found[k] is False for k in ("model_executed", "content_appraised", "clinical_approval")))
        record, = found["records"]
        self.assertEqual((record["citation"], record["availability"]), ("FICT-RECORD-CONTINUITY@1", "metadata_only"))
        return record

    @staticmethod
    def command(record, anchor, key):
        return {"synthetic": True, "request_key": key, "citation": record["citation"],
                "expected_metadata_sha256": record["metadata_sha256"],
                "source_snapshot_contract": "oi.pg-source-world-model/1",
                "expected_source_snapshot_sha256": anchor["source_snapshot_sha256"],
                "expected_preflight_sha256": anchor["preflight_sha256"]}

    def counts(self):
        with self.engine.connect() as c:
            return tuple(c.execute(text("""SELECT
                (SELECT count(*) FROM investigation.question_evidence_links),
                (SELECT count(*) FROM investigation.laboratory_citation_anchors),
                (SELECT count(*) FROM identity.identity_domain_events WHERE event_type='evidence.citation.linked'),
                (SELECT count(*) FROM identity.identity_domain_events)""")).one())

    def test_parallel_exact_link_binds_one_observation_and_replays_after_amendment(self):
        with running_server(create_app(self.settings)) as base:
            _, case = self.scope(base)
            v1 = self.import_lab(base, case)
            path, anchor = self.saved(base, case, v1)
            sibling, sibling_anchor = self.saved(base, case, v1, laboratory.ABSENT, "SIBLING-QUESTION")
            metadata = self.find(base, path, anchor)
            cmd = self.command(metadata, anchor, "CITE-SYNTHETIC-METADATA")
            self.assertEqual(self.find(base, sibling, sibling_anchor), metadata)
            # Same original bytes and snapshot, different Observation preflight.
            self.expect(409, base, sibling + "/evidence-links", cmd)
            self.assertEqual(self.counts()[:3], (0, 0, 0))
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(request, base, path + "/evidence-links", token=TOKEN_A, body=cmd)
                           for _ in range(2)]
                responses = sorted((f.result()[:2] for f in futures), key=lambda r: r[0])
            self.assertEqual([r[0] for r in responses], [200, 201])
            linked = responses[1][1]
            self.assertFalse(linked["duplicate"])
            self.assertEqual(responses[0][1], {**linked, "duplicate": True})
            self.assertEqual(self.counts()[:3], (1, 1, 1))
            self.expect(409, base, sibling + "/evidence-links", self.command(metadata, sibling_anchor, cmd["request_key"]))
            self.assertEqual(self.expect(200, base, sibling + "/evidence-links")["links"], [])
            first = self.expect(200, base, path + "/evidence-links")
            self.assertEqual(first["question_anchor"], anchor)
            entry, = first["links"]
            self.assertEqual((entry["link_id"], entry["record"]), (linked["link_id"], metadata))
            v2 = self.import_lab(base, case, value=1, previous=v1["source_id"])
            for route, payload in (("/evidence-search", SEARCH),
                                   ("/evidence-links", {**cmd, "request_key": "STALE-LINK-NEW-KEY"})):
                self.expect(409, base, path + route, payload)
            historical = self.expect(200, base, path + "/evidence-links")
            self.assertEqual(historical["source_context_state"], "source_reassessment_required")
            self.assertEqual(historical["question_anchor"], anchor)
            self.assertEqual(historical["links"], [entry])
            self.assertEqual(self.expect(200, base, path + "/evidence-links", cmd), {**linked, "duplicate": True})
            current_path, current_anchor = self.saved(base, case, v2, key="QUESTION-AMENDED")
            current = self.expect(200, base, current_path + "/evidence-links")
            self.assertEqual(current["question_anchor"], current_anchor)
            self.assertEqual(current["links"], [])
            self.assertEqual(self.counts()[:3], (1, 1, 1))

    def test_withdrawn_catalog_rights_redact_history_and_refuse_exact_write_receipt(self):
        with running_server(create_app(self.settings)) as base:
            _, case = self.scope(base)
            path, anchor = self.saved(base, case, self.import_lab(base, case))
            record = self.find(base, path, anchor)
            cmd = self.command(record, anchor, "RIGHTS-CITATION")
            linked = self.expect(201, base, path + "/evidence-links", cmd)
            original, = self.expect(200, base, path + "/evidence-links")["links"]
            with self.catalog_db.registry_connection() as conn:
                evidence_catalog.append_rights_decision(
                    PostgresPatientRegistry(conn), record["id"], record["version"],
                    permissions={}, revoked=True, superseded=False, recorded_by="FIXTURE-REVIEWER",
                    reason="Withdraw the independently fictional metadata display permission")
            found = self.expect(200, base, path + "/evidence-search", SEARCH)
            history = self.expect(200, base, path + "/evidence-links")
            self.assertEqual(history["question_anchor"], anchor)
            self.assertEqual(found["records"], [])
            row, = history["links"]
            self.assertEqual(row, {**original, "record": None, "status": "rights_restricted"})
            self.assertEqual(row["link_id"], linked["link_id"])
            before = self.counts()
            for key in (cmd["request_key"], "NEW-RESTRICTED-LINK"):
                refused = self.expect(404, base, path + "/evidence-links", {**cmd, "request_key": key})
                self.assertEqual(set(refused), {"detail"})
            self.assertEqual(self.counts(), before)
            for response in (history, found, refused):
                self.assertNotIn(record["title"], json.dumps(response))
                self.assertNotIn(record["link"], json.dumps(response))

    def test_patient_case_organization_and_each_current_grant_gate_disclosure_and_exact_replay(self):
        with running_server(create_app(self.settings)) as base:
            pid, case = self.scope(base)
            path, anchor = self.saved(base, case, self.import_lab(base, case))
            record = self.find(base, path, anchor)
            cmd = self.command(record, anchor, "ACCESS-CITATION")
            self.expect(201, base, path + "/evidence-links", cmd)
            self.creds[1]["patient_ids"] = [pid]
            self.write()
            reads = (("/evidence-search", SEARCH), ("/evidence-links", None))
            operations = (*reads, ("/evidence-links", cmd))
            def denied(prefix, token=TOKEN_A, operations=operations):
                before = self.counts()
                for suffix, fields in operations:
                    refused = self.expect(404, base, prefix + suffix, fields, token)
                    self.assertEqual(set(refused), {"detail"})
                    self.assertNotIn(record["title"], json.dumps(refused))
                self.assertEqual(self.counts(), before)

            denied(path, TOKEN_B)
            denied(path, operations=[(suffix + "?source=untrusted", payload) for suffix, payload in operations])
            denied(path.replace(laboratory.CASE, "CASE-WRONG"))
            for grant in ("patient_read", "source_read", "question_read", "evidence_read", "evidence_link"):
                with self.subTest(grant=grant):
                    self.creds[0]["actions"].remove(grant)
                    self.write()
                    if grant == "evidence_link":
                        denied(path, operations=(("/evidence-links", cmd),))
                        self.assertEqual(self.find(base, path, anchor), record)
                    else:
                        denied(path)
                    self.creds[0]["actions"].append(grant)
                    self.write()
            other_pid = self.setup_case(base, token=TOKEN_A, case="CASE-OTHER", key="OTHER-PATIENT", source_subject="OTHER-SUBJECT")
            denied(path.replace(laboratory.CASE, "CASE-OTHER").replace(pid, other_pid))
            self.expect(200, base, f"/v1/patients/{pid}/case-bindings/{laboratory.CASE}/revoke",
                        {"synthetic": True, "reason": "Fictional source binding withdrawn"})
            denied(path)

    def test_rights_revocation_after_source_receipt_withholds_output_and_rolls_back_new_link(self):
        with running_server(create_app(self.settings)) as base:
            _, case = self.scope(base)
            path, anchor = self.saved(base, case, self.import_lab(base, case))
            record = self.find(base, path, anchor)
            cmd = self.command(record, anchor, "AUDIT-TAIL-LINK")
            initial = self.counts()
            appended = PostgresPatientRegistry.append_event
            calls = []
            def withdraw_on_receipt(registry, pid, event_type, **data):
                appended(registry, pid, event_type, **data)
                if event_type == "source.read_authorized":
                    evidence_catalog._rights_locked(
                        registry, record["id"], record["version"], permissions={}, revoked=True,
                        superseded=False, recorded_by="FIXTURE-REVIEWER", reason="Fictional audit tail failure")
                    calls.append(event_type)
            for suffix, payload in (("/evidence-search", SEARCH), ("/evidence-links", cmd)):
                with patch.object(PostgresPatientRegistry, "append_event", withdraw_on_receipt):
                    result = self.expect(404, base, path + suffix, payload)
                self.assertEqual(set(result), {"detail"})
                self.assertEqual(self.counts(), initial)
            self.assertEqual(calls, ["source.read_authorized"] * 2)
            self.assertEqual(self.find(base, path, anchor), record)
            self.expect(201, base, path + "/evidence-links", cmd)
            self.assertEqual(self.counts()[:3], (1, 1, 1))
