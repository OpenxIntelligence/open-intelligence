"""Durable synthetic adapter gate — actual SQLite CaseStore acceptance tests.

No model, real patient, hospital connection or clinical authorization is used.
These tests intentionally fail on the PR #51 in-memory-only baseline.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from open_intelligence.patient_access import AdapterEnvelope, AuthorizationReceipt, PatientAccessAdapter
from open_intelligence.store import CaseStore, InvalidInput


def report(case="CASE-DUR-A", doc="PATH-DUR-A", *, amendment=None):
    parts = [
        "OI-SYNTHETIC-REPORT/1",
        f"Patient: {case}",
        f"Document: {doc}",
        "Type: pathology",
        "Event-Date: 2026-01-02",
        "Issued-At: 2026-01-03",
        "Specimen: SPEC-DUR-A",
    ]
    if amendment is not None:
        parts.append(f"Amends: {doc}@{amendment}")
    parts.append("Finding: marker|pending|Synthetic biomarker result remains pending.")
    return ("\n".join(parts) + "\n").encode("utf-8")


def envelope(case="CASE-DUR-A", subject="SUBJECT-DUR-A", *,
             org="ORG-DUR", system="PATH-SYS", receipt_id="RECEIPT-DUR-1"):
    return AdapterEnvelope(
        "SYNTHETIC-ADAPTER", org, system, case, subject,
        AuthorizationReceipt(receipt_id, "individual-access", ("pathology",),
                             "2026-01-01", "2026-12-31"),
        "2026-01-04",
    )


class DurableAdapterIdentityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "durable-fiction.sqlite"
        self.store = CaseStore(self.path)
        self.store.add_case("CASE-DUR-A", "Fictional patient A")
        self.store.add_case("CASE-DUR-B", "Fictional patient B")
        self.adapter = PatientAccessAdapter(self.store)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def reopen(self):
        self.store.close()
        self.store = CaseStore(self.path)
        self.adapter = PatientAccessAdapter(self.store)

    def sources(self, case="CASE-DUR-A"):
        return self.store.state(case)["sources"]

    def events(self, case="CASE-DUR-A", kind="adapter_delivery_accepted"):
        return [x for x in self.store.state(case)["events"] if x["kind"] == kind]

    def test_case_namespace_binding_survives_adapter_and_database_restart(self):
        accepted = self.adapter.deliver(envelope(), report())
        self.assertEqual(accepted["result"], "imported")
        self.reopen()
        other_subject = self.adapter.deliver(envelope(subject="WRONG-SUBJECT"),
                                             report(doc="PATH-DUR-2"))
        self.assertEqual(other_subject["reason"], "identity_collision")
        self.assertEqual(len(self.sources()), 1)
        self.assertEqual(self.adapter.deliver(envelope(), report())["result"], "duplicate")

    def test_global_qualified_subject_conflict_survives_restart(self):
        self.assertEqual(self.adapter.deliver(envelope(), report())["result"], "imported")
        self.reopen()
        conflict = self.adapter.deliver(
            envelope(case="CASE-DUR-B"), report(case="CASE-DUR-B", doc="PATH-DUR-B"))
        self.assertEqual(conflict["reason"], "identity_collision")
        self.assertEqual(self.sources("CASE-DUR-B"), [])

    def test_revocation_survives_restart_and_blocks_fresh_adapter(self):
        self.adapter.deliver(envelope(), report())
        self.adapter.revoke("CASE-DUR-A", "RECEIPT-DUR-1",
                            "Fictional receipt deliberately revoked.")
        self.reopen()
        blocked = self.adapter.deliver(envelope(), report(doc="PATH-DUR-2"))
        self.assertEqual(blocked["reason"], "revoked_authorization")
        self.assertEqual(len(self.sources()), 1)
        self.assertEqual(len(self.events()), 1)

    def test_two_independent_connections_cannot_accept_conflicting_bindings(self):
        second_store = CaseStore(self.path)
        self.addCleanup(second_store.close)
        second_adapter = PatientAccessAdapter(second_store)
        self.assertEqual(self.adapter.deliver(envelope(), report())["result"], "imported")
        result = second_adapter.deliver(envelope(case="CASE-DUR-B"),
                                        report(case="CASE-DUR-B", doc="PATH-DUR-B"))
        self.assertEqual(result["reason"], "identity_collision")
        self.assertEqual(second_store.state("CASE-DUR-B")["sources"], [])

    def test_failed_import_never_reserves_a_binding(self):
        with self.assertRaises(InvalidInput):
            self.adapter.deliver(envelope(subject="BAD-SUBJECT"),
                                 report(amendment=1))
        result = self.adapter.deliver(envelope(subject="GOOD-SUBJECT"), report())
        self.assertEqual(result["result"], "imported")

    def test_receipt_failure_rolls_back_source_and_binding(self):
        original_event = self.store._event

        def fail_acceptance(case_id, kind, **details):
            if kind == "adapter_delivery_accepted":
                raise RuntimeError("Synthetic acceptance receipt failure")
            return original_event(case_id, kind, **details)

        self.store._event = fail_acceptance
        with self.assertRaisesRegex(RuntimeError, "receipt failure"):
            self.adapter.deliver(envelope(subject="TEMP-SUBJECT"), report())
        self.store._event = original_event
        self.assertEqual(self.sources(), [], "Source must roll back with acceptance receipt")
        self.reopen()
        self.assertEqual(
            self.adapter.deliver(envelope(subject="FINAL-SUBJECT"), report())["result"],
            "imported",
        )
        row = self.store.db.execute(
            "SELECT source_subject_ref FROM adapter_identity_bindings WHERE case_id=?",
            ("CASE-DUR-A",),
        ).fetchone()
        self.assertEqual(row[0], "FINAL-SUBJECT")

    def test_duplicate_is_idempotent_across_restart_with_one_receipt(self):
        self.assertEqual(self.adapter.deliver(envelope(), report())["result"], "imported")
        self.assertEqual(len(self.events()), 1)
        self.reopen()
        self.assertEqual(self.adapter.deliver(envelope(), report())["result"], "duplicate")
        self.assertEqual(len(self.sources()), 1)
        self.assertEqual(len(self.events()), 1)

    def test_revocation_id_is_case_scoped_not_global(self):
        self.adapter.revoke("CASE-DUR-A", "SAME-LOCAL-RECEIPT",
                            "Fictional case A receipt revoked.")
        result = self.adapter.deliver(
            envelope(case="CASE-DUR-B", subject="SUBJECT-DUR-B",
                     receipt_id="SAME-LOCAL-RECEIPT"),
            report(case="CASE-DUR-B", doc="PATH-DUR-B"))
        self.assertEqual(result["result"], "imported")

    def test_report_kind_requires_declared_receipt_scope(self):
        restricted = envelope()
        restricted.authorization = AuthorizationReceipt(
            "RECEIPT-DUR-2", "individual-access", ("laboratory",),
            "2026-01-01", "2026-12-31")
        with self.assertRaisesRegex(InvalidInput, "scope"):
            self.adapter.deliver(restricted, report())
        self.assertEqual(self.sources(), [])
        self.assertEqual(self.store.db.execute(
            "SELECT count(*) FROM adapter_identity_bindings").fetchone()[0], 0)

    def test_scope_cannot_contain_empty_or_non_string_values(self):
        for scope in (("pathology", ""), ("pathology", None)):
            with self.subTest(scope=scope):
                restricted = envelope()
                restricted.authorization = AuthorizationReceipt(
                    "RECEIPT-DUR-3", "individual-access", scope,
                    "2026-01-01", "2026-12-31")
                with self.assertRaisesRegex(InvalidInput, "scope"):
                    self.adapter.deliver(restricted, report())
        self.assertEqual(self.sources(), [])

    def test_existing_plain_import_path_remains_compatible(self):
        direct = self.store.import_report("CASE-DUR-A", report())
        self.assertEqual(direct["result"], "imported")
        self.reopen()
        self.assertEqual(self.store.import_report("CASE-DUR-A", report())["result"],
                         "duplicate")
        self.assertEqual(len(self.sources()), 1)


if __name__ == "__main__":
    unittest.main()
