"""Actual PostgreSQL 16 H1 source-only World Model acceptance.

Uses the existing identity/case/source fixture and real HTTP server; no parallel
source database and no real patient or biomedical content.
"""
import copy
import unittest

from oi_api.app import create_app
from oi_api.source_world_model import project_source_world_model
from open_intelligence.patient_registry import PatientRegistryError

from http_support import running_server
from test_patients import request, TOKEN_A, TOKEN_B
from test_source_versions import SourceVersionHTTPTests as SourceFixture, ORIGINAL, AMENDED


class SourceWorldModelHTTPTests(SourceFixture):
    def world_url(self, patient, case="CASE-ALPHA"):
        return f"/v1/patients/{patient}/cases/{case}/world-model"

    def test_derived_current_snapshot_preserves_history_and_fingerprint(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            route = self.world_url(patient)
            status, empty, _ = request(base, route, token=TOKEN_A)
            self.assertEqual(status, 200)
            self.assertEqual(empty["contract"], "oi.pg-source-world-model/1")
            self.assertEqual(empty["patient_id"], patient)
            self.assertEqual(empty["case_id"], "CASE-ALPHA")
            self.assertEqual(empty["summary"]["current_sources"], 0)
            self.assertEqual(empty["observations"], [])
            self.assertEqual(empty["laboratory_observations"], [])
            self.assertEqual(empty["laboratory_timeline"], [])
            self.assertEqual(empty["summary"]["current_laboratory_observations"], 0)
            self.assertFalse(empty["clinical_interpretation"])
            self.assertFalse(empty["composer_execution_authorized"])
            self.assertFalse(empty["research_review_invalidation_integrated"])
            self.assertEqual(len(empty["snapshot_fingerprint"]), 64)

            first = self.ingest(base, patient)
            self.assertEqual(first[0], 201)
            original_id = first[1]["source_id"]
            status, world, _ = request(base, route, token=TOKEN_A)
            self.assertEqual(status, 200)
            self.assertNotEqual(world["snapshot_fingerprint"], empty["snapshot_fingerprint"])
            self.assertEqual(world["summary"], {
                "current_sources": 1, "historical_sources": 0,
                "current_observations": 1, "current_laboratory_observations": 0,
                "unresolved_observations": 1, "source_disagreements": 0,
            })
            observation = world["observations"][0]
            self.assertEqual(observation["source_id"], original_id)
            self.assertEqual(observation["source_line"], 8)
            self.assertEqual(observation["reported_state"], "not-reported")
            self.assertIn("<script>literal</script>", observation["source_statement"])
            self.assertEqual(observation["review_state"], "not_established")
            self.assertIsNone(observation["clinical_meaning"])
            self.assertEqual(world["unresolved_refs"],
                             [{"source_id": original_id, "source_line": 8}])
            repeated = request(base, route, token=TOKEN_A)[1]
            self.assertEqual(repeated['snapshot_fingerprint'], world['snapshot_fingerprint'])
            self.assertEqual(repeated['summary'], world['summary'])
            self.assertNotEqual(repeated['access_receipt_id'], world['access_receipt_id'])

            second = self.ingest(base, patient, AMENDED)
            self.assertEqual((second[0], second[1]["version"]), (201, 2))
            status, amended, _ = request(base, route, token=TOKEN_A)
            self.assertEqual(status, 200)
            self.assertNotEqual(amended["snapshot_fingerprint"], world["snapshot_fingerprint"])
            self.assertEqual(amended["summary"], {
                "current_sources": 1, "historical_sources": 1,
                "current_observations": 1, "current_laboratory_observations": 0,
                "unresolved_observations": 0, "source_disagreements": 0,
            })
            self.assertEqual(amended["history"][0]["source_id"], original_id)
            self.assertEqual(amended["history"][0]["state"], "superseded")
            self.assertEqual(amended["current_sources"][0]["version"], 2)
            self.assertEqual(amended["current_sources"][0]["supersedes_id"], original_id)
            self.assertEqual(amended["observations"][0]["reported_state"], "negative")
            self.assertNotIn("Fictional café", str(amended["observations"]))
            self.assertEqual(amended["unresolved_refs"], [])
            self.assertFalse(amended["composer_execution_authorized"])
            self.assertEqual(request(base, self.url(patient)+"/"+original_id,
                                     token=TOKEN_A)[1]["original_text"], ORIGINAL)
        with running_server(create_app(self.settings)) as restarted:
            after_restart = request(restarted, route, token=TOKEN_A)[1]
            self.assertEqual(after_restart['snapshot_fingerprint'], amended['snapshot_fingerprint'])
            self.assertEqual(after_restart['history'], amended['history'])
            self.assertNotEqual(after_restart['access_receipt_id'], amended['access_receipt_id'])

    def test_same_specimen_and_event_date_disagreement_never_claims_clinical_truth(self):
        report = lambda doc, date, state: (
            "OI-SYNTHETIC-REPORT/1\nPatient: CASE-ALPHA\n"
            f"Document: {doc}\nType: pathology\n"
            f"Event-Date: {date}\nIssued-At: 2026-01-12\n"
            "Specimen: SPECIMEN-ONE\n"
            f"Finding: marker|{state}|Independently fictional {doc} statement.\n"
        )
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            original = self.ingest(base, patient, report("DOC-ONE", "2026-01-10", "reported"))
            negative = self.ingest(base, patient, report("DOC-TWO", "2026-01-10", "negative"))
            different_date = self.ingest(base, patient, report("DOC-THREE", "2026-02-10", "reported"))
            self.assertTrue(all(x[0] == 201 for x in (original, negative, different_date)))
            status, body, _ = request(base, self.world_url(patient), token=TOKEN_A)
            self.assertEqual(status, 200)
            self.assertEqual(body["summary"]["source_disagreements"], 1)
            self.assertEqual(body["summary"]["current_observations"], 3)
            conflict = body["conflicts"][0]
            self.assertEqual(conflict["status"], "unresolved_source_disagreement")
            self.assertEqual(conflict["clinical_interpretation"], "not_performed")
            self.assertEqual(conflict["specimen_id"], "SPECIMEN-ONE")
            self.assertEqual(conflict["event_date"], "2026-01-10")
            self.assertEqual(conflict["finding_key"], "marker")
            self.assertEqual(conflict["reported_states"], ["negative", "reported"])
            self.assertEqual({r["source_id"] for r in conflict["source_refs"]},
                             {original[1]["source_id"], negative[1]["source_id"]})
            self.assertNotIn(different_date[1]["source_id"],
                             {r["source_id"] for r in conflict["source_refs"]})
            self.assertFalse(body["clinical_interpretation"])
            self.assertTrue(all(x["review_state"] == "not_established"
                                and x["clinical_meaning"] is None
                                for x in body["observations"]))

    def test_typed_laboratory_projection_does_not_change_source_snapshot_fingerprint(self):
        index = {
            "contract":"oi.synthetic-original-sources/1",
            "patient_id":"PAT-SYNTH", "case_id":"CASE-ALPHA",
            "access_receipt_id":"ACCESS-"+"A"*32, "synthetic":True,
            "clinical_interpretation":False, "research_review_invalidation_integrated":False,
            "sources":[{
                "source_id":"SRC-"+"B"*32, "document_id":"FICTIONAL-REPORT-A", "version":1,
                "sha256":"b"*64,"kind":"laboratory","event_date":"2026-04-03",
                "issued_at":"2026-04-04","received_at":"2026-04-05T00:00:00+00:00",
                "specimen_id":"FICTIONAL-SPECIMEN-A","state":"current","supersedes_id":None,
            }],
            "source_reported_assertions":[],
        }
        lab = {
            "source_id":"SRC-"+"B"*32,"document_id":"FICTIONAL-REPORT-A",
            "document_version":1,"source_sha256":"b"*64,
            "observation_reference":"Observation/FICTIONAL-OBS-A","loinc_code":"777-3",
            "effective_at":"2026-04-03T09:05:00-04:00","issued_at":"2026-04-04T12:00:00Z",
            "specimen_reference":"Specimen/FICTIONAL-SPECIMEN-A",
            "specimen_type_text":"Fictional plasma sample",
            "specimen_collected_at":"2026-04-03T09:05:00-04:00",
            "report_reference":"DiagnosticReport/FICTIONAL-REPORT-A",
            "status":"reported_value","value_text":"4.20","unit_code":"10*9/L",
            "absent_reason":None,"source_reported":True,"review_state":"not_established",
            "clinical_review":"not_performed","clinical_meaning":None,
        }
        source_only = project_source_world_model(index)
        typed = project_source_world_model(index, [lab])
        self.assertEqual(source_only["snapshot_fingerprint"], typed["snapshot_fingerprint"])
        self.assertEqual(source_only["summary"]["current_laboratory_observations"], 0)
        self.assertEqual(typed["summary"]["current_laboratory_observations"], 1)
        self.assertEqual(typed["laboratory_observations"][0]["value_text"], "4.20")

    def test_case_and_source_permission_revocation_fails_closed_without_original_bytes(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            source_id = self.ingest(base, patient)[1]["source_id"]
            route = self.world_url(patient)
            status, projection, _ = request(base, route, token=TOKEN_A)
            self.assertEqual(status, 200)
            self.assertNotIn("original_text", projection)
            self.assertNotIn("raw", projection)
            self.assertEqual(projection["observations"][0]["source_id"], source_id)
            self.assertEqual(request(base, route, token=TOKEN_B)[0], 404)
            self.assertEqual(request(base, self.world_url(patient, "CASE-OTHER"), token=TOKEN_A)[0], 404)
            self.creds[0]["actions"].remove("source_read")
            self.write()
            self.assertEqual(request(base, route, token=TOKEN_A)[0], 404)
            self.creds[0]["actions"].append("source_read")
            self.creds[0]["actions"].remove("patient_read")
            self.write()
            self.assertEqual(request(base, route, token=TOKEN_A)[0], 404)
            self.creds[0]["actions"].append("patient_read")
            self.write()
            revoked = request(base,
                f"/v1/patients/{patient}/case-bindings/CASE-ALPHA/revoke",
                token=TOKEN_A, body={"synthetic":True,
                                    "reason":"Withdraw independently fictional reference"})
            self.assertEqual(revoked[0], 200)
            self.assertEqual(request(base, route, token=TOKEN_A)[0], 404)

    def test_inconsistent_source_refs_and_fake_review_status_are_not_projected(self):
        sample = {
            "contract":"oi.synthetic-original-sources/1",
            "patient_id":"PAT-SYNTH", "case_id":"CASE-ALPHA",
            "access_receipt_id":"ACCESS-"+"A"*32, "synthetic":True,
            "clinical_interpretation":False, "research_review_invalidation_integrated":False,
            "sources":[{
                "source_id":"SRC-"+"A"*32, "document_id":"DOC-ONE", "version":1,
                "sha256":"a"*64,"kind":"pathology","event_date":"2026-01-10",
                "issued_at":"2026-01-11","received_at":"2026-01-12T00:00:00+00:00",
                "specimen_id":"SPECIMEN-ONE","state":"current","supersedes_id":None,
            }],
            "source_reported_assertions":[{
                "source_id":"SRC-"+"A"*32,"finding_key":"marker",
                "reported_state":"pending","source_statement":"Fictional result pending",
                "source_line":8,"clinical_review_state":"not_established",
            }],
        }
        self.assertEqual(project_source_world_model(sample)["summary"]["unresolved_observations"], 1)
        for alteration in (
            lambda s:s.update({"synthetic":False}),
            lambda s:s.update({"clinical_interpretation":True}),
            lambda s:s["sources"][0].update({"state":"superseded"}),
            lambda s:s["source_reported_assertions"][0].update({"source_id":"SRC-OTHER"}),
            lambda s:s["source_reported_assertions"][0].update({"clinical_review_state":"approved"}),
            lambda s:s["source_reported_assertions"][0].update({"reported_state":"recommended"}),
            lambda s:s["sources"].append(dict(s["sources"][0])),
        ):
            with self.subTest(alteration=alteration):
                data=copy.deepcopy(sample)
                alteration(data)
                with self.assertRaises(PatientRegistryError):
                    project_source_world_model(data)


if __name__=="__main__":
    unittest.main()
