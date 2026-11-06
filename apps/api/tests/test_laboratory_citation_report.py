"""Read the actual saved laboratory source at two time points with current citation rights."""
from decimal import Decimal
import json
from unittest.mock import patch

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
