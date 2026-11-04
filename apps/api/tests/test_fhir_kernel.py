"""Tests-first contract for the bounded FHIR source/context kernel.

Independently authored synthetic resources only. These tests intentionally require
source preservation and truthful non-conformance before any broader FHIR server.
"""
from __future__ import annotations

import hashlib
import json
import unittest

from oi_api.fhir_kernel import (
    FHIR_R4,
    FhirRejected,
    admit_fhir_json,
    capability_statement,
    declared_package_baselines,
)
from oi_api.fhir_routes import fhir_router


def encoded(value: dict, *, pretty: bool = False) -> bytes:
    if pretty:
        return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class FhirKernelTests(unittest.TestCase):
    def test_capability_statement_advertises_only_the_implemented_metadata_surface(self):
        value = capability_statement()
        self.assertEqual(value["resourceType"], "CapabilityStatement")
        self.assertEqual(value["fhirVersion"], FHIR_R4)
        self.assertEqual(value["format"], ["json"])
        self.assertIs(value["experimental"], True)
        self.assertEqual(value["rest"][0]["mode"], "server")
        self.assertEqual(value["rest"][0]["resource"], [])
        self.assertIn("no FHIR resource REST interactions", value["rest"][0]["documentation"])
        self.assertNotIn("xml", value["format"])

    def test_declared_us_core_baseline_is_not_misrepresented_as_loaded_or_validating(self):
        values = declared_package_baselines()
        self.assertEqual(len(values), 1)
        baseline = values[0]
        self.assertEqual(
            (baseline["package_id"], baseline["version"], baseline["fhir_version"]),
            ("hl7.fhir.us.core", "9.0.0", "4.0.1"),
        )
        self.assertEqual(baseline["state"], "declared_not_loaded")
        self.assertIsNone(baseline["artifact_sha256"])
        self.assertIs(baseline["profile_validation_available"], False)

    def test_json_admission_preserves_original_bytes_and_source_identity_without_patient_merge(self):
        resource = {
            "resourceType": "Patient",
            "id": "synthetic-patient-a",
            "meta": {"profile": ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"]},
            "identifier": [{"system": "urn:synthetic:mrn", "value": "A-100"}],
            "name": [{"text": "Independent Fictional Patient"}],
        }
        raw = encoded(resource, pretty=True)
        value = admit_fhir_json(
            raw,
            source_system="synthetic-ehr-a",
            issuer="urn:synthetic:issuer:a",
            package_id="hl7.fhir.us.core",
            package_version="9.0.0",
            fhir_version=FHIR_R4,
        )
        self.assertEqual(value["contract"], "oi.fhir-source-envelope/1")
        self.assertEqual(value["original_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(value["original_size"], len(raw))
        self.assertEqual(value["resource_type"], "Patient")
        self.assertEqual(value["logical_id"], "synthetic-patient-a")
        self.assertEqual(value["normalized_resource"], resource)
        self.assertEqual(value["source_identity"], {
            "source_system": "synthetic-ehr-a",
            "issuer": "urn:synthetic:issuer:a",
        })
        self.assertEqual(value["profiles"], resource["meta"]["profile"])
        self.assertEqual(value["profile_validation"], "not_performed")
        self.assertEqual(value["interpretation_state"], "source_only_unreviewed")
        self.assertIs(value["clinical_interpretation"], False)
        self.assertNotIn("patient_id", value)
        self.assertNotIn("canonical_patient_id", value)

    def test_duplicate_json_members_invalid_utf8_and_excessive_depth_fail_closed(self):
        with self.assertRaisesRegex(FhirRejected, "duplicate"):
            admit_fhir_json(
                b'{"resourceType":"Patient","id":"a","id":"b"}',
                source_system="synthetic-ehr", issuer="urn:synthetic:issuer",
            )
        with self.assertRaises(FhirRejected):
            admit_fhir_json(
                b'{"resourceType":"Patient","name":"\xff"}',
                source_system="synthetic-ehr", issuer="urn:synthetic:issuer",
            )
        deep = '{"resourceType":"Patient","x":' + "[" * 70 + "0" + "]" * 70 + "}"
        with self.assertRaisesRegex(FhirRejected, "depth"):
            admit_fhir_json(
                deep.encode(), source_system="synthetic-ehr", issuer="urn:synthetic:issuer",
            )

    def test_only_the_bounded_source_resource_set_is_admitted_and_profiles_are_bounded(self):
        with self.assertRaisesRegex(FhirRejected, "resource type"):
            admit_fhir_json(
                encoded({"resourceType": "MedicationRequest", "id": "m1"}),
                source_system="synthetic-ehr", issuer="urn:synthetic:issuer",
            )
        with self.assertRaisesRegex(FhirRejected, "profiles"):
            admit_fhir_json(
                encoded({
                    "resourceType": "Observation",
                    "id": "o1",
                    "meta": {"profile": [f"urn:synthetic:p:{i}" for i in range(17)]},
                }),
                source_system="synthetic-ehr", issuer="urn:synthetic:issuer",
            )

    def test_provenance_and_audit_event_are_trust_records_not_clinical_assertions(self):
        for resource_type, expected in (
            ("Provenance", "provenance"),
            ("AuditEvent", "security_audit"),
        ):
            with self.subTest(resource_type=resource_type):
                value = admit_fhir_json(
                    encoded({"resourceType": resource_type, "id": "fixture-1"}),
                    source_system="synthetic-ehr", issuer="urn:synthetic:issuer",
                )
                self.assertEqual(value["classification"], expected)
                self.assertEqual(value["interpretation_state"], "source_only_unreviewed")
                self.assertNotIn("clinical_assertions", value)

    def test_observation_absence_state_is_preserved_without_becoming_negative(self):
        resource = {
            "resourceType": "Observation",
            "id": "obs-not-assessed",
            "status": "final",
            "code": {"text": "Independent fictional marker"},
            "dataAbsentReason": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/data-absent-reason",
                                            "code": "not-asked"}]},
            "subject": {"reference": "Patient/synthetic-patient-a"},
        }
        value = admit_fhir_json(
            encoded(resource),
            source_system="synthetic-ehr", issuer="urn:synthetic:issuer",
        )
        self.assertEqual(value["classification"], "clinical_source")
        self.assertEqual(value["normalized_resource"]["dataAbsentReason"], resource["dataAbsentReason"])
        self.assertNotIn("negative", json.dumps(value).lower())
        self.assertIs(value["clinical_interpretation"], False)

    def test_metadata_route_returns_the_same_truthful_capability_statement(self):
        router = fhir_router()
        route = next(item for item in router.routes if item.path == "/v1/fhir/metadata")
        self.assertEqual(route.endpoint(), capability_statement())


if __name__ == "__main__":
    unittest.main()
