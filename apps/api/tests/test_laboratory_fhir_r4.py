"""Offline fictional FHIR-R4 laboratory preparation refusal/identity tests.

No personal medical data, connection to FHIR servers, clinical import or database.
"""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import unittest

from oi_api.laboratory_fhir_r4 import (
    MAX_BUNDLE_BYTES, LaboratoryBundleRejected, prepare_laboratory_bundle,
)


PATIENT = "Patient/FICTIONAL-PATIENT-A"
SPECIMEN = "Specimen/FICTIONAL-SPECIMEN-A"
OBS = "Observation/FICTIONAL-OBS-A"
REPORT = "DiagnosticReport/FICTIONAL-REPORT-A"


def _category():
    return [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category",
                          "code": "laboratory"}]}]


def _loinc(code="777-3"):
    return {"coding": [{"system": "http://loinc.org", "code": code}]}


def example():
    resources = [
        {"resourceType": "Patient", "id": "FICTIONAL-PATIENT-A"},
        {"resourceType": "Specimen", "id": "FICTIONAL-SPECIMEN-A",
         "subject": {"reference": PATIENT}, "type": {"text": "Fictional plasma sample"},
         "collection": {"collectedDateTime": "2026-04-03T09:05:00-04:00"}},
        {"resourceType": "Observation", "id": "FICTIONAL-OBS-A", "status": "final",
         "category": _category(), "code": _loinc(),
         "subject": {"reference": PATIENT}, "specimen": {"reference": SPECIMEN},
         "effectiveDateTime": "2026-04-03T09:05:00-04:00",
         "issued": "2026-04-04T12:00:00Z",
         "valueQuantity": {"value": Decimal("4.20"), "system": "http://unitsofmeasure.org",
                           "code": "10*9/L"}},
        {"resourceType": "DiagnosticReport", "id": "FICTIONAL-REPORT-A",
         "status": "final", "category": _category(), "code": _loinc("58410-2"),
         "subject": {"reference": PATIENT}, "specimen": [{"reference": SPECIMEN}],
         "result": [{"reference": OBS}],
         "effectiveDateTime": "2026-04-03T09:05:00-04:00",
         "issued": "2026-04-04T12:00:00Z"},
    ]
    return {"resourceType": "Bundle", "type": "collection",
            "entry": [{"fullUrl": "urn:uuid:00000000-0000-4000-8000-%012d" % i,
                       "resource": r} for i, r in enumerate(resources, 1)]}


def encode(bundle):
    # Preserve fractional number formatting as a JSON token, not a floating float.
    def encode_numbers(value):
        if isinstance(value, Decimal):
            return {"___decimal___": str(value)}
        if isinstance(value, dict):
            return {k: encode_numbers(v) for k, v in value.items()}
        if isinstance(value, list):
            return [encode_numbers(v) for v in value]
        return value
    s = json.dumps(encode_numbers(bundle), separators=(",", ":"))
    s = s.replace('{"___decimal___":"4.20"}', '4.20')
    return s.encode()


def resource(bundle, kind):
    return next(entry["resource"] for entry in bundle["entry"]
                if entry["resource"]["resourceType"] == kind)


