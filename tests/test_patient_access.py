"""OI-017: patient-directed adapter contract against the existing ledger.

Synthetic fixtures only. Every test asserts a boundary, not an implementation
detail: no silent loss, no merged identity collision, no revoked delivery,
no second source ledger (sources are counted only in source_versions).
"""

import hashlib
import json
import unittest
from pathlib import Path

from open_intelligence.patient_access import (
    AdapterEnvelope,
    AuthorizationReceipt,
    PatientAccessAdapter,
    TransformationReceipt,
    assess_transformation,
    classify_coverage,
)
from open_intelligence.store import CaseStore, InvalidInput

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "examples" / "patient-access"


def read(name):
    return (FIX / name).read_bytes()


def receipt(receipt_id="RCPT-OI017-1", purpose="individual-access",
            granted="2026-01-01", expires="2026-12-31", revoked=None):
    return AuthorizationReceipt(receipt_id, purpose, ("encounter", "pathology"),
                                granted, expires, revoked)


def envelope(case="CASE-OI017", org="INST-A", subject="SUBJ-OI017-A",
             retrieved="2026-02-10", auth=None, **kw):
    return AdapterEnvelope("adapter-synthetic", org, "fhir-synthetic", case,
                           subject, auth or receipt(), retrieved, **kw)


