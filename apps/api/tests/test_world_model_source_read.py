"""H1 actual PostgreSQL 16: source-derived World Model without any new record."""
import hashlib
import unittest

from sqlalchemy import text

from oi_api.app import create_app
from http_support import running_server
from test_patients import TOKEN_A, TOKEN_B, request
from test_source_versions import (
    SourceVersionHTTPTests as SourceFixture, ORIGINAL, AMENDED,
)


class PostgresWorldModelHTTPTests(SourceFixture):
    """Reuse owner fixture and real source/binding tests; no fake HTTP."""

    def url_world(self, pid, case="CASE-ALPHA"):
        return f"/v1/patients/{pid}/cases/{case}/world-model"

    def model(self, base, pid, *, case="CASE-ALPHA", token=TOKEN_A):
        return request(base, self.url_world(pid, case), token=token)

    def test_exact_current_source_and_correction_replaces_only_derived_observation(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            original = self.ingest(base, patient)
            self.assertEqual(original[0], 201)
            source_one = original[1]["source_id"]
            status, first, _ = self.model(base, patient)
            self.assertEqual(status, 200)
            self.assertEqual(first["contract"], "oi.synthetic-postgres-world-model-sources/1")
            self.assertEqual((first["patient_id"], first["case_id"]), (patient, "CASE-ALPHA"))
            self.assertTrue(first["synthetic"])
            self.assertEqual(first["authority"], "source_report_only_unreviewed")
            self.assertFalse(first["clinical_approval"])
            self.assertFalse(first["review_workflow_connected"])
            self.assertEqual(first["summary"]["current_sources"], 1)
            self.assertEqual(first["summary"]["current_observations"], 1)
            self.assertEqual(first["summary"]["unresolved_observations"], 1)
            finding = first["observations"][0]
            self.assertEqual((finding["source_version_id"], finding["source_line"]),
                             (source_one, 8))
            self.assertEqual(finding["reported_state"], "not-reported")
            self.assertEqual(finding["source_sha256"],
                             hashlib.sha256(ORIGINAL.encode()).hexdigest())
            self.assertEqual(finding["review_state"], "not_established")
            self.assertIsNone(finding["clinical_meaning"])
            self.assertEqual(first["unresolved"], [finding])
            self.assertNotIn("original_text", str(first))
            self.assertEqual(first["conflicts"], [])
            digest_before = first["source_snapshot_sha256"]
            self.assertEqual(len(digest_before), 64)
            status, again, _ = self.model(base, patient)
            self.assertEqual(status, 200)
            self.assertEqual(again["source_snapshot_sha256"], digest_before)

            amended = self.ingest(base, patient, AMENDED)
            self.assertEqual(amended[0], 201)
            source_two = amended[1]["source_id"]
            status, after, _ = self.model(base, patient)
            self.assertEqual(status, 200)
            self.assertNotEqual(after["source_snapshot_sha256"], digest_before)
            self.assertEqual(after["summary"]["superseded_sources"], 1)
            self.assertEqual(after["current_sources"][0]["source_version_id"], source_two)
            self.assertEqual(after["history"][0]["source_version_id"], source_one)
            self.assertEqual(after["current_sources"][0]["supersedes_source_id"], source_one)
            self.assertEqual(len(after["observations"]), 1)
            self.assertEqual(after["observations"][0]["source_version_id"], source_two)
            self.assertEqual(after["observations"][0]["reported_state"], "negative")
            self.assertEqual(after["unresolved"], [])
            self.assertEqual(after["review_workflow_connected"], False)
        with running_server(create_app(self.settings)) as restarted:
            final = self.model(restarted, patient)[1]
            self.assertEqual(final["source_snapshot_sha256"], after["source_snapshot_sha256"])
            self.assertEqual(final["observations"][0]["source_version_id"], source_two)

    def test_distinct_source_right_and_case_mapping_fail_closed(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            self.ingest(base, patient)
            other = self.setup_case(base, token=TOKEN_B, case="CASE-BETA",
                                    key="CREATE-BETA", source_subject="SUBJECT-BETA")
            self.assertEqual(self.model(base, other, case="CASE-ALPHA", token=TOKEN_B)[0], 404)
            self.assertEqual(self.model(base, patient, case="CASE-BETA")[0], 404)
            self.assertEqual(self.model(base, patient, token=TOKEN_B)[0], 404)
            self.creds[0]["actions"].remove("source_read")
            self.write()
            self.assertEqual(self.model(base, patient)[0], 404)
            self.creds[0]["actions"].append("source_read")
            self.write()
            self.assertEqual(self.model(base, patient)[0], 200)
            revoked = request(base,
                f"/v1/patients/{patient}/case-bindings/CASE-ALPHA/revoke",
                token=TOKEN_A,
                body={"synthetic": True, "reason": "Fictional mapping removed"})
            self.assertEqual(revoked[0], 200)
            self.assertEqual(self.model(base, patient)[0], 404)

    def test_source_assertion_tampering_is_rejected_even_with_valid_source_hash(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            self.ingest(base, patient)
            self.assertEqual(self.model(base, patient)[0], 200)
            with self.engine.begin() as connection:
                # A test-only SQL superuser can disable a trigger. The app
                # must independently detect the altered quote/line on read.
                connection.exec_driver_sql(
                    "DROP TRIGGER oi_assertion_update_guard ON clinical_source.assertions"
                )
                connection.exec_driver_sql(
                    "UPDATE clinical_source.assertions SET quote='forged source statement'"
                )
            status, rejected, _ = self.model(base, patient)
            self.assertEqual(status, 422)
            self.assertNotIn("forged source statement", str(rejected))

    def test_same_specimen_date_conflict_has_exact_source_refs_not_clinical_meaning(self):
        other = (
            "OI-SYNTHETIC-REPORT/1\nPatient: CASE-ALPHA\nDocument: DOC-TWO\n"
            "Type: pathology\nEvent-Date: 2026-01-10\nIssued-At: 2026-01-11\n"
            "Specimen: SPECIMEN-ONE\n"
            "Finding: marker|reported|Independently fictional reported marker.\n"
        )
        original_reported = ORIGINAL.replace("not-reported", "negative")
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            first = self.ingest(base, patient, original_reported)
            second = self.ingest(base, patient, other)
            self.assertEqual((first[0], second[0]), (201, 201))
            value = self.model(base, patient)[1]
            self.assertEqual(value["summary"]["current_sources"], 2)
            self.assertEqual(value["summary"]["source_disagreements"], 1)
            conflict = value["conflicts"][0]
            self.assertEqual(conflict["status"], "unresolved_source_disagreement")
            self.assertEqual(conflict["clinical_interpretation"], "not_performed")
            self.assertEqual(set(conflict["reported_states"]), {"reported", "negative"})
            self.assertEqual({r["source_version_id"] for r in conflict["observation_refs"]},
                             {first[1]["source_id"], second[1]["source_id"]})


if __name__ == "__main__":
    unittest.main()
