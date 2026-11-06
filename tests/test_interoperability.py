"""Tests for program plan slice D2: live interoperability.

FHIR R4 exchange (routes + UI wiring is covered by the HTTP tests
below), terminology (modality schema packs), and the DICOM report-only
surface — all on synthetic fixtures, with no live-system connection
and no live model call.

The import fixtures are hand-authored bundles, independent of the
exporter, so the translator is tested against its contract rather than
against its own output; the round-trip test then proves export and
import agree.
"""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence.__main__ import FICTIONAL_ACTOR_HEADER, Handler, seed
from open_intelligence.dicom import validate_dicom_report
from open_intelligence.fhir_exchange import (
    build_fhir_bundle,
    fhir_bundle_to_report,
    mcode_status,
)
from open_intelligence.patient_access import (
    PatientAccessAdapter,
    adapter_envelope_from_dict,
)
from open_intelligence.store import CaseStore, InvalidInput
from open_intelligence.terminology import (
    MODALITY_PACKS,
    TERMINOLOGY_SYSTEMS,
    codings_for,
    system_status,
    terminology_table,
    validate_coding,
)
from open_intelligence.vertical import default_vertical, get_vertical

LOINC = "http://loinc.org"
ICD10 = "http://hl7.org/fhir/sid/icd-10"
SNOMED = "http://snomed.info/sct"


def _div(text):
    return {"status": "generated",
            "div": '<div xmlns="http://www.w3.org/1999/xhtml">' + text + "</div>"}


def _observation(obs_id, *, status="final", codings=(), text="hemoglobin",
                 quote="Hemoglobin was measured as 14.2 g/dL in the fictional sample.",
                 certainty="reported", effective="2026-05-03", specimen=None,
                 patient_id="CASE-ALPHA"):
    resource = {
        "resourceType": "Observation",
        "id": obs_id,
        "status": status,
        "code": {"coding": [dict(c) for c in codings], "text": text},
        "subject": {"reference": f"Patient/{patient_id}"},
        "effectiveDateTime": effective,
        "valueString": quote,
        "text": _div(quote),
        "extension": [{"url": "https://example.invalid/oi-synthetic/certainty",
                       "valueCode": certainty}],
    }
    if specimen is not None:
        resource["specimen"] = {"reference": f"Specimen/{specimen}"}
    return resource


def _condition(cond_id, *, quote="Fictional biopsy reports a malignant epithelial neoplasm.",
              certainty="indeterminate", onset="2026-05-03"):
    return {
        "resourceType": "Condition",
        "id": cond_id,
        "clinicalStatus": {"coding": [{
            "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
            "code": "active", "display": "Active"}]},
        "verificationStatus": {"coding": [{
            "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
            "code": "unconfirmed", "display": "Unconfirmed"}]},
        "code": {"coding": [{"system": ICD10, "code": "C80.1",
                             "display": "Malignant (primary) neoplasm, unspecified"}],
                 "text": "histology"},
        "subject": {"reference": "Patient/CASE-ALPHA"},
        "onsetDateTime": onset,
        "text": _div(quote),
        "note": [{"text": "Synthetic demonstration data — unconfirmed, not a diagnosis."}],
        "extension": [{"url": "https://example.invalid/oi-synthetic/certainty",
                       "valueCode": certainty}],
    }


def _bundle(*resources, bundle_id="OI-BUNDLE-CASE-ALPHA-1", version="1",
            last_updated="2026-05-18", patient_id="CASE-ALPHA"):
    entries = [{"fullUrl": f"Patient/{patient_id}",
                "resource": {"resourceType": "Patient", "id": patient_id,
                             "text": _div(f"Fictional case {patient_id}.")}}]
    for resource in resources:
        entries.append({"fullUrl": f"{resource['resourceType']}/{resource['id']}",
                        "resource": resource})
    return {
        "resourceType": "Bundle",
        "id": bundle_id,
        "meta": {"lastUpdated": last_updated, "versionId": version},
        "type": "collection",
        "entry": entries,
    }


def _canonical(bundle):
    return json.dumps(bundle, indent=2, sort_keys=True,
                      ensure_ascii=False).encode("utf-8")


def _loinc_hemoglobin():
    return {"system": LOINC, "code": "718-7",
            "display": "Hemoglobin [Mass/volume] in Blood"}