class PatientAccessTest(unittest.TestCase):
    def setUp(self):
        self.store = CaseStore(":memory:")
        self.store.add_case("CASE-OI017", "Fictional OI-017 case")
        self.adapter = PatientAccessAdapter(self.store)

    def tearDown(self):
        self.store.close()

    def sources(self):
        return self.store.state("CASE-OI017")["sources"]

    def events(self, kind):
        return [e for e in self.store.state("CASE-OI017")["events"] if e["kind"] == kind]

    def test_verbatim_import_preserves_hash_and_original(self):
        raw = read("oi017-pathology-specimen-a.txt")
        out = self.adapter.deliver(envelope(), raw)
        self.assertEqual(out["result"], "imported")
        src = self.sources()[0]
        self.assertEqual(src["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(self.store.source_text("CASE-OI017", src["id"]), raw.decode())
        accepted = self.events("adapter_delivery_accepted")
        self.assertEqual(len(accepted), 1)
        # The acceptance event pins the same hash, receipt, and retrieval
        # date as the stored source: the event cannot describe other bytes.
        details = json.loads(accepted[0]["details"])
        self.assertEqual(details["sha256"], src["sha256"])
        self.assertEqual(details["receipt_id"], "RCPT-OI017-1")
        self.assertEqual(details["retrieved_at"], "2026-02-10")

    def test_lossy_transform_without_receipt_is_rejected_and_not_imported(self):
        raw = read("oi017-pathology-specimen-a.txt")
        env = envelope(original_fields={"histology", "marker-a", "margin", "specimen-note"},
                       transformed_fields={"histology", "marker-a"})
        out = self.adapter.deliver(env, raw)
        self.assertEqual(out, {"result": "rejected",
                               "reason": "transformation_loss_undocumented"})
        self.assertEqual(self.sources(), [])

    def test_lossy_transform_with_receipt_imports_original_not_normalized(self):
        raw = read("oi017-pathology-specimen-a.txt")
        loss = assess_transformation({"histology", "marker-a", "margin", "specimen-note"},
                                     {"histology", "marker-a"})
        env = envelope(original_fields={"histology", "marker-a", "margin", "specimen-note"},
                       transformed_fields={"histology", "marker-a"},
                       transformation=loss)
        out = self.adapter.deliver(env, raw)
        self.assertEqual(out["result"], "imported")
        # Original bytes, not a normalized substitute, are the stored source.
        self.assertEqual(self.store.source_text("CASE-OI017", out["source_id"]), raw.decode())
        loss_events = self.events("adapter_loss_receipt")
        self.assertEqual(len(loss_events), 1)
        details = json.loads(loss_events[0]["details"])
        self.assertEqual(sorted(details["dropped_fields"]), ["margin", "specimen-note"])

    def test_identity_collision_is_quarantined_not_merged(self):
        first = self.adapter.deliver(envelope(), read("oi017-encounter-inst-a.txt"))
        self.assertEqual(first["result"], "imported")
        # Same organization, different subject binding: a collision.
        out = self.adapter.deliver(
            envelope(subject="SUBJ-OI017-OTHER"),
            read("oi017-collision-wrong-binding.txt"))
        self.assertEqual(out["result"], "rejected")
        self.assertEqual(out["reason"], "identity_collision")
        self.assertEqual(len(self.sources()), 1)  # collision never became a source
        quarantines = self.store.state("CASE-OI017")["quarantines"]
        self.assertEqual(len(quarantines), 1)
        self.assertEqual(quarantines[0]["reason"], "identity_collision")

    def test_cross_case_subject_reuse_is_rejected(self):
        # One adapter instance, two sequential real deliveries: the second
        # reuses a subject already bound to another case. No private-state
        # injection: the binding below is created by the first deliver call.
        # (Bindings are per adapter instance; see the research doc.)
        first = self.adapter.deliver(envelope(), read("oi017-encounter-inst-a.txt"))
        self.assertEqual(first["result"], "imported")
        self.store.add_case("CASE-OI017-B", "Second fictional case")
        out = self.adapter.deliver(envelope(case="CASE-OI017-B"),
                                   read("oi017-encounter-inst-a.txt"))
        self.assertEqual(out["result"], "rejected")
        self.assertEqual(out["reason"], "identity_collision")
        self.assertEqual(self.store.state("CASE-OI017-B")["sources"], [])
        self.assertEqual(len(self.store.state("CASE-OI017-B")["quarantines"]), 1)

    def test_contradictory_specimen_pathology_coexists_not_merged(self):
        self.adapter.deliver(envelope(), read("oi017-pathology-specimen-a.txt"))
        out = self.adapter.deliver(envelope(org="INST-B", subject="SUBJ-OI017-B"),
                                   read("oi017-pathology-specimen-b.txt"))
        self.assertEqual(out["result"], "imported")
        state = self.store.state("CASE-OI017")
        self.assertEqual(len([s for s in state["sources"] if s["state"] == "current"]), 2)
        specimens = {s["specimen_id"] for s in state["sources"]}
        self.assertEqual(specimens, {"SPEC-OI017-A", "SPEC-OI017-B"})
        histology = {a["quote"] for a in state["assertions"] if a["finding_key"] == "histology"}
        self.assertEqual(len(histology), 2)  # conflict preserved, not resolved

    def test_late_correction_supersedes_and_invalidates_snapshot(self):
        self.adapter.deliver(envelope(), read("oi017-pathology-specimen-a.txt"))
        q = self.store.add_question("CASE-OI017", "What does the fictional pathology show?")
        snap = self.store.create_snapshot("CASE-OI017", q, "Draft based on original fictional report.",
                                          [self.sources()[0]["id"]])
        out = self.adapter.deliver(envelope(), read("oi017-pathology-specimen-a-amended.txt"))
        self.assertEqual(out["result"], "imported")
        self.assertEqual(out["version"], 2)
        state = self.store.state("CASE-OI017")
        self.assertEqual(state["snapshots"][0]["state"], "stale")
        self.assertEqual(state["questions"][0]["state"], "open")
        # History recoverable: v1 superseded, v2 current.
        self.assertEqual(sorted(s["state"] for s in state["sources"]),
                         ["current", "superseded"])

    def test_duplicate_delivery_creates_no_new_source(self):
        raw = read("oi017-pathology-specimen-a.txt")
        self.assertEqual(self.adapter.deliver(envelope(), raw)["result"], "imported")
        self.assertEqual(self.adapter.deliver(envelope(), raw)["result"], "duplicate")
        self.assertEqual(len(self.sources()), 1)

    def test_revocation_blocks_future_delivery_but_preserves_history(self):
        raw = read("oi017-pathology-specimen-a.txt")
        self.assertEqual(self.adapter.deliver(envelope(), raw)["result"], "imported")
        self.adapter.revoke("CASE-OI017", "RCPT-OI017-1", "Fictional subject withdrew adapter access.")
        out = self.adapter.deliver(envelope(), read("oi017-encounter-inst-a.txt"))
        self.assertEqual(out, {"result": "rejected", "reason": "revoked_authorization"})
        self.assertEqual(len(self.sources()), 1)  # history not deleted
        self.assertTrue(self.events("adapter_authorization_revoked"))

    def test_treatment_purpose_and_expired_receipt_rejected(self):
        with self.assertRaises(InvalidInput):
            self.adapter.deliver(envelope(auth=receipt(purpose="treatment")),
                                 read("oi017-encounter-inst-a.txt"))
        with self.assertRaises(InvalidInput):
            self.adapter.deliver(envelope(retrieved="2027-01-05"),
                                 read("oi017-encounter-inst-a.txt"))
        self.assertEqual(self.sources(), [])

    def test_time_semantics_retrieved_before_issued_rejected(self):
        with self.assertRaises(InvalidInput):
            self.adapter.deliver(envelope(retrieved="2026-01-10"),
                                 read("oi017-encounter-inst-a.txt"))
        self.assertEqual(self.sources(), [])

    def test_retrieval_before_grant_rejected(self):
        # retrieved_at is after issue but before the receipt window opens.
        auth = receipt(granted="2026-02-01", expires="2026-12-31")
        with self.assertRaises(InvalidInput):
            self.adapter.deliver(envelope(retrieved="2026-01-15", auth=auth),
                                 read("oi017-encounter-inst-a.txt"))
        self.assertEqual(self.sources(), [])

    def test_revoked_at_receipt_rejected_after_revocation_only(self):
        raw = read("oi017-encounter-inst-a.txt")
        auth = receipt(revoked="2026-02-01")
        with self.assertRaises(InvalidInput):
            self.adapter.deliver(envelope(auth=auth), raw)
        self.assertEqual(self.sources(), [])
        # Retrieval strictly before revocation still imports.
        out = self.adapter.deliver(envelope(retrieved="2026-01-15", auth=auth), raw)
        self.assertEqual(out["result"], "imported")

    def test_event_date_after_issued_rejected(self):
        raw = (
            "OI-SYNTHETIC-REPORT/1\n"
            "Patient: CASE-OI017\n"
            "Document: TIME-OI017-X\n"
            "Type: clinical\n"
            "Event-Date: 2026-02-20\n"
            "Issued-At: 2026-02-10\n"
            "Finding: time-probe|reported|Fictional probe whose event date is after its issue date.\n"
        ).encode()
        with self.assertRaises(InvalidInput):
            self.adapter.deliver(envelope(), raw)
        self.assertEqual(self.sources(), [])

    def test_envelope_validation_rejects_bad_ids_scope_window_and_case(self):
        raw = read("oi017-encounter-inst-a.txt")
        env = envelope()
        env.adapter_id = "  "
        with self.assertRaises(InvalidInput):
            self.adapter.deliver(env, raw)
        env = envelope()
        env.source_organization = ""
        with self.assertRaises(InvalidInput):
            self.adapter.deliver(env, raw)
        env = envelope()
        env.source_subject_ref = " "
        with self.assertRaises(InvalidInput):
            self.adapter.deliver(env, raw)
        with self.assertRaises(InvalidInput):
            self.adapter.deliver(
                envelope(auth=AuthorizationReceipt(
                    "RCPT-X", "individual-access", (), "2026-01-01", "2026-12-31")), raw)
        with self.assertRaises(InvalidInput):
            self.adapter.deliver(
                envelope(auth=AuthorizationReceipt(
                    "RCPT-X", "individual-access", ("encounter",), "2026-12-31", "2026-01-01")),
                raw)
        # Unknown target case last: the rejection below still consumes the
        # first-wins binding (documented limitation, see the research doc).
        with self.assertRaises(InvalidInput):
            self.adapter.deliver(envelope(case="CASE-NOPE"), raw)
        self.assertEqual(self.sources(), [])

    def test_wrong_case_bytes_are_quarantined_not_imported(self):
        raw = (
            "OI-SYNTHETIC-REPORT/1\n"
            "Patient: CASE-OI017-B\n"
            "Document: ENC-OI017-BX\n"
            "Type: clinical\n"
            "Event-Date: 2026-01-12\n"
            "Issued-At: 2026-01-13\n"
            "Finding: visit-reason|reported|Fictional bytes declaring a different synthetic case.\n"
        ).encode()
        out = self.adapter.deliver(envelope(), raw)
        self.assertEqual(out["result"], "quarantined")
        self.assertEqual(out["reason"], "patient_mismatch")
        self.assertEqual(self.sources(), [])
        quarantines = self.store.state("CASE-OI017")["quarantines"]
        self.assertEqual(len(quarantines), 1)
        self.assertEqual(quarantines[0]["reason"], "patient_mismatch")
        # The store's own quarantine event is the record on this path.
        self.assertEqual(len(self.events("source_quarantined")), 1)

    def test_coverage_distinguishes_negative_from_known_missing(self):
        result = classify_coverage([
            {"artifact": "encounter", "status": "present"},
            {"artifact": "pathology", "status": "present"},
            # Marker-A is negative ONLY by virtue of the amended v2 report. The v1
            # report says not-reported and must never be cited as a negative.
            {"artifact": "marker-a-on-specimen-a-amended", "status": "negative",
             "source_document": "PATH-OI017-A@2"},
            {"artifact": "dicom-pixels", "status": "known_missing",
             "reason": "Report-only delivery; native pixels not exposed"},
            {"artifact": "molecular", "status": "known_missing",
             "reason": "No molecular artifact delivered by either institution"},
            {"artifact": "payer-administration-confirmation", "status": "known_missing",
             "reason": "Medication list contains no administration confirmation"},
            {"artifact": "original-documents", "status": "unknown"},
        ])
        self.assertEqual(result["counts"]["negative"], 1)
        self.assertEqual(result["counts"]["known_missing"], 3)
        self.assertEqual(result["counts"]["unknown"], 1)
        # A negative without a source document is not a negative.
        with self.assertRaises(InvalidInput):
            classify_coverage([{"artifact": "marker-a", "status": "negative"}])
        # A gap without a reason is not a known missing.
        with self.assertRaises(InvalidInput):
            classify_coverage([{"artifact": "molecular", "status": "known_missing"}])

    def test_declared_loss_receipt_mismatch_raises_and_imports_nothing(self):
        raw = read("oi017-pathology-specimen-a.txt")
        wrong = TransformationReceipt(dropped_fields=("wrong-field",))
        env = envelope(original_fields={"histology", "marker-a", "margin"},
                       transformed_fields={"histology", "marker-a"},
                       transformation=wrong)
        with self.assertRaises(InvalidInput):
            self.adapter.deliver(env, raw)
        self.assertEqual(self.sources(), [])

    def test_repeated_collision_returns_same_quarantine_id(self):
        self.adapter.deliver(envelope(), read("oi017-encounter-inst-a.txt"))
        first = self.adapter.deliver(
            envelope(subject="SUBJ-OI017-OTHER"),
            read("oi017-collision-wrong-binding.txt"))
        second = self.adapter.deliver(
            envelope(subject="SUBJ-OI017-OTHER"),
            read("oi017-collision-wrong-binding.txt"))
        self.assertEqual(first["reason"], "identity_collision")
        self.assertEqual(second["reason"], "identity_collision")
        self.assertEqual(first["quarantine_id"], second["quarantine_id"])
        self.assertEqual(len(self.store.state("CASE-OI017")["quarantines"]), 1)
        self.assertEqual(len(self.sources()), 1)

    def test_amendment_leaves_unrelated_case_unaffected(self):
        self.adapter.deliver(envelope(), read("oi017-pathology-specimen-a.txt"))
        self.store.add_case("CASE-OI017-B", "Second fictional case")
        other_raw = (
            "OI-SYNTHETIC-REPORT/1\n"
            "Patient: CASE-OI017-B\n"
            "Document: ENC-OI017-B\n"
            "Type: clinical\n"
            "Event-Date: 2026-01-12\n"
            "Issued-At: 2026-01-13\n"
            "Finding: visit-reason|reported|Fictional intake for a second synthetic case.\n"
        ).encode()
        other_adapter = PatientAccessAdapter(self.store)
        out_b = other_adapter.deliver(
            envelope(case="CASE-OI017-B", org="INST-B", subject="SUBJ-OI017-B2"),
            other_raw)
        self.assertEqual(out_b["result"], "imported")
        q_b = self.store.add_question("CASE-OI017-B", "Fictional question for second case?")
        self.store.create_snapshot("CASE-OI017-B", q_b,
                                   "Draft for second fictional case.",
                                   [out_b["source_id"]])
        out = self.adapter.deliver(envelope(), read("oi017-pathology-specimen-a-amended.txt"))
        self.assertEqual(out["result"], "imported")
        state_b = self.store.state("CASE-OI017-B")
        self.assertEqual(len(state_b["sources"]), 1)
        self.assertEqual(state_b["sources"][0]["state"], "current")
        self.assertEqual(state_b["snapshots"][0]["state"], "draft")

    def test_expected_results_manifest_matches_fixtures(self):
        # The manifest is acceptance evidence: its hashes, byte counts, step
        # list, and coverage block must describe the fixtures on disk.
        manifest = json.loads((FIX / "EXPECTED_RESULTS.json").read_text())
        files = {entry["file"]: entry for entry in manifest["fixtures"]}
        self.assertEqual(len(files), 7)
        for name, entry in files.items():
            raw = (FIX / name).read_bytes()
            self.assertEqual(len(raw), entry["bytes"], name)
            self.assertEqual(hashlib.sha256(raw).hexdigest(), entry["sha256"], name)
        self.assertEqual([s["step"] for s in manifest["expected_sequence"]],
                         list(range(1, 12)))
        for step in manifest["expected_sequence"]:
            first = step["fixture"].split()[0]
            if first.endswith(".txt"):
                self.assertIn(first, files, step["fixture"])
        result = classify_coverage(manifest["coverage"])
        self.assertEqual(result["counts"], {"known_missing": 4, "negative": 1,
                                           "present": 6, "unknown": 0})

    def test_no_second_source_ledger_tables(self):
        # Sources exist only in source_versions; the adapter adds no table.
        tables = [r[0] for r in self.store.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        self.assertNotIn("adapter_sources", tables)
        self.assertNotIn("patient_store", tables)


if __name__ == "__main__":
    unittest.main()
