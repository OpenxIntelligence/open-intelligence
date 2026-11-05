"""Read the actual saved laboratory source at two time points with current citation rights."""
from decimal import Decimal
import json
from unittest.mock import patch

from sqlalchemy import text

from http_support import running_server
from oi_api import evidence_catalog, laboratory_citation_report_routes
from oi_api.app import create_app
from oi_api.database import Database
from open_intelligence.postgres_registry import PostgresPatientRegistry
from test_patients import TOKEN_B
from test_source_versions import SourceVersionFixture
import test_durable_laboratory_questions as lab
import test_laboratory_metadata_citations as catalog


class LaboratoryCitationInspectionTests(SourceVersionFixture):
    expect = catalog.LaboratoryMetadataCitationTests.expect
    scope = catalog.LaboratoryMetadataCitationTests.scope
    import_lab = catalog.LaboratoryMetadataCitationTests.import_lab
    prepare = catalog.LaboratoryMetadataCitationTests.prepare
    saved = catalog.LaboratoryMetadataCitationTests.saved
    find = catalog.LaboratoryMetadataCitationTests.find
    command = staticmethod(catalog.LaboratoryMetadataCitationTests.command)
    counts = catalog.LaboratoryMetadataCitationTests.counts

    def setUp(self):
        super().setUp()
        for principal in self.creds:
            principal["actions"].extend(("question_create", "composer_context_read", "question_read",
                                         "evidence_read", "evidence_link", "review_packet_read"))
        self.write()
        self.catalog_db = Database(self.settings)
        self.addCleanup(self.catalog_db.close)
        with self.catalog_db.registry_connection() as connection:
            evidence_catalog.seed_fictional_records(PostgresPatientRegistry(connection),
                evidence_catalog.fictional_records(), recorded_by="FIXTURE-AUTHOR")

    def coded_source(self, base, case, coding, key, previous=None):
        bundle = json.loads(lab.two_observations(0))
        first = lab.resource(bundle, "Observation")
        del first["valueQuantity"]
        first["valueCodeableConcept"] = {"coding": [coding]}
        raw = lab.encode(bundle).decode()
        preview = self.expect(200, base, case + "/laboratory/fhir-r4/preview",
                              {"synthetic": True, "bundle_json": raw})
        rows = {row["reference"]: row for row in preview["observations"]}
        self.assertEqual(rows[lab.OBS]["coded_result"], coding)
        self.assertNotIn("coded_result", rows[lab.ABSENT])
        receipt = self.expect(201, base, case + "/laboratory/fhir-r4/sources", {
            "synthetic": True, "request_key": key, "expected_previous_source_id": previous,
            "bundle_json": raw})
        self.assertEqual(receipt["original_sha256"], preview["original_sha256"])
        return receipt

    def test_literal_coding_is_bound_to_its_observation_source_version_and_question(self):
        with running_server(create_app(self.settings)) as base:
            _, case = self.scope(base)
            first = {"system": "urn:oi:synthetic:lab-results", "code": "Fixt.A-1",
                     "version": "rev.1", "display": "Fictional <pattern> A"}
            v1 = self.coded_source(base, case, first, "IMPORT-CODED-1")
            world = self.expect(200, base, case + "/world-model")
            rows = {r["observation_reference"]: r for r in world["laboratory_observations"]}
            self.assertEqual(rows[lab.OBS]["coded_result"], first)
            self.assertNotIn("coded_result", rows[lab.ABSENT])
            self.assertEqual(world["summary"]["unresolved_observations"], 1)
            self.assertEqual({r["status"] for r in world["laboratory_timeline"]},
                             {"reported_coded", "reported_absent"})
            prepared, stale = self.prepare(base, case, v1["source_id"])
            path, anchor = self.saved(base, case, v1)
            selected = prepared["selected_source"]
            self.assertEqual(selected["coded_result"], first)
            self.assertEqual((selected["value_text"], selected["unit_code"], selected["absent_reason"]),
                             (None, None, None))
            metadata = self.find(base, path, anchor)
            self.expect(201, base, path + "/evidence-links", self.command(metadata, anchor, "CITE-CODED"))
            def report(path):
                return self.expect(200, base, path + "/source-citation-report")
            current = report(path)
            self.assertEqual(current["reported_result"], selected)
            self.assertEqual(current["citations"]["source_context_state"], "current_unreviewed_question")
            second = {"system": first["system"], "code": first["code"]}
            v2 = self.coded_source(base, case, second, "IMPORT-CODED-2", v1["source_id"])
            self.expect(409, base, case + lab.LAB_HISTORY, {**stale, "request_key": "STALE-CODED-KEY"})
            fresh_path, new_anchor = self.saved(base, case, v2, key="SAVE-CODED-2")
            fresh = report(fresh_path)
            self.assertEqual(fresh["reported_result"]["coded_result"], second)
            self.assertEqual(fresh["reported_result"]["version"], 2)
            self.assertEqual(fresh["citations"]["links"], [])
            for field in ("source_sha256", "source_snapshot_sha256", "preflight_sha256"):
                self.assertNotEqual(anchor[field], new_anchor[field])
            historical = report(path)
            self.assertEqual(historical["reported_result"], selected)
            self.assertEqual(historical["citations"]["question_anchor"], anchor)
            self.assertEqual(historical["citations"]["source_context_state"], "source_reassessment_required")
            self.assertEqual(historical["citations"]["links"], current["citations"]["links"])
            self.creds[0]["actions"].remove("source_read")
            self.write()
            self.assertEqual(set(self.expect(404, base, path + "/source-citation-report")), {"detail"})

    def test_valid_but_false_historical_coding_blocks_even_a_siblings_citation_read(self):
        with running_server(create_app(self.settings)) as base:
            _, case = self.scope(base)
            v1 = self.coded_source(base, case, {"system": "urn:oi:synthetic:lab-results",
                                   "code": "Source.A"}, "IMPORT-INTACT-V1")
            coded, _ = self.saved(base, case, v1)
            sibling, _ = self.saved(base, case, v1, lab.ABSENT, "ABSENT-SIBLING")
            self.import_lab(base, case, value=1, previous=v1["source_id"])
            for question in (coded, sibling):
                self.expect(200, base, question + "/source-citation-report")
            # Simulate out-of-band corruption of one typed child. The replacement
            # is structurally allowed; only the preserved source bytes disprove it.
            with self.engine.begin() as db:
                db.exec_driver_sql("ALTER TABLE clinical_source.fhir_laboratory_observations "
                                   "DISABLE TRIGGER oi_fhir_observation_update_guard")
                changed = db.execute(text("""
                    UPDATE clinical_source.fhir_laboratory_observations
                    SET coded_result=jsonb_set(coded_result, '{code}', to_jsonb('Changed.B'::text))
                    WHERE source_id=:sid AND observation_reference=:ref
                    """), {"sid": v1["source_id"], "ref": lab.OBS})
                self.assertEqual(changed.rowcount, 1)
                db.exec_driver_sql("ALTER TABLE clinical_source.fhir_laboratory_observations "
                                   "ENABLE TRIGGER oi_fhir_observation_update_guard")
            before = self.counts()
            for question in (coded, sibling):
                error = self.expect(503, base, question + "/source-citation-report")
                self.assertEqual(error, {"detail": "Patient registry unavailable"})
            self.assertEqual(self.counts(), before)

    def test_exact_measured_and_absent_results_survive_amendment_but_revoked_metadata_does_not(self):
        with running_server(create_app(self.settings)) as base:
            _, case = self.scope(base)
            original = self.import_lab(base, case, value=Decimal("4.20"))
            path, anchor = self.saved(base, case, original)
            sibling, _ = self.saved(base, case, original, lab.ABSENT, "ABSENT-QUESTION")
            metadata = self.find(base, path, anchor)
            linked = self.expect(201, base, path + "/evidence-links",
                                 self.command(metadata, anchor, "CITE-ORIGINAL-QUESTION"))
            def report(p):
                return self.expect(200, base, p + "/source-citation-report")
            first = report(path)
            self.assertEqual(first["question"], lab.QUESTION)
            self.assertEqual((first["clinical_review"], first["claim_appraisal"]), ("not_performed", "not_performed"))
            self.assertEqual(first["citations"]["question_anchor"], anchor)
            entry, = first["citations"]["links"]
            self.assertEqual((entry["link_id"], entry["record"]), (linked["link_id"], metadata))
            old = first["reported_result"]
            self.assertEqual((old["resource_reference"], old["value_text"], old["unit_code"], old["absent_reason"]),
                             (lab.OBS, "4.20", "10*9/L", None))
            self.assertEqual((old["specimen_reference"], old["report_reference"], old["sha256"]),
                             ("Specimen/FICTIONAL-SPECIMEN-A", "DiagnosticReport/FICTIONAL-REPORT-A", original["original_sha256"]))
            absent = report(sibling)
            result = absent["reported_result"]
            self.assertEqual((result["resource_reference"], result["value_text"], result["unit_code"], result["absent_reason"]),
                             (lab.ABSENT, None, None, "not-performed"))
            self.assertEqual(absent["citations"]["links"], [])
            amended = self.import_lab(base, case, value=0, previous=original["source_id"])
            historical = report(path)
            self.assertEqual(historical["reported_result"], old)
            self.assertEqual(historical["citations"]["source_context_state"], "source_reassessment_required")
            self.assertNotEqual(first["citations"]["source_access_receipt_id"], historical["citations"]["source_access_receipt_id"])
            fresh_path, _ = self.saved(base, case, amended, key="AMENDED-QUESTION")
            fresh = report(fresh_path)
            self.assertEqual((fresh["reported_result"]["value_text"], fresh["citations"]["links"]), ("0", []))
            with self.catalog_db.registry_connection() as connection:
                evidence_catalog.append_rights_decision(PostgresPatientRegistry(connection),
                    metadata["id"], metadata["version"], permissions={}, revoked=True, superseded=False,
                    recorded_by="FIXTURE-AUTHOR", reason="Fictional display rights withdrawn")
            restricted = report(path)
            self.assertEqual(restricted["reported_result"], old)
            self.assertEqual(restricted["citations"]["links"], [{**entry, "status": "rights_restricted", "record": None}])
            self.assertNotIn(metadata["title"], json.dumps(restricted))
            self.assertNotIn(metadata["link"], json.dumps(restricted))

    def test_read_permission_context_and_post_encoding_denial_prevent_report_disclosure_and_receipt(self):
        with running_server(create_app(self.settings)) as base:
            pid, case = self.scope(base)
            path, anchor = self.saved(base, case, self.import_lab(base, case))
            metadata = self.find(base, path, anchor)
            self.expect(201, base, path + "/evidence-links", self.command(metadata, anchor, "CITE-REPORT"))
            endpoint = path + "/source-citation-report"
            self.creds[1]["patient_ids"] = [pid]
            self.write()
            initial = self.counts()
            self.expect(404, base, endpoint, token=TOKEN_B)
            self.expect(404, base, endpoint + "?use_cached=true")
            self.expect(404, base, endpoint.replace(lab.CASE, "CASE-UNBOUND"))
            for action in ("patient_read", "source_read", "question_read", "evidence_read", "review_packet_read"):
                self.creds[0]["actions"].remove(action)
                self.write()
                with self.subTest(action=action):
                    self.assertEqual(set(self.expect(404, base, endpoint)), {"detail"})
                    self.assertEqual(self.counts(), initial)
                self.creds[0]["actions"].append(action)
                self.write()
            self.creds[0]["actions"].remove("evidence_link")
            self.write()
            original_prepare = laboratory_citation_report_routes._prepare
            encoded = []
            def revoke_after_encoding(*args):
                response = original_prepare(*args)
                encoded.append(metadata["title"] == json.loads(response.body)["citations"]["links"][0]["record"]["title"])
                self.creds[0]["actions"].remove("review_packet_read")
                self.write()
                return response
            with patch.object(laboratory_citation_report_routes, "_prepare", revoke_after_encoding):
                self.assertEqual(set(self.expect(404, base, endpoint)), {"detail"})
            self.assertEqual(encoded, [True])
            self.assertEqual(self.counts(), initial)
            self.creds[0]["actions"].append("review_packet_read")
            self.write()
            self.assertEqual(self.expect(200, base, endpoint)["citations"]["links"][0]["record"], metadata)
            self.expect(200, base, f"/v1/patients/{pid}/case-bindings/{lab.CASE}/revoke",
                        {"synthetic": True, "reason": "Fictional binding revoked"})
            after = self.counts()
            self.assertEqual(set(self.expect(404, base, endpoint)), {"detail"})
            self.assertEqual(self.counts(), after)
