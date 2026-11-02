"""Actual CaseStore integration; fictional reports, not clinical services.

No parser/storage doubles, model API, real patients, native images or genomic
pipelines. Reopening checks canonical source/snapshot persistence, NOT durable
adapter identity/authorization (the adapter still documents in-memory state).
"""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from open_intelligence.patient_access import AdapterEnvelope, AuthorizationReceipt, PatientAccessAdapter
from open_intelligence.store import CaseStore, InvalidInput


def report(case="CASE-XA", document="PATH-XA", kind="pathology", *,
           state="negative", statement="Fictional marker is reported negative.",
           specimen="SPEC-XA", amends=None):
    lines = ["OI-SYNTHETIC-REPORT/1", f"Patient: {case}",
             f"Document: {document}", f"Type: {kind}",
             "Event-Date: 2026-01-01", "Issued-At: 2026-01-02"]
    if specimen is not None:
        lines.append(f"Specimen: {specimen}")
    if amends is not None:
        lines.append(f"Amends: {document}@{amends}")
    lines.append(f"Finding: result|{state}|{statement}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def envelope(case="CASE-XA", org="ORG-X", system="PATH-SYSTEM", subject="LOCAL-1"):
    return AdapterEnvelope(
        "SYNTHETIC-ADAPTER", org, system, case, subject,
        AuthorizationReceipt("RECEIPT-" + case, "individual-access",
                             ("clinical", "laboratory", "pathology", "molecular", "imaging"),
                             "2026-01-01", "2026-12-31"), "2026-01-03")


class CrossDomainSourceJourneyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "fictional-case.sqlite3"
        self.store = CaseStore(self.path)
        self.store.add_case("CASE-XA", "Fictional cross-domain case A")
        self.store.add_case("CASE-XB", "Fictional cross-domain case B")
        self.adapter = PatientAccessAdapter(self.store)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_multiple_patients_in_one_hospital_and_source_system(self):
        a = self.adapter.deliver(envelope(), report())
        b = self.adapter.deliver(envelope(case="CASE-XB", subject="LOCAL-2"),
                                 report("CASE-XB", "PATH-XB", specimen="SPEC-XB"))
        self.assertEqual((a["result"], b["result"]), ("imported", "imported"))
        for case in ("CASE-XA", "CASE-XB"):
            self.assertEqual(len(self.store.state(case)["sources"]), 1)

    def test_equal_local_ids_in_different_organizations_do_not_collide(self):
        self.adapter.deliver(envelope(), report())
        b = self.adapter.deliver(envelope(case="CASE-XB", org="ORG-Y"),
                                 report("CASE-XB", "PATH-XB", specimen="SPEC-XB"))
        self.assertEqual(b["result"], "imported")
        with self.assertRaises(InvalidInput):
            self.store.source_text("CASE-XA", b["source_id"])

    def test_equal_local_ids_in_different_source_systems_do_not_collide(self):
        self.adapter.deliver(envelope(), report())
        b = self.adapter.deliver(envelope(case="CASE-XB", system="SECOND-SYSTEM"),
                                 report("CASE-XB", "PATH-XB", specimen="SPEC-XB"))
        self.assertEqual(b["result"], "imported")

    def test_qualified_identifier_cannot_move_to_another_case(self):
        self.adapter.deliver(envelope(), report())
        b = self.adapter.deliver(envelope(case="CASE-XB"),
                                 report("CASE-XB", "PATH-XB", specimen="SPEC-XB"))
        self.assertEqual(b["reason"], "identity_collision")
        self.assertEqual(self.store.state("CASE-XB")["sources"], [])
        self.assertEqual(len(self.store.state("CASE-XB")["quarantines"]), 1)

    def test_wrong_case_delivery_does_not_poison_later_binding(self):
        bad = self.adapter.deliver(envelope(subject="WRONG"),
                                   report("CASE-XB", "PATH-XB", specimen="SPEC-XB"))
        self.assertEqual(bad["result"], "quarantined")
        good = self.adapter.deliver(envelope(subject="RIGHT"), report())
        self.assertEqual(good["result"], "imported")
        self.assertEqual(len(self.store.state("CASE-XA")["sources"]), 1)
        self.assertEqual(len(self.store.state("CASE-XA")["quarantines"]), 1)

    def test_amendment_across_report_domains_preserves_history_and_other_case(self):
        specs = [
            ("ORDER-XA", "clinical", "reported", "Fictional order recorded; administration is not established.", None),
            ("LAB-XA", "laboratory", "pending", "Fictional laboratory result is pending.", "SPEC-XA"),
            ("PATH-XA", "pathology", "negative", "Fictional marker is reported negative.", "SPEC-XA"),
            ("MOL-XA", "molecular", "not-assessed", "Fictional molecular interpretation is not assessed.", "SPEC-XA"),
            ("IMG-XA", "imaging", "reported", "Fictional report only; source pixels were not supplied.", None),
        ]
        originals = {}
        source_ids = []
        for doc, kind, value_state, statement, specimen in specs:
            raw = report(document=doc, kind=kind, state=value_state,
                         statement=statement, specimen=specimen)
            out = self.adapter.deliver(envelope(system=kind.upper()), raw)
            self.assertEqual(out["result"], "imported")
            originals[doc] = (out["source_id"], raw)
            source_ids.append(out["source_id"])
        state = self.store.state("CASE-XA")
        self.assertEqual(len(state["sources"]), 5)
        self.assertEqual({a["certainty"] for a in state["assertions"]},
                         {"reported", "pending", "negative", "not-assessed"})
        for sid, raw in originals.values():
            self.assertEqual(self.store.source_text("CASE-XA", sid), raw.decode())
        q = self.store.add_question("CASE-XA", "Which fictional reports changed and what remains unknown?")
        snap = self.store.create_snapshot("CASE-XA", q,
                    "Synthetic source-linked draft; no medical interpretation or treatment decision.", source_ids)

        other = self.adapter.deliver(envelope(case="CASE-XB", system="PATHOLOGY", subject="LOCAL-2"),
                                     report("CASE-XB", "PATH-XB", specimen="SPEC-XB"))
        self.assertEqual(other["result"], "imported")
        qb = self.store.add_question("CASE-XB", "What does the separate fictional report state?")
        snap_b = self.store.create_snapshot("CASE-XB", qb,
                    "Separate fictional draft which must remain unaffected.", [other["source_id"]])

        amendment = report(state="indeterminate", amends=1,
                           statement="Fictional correction: marker result is indeterminate, not negative.")
        changed = self.adapter.deliver(envelope(system="PATHOLOGY"), amendment)
        self.assertEqual(changed["version"], 2)
        after = self.store.state("CASE-XA")
        path_sources = [s for s in after["sources"] if s["document_id"] == "PATH-XA"]
        self.assertEqual({s["state"] for s in path_sources}, {"current", "superseded"})
        self.assertEqual(next(s for s in after["snapshots"] if s["id"] == snap)["state"], "stale")
        self.assertEqual(next(x for x in after["questions"] if x["id"] == q)["state"], "open")
        self.assertEqual(next(s for s in self.store.state("CASE-XB")["snapshots"]
                              if s["id"] == snap_b)["state"], "draft")
        old_id, old_raw = originals["PATH-XA"]
        old = next(s for s in path_sources if s["id"] == old_id)
        self.assertEqual(old["sha256"], hashlib.sha256(old_raw).hexdigest())
        self.assertEqual(self.store.source_text("CASE-XA", old_id), old_raw.decode())
        n_sources = len(after["sources"])
        events_before = len(after["events"])
        self.assertEqual(self.adapter.deliver(envelope(system="PATHOLOGY"), amendment)["result"], "duplicate")
        self.assertEqual(len(self.store.state("CASE-XA")["sources"]), n_sources)
        self.assertEqual(len(self.store.state("CASE-XA")["events"]), events_before)
        exported = self.store.export_markdown("CASE-XA", snap)
        self.assertIn("stale", exported)
        self.assertIn("Fictional marker is reported negative.", exported)
        self.assertNotIn("reviewed_in_demo", exported)

        self.store.close()
        self.store = CaseStore(self.path)
        restored = self.store.state("CASE-XA")
        self.assertEqual(len(restored["sources"]), n_sources)
        self.assertEqual(next(s for s in restored["snapshots"] if s["id"] == snap)["state"], "stale")
        self.assertEqual(self.store.source_text("CASE-XA", old_id), old_raw.decode())
        self.assertEqual(next(s for s in self.store.state("CASE-XB")["snapshots"]
                              if s["id"] == snap_b)["state"], "draft")

    def test_accepted_receipt_preserves_declared_namespace(self):
        self.adapter.deliver(envelope(system="PATHOLOGY"), report())
        event = next(e for e in self.store.state("CASE-XA")["events"]
                     if e["kind"] == "adapter_delivery_accepted")
        details = json.loads(event["details"])
        self.assertEqual(details["source_organization"], "ORG-X")
        self.assertEqual(details["source_system"], "PATHOLOGY")
        self.assertEqual(details["source_subject_ref"], "LOCAL-1")


if __name__ == "__main__":
    unittest.main()
