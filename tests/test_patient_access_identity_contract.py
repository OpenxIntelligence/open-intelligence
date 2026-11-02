"""Focused identity regression tests; parsing/storage are explicit test doubles.

These tests exercise the actual adapter's namespace and binding control flow.
They do not establish clinical parsing, authentication, or durable storage.
See test_cross_domain_source_journey.py for the actual CaseStore path.
"""
from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from open_intelligence import patient_access as access
from open_intelligence.store import InvalidInput


def fake_parse(raw):
    return SimpleNamespace(**json.loads(raw))


def raw_report(patient="CASE-A", document="REPORT-A"):
    return json.dumps(dict(patient_id=patient, document_id=document,
                           kind="pathology", event_date="2026-01-01",
                           issued_at="2026-01-02")).encode()


def envelope(case="CASE-A", org="ORG-A", system="SYS-A", subject="LOCAL-1"):
    return access.AdapterEnvelope(
        "ADAPTER-A", org, system, case, subject,
        access.AuthorizationReceipt("RECEIPT-A", "individual-access", ("pathology",),
                                    "2026-01-01", "2026-12-31"), "2026-01-03")


class FakeLedger:
    def __init__(self):
        self.sources = {}
        self.events = []
        self.quarantines = []
        self.raise_on_import = False

    def import_report(self, case, raw):
        if self.raise_on_import:
            raise InvalidInput("Synthetic rejected import")
        if fake_parse(raw).patient_id != case:
            return self.quarantine_adapter_delivery(case, raw,
                                                     fake_parse(raw).patient_id,
                                                     "patient_mismatch")
        key = case, raw
        if key in self.sources:
            return dict(result="duplicate", source_id=self.sources[key], version=1)
        self.sources[key] = len(self.sources) + 1
        return dict(result="imported", source_id=self.sources[key], version=1)

    def record_adapter_event(self, case, kind, **details):
        self.events.append(dict(case=case, kind=kind, **details))

    def quarantine_adapter_delivery(self, case, raw, patient, reason):
        self.quarantines.append(dict(case=case, raw=raw, patient=patient, reason=reason))
        return dict(result="quarantined", reason=reason,
                    quarantine_id=len(self.quarantines))


class PatientBindingContractTest(unittest.TestCase):
    def setUp(self):
        self.ledger = FakeLedger()
        self.adapter = access.PatientAccessAdapter(self.ledger)
        p = patch.object(access, "parse_report", side_effect=fake_parse)
        p.start()
        self.addCleanup(p.stop)

    def test_multiple_patients_from_one_source_namespace(self):
        self.assertEqual(self.adapter.deliver(envelope(), raw_report())["result"], "imported")
        result = self.adapter.deliver(envelope(case="CASE-B", subject="LOCAL-2"),
                                      raw_report("CASE-B", "REPORT-B"))
        self.assertEqual(result["result"], "imported")
        self.assertEqual(len(self.ledger.sources), 2)

    def test_same_subject_value_from_different_organizations(self):
        self.adapter.deliver(envelope(), raw_report())
        result = self.adapter.deliver(envelope(case="CASE-B", org="ORG-B"),
                                      raw_report("CASE-B", "REPORT-B"))
        self.assertEqual(result["result"], "imported")
        self.assertEqual(len(self.ledger.sources), 2)

    def test_same_subject_value_from_different_source_systems(self):
        self.adapter.deliver(envelope(), raw_report())
        result = self.adapter.deliver(envelope(case="CASE-B", system="SYS-B"),
                                      raw_report("CASE-B", "REPORT-B"))
        self.assertEqual(result["result"], "imported")

    def test_same_qualified_subject_cannot_rebind_to_another_case(self):
        self.adapter.deliver(envelope(), raw_report())
        result = self.adapter.deliver(envelope(case="CASE-B"),
                                      raw_report("CASE-B", "REPORT-B"))
        self.assertEqual(result["reason"], "identity_collision")
        self.assertEqual(len(self.ledger.sources), 1)

    def test_same_case_namespace_cannot_silently_change_subject(self):
        self.adapter.deliver(envelope(), raw_report())
        result = self.adapter.deliver(envelope(subject="DIFFERENT"),
                                      raw_report(document="REPORT-B"))
        self.assertEqual(result["reason"], "identity_collision")
        self.assertEqual(len(self.ledger.sources), 1)

    def test_multiple_namespaces_can_supply_the_same_case(self):
        self.adapter.deliver(envelope(), raw_report())
        result = self.adapter.deliver(envelope(org="ORG-B", system="SYS-B", subject="LOCAL-9"),
                                      raw_report(document="REPORT-B"))
        self.assertEqual(result["result"], "imported")

    def test_quarantined_first_delivery_does_not_claim_binding(self):
        result = self.adapter.deliver(envelope(subject="WRONG"), raw_report("CASE-B"))
        self.assertEqual(result["result"], "quarantined")
        result = self.adapter.deliver(envelope(subject="RIGHT"), raw_report())
        self.assertEqual(result["result"], "imported")

    def test_exception_during_import_does_not_claim_binding(self):
        self.ledger.raise_on_import = True
        with self.assertRaises(InvalidInput):
            self.adapter.deliver(envelope(subject="WRONG"), raw_report())
        self.ledger.raise_on_import = False
        result = self.adapter.deliver(envelope(subject="RIGHT"), raw_report())
        self.assertEqual(result["result"], "imported")

    def test_duplicate_accepted_bytes_establish_binding_without_new_source(self):
        self.ledger.import_report("CASE-A", raw_report())
        self.assertEqual(self.adapter.deliver(envelope(), raw_report())["result"], "duplicate")
        result = self.adapter.deliver(envelope(subject="DIFFERENT"),
                                      raw_report(document="REPORT-B"))
        self.assertEqual(result["reason"], "identity_collision")
        self.assertEqual(len(self.ledger.sources), 1)

    def test_missing_source_system_rejected_before_import(self):
        with self.assertRaises(InvalidInput):
            self.adapter.deliver(envelope(system=""), raw_report())
        self.assertEqual(self.ledger.sources, {})
        self.assertEqual(self.ledger.events, [])

    def test_non_string_source_system_rejected_before_import(self):
        with self.assertRaises(InvalidInput):
            self.adapter.deliver(envelope(system=None), raw_report())
        self.assertEqual(self.ledger.sources, {})

    def test_accepted_receipt_identifies_namespace_and_subject(self):
        self.adapter.deliver(envelope(), raw_report())
        event = self.ledger.events[-1]
        self.assertEqual(event.get("source_system"), "SYS-A")
        self.assertEqual(event.get("source_subject_ref"), "LOCAL-1")

    def test_existing_revocation_still_blocks_delivery(self):
        self.adapter.deliver(envelope(), raw_report())
        self.adapter.revoke("CASE-A", "RECEIPT-A", "Synthetic permission withdrawn.")
        result = self.adapter.deliver(envelope(), raw_report(document="REPORT-B"))
        self.assertEqual(result["reason"], "revoked_authorization")
        self.assertEqual(len(self.ledger.sources), 1)

    def test_missingness_is_not_converted_to_negative(self):
        result = access.classify_coverage([
            dict(artifact="molecular", status="unknown"),
            dict(artifact="pixels", status="known_missing", reason="Report only"),
            dict(artifact="marker", status="negative", source_document="REPORT-A"),
        ])
        self.assertEqual(result["counts"]["unknown"], 1)
        self.assertEqual(result["counts"]["known_missing"], 1)
        self.assertEqual(result["counts"]["negative"], 1)


if __name__ == "__main__":
    unittest.main()
