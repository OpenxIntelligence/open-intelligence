"""Independently fictional result Codings: literal preservation and refusal tests."""
from copy import deepcopy
from datetime import date
import unittest

from oi_api.laboratory_fhir_r4 import LaboratoryBundleRejected, prepare_laboratory_bundle
from oi_api.source_integrity import SourceIntegrityError, validate_fhir_laboratory_original
from test_laboratory_fhir_r4 import PATIENT, encode, example, resource

CODING = {"system": "urn:oi:synthetic:lab-results", "code": "Fictional-A_2.0",
          "version": "V4.2", "display": "Fictional assay: A (reported)"}
ABSENT = {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/data-absent-reason",
                      "code": "unknown"}]}


def coded_bundle(coding=CODING):
    bundle = example()
    observation = resource(bundle, "Observation")
    del observation["valueQuantity"]
    observation["valueCodeableConcept"] = {"coding": [dict(coding)]}
    return bundle


def prepare(bundle):
    return prepare_laboratory_bundle(encode(bundle), expected_subject_reference=PATIENT)


class CodedLaboratoryResultsTests(unittest.TestCase):
    def test_literal_exact_optional_fields_and_original(self):
        for coding in (CODING, {k: CODING[k] for k in ("system", "code")},
                       {**CODING, "code": "a" * 64, "version": "v" * 64, "display": "~" * 120}):
            with self.subTest(coding=coding):
                bundle = coded_bundle(coding)
                prepared = prepare(bundle)
                row, = prepared.observations
                self.assertEqual(prepared.original_bytes, encode(bundle))
                self.assertEqual(prepared.profile_contract, "oi.fhir-r4-laboratory-custody/2")
                self.assertEqual((row["status"], row["coded_result"]), ("reported_coded", coding))
                self.assertIsNone(row["value_text"])
                self.assertIsNone(row["unit_code"])
                self.assertIsNone(row["absent_reason"])

    def test_legacy_result_arms_keep_no_coded_member_and_original_profile(self):
        bundle = example()
        quantity = prepare(bundle)
        observation = resource(bundle, "Observation")
        del observation["valueQuantity"]
        observation["dataAbsentReason"] = ABSENT
        absent = prepare(bundle)
        for prepared in (quantity, absent):
            self.assertEqual(prepared.profile_contract, "oi.fhir-r4-laboratory-custody/1")
            self.assertNotIn("coded_result", prepared.observations[0])

    def test_ambiguous_or_unsupported_concepts_fail_closed(self):
        for concept in (None, {}, {"text": "fictional"}, {"coding": [CODING], "text": "fictional"},
                        {"coding": None}, {"coding": []}, {"coding": [CODING, CODING]},
                        {"coding": [None]}, {"coding": CODING}, {"coding": [CODING | {"userSelected": True}]}):
            with self.subTest(concept=concept), self.assertRaises(LaboratoryBundleRejected):
                bundle = coded_bundle()
                resource(bundle, "Observation")["valueCodeableConcept"] = concept
                prepare(bundle)
        extra_arms = (("valueQuantity", resource(example(), "Observation")["valueQuantity"]),
                      ("dataAbsentReason", ABSENT), ("valueString", "fictional"),
                      ("valueBoolean", False), ("dataAbsentReason", None))
        for key, value in extra_arms:
            with self.subTest(key=key), self.assertRaises(LaboratoryBundleRejected):
                bundle = coded_bundle()
                resource(bundle, "Observation")[key] = value
                prepare(bundle)

    def test_result_coding_bounds_and_explicit_null_refusals(self):
        for key, invalid in {
            "system": [None, "http://loinc.org", CODING["system"] + "/", 1],
            "code": [None, False, 9, "", "-x", "_x", ".x", "a/b", "a b", "a" * 65, "é", "x\n"],
            "version": [None, False, "", ".1", "1[2]", "1" * 65, "é"],
            "display": [None, False, "", " before", "after ", " ", "one\ttwo", "x\n", "x\x7f", "é", "x" * 121],
        }.items():
            for value in invalid:
                with self.subTest(key=key, value=value), self.assertRaises(LaboratoryBundleRejected):
                    prepare(coded_bundle(CODING | {key: value}))
        for required in ("system", "code"):
            with self.subTest(missing=required), self.assertRaises(LaboratoryBundleRejected):
                prepare(coded_bundle({k: v for k, v in CODING.items() if k != required}))

    def test_every_coded_field_rechecked_against_original_including_superseded(self):
        prepared = prepare(coded_bundle())
        raw_row = dict(source_id="SRC-" + "A" * 32, case_id="CASE-LAB", kind="laboratory",
                       raw=prepared.original_bytes, sha256=prepared.source_sha256, version=1,
                       supersedes_id=None, document_id="FICTIONAL-REPORT-A", specimen_id="FICTIONAL-SPECIMEN-A",
                       event_date=date(2026, 4, 3), issued_at=date(2026, 4, 4))
        metadata = {key: getattr(prepared, key) for key in ("subject_reference", "specimen_reference",
                    "specimen_type_text", "specimen_collected_at", "report_reference",
                    "report_effective_at", "report_issued_at", "profile_contract")}
        metadata.update(source_id=raw_row["source_id"], observation_count=1, fhir_release="R4")
        observation = deepcopy(prepared.observations[0])
        observation.update(source_id=raw_row["source_id"], position=1,
                           observation_reference=observation.pop("reference"))
        for state in ("current", "superseded"):
            row = dict(raw_row, state=state)
            def verify(child, parent=metadata):
                return validate_fhir_laboratory_original(row, parent, [child], requested_case_id="CASE-LAB")
            self.assertEqual(verify(observation), prepared.original_bytes)
            with self.assertRaises(SourceIntegrityError):
                verify(observation, metadata | {"profile_contract": "oi.fhir-r4-laboratory-custody/1"})
            for key in CODING:
                for wrong in (CODING | {key: "changed"}, {k: v for k, v in CODING.items() if k != key}):
                    with self.subTest(state=state, wrong=wrong), self.assertRaises(SourceIntegrityError):
                        verify(observation | {"coded_result": wrong})
            for wrong in ({"coded_result": None}, {"status": "reported_absent"}, {"value_text": "1"},
                          {"unit_code": "1"}, {"absent_reason": "unknown"},
                          {"coded_result": CODING | {"interpretation": "unknown"}}):
                with self.subTest(state=state, wrong=wrong), self.assertRaises(SourceIntegrityError):
                    verify(observation | wrong)
            with self.assertRaises(SourceIntegrityError):
                verify({k: v for k, v in observation.items() if k != "coded_result"})
