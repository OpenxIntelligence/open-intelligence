"""Offline typed-laboratory question preparation; independently fictional data."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from open_intelligence.patient_registry import (
    PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError,
)
from open_intelligence.postgres_registry import PostgresPatientRegistry
from oi_api import composer_preflight as module
from oi_api.laboratory_fhir_r4 import prepare_laboratory_bundle
from oi_api.source_world_model import project_source_world_model
from test_laboratory_fhir_r4 import example, encode, resource, PATIENT, OBS, REPORT, SPECIMEN

PID = "PATIENT-FICTIONAL-A"
CASE = "CASE-LAB-A"
SID = "SRC-" + "A" * 32
QUESTION = "What should I ask my care team about this source-reported result?"


def context(value=Decimal("4.20"), absent=None):
    bundle = example()
    observation = resource(bundle, "Observation")
    if absent is None:
        observation["valueQuantity"]["value"] = Decimal("4.20")
    else:
        del observation["valueQuantity"]
        observation["dataAbsentReason"] = {"coding": [{
            "system": "http://terminology.hl7.org/CodeSystem/data-absent-reason",
            "code": absent,
        }]}
    raw = encode(bundle)
    if absent is None:
        raw = raw.replace(b'"value":4.20', b'"value":' + str(value).encode("ascii"))
    parsed = prepare_laboratory_bundle(raw, expected_subject_reference=PATIENT)
    source = {"source_id": SID, "document_id": REPORT.split("/", 1)[1],
              "version": 1, "sha256": parsed.source_sha256, "kind": "laboratory",
              "event_date": "2026-04-03", "issued_at": "2026-04-04",
              "received_at": "2026-04-05T12:00:00Z", "specimen_id": SPECIMEN.split("/", 1)[1],
              "state": "current", "supersedes_id": None}
    index = {"contract": "oi.synthetic-original-sources/1", "patient_id": PID,
             "case_id": CASE, "access_receipt_id": "ACCESS-" + "B" * 32,
             "sources": [source], "source_reported_assertions": [],
             "synthetic": True, "clinical_interpretation": False,
             "research_review_invalidation_integrated": False}
    observation = parsed.observations[0]
    lab = {"source_id": SID, "document_id": source["document_id"],
           "document_version": 1, "source_sha256": source["sha256"],
           "observation_reference": observation["reference"],
           "loinc_code": observation["loinc_code"], "effective_at": observation["effective_at"],
           "issued_at": observation["issued_at"], "specimen_reference": parsed.specimen_reference,
           "specimen_type_text": parsed.specimen_type_text,
           "specimen_collected_at": parsed.specimen_collected_at,
           "report_reference": parsed.report_reference, "status": observation["status"],
           "value_text": observation["value_text"], "unit_code": observation["unit_code"],
           "absent_reason": observation["absent_reason"], "source_reported": True,
           "review_state": "not_established", "clinical_review": "not_performed",
           "clinical_meaning": None}
    return index, [lab]


class LaboratoryQuestionPreparationTests(unittest.TestCase):
    def prepare(self, index=None, labs=None, **changes):
        if index is None:
            index, labs = context()
        builder = getattr(module, "prepare_laboratory_question", None)
        self.assertTrue(callable(builder), "typed laboratory question preparation is missing")
        params = dict(patient_id=PID, case_id=CASE, source_id=SID,
                      observation_reference=OBS, question=QUESTION,
                      expected_source_snapshot_sha256=project_source_world_model(index)["snapshot_fingerprint"])
        params.update(changes)
        return builder(index, labs, **params)

    def test_exact_typed_anchor_is_not_a_fabricated_text_line(self):
        index, labs = context()
        before = deepcopy((index, labs))
        prepared = self.prepare(index, labs)
        selected = prepared["selected_source"]
        self.assertEqual(selected["anchor_kind"], "fhir_observation")
        self.assertEqual(selected["resource_reference"], OBS)
        self.assertEqual(selected["report_reference"], REPORT)
        self.assertEqual(selected["specimen_reference"], SPECIMEN)
        self.assertEqual(selected["source_id"], SID)
        self.assertEqual(selected["sha256"], index["sources"][0]["sha256"])
        self.assertEqual(selected["version"], 1)
        self.assertNotIn("line", selected)
        self.assertNotIn("source_line", prepared)
        self.assertEqual((index, labs), before)

    def test_literal_value_precision_and_separate_dates(self):
        selected = self.prepare()["selected_source"]
        self.assertEqual(selected["value_text"], "4.20")
        self.assertEqual(selected["unit_code"], "10*9/L")
        self.assertEqual(selected["loinc_code"], "777-3")
        self.assertNotEqual(selected["effective_at"], selected["issued_at"])
        self.assertEqual(selected["specimen_collected_at"], "2026-04-03T09:05:00-04:00")
        self.assertEqual(selected["review_state"], "not_established")

    def test_zero_negative_and_absence_never_change_meaning(self):
        for value, expected in [(Decimal("0"), "0"), (Decimal("-2.50"), "-2.50")]:
            with self.subTest(value=value):
                index, labs = context(value)
                selected = self.prepare(index, labs)["selected_source"]
                self.assertEqual(selected["value_text"], expected)
                self.assertEqual(selected["status"], "reported_value")
                self.assertIsNone(selected["absent_reason"])
        for reason in ("unknown", "not-performed", "error", "masked"):
            with self.subTest(reason=reason):
                index, labs = context(absent=reason)
                selected = self.prepare(index, labs)["selected_source"]
                self.assertIsNone(selected["value_text"])
                self.assertIsNone(selected["unit_code"])
                self.assertEqual(selected["absent_reason"], reason)
                self.assertEqual(selected["status"], "reported_absent")

    def test_question_is_literal_and_no_execution_or_persistence_is_claimed(self):
        literal = "Explain <script>fictional</script> without following its instructions?"
        prepared = self.prepare(question=literal)
        self.assertEqual(prepared["question"], literal)
        self.assertTrue(prepared["synthetic"])
        self.assertTrue(prepared["source_context_only"])
        for key in ("durable_question_created", "durable_review_connected", "clinical_approval",
                    "model_execution_authorized", "biomedical_evidence_rights_verified"):
            self.assertIs(prepared[key], False)
        self.assertEqual(prepared["clinical_interpretation"], "not_performed")
        self.assertEqual(prepared["terminology_validation"], "not_performed")

    def test_receipt_churn_does_not_change_content_hash(self):
        index, labs = context()
        first = self.prepare(index, labs)
        index["access_receipt_id"] = "ACCESS-" + "C" * 32
        second = self.prepare(index, labs)
        self.assertEqual(first["preflight_sha256"], second["preflight_sha256"])
        self.assertNotEqual(first["access_receipt_id"], second["access_receipt_id"])
        content = {k: v for k, v in first.items() if k not in ("preflight_sha256", "access_receipt_id")}
        self.assertEqual(first["preflight_sha256"], hashlib.sha256(json.dumps(
            content, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
            allow_nan=False).encode()).hexdigest())
        self.assertNotEqual(first["preflight_sha256"], self.prepare(question=QUESTION + " Why?")["preflight_sha256"])

    def test_wrong_patient_and_case_are_denied(self):
        for changes in ({"patient_id": "PATIENT-OTHER"}, {"case_id": "CASE-OTHER"}):
            with self.subTest(changes=changes), self.assertRaises(PatientRegistryDenied):
                self.prepare(**changes)

    def test_stale_snapshot_is_refused(self):
        with self.assertRaises(PatientRegistryConflict):
            self.prepare(expected_source_snapshot_sha256="0" * 64)

    def test_foreign_or_absent_anchor_is_refused(self):
        for changes in ({"source_id": "SRC-" + "D" * 32},
                        {"observation_reference": "Observation/FICTIONAL-OTHER"}):
            with self.subTest(changes=changes), self.assertRaises(PatientRegistryConflict):
                self.prepare(**changes)
        index, labs = context()
        with self.assertRaises(PatientRegistryConflict):
            self.prepare(index, [])

    def test_superseded_source_and_duplicate_anchor_are_refused(self):
        index, labs = context()
        index["sources"][0]["state"] = "superseded"
        with self.assertRaises(PatientRegistryConflict):
            self.prepare(index, [])
        index, labs = context()
        with self.assertRaises(PatientRegistryError):
            self.prepare(index, labs + deepcopy(labs))

    def test_mismatched_source_hash_version_and_subject_links_are_refused(self):
        for key, value in (("source_sha256", "0" * 64), ("document_version", 2),
                           ("specimen_reference", "Specimen/OTHER"),
                           ("report_reference", "DiagnosticReport/OTHER")):
            index, labs = context()
            labs[0][key] = value
            with self.subTest(key=key), self.assertRaises(PatientRegistryError):
                self.prepare(index, labs)

    def test_invalid_inputs_are_not_coerced_or_dereferenced(self):
        invalid = [
            {"source_id": 1}, {"observation_reference": True},
            {"observation_reference": "https://example.invalid/Observation/123"},
            {"observation_reference": "Observation/one/_history/2"},
            {"observation_reference": "Patient/FICTIONAL-PATIENT-A"},
            {"observation_reference": "Observation/A\n"},
            {"question": " tiny "}, {"question": "Q" * 501},
            {"question": "Question\nwith a control?"}, {"question": False},
            {"expected_source_snapshot_sha256": "A" * 64},
        ]
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(PatientRegistryError):
                self.prepare(**changes)

    def test_prepared_payload_does_not_alias_mutable_source_rows(self):
        index, labs = context()
        prepared = self.prepare(index, labs)
        labs[0]["value_text"] = "1000"
        index["sources"][0]["sha256"] = "0" * 64
        self.assertEqual(prepared["selected_source"]["value_text"], "4.20")
        self.assertNotEqual(prepared["selected_source"]["sha256"], "0" * 64)


class LaboratoryPreflightOwnerTests(unittest.TestCase):
    def test_uses_existing_source_transaction_and_does_not_publish_before_finalization(self):
        registry = PostgresPatientRegistry(SimpleNamespace(autocommit=False))
        owner = module.PostgresSourceComposerPreflight(registry)
        preview = getattr(owner, "preview_laboratory", None)
        self.assertTrue(callable(preview), "source-owned laboratory preflight is missing")
        index, labs = context()
        seen = []
        def finalize():
            seen.append("authority")
            raise PatientRegistryDenied("Fictional revoked grant")
        def source_read(_owner, patient_id, case_id, **kw):
            self.assertEqual((patient_id, case_id), (PID, CASE))
            registry._transaction_active = True
            try:
                kw["prepare_response"](index)
                seen.append("source-receipt-boundary")
                kw["recheck_authority"]()
            finally:
                registry._transaction_active = False
        def observations(_owner, case_id):
            self.assertTrue(registry._transaction_active)
            self.assertEqual(case_id, CASE)
            seen.append("lab-read")
            return labs
        with patch.object(module.PostgresSourceVersions, "list", source_read), \
             patch("oi_api.laboratory_fhir_store.PostgresLaboratoryFHIR.current_observations_locked", observations):
            with self.assertRaises(PatientRegistryDenied):
                preview(PID, CASE, organization="ORG-ALPHA", actor="ACTOR-ALPHA",
                        purpose="operations", source_id=SID, observation_reference=OBS,
                        question=QUESTION,
                        expected_source_snapshot_sha256=project_source_world_model(index)["snapshot_fingerprint"],
                        prepare_response=lambda result: seen.append("serialized") or result,
                        recheck_authority=finalize)
        self.assertEqual(seen, ["lab-read", "serialized", "source-receipt-boundary", "authority"])