def _envelope(case_id="CASE-ALPHA", *, dropped=(), subject="CASE-ALPHA",
              org="OI-TEST-ORG"):
    data = {
        "adapter_id": "OI-TEST-ADAPTER",
        "source_organization": org,
        "source_system": "OI-TEST-EHR",
        "case_id": case_id,
        "source_subject_ref": subject,
        "authorization": {
            "receipt_id": "RCPT-1",
            "purpose": "individual-access",
            "scope": ["read"],
            "granted_at": "2026-01-01",
            "expires_at": "2027-01-01",
        },
        "retrieved_at": "2026-05-20",
    }
    if dropped is not None:
        data["transformation"] = {"dropped_fields": list(dropped),
                                  "truncated_fields": [],
                                  "cardinality_changes": []}
    return adapter_envelope_from_dict(data)


class TerminologyTests(unittest.TestCase):
    def test_system_availability(self):
        self.assertEqual(system_status(LOINC)["availability"], "available")
        self.assertEqual(system_status(ICD10)["availability"], "available")
        self.assertEqual(
            system_status("http://www.nlm.nih.gov/research/umls/rxnorm")["availability"],
            "no_pinned_codes")
        self.assertEqual(system_status(SNOMED)["availability"], "blocked")
        with self.assertRaises(InvalidInput) as ctx:
            system_status("http://example.invalid/nope")
        self.assertIn("unknown_terminology_system", str(ctx.exception))

    def test_pinned_codes_are_exact(self):
        # The table's exact contents are pinned: three LOINC lab codes.
        # Any drift (a new code, a changed code) fails here by design.
        pinned = set()
        for pack in MODALITY_PACKS.values():
            for codings in pack["bindings"].values():
                for coding in codings:
                    pinned.add((coding["system"], coding["code"]))
        self.assertEqual(pinned, {
            (LOINC, "718-7"), (LOINC, "2339-0"), (LOINC, "2160-0")})

    def test_shared_and_vertical_lookups(self):
        self.assertEqual(codings_for("hemoglobin"),
                         (_loinc_hemoglobin(),))
        self.assertEqual(codings_for("glucose")[0]["code"], "2339-0")
        self.assertEqual(codings_for("creatinine")[0]["code"], "2160-0")
        self.assertEqual(codings_for("marker-a"), ())
        oncology = get_vertical("oncology")
        self.assertEqual(codings_for("histology", oncology),
                         ({"system": ICD10, "code": "C80.1",
                           "display": "Malignant (primary) neoplasm, unspecified"},))
        self.assertEqual(codings_for("histology", get_vertical("cardiology")), ())

    def test_validate_coding_fails_closed(self):
        self.assertEqual(validate_coding(LOINC, "718-7"), _loinc_hemoglobin())
        oncology = get_vertical("oncology")
        self.assertEqual(validate_coding(ICD10, "C80.1", oncology)["code"], "C80.1")
        for system, code in ((LOINC, "99999-9"), (ICD10, "C99.9"),
                             (LOINC, "718-7 "), ("http://example.invalid/x", "1")):
            with self.subTest(system=system, code=code):
                with self.assertRaises(InvalidInput):
                    validate_coding(system, code, oncology)
        with self.assertRaises(InvalidInput) as ctx:
            validate_coding(SNOMED, "254837009", oncology)
        self.assertIn("terminology_system_blocked", str(ctx.exception))
        # A vertical binding is not valid without its vertical.
        with self.assertRaises(InvalidInput):
            validate_coding(ICD10, "C80.1")

    def test_terminology_table_states_the_limits(self):
        table = terminology_table(default_vertical())
        self.assertEqual(table["vertical"], "oncology")
        self.assertEqual(table["systems"][SNOMED]["availability"], "blocked")
        self.assertEqual(table["vertical_bindings"]["histology"][0]["code"], "C80.1")
        self.assertEqual(table["modality_packs"]["laboratory"]["bindings"]
                         ["hemoglobin"][0]["code"], "718-7")
        self.assertEqual(table["modality_packs"]["clinical"]["bindings"], {})