class FHIRPreparationTests(unittest.TestCase):
    def prepared(self, bundle=None, mapping=PATIENT):
        return prepare_laboratory_bundle(encode(example() if bundle is None else bundle),
                                         expected_subject_reference=mapping)

    def rejected(self, bundle, mapping=PATIENT):
        with self.assertRaises(LaboratoryBundleRejected):
            self.prepared(bundle, mapping=mapping)

    def test_bounded_exact_original_unreviewed_and_preserves_decimal_precision(self):
        original = encode(example())
        result = prepare_laboratory_bundle(original, expected_subject_reference=PATIENT)
        self.assertEqual(result.original_bytes, original)
        self.assertEqual(result.source_sha256, hashlib.sha256(original).hexdigest())
        self.assertEqual(result.specimen_reference, SPECIMEN)
        self.assertEqual(result.specimen_collected_at, "2026-04-03T09:05:00-04:00")
        self.assertEqual(result.report_reference, REPORT)
        self.assertEqual(len(result.observations), 1)
        self.assertEqual(result.observations[0]["value_text"], "4.20")
        self.assertEqual(result.observations[0]["status"], "reported_value")
        self.assertEqual(result.authority, "synthetic_source_unreviewed")
        self.assertEqual(result.clinical_review, "not_performed")
        self.assertFalse(result.persisted)
        self.assertEqual(self.prepared(), result)

    def test_case_qualified_patient_mapping_and_cross_patient_denials(self):
        b = example()
        self.rejected(b, "Patient/OTHER-PATIENT")
        resource(b, "Specimen")["subject"]["reference"] = "Patient/OTHER-PATIENT"
        self.rejected(b)
        b = example()
        resource(b, "Observation")["subject"]["reference"] = "Patient/OTHER-PATIENT"
        self.rejected(b)
        b = example()
        resource(b, "DiagnosticReport")["subject"]["reference"] = "Patient/OTHER-PATIENT"
        self.rejected(b)

    def test_specimen_and_result_link_fail_closed(self):
        b = example()
        resource(b, "Observation")["specimen"]["reference"] = "Specimen/OTHER"
        self.rejected(b)
        b = example()
        resource(b, "DiagnosticReport")["result"] = [{"reference": "Observation/OTHER"}]
        self.rejected(b)
        b = example()
        resource(b, "DiagnosticReport")["result"] = [{"reference": OBS}, {"reference": OBS}]
        self.rejected(b)
        b = example()
        b["entry"][2]["fullUrl"] = b["entry"][1]["fullUrl"]
        self.rejected(b)

    def test_absent_vs_negative_vs_zero_are_not_conflated(self):
        b = example()
        obs = resource(b, "Observation")
        obs.pop("valueQuantity")
        obs["dataAbsentReason"] = {"coding": [{
            "system": "http://terminology.hl7.org/CodeSystem/data-absent-reason",
            "code": "not-performed"}]}
        row = self.prepared(b).observations[0]
        self.assertEqual(row["status"], "reported_absent")
        self.assertIsNone(row["value_text"])
        self.assertEqual(row["absent_reason"], "not-performed")
        obs["valueQuantity"] = {"value": 0, "system": "http://unitsofmeasure.org", "code": "10*9/L"}
        self.rejected(b)
        del obs["dataAbsentReason"]
        row = self.prepared(b).observations[0]
        self.assertEqual(row["status"], "reported_value")
        self.assertEqual(row["value_text"], "0")
        del obs["valueQuantity"]
        self.rejected(b)

    def test_nonfinal_unsupported_clinical_interpretation_and_unit_holds(self):
        for value in ("preliminary", "amended", "entered-in-error", "cancelled"):
            b = example()
            resource(b, "Observation")["status"] = value
            self.rejected(b)
        b = example()
        resource(b, "DiagnosticReport")["conclusion"] = "treatment recommended"
        self.rejected(b)
        b = example()
        resource(b, "Observation")["valueQuantity"]["system"] = "https://unknown.invalid"
        self.rejected(b)
        b = example()
        resource(b, "Observation")["interpretation"] = [{"text": "normal"}]
        self.rejected(b)

    def test_json_structural_and_dangerous_values_rejected(self):
        original = encode(example())
        with self.assertRaises(LaboratoryBundleRejected):
            prepare_laboratory_bundle(original + b" ", expected_subject_reference="Patient/OTHER")
        for bad in (b"", b"[]", b"{}", b"{", b"\xff", b"0" * (MAX_BUNDLE_BYTES + 1)):
            with self.subTest(bad=bad[:10]), self.assertRaises(LaboratoryBundleRejected):
                prepare_laboratory_bundle(bad, expected_subject_reference=PATIENT)
        dup = original.replace(b'"resourceType":"Bundle"', b'"resourceType":"Bundle","resourceType":"Bundle"', 1)
        with self.assertRaises(LaboratoryBundleRejected):
            prepare_laboratory_bundle(dup, expected_subject_reference=PATIENT)
        for bad in (b"NaN", b"Infinity", b"true", b'"5.0"'):
            modified = original.replace(b'"value":4.20', b'"value":' + bad)
            with self.subTest(value=bad), self.assertRaises(LaboratoryBundleRejected):
                prepare_laboratory_bundle(modified, expected_subject_reference=PATIENT)

    def test_links_are_not_network_or_externally_resolved(self):
        b = example()
        b["entry"][1]["fullUrl"] = "https://clinical.example.test/Specimen/1"
        self.rejected(b)
        b = example()
        resource(b, "Observation")["specimen"]["reference"] = "https://clinical.example.test/Specimen/1"
        self.rejected(b)

    def test_multiple_observations_are_bounded_and_report_complete(self):
        b = example()
        obs = deepcopy(resource(b, "Observation"))
        obs["id"] = "FICTIONAL-OBS-B"
        obs["code"] = _loinc("718-7")
        b["entry"].insert(3, {"fullUrl": "urn:uuid:00000000-0000-4000-8000-000000000009", "resource": obs})
        resource(b, "DiagnosticReport")["result"].append({"reference": "Observation/FICTIONAL-OBS-B"})
        parsed = self.prepared(b)
        self.assertEqual(len(parsed.observations), 2)
        self.assertEqual({x["loinc_code"] for x in parsed.observations}, {"777-3", "718-7"})
        resource(b, "DiagnosticReport")["result"].pop()
        self.rejected(b)


if __name__ == "__main__":
    unittest.main()