class FhirTranslationTests(unittest.TestCase):
    def _translate(self, bundle):
        return fhir_bundle_to_report(_canonical(bundle),
                                     validate_coding=validate_coding)

    def test_valid_bundle_translates(self):
        report, dropped = self._translate(_bundle(
            _observation("OBS-HGB-1", codings=(_loinc_hemoglobin(),))))
        self.assertEqual(dropped, ())
        self.assertEqual(report.kind, "fhir-bundle")
        self.assertEqual(report.document_id, "OI-BUNDLE-CASE-ALPHA-1")
        self.assertEqual(report.patient_id, "CASE-ALPHA")
        self.assertEqual(report.event_date, "2026-05-03")
        self.assertEqual(report.issued_at, "2026-05-18")
        self.assertIsNone(report.amends)
        self.assertEqual(len(report.findings), 1)
        finding = report.findings[0]
        self.assertEqual(finding.key, "fhir-observation-obs-hgb-1")
        self.assertEqual(finding.state, "reported")
        self.assertIn("14.2 g/dL", finding.quote)
        self.assertIsInstance(finding.line, int)
        self.assertGreater(finding.line, 1)

    def test_shared_id_across_resource_types_uses_distinct_lines(self):
        observation = _observation("SHARED-1", quote="Fictional hemoglobin 14.2 g/dL.")
        condition = _condition("SHARED-1", quote="Fictional unconfirmed pathology.")
        original = _canonical(_bundle(observation, condition))
        report, _ = fhir_bundle_to_report(original,
                                          validate_coding=validate_coding)
        self.assertEqual(len(report.findings), 2)
        self.assertNotEqual(report.findings[0].line, report.findings[1].line)
        original_lines = original.decode("utf-8").splitlines()
        for finding in report.findings:
            self.assertIn('"id": "SHARED-1"', original_lines[finding.line - 1])
        self.assertEqual({f.key for f in report.findings}, {
            "fhir-observation-shared-1", "fhir-condition-shared-1"})

    def test_status_map_without_certainty_extension(self):
        observation = _observation("OBS-1", status="preliminary")
        del observation["extension"]
        report, _ = self._translate(_bundle(observation))
        self.assertEqual(report.findings[0].state, "pending")
        observation = _observation("OBS-2", status="cancelled")
        del observation["extension"]
        report, _ = self._translate(_bundle(observation))
        self.assertEqual(report.findings[0].state, "not-reported")

    def test_condition_translates_with_verification_status(self):
        report, dropped = self._translate(_bundle(_condition("COND-1")))
        self.assertEqual(dropped, ())
        self.assertEqual(report.findings[0].key, "fhir-condition-cond-1")
        self.assertEqual(report.findings[0].state, "indeterminate")

    def test_amendment_version_maps_to_amends(self):
        report, _ = self._translate(_bundle(
            _observation("OBS-HGB-1", codings=(_loinc_hemoglobin(),)),
            version="2"))
        self.assertEqual(report.amends, ("OI-BUNDLE-CASE-ALPHA-1", 1))

    def test_dropped_fields_are_computed(self):
        observation = _observation("OBS-HGB-1", codings=(_loinc_hemoglobin(),))
        observation["performer"] = [{"display": "Fictional Lab"}]
        bundle = _bundle(observation)
        bundle["entry"][1]["request"] = {"method": "POST"}
        _, dropped = self._translate(bundle)
        self.assertEqual(dropped, ("Observation.performer", "entry.request"))

    def test_rejections(self):
        cases = {
            "snomed_coding": _bundle(_observation(
                "OBS-1", codings=({"system": SNOMED, "code": "254837009",
                                   "display": "Malignant neoplasm"},))),
            "unknown_code": _bundle(_observation(
                "OBS-1", codings=({"system": LOINC, "code": "99999-9",
                                   "display": "No such code"},))),
            "unknown_system": _bundle(_observation(
                "OBS-1", codings=({"system": "http://example.invalid/x",
                                   "code": "1", "display": "x"},))),
            "entered_in_error": _bundle(_observation(
                "OBS-1", status="entered-in-error")),
            "missing_narrative": _bundle(
                {**_observation("OBS-1"), "text": {"status": "generated"}}),
            "wrong_subject": _bundle({**_observation("OBS-1"),
                                      "subject": {"reference": "Patient/CASE-BETA"}}),
            "duplicate_resource": _bundle(
                _observation("OBS-1"), _observation("OBS-1")),
            "no_patient": {**_bundle(_observation("OBS-1")), "entry": []},
            "bad_type": {**_bundle(_observation("OBS-1")), "type": "transaction"},
        }
        for name, bundle in cases.items():
            with self.subTest(name=name):
                with self.assertRaises(InvalidInput):
                    self._translate(bundle)

    def test_mcode_profile_claim_is_rejected(self):
        bundle = _bundle(_observation("OBS-1"))
        bundle["meta"]["profile"] = [
            "http://hl7.org/fhir/us/mcode/StructureDefinition/mcode-cancer-condition"]
        with self.assertRaises(InvalidInput) as ctx:
            self._translate(bundle)
        self.assertIn("mcode_profile_unverified", str(ctx.exception))
        bundle["meta"]["profile"] = ["http://example.invalid/some-profile"]
        with self.assertRaises(InvalidInput) as ctx:
            self._translate(bundle)
        self.assertIn("fhir_profile_claim_unverified", str(ctx.exception))

    def test_dangling_report_reference_is_rejected(self):
        report_resource = {
            "resourceType": "DiagnosticReport", "id": "REP-1",
            "status": "final",
            "code": {"text": "pathology report X"},
            "subject": {"reference": "Patient/CASE-ALPHA"},
            "effectiveDateTime": "2026-05-03",
            "result": [{"reference": "Observation/OBS-MISSING"}],
            "text": _div("Report narrative."),
        }
        with self.assertRaises(InvalidInput) as ctx:
            self._translate(_bundle(_observation("OBS-1"), report_resource))
        self.assertIn("fhir_dangling_reference", str(ctx.exception))

    def test_value_narrative_mismatch_is_rejected(self):
        observation = _observation("OBS-1")
        observation["valueString"] = "A different string."
        with self.assertRaises(InvalidInput) as ctx:
            self._translate(_bundle(observation))
        self.assertIn("fhir_value_narrative_mismatch", str(ctx.exception))

    def test_mcode_status_is_not_claimed(self):
        status = mcode_status()
        self.assertEqual(status["status"], "not_claimed")
        self.assertTrue(all(info["status"] == "not_claimed"
                            for info in status["profiles"].values()))


class FhirStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "fhir.sqlite")
        self.store = CaseStore(self.path)
        self.store.add_case("CASE-ALPHA", "Fictional case Alpha")
        self.store.add_case("CASE-BETA", "Fictional case Beta")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_import_stores_original_bytes_and_assertions(self):
        bundle = _bundle(_observation("OBS-HGB-1", codings=(_loinc_hemoglobin(),)),
                         _condition("COND-1"))
        raw = _canonical(bundle)
        outcome = self.store.import_fhir_bundle("CASE-ALPHA", raw)
        self.assertEqual(outcome["result"], "imported")
        self.assertEqual(outcome["version"], 1)
        state = self.store.state("CASE-ALPHA")
        sources = [s for s in state["sources"] if s["kind"] == "fhir-bundle"]
        self.assertEqual(len(sources), 1)
        import hashlib
        self.assertEqual(sources[0]["sha256"], hashlib.sha256(raw).hexdigest())
        keys = {a["finding_key"]: a for a in state["assertions"]}
        self.assertEqual(keys["fhir-observation-obs-hgb-1"]["certainty"], "reported")
        self.assertEqual(keys["fhir-condition-cond-1"]["certainty"], "indeterminate")
        self.assertEqual(self.store.import_fhir_bundle("CASE-ALPHA", raw)["result"],
                         "duplicate")

    def test_fhir_assertions_keep_independent_same_id_anchors(self):
        bundle = _bundle(
            _observation("SHARED-1", quote="Fictional hemoglobin 14.2 g/dL."),
            _condition("SHARED-1", quote="Fictional unconfirmed pathology."))
        raw = _canonical(bundle)
        outcome = self.store.import_fhir_bundle("CASE-ALPHA", raw)
        source_id = outcome["source_id"]
        rows = self.store.db.execute(
            "SELECT finding_key, quote, source_line FROM assertions "
            "WHERE source_version_id=? ORDER BY source_line",
            (source_id,)).fetchall()
        self.assertEqual(len(rows), 2)
        self.assertNotEqual(rows[0]["source_line"], rows[1]["source_line"])
        lines = raw.decode("utf-8").splitlines()
        for row in rows:
            self.assertIn('"id": "SHARED-1"', lines[row["source_line"] - 1])
        self.assertEqual({r["finding_key"] for r in rows}, {
            "fhir-observation-shared-1", "fhir-condition-shared-1"})

    def test_unverified_direct_fhir_proposal_fails_closed(self):
        from open_intelligence.extraction import record_extraction_proposal
        result = self.store.import_fhir_bundle(
            "CASE-ALPHA", _canonical(_bundle(_observation("OBS-1"))))
        source_id = result["source_id"]
        row = self.store.db.execute(
            "SELECT source_line FROM assertions WHERE source_version_id=?",
            (source_id,)).fetchone()
        proposed = record_extraction_proposal(
            self.store, "CASE-ALPHA", source_id,
            [{"finding_key": "unverified-fhir", "certainty": "reported",
              "quote": "Fabricated narrative.",
              "source_line": row["source_line"]}])
        self.assertEqual(proposed.kept, [])
        self.assertEqual(proposed.dropped[0]["reason"],
                         "source_anchor_not_verified")

    def test_wrong_case_bundle_is_quarantined(self):
        bundle = _bundle(_observation("OBS-1", patient_id="CASE-BETA"),
                         patient_id="CASE-BETA")
        outcome = self.store.import_fhir_bundle("CASE-ALPHA", _canonical(bundle))
        self.assertEqual(outcome["result"], "quarantined")
        self.assertEqual(outcome["reason"], "patient_mismatch")

    def test_amendment_supersedes_and_requires_version(self):
        first = _bundle(_observation("OBS-HGB-1", codings=(_loinc_hemoglobin(),)))
        self.assertEqual(
            self.store.import_fhir_bundle("CASE-ALPHA", _canonical(first))["result"],
            "imported")
        changed = _bundle(_observation(
            "OBS-HGB-1", codings=(_loinc_hemoglobin(),),
            quote="Hemoglobin was measured as 13.9 g/dL in the fictional sample."))
        with self.assertRaises(InvalidInput):
            self.store.import_fhir_bundle("CASE-ALPHA", _canonical(changed))
        amended = _bundle(_observation(
            "OBS-HGB-1", codings=(_loinc_hemoglobin(),),
            quote="Hemoglobin was measured as 13.9 g/dL in the fictional sample."),
            version="2")
        outcome = self.store.import_fhir_bundle("CASE-ALPHA", _canonical(amended))
        self.assertEqual(outcome["result"], "imported")
        self.assertEqual(outcome["version"], 2)
        state = self.store.state("CASE-ALPHA")
        self.assertEqual(
            [s["state"] for s in state["sources"] if s["kind"] == "fhir-bundle"],
            ["superseded", "current"])


class FhirExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "export.sqlite")
        seed(self.path)
        self.store = CaseStore(self.path)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_seeded_case_exports_a_bundle(self):
        payload = build_fhir_bundle(self.store.state("CASE-ALPHA"),
                                    default_vertical(), codings_for=codings_for)
        bundle = payload["bundle"]
        self.assertEqual(bundle["resourceType"], "Bundle")
        self.assertEqual(bundle["type"], "collection")
        self.assertEqual(bundle["id"], "OI-BUNDLE-CASE-ALPHA-1")
        self.assertEqual(payload["mcode"]["status"], "not_claimed")
        self.assertEqual(payload["unbound_findings"],
                         ["comparison", "lesion-size", "margin", "marker-a"])
        types = [e["resource"]["resourceType"] for e in bundle["entry"]]
        self.assertEqual(types.count("Patient"), 1)
        self.assertEqual(types.count("Observation"), 5)
        self.assertEqual(types.count("DiagnosticReport"), 2)
        self.assertEqual(types.count("Condition"), 1)
        self.assertFalse(any("profile" in (e["resource"].get("meta") or {})
                             for e in bundle["entry"]))
        self.assertNotIn("profile", bundle.get("meta", {}))
        histology = next(
            e["resource"] for e in bundle["entry"]
            if e["resource"]["resourceType"] == "Condition")
        self.assertEqual(histology["code"]["coding"][0]["code"], "C80.1")
        self.assertEqual(
            histology["verificationStatus"]["coding"][0]["code"], "unconfirmed")

    def test_export_import_round_trip(self):
        payload = build_fhir_bundle(self.store.state("CASE-ALPHA"),
                                    default_vertical(), codings_for=codings_for)
        raw = _canonical(payload["bundle"])
        fresh = tempfile.TemporaryDirectory()
        try:
            path = str(Path(fresh.name) / "roundtrip.sqlite")
            store = CaseStore(path)
            try:
                store.add_case("CASE-ALPHA", "Fictional case Alpha")
                outcome = store.import_fhir_bundle("CASE-ALPHA", raw)
                self.assertEqual(outcome["result"], "imported")
                state = store.state("CASE-ALPHA")
                keys = {a["finding_key"]: a for a in state["assertions"]}
                self.assertEqual(len(keys), 6)
                self.assertEqual(keys["fhir-observation-obs-1"]["certainty"],
                                 "reported")
                self.assertEqual(keys["fhir-condition-cond-1"]["certainty"],
                                 "indeterminate")
                self.assertEqual(
                    keys["fhir-observation-obs-1"]["quote"],
                    "Fictional biopsy reports a malignant epithelial neoplasm; "
                    "classification pending external review.")
            finally:
                store.close()
        finally:
            fresh.cleanup()

    def test_lab_finding_exports_its_loinc_code(self):
        lab = (b"OI-SYNTHETIC-REPORT/1\nPatient: CASE-ALPHA\nDocument: LAB-1\n"
               b"Type: laboratory\nEvent-Date: 2026-05-04\nIssued-At: 2026-05-05\n"
               b"Finding: hemoglobin|reported|Hemoglobin was measured as 14.2 g/dL.\n")
        self.assertEqual(self.store.import_report("CASE-ALPHA", lab)["result"],
                         "imported")
        payload = build_fhir_bundle(self.store.state("CASE-ALPHA"),
                                    default_vertical(), codings_for=codings_for)
        hemoglobin = next(
            e["resource"] for e in payload["bundle"]["entry"]
            if e["resource"]["resourceType"] == "Observation"
            and e["resource"]["code"]["text"] == "hemoglobin")
        self.assertEqual(hemoglobin["code"]["coding"],
                         [{"system": LOINC, "code": "718-7",
                           "display": "Hemoglobin [Mass/volume] in Blood"}])
        self.assertNotIn("hemoglobin", payload["unbound_findings"])


class AdapterDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / "adapter.sqlite")
        self.store = CaseStore(self.path)
        self.store.add_case("CASE-ALPHA", "Fictional case Alpha")
        self.store.add_case("CASE-BETA", "Fictional case Beta")
        self.adapter = PatientAccessAdapter(self.store)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_fhir_delivery_happy_path(self):
        bundle = _bundle(_observation("OBS-HGB-1", codings=(_loinc_hemoglobin(),)))
        outcome = self.adapter.deliver_fhir_bundle(
            _envelope(), _canonical(bundle))
        self.assertEqual(outcome["result"], "imported")
        self.assertEqual(outcome["dropped_fields"], [])

    def test_lossy_delivery_requires_declared_receipt(self):
        observation = _observation("OBS-HGB-1", codings=(_loinc_hemoglobin(),))
        observation["performer"] = [{"display": "Fictional Lab"}]
        raw = _canonical(_bundle(observation))
        outcome = self.adapter.deliver_fhir_bundle(_envelope(dropped=None), raw)
        self.assertEqual(outcome["result"], "rejected")
        self.assertEqual(outcome["reason"], "transformation_loss_undocumented")
        outcome = self.adapter.deliver_fhir_bundle(
            _envelope(dropped=("Observation.performer",)), raw)
        self.assertEqual(outcome["result"], "imported")
        self.assertEqual(outcome["dropped_fields"], ["Observation.performer"])

    def test_declared_receipt_must_match_computed_loss(self):
        bundle = _bundle(_observation("OBS-HGB-1", codings=(_loinc_hemoglobin(),)))
        with self.assertRaises(InvalidInput):
            self.adapter.deliver_fhir_bundle(
                _envelope(dropped=("Observation.performer",)), _canonical(bundle))

    def test_revoked_receipt_is_rejected(self):
        adapter = PatientAccessAdapter(self.store)
        adapter.revoke("CASE-ALPHA", "RCPT-1", "Fictional revocation for testing")
        bundle = _bundle(_observation("OBS-HGB-1", codings=(_loinc_hemoglobin(),)))
        outcome = adapter.deliver_fhir_bundle(_envelope(), _canonical(bundle))
        self.assertEqual(outcome["result"], "rejected")
        self.assertEqual(outcome["reason"], "revoked_authorization")

    def test_identity_collision_is_quarantined(self):
        bundle = _bundle(_observation("OBS-HGB-1", codings=(_loinc_hemoglobin(),)))
        self.assertEqual(self.adapter.deliver_fhir_bundle(
            _envelope(), _canonical(bundle))["result"], "imported")
        outcome = self.adapter.deliver_fhir_bundle(
            _envelope(subject="CASE-BETA"), _canonical(bundle))
        self.assertEqual(outcome["result"], "rejected")
        self.assertEqual(outcome["reason"], "identity_collision")


class DicomTests(unittest.TestCase):
    def test_valid_report(self):
        record = validate_dicom_report({
            "study_uid": "OI-SYNTHETIC-STUDY-1", "modality": "CT",
            "accession": "ACC-1", "report_text": "Fictional CT report text.",
            "source_version_id": None})
        self.assertEqual(record["modality"], "CT")

    def test_pixel_fields_are_rejected_at_any_depth(self):
        for payload in (
            {"study_uid": "OI-SYNTHETIC-STUDY-1", "modality": "CT",
             "accession": "ACC-1", "report_text": "x", "PixelData": "AAAA"},
            {"study_uid": "OI-SYNTHETIC-STUDY-1", "modality": "CT",
             "accession": "ACC-1", "report_text": "x",
             "series": [{"pixel_data": "AAAA"}]},
            {"study_uid": "OI-SYNTHETIC-STUDY-1", "modality": "CT",
             "accession": "ACC-1", "report_text": "x",
             "BulkDataURI": "http://example.invalid/pixels"},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(InvalidInput) as ctx:
                    validate_dicom_report(payload)
                self.assertIn("dicom_pixels_rejected", str(ctx.exception))

    def test_bad_modality_and_study_uid(self):
        base = {"study_uid": "OI-SYNTHETIC-STUDY-1", "modality": "CT",
                "accession": "ACC-1", "report_text": "x"}
        with self.assertRaises(InvalidInput):
            validate_dicom_report({**base, "modality": "NOPE"})
        with self.assertRaises(InvalidInput):
            validate_dicom_report({**base, "study_uid": "1.2.840.12345"})

    def test_store_round_trip_and_no_pixel_column(self):
        tmp = tempfile.TemporaryDirectory()
        try:
            store = CaseStore(str(Path(tmp.name) / "dicom.sqlite"))
            try:
                store.add_case("CASE-ALPHA", "Fictional case Alpha")
                outcome = store.record_dicom_report("CASE-ALPHA", {
                    "study_uid": "OI-SYNTHETIC-STUDY-1", "modality": "MR",
                    "accession": "ACC-9",
                    "report_text": "Fictional MR report: no pixels stored.",
                    "source_version_id": None})
                self.assertEqual(outcome["result"], "recorded")
                rows = store.list_dicom_reports("CASE-ALPHA")
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["modality"], "MR")
                with self.assertRaises(InvalidInput):
                    store.record_dicom_report("CASE-ALPHA", {
                        "study_uid": "OI-SYNTHETIC-STUDY-1", "modality": "CT",
                        "accession": "ACC-2", "report_text": "duplicate study"})
                ddl = store.db.execute(
                    "SELECT sql FROM sqlite_master WHERE type='table' "
                    "AND name='dicom_reports'").fetchone()[0].lower()
                self.assertNotIn("pixel", ddl)
            finally:
                store.close()
        finally:
            tmp.cleanup()


class InteroperabilityHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "interop-http.sqlite")
        seed(cls.path)
        bound_handler = type(
            "BoundInteropHandlerForTest", (Handler,), {"db_path": cls.path})
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), bound_handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(
            target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def request(self, path, data=None, headers=None):
        values = {"Content-Type": "application/json"} if data is not None else {}
        values.setdefault(FICTIONAL_ACTOR_HEADER, "FICTIONAL-NAVIGATOR-A")
        values.update(headers or {})
        request = Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=None if data is None else json.dumps(data).encode(),
            headers=values)
        try:
            with urlopen(request, timeout=5) as response:
                content = response.read()
                return (response.status,
                        json.loads(content)
                        if "json" in response.headers.get("Content-Type")
                        else content)
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_get_bundle(self):
        status, payload = self.request("/api/cases/CASE-ALPHA/fhir/bundle")
        self.assertEqual(status, 200)
        self.assertEqual(payload["bundle"]["resourceType"], "Bundle")
        self.assertEqual(payload["mcode"]["status"], "not_claimed")

    def test_get_terminology(self):
        status, payload = self.request("/api/cases/CASE-ALPHA/fhir/terminology")
        self.assertEqual(status, 200)
        self.assertEqual(payload["systems"][SNOMED]["availability"], "blocked")
        self.assertEqual(payload["vertical_bindings"]["histology"][0]["code"],
                         "C80.1")

    def test_dicom_round_trip_and_pixel_rejection(self):
        status, payload = self.request("/api/cases/CASE-ALPHA/fhir/dicom")
        self.assertEqual(status, 200)
        self.assertEqual(payload["dicom_reports"], [])
        status, payload = self.request("/api/cases/CASE-ALPHA/fhir/dicom", {
            "study_uid": "OI-SYNTHETIC-STUDY-7", "modality": "CT",
            "accession": "ACC-7", "report_text": "Fictional CT report.",
            "source_version_id": None})
        self.assertEqual(status, 201)
        self.assertEqual(payload["result"], "recorded")
        status, payload = self.request("/api/cases/CASE-ALPHA/fhir/dicom")
        self.assertEqual(len(payload["dicom_reports"]), 1)
        status, payload = self.request("/api/cases/CASE-ALPHA/fhir/dicom", {
            "study_uid": "OI-SYNTHETIC-STUDY-8", "modality": "CT",
            "accession": "ACC-8", "report_text": "x", "PixelData": "AAAA"})
        self.assertEqual(status, 422)
        self.assertIn("dicom_pixels_rejected", payload["error"])

    def test_post_bundle_round_trips_through_the_route(self):
        bundle = _bundle(_observation("OBS-HGB-1", codings=(_loinc_hemoglobin(),)))
        envelope = {
            "adapter_id": "OI-TEST-ADAPTER",
            "source_organization": "OI-TEST-ORG-HTTP",
            "source_system": "OI-TEST-EHR",
            "case_id": "CASE-ALPHA",
            "source_subject_ref": "CASE-ALPHA",
            "authorization": {
                "receipt_id": "RCPT-HTTP-1",
                "purpose": "individual-access",
                "scope": ["read"],
                "granted_at": "2026-01-01",
                "expires_at": "2027-01-01",
            },
            "retrieved_at": "2026-05-20",
        }
        status, payload = self.request("/api/cases/CASE-ALPHA/fhir/bundle",
                                       {"envelope": envelope, "bundle": bundle})
        self.assertEqual(status, 200)
        self.assertEqual(payload["result"], "imported")
        status, exported = self.request("/api/cases/CASE-ALPHA/fhir/bundle")
        self.assertEqual(status, 200)
        keys = [e["resource"]["code"]["text"]
                for e in exported["bundle"]["entry"]
                if e["resource"]["resourceType"] == "Observation"]
        self.assertIn("fhir-observation-obs-hgb-1", keys)

    def test_bundle_post_without_actor_is_denied(self):
        bundle = _bundle(_observation("OBS-HGB-1", codings=(_loinc_hemoglobin(),)))
        status, _ = self.request(
            "/api/cases/CASE-ALPHA/fhir/bundle", {"bundle": bundle},
            headers={FICTIONAL_ACTOR_HEADER: "FICTIONAL-NOBODY"})
        self.assertEqual(status, 403)

    def test_malformed_bundle_is_422(self):
        status, payload = self.request(
            "/api/cases/CASE-ALPHA/fhir/bundle",
            {"envelope": {
                "adapter_id": "OI-TEST-ADAPTER",
                "source_organization": "OI-TEST-ORG-HTTP2",
                "source_system": "OI-TEST-EHR",
                "case_id": "CASE-ALPHA",
                "source_subject_ref": "CASE-ALPHA",
                "authorization": {
                    "receipt_id": "RCPT-HTTP-2",
                    "purpose": "individual-access",
                    "scope": ["read"],
                    "granted_at": "2026-01-01",
                    "expires_at": "2027-01-01",
                },
                "retrieved_at": "2026-05-20",
            }, "bundle": {"resourceType": "Bundle", "type": "transaction",
                          "id": "OI-BUNDLE-CASE-ALPHA-9",
                          "meta": {"lastUpdated": "2026-05-18"},
                          "entry": []}})
        self.assertEqual(status, 422)


if __name__ == "__main__":
    unittest.main()
