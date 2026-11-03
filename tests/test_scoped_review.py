"""Scoped human review: sign-off, dissent, handoff (brief B-04, gap G-04).

Fictional fixtures only. Each test imports fresh synthetic bytes and asserts
on the recorded ledger rows, the read-only state projection, and the export
text. Nothing here is a clinical sign-off: scope notes record what was
looked at and what remains open.
"""

import copy
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from open_intelligence import CaseStore, InvalidInput

FIG_ORIGINAL = b"""OI-SYNTHETIC-REPORT/1
Patient: CASE-FIG-01
Document: FIG-DOC-01
Type: pathology
Event-Date: 2026-04-01
Issued-At: 2026-04-03
Specimen: BIOPSY-FIG-01
Finding: histology|reported|Fictional biopsy notes crowded glands for scoped review testing.
Finding: marker-a|not-reported|Marker A was not tested in this fictional specimen.
"""

FIG_AMENDED = b"""OI-SYNTHETIC-REPORT/1
Patient: CASE-FIG-01
Document: FIG-DOC-01
Type: pathology
Event-Date: 2026-04-01
Issued-At: 2026-04-09
Specimen: BIOPSY-FIG-01
Amends: FIG-DOC-01@1
Finding: histology|reported|Fictional amended note keeps the histology wording for scoped review testing.
Finding: marker-a|negative|Marker A assay was performed and reported negative in this fictional amendment.
"""

FIG_IMAGING = b"""OI-SYNTHETIC-REPORT/1
Patient: CASE-FIG-01
Document: FIG-DOC-03
Type: imaging
Event-Date: 2026-04-02
Issued-At: 2026-04-04
Finding: comparison|reported|Fictional imaging comparison note for scoped review testing.
"""

FIG_OTHER_CASE = b"""OI-SYNTHETIC-REPORT/1
Patient: CASE-FIG-02
Document: FIG-DOC-02
Type: pathology
Event-Date: 2026-04-01
Issued-At: 2026-04-03
Finding: histology|reported|Fictional second-case biopsy note, independent of the first case.
"""

FIG_EVIDENCE = b"""OI-SYNTHETIC-EVIDENCE/1
Evidence: FIG-EVID-01
Title: Fictional scoped review evidence example
Issued-At: 2026-03-01
Rights: original-synthetic
Statement: Fictional statement about marker review practice for testing only.
"""

REVIEWER_B = "FICTIONAL-REVIEWER-B"
REVIEWER_C = "FICTIONAL-REVIEWER-C"
EXTRACTION_NOTE = "Checked the recorded findings word-for-word against FIG-DOC-01 version 1."
INTERPRETATION_NOTE = "Noted the stated reading that marker A was not tested in version 1."
DISSENT_TEXT = "Reads the marker-a wording as needing a repeat look, unlike the noted view."
LEFT_OPEN_NOTE = "Leaving this review open until the amended source version is available."


class ScopedReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / "scoped.sqlite")
        self.store.add_case("CASE-FIG-01", "Fictional scoped review case")
        self.store.add_case("CASE-FIG-02", "Fictional second case")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _draft(self, raw=FIG_ORIGINAL, case_id="CASE-FIG-01"):
        imported = self.store.import_report(case_id, raw)
        question = self.store.add_question(case_id, "What does the fictional source record?")
        snapshot = self.store.create_snapshot(
            case_id, question, "Human-authored fictional draft for scoped review.",
            [imported["source_id"]])
        return imported["source_id"], question, snapshot

    def _scoped(self, case_id, snapshot_id):
        for item in self.store.state(case_id)["snapshots"]:
            if item["id"] == snapshot_id:
                return item["scoped_review"]
        raise AssertionError("snapshot missing from state")

    def test_extraction_accept_does_not_imply_interpretation_endorsement(self):
        _, _, snapshot = self._draft()
        self.store.record_scoped_decision(
            "CASE-FIG-01", snapshot, REVIEWER_B, "extraction_accepted", EXTRACTION_NOTE)
        scoped = self._scoped("CASE-FIG-01", snapshot)
        self.assertEqual(scoped["extraction"], "extraction_accepted")
        self.assertEqual(scoped["interpretation"], "unreviewed")
        self.assertEqual(scoped["open_items"], ["interpretation"])
        exported = self.store.export_markdown("CASE-FIG-01", snapshot)
        self.assertIn("Extraction record state: extraction_accepted", exported)
        self.assertIn("Interpretation record state: unreviewed", exported)
        self.store.record_scoped_decision(
            "CASE-FIG-01", snapshot, REVIEWER_B, "interpretation_endorsed", INTERPRETATION_NOTE)
        scoped = self._scoped("CASE-FIG-01", snapshot)
        self.assertEqual(scoped["extraction"], "extraction_accepted")
        self.assertEqual(scoped["interpretation"], "interpretation_endorsed")
        self.assertEqual(scoped["open_items"], [])
        _, _, open_snapshot = self._draft(FIG_IMAGING, "CASE-FIG-01")
        self.store.record_scoped_decision(
            "CASE-FIG-01", open_snapshot, REVIEWER_B, "left_open", LEFT_OPEN_NOTE)
        left = self._scoped("CASE-FIG-01", open_snapshot)
        self.assertEqual(left["extraction"], "left_open")
        self.assertEqual(left["interpretation"], "left_open")
        self.assertEqual(left["open_items"], ["extraction", "interpretation"])

    def test_scoped_decision_pins_reviewer_scope_versions_timestamp_note(self):
        first = self.store.import_report("CASE-FIG-01", FIG_ORIGINAL)["source_id"]
        second = self.store.import_report("CASE-FIG-01", FIG_IMAGING)["source_id"]
        evidence = self.store.import_synthetic_evidence(FIG_EVIDENCE)["evidence_version_id"]
        question = self.store.add_question("CASE-FIG-01", "What does the fictional source record?")
        assessment = self.store.assess_synthetic_evidence(
            "CASE-FIG-01", question, evidence, "context", "limited",
            "Fictional evidence gives background context for this test only.")
        rights = self.store.register_rights_source(
            "FIG-RIGHTS-01", "Fictional rights holder", "v1", "2026-03-15",
            {"metadata": {"store": "allowed"}})["rights_source_id"]
        broker = self.store.create_broker_link(
            "CASE-FIG-01", question, rights, "context", "limited",
            "Fictional broker background note for scoped review testing.",
            citation_title="Fictional broker citation")["broker_link_id"]
        snapshot = self.store.create_snapshot(
            "CASE-FIG-01", question, "Human-authored fictional draft for scoped review.",
            [first, second], evidence_assessment_ids=[assessment], broker_link_ids=[broker])
        note = "Checked both source versions and the linked evidence background note."
        outcome = self.store.record_scoped_decision(
            "CASE-FIG-01", snapshot, REVIEWER_B, "extraction_accepted", note)
        self.assertEqual(outcome["pinned_source_ids"], sorted([first, second]))
        self.assertEqual(outcome["pinned_evidence_assessment_ids"], [assessment])
        self.assertEqual(outcome["pinned_broker_link_ids"], [broker])
        parsed = datetime.fromisoformat(outcome["decided_at"])
        self.assertIsNotNone(parsed.tzinfo)
        scoped = self._scoped("CASE-FIG-01", snapshot)
        self.assertEqual(len(scoped["decisions"]), 1)
        row = scoped["decisions"][0]
        self.assertEqual(row["reviewer_label"], REVIEWER_B)
        self.assertEqual(row["scope"], "extraction_accepted")
        self.assertEqual(row["source_version_ids"], sorted([first, second]))
        self.assertEqual(row["evidence_assessment_ids"], [assessment])
        self.assertEqual(row["broker_link_ids"], [broker])
        self.assertEqual(row["note"], note)
        self.assertEqual(row["decided_at"], outcome["decided_at"])
        # Fictional free-text labels only: the existing 2-80 rule applies, and
        # notes keep the brief's 10-600 rule. Unknown scopes are rejected.
        with self.assertRaises(InvalidInput):
            self.store.record_scoped_decision("CASE-FIG-01", snapshot, "X", "extraction_accepted", note)
        with self.assertRaises(InvalidInput):
            self.store.record_scoped_decision("CASE-FIG-01", snapshot, REVIEWER_B, "extraction_accepted", "short")
        with self.assertRaises(InvalidInput):
            self.store.record_scoped_decision("CASE-FIG-01", snapshot, REVIEWER_B, "approved_for_care", note)
        _, _, other_snapshot = self._draft(FIG_OTHER_CASE, "CASE-FIG-02")
        with self.assertRaisesRegex(InvalidInput, "not in this case"):
            self.store.record_scoped_decision("CASE-FIG-01", other_snapshot, REVIEWER_B, "extraction_accepted", note)

    def test_dissent_recorded_alongside_with_both_views_visible_in_export(self):
        _, _, snapshot = self._draft()
        self.store.record_scoped_decision(
            "CASE-FIG-01", snapshot, REVIEWER_B, "extraction_accepted", EXTRACTION_NOTE)
        outcome = self.store.record_scoped_dissent(
            "CASE-FIG-01", snapshot, REVIEWER_C, "marker-a", DISSENT_TEXT)
        scoped = self._scoped("CASE-FIG-01", snapshot)
        self.assertEqual(len(scoped["decisions"]), 1)
        self.assertEqual(len(scoped["dissents"]), 1)
        dissent = scoped["dissents"][0]
        self.assertEqual(dissent["id"], outcome["dissent_id"])
        self.assertEqual(dissent["reviewer_label"], REVIEWER_C)
        self.assertEqual(dissent["claim_ref"], "marker-a")
        self.assertEqual(dissent["rationale"], DISSENT_TEXT)
        self.assertEqual(dissent["source_version_ids"], outcome["pinned_source_ids"])
        self.assertNotEqual(dissent["source_version_ids"], [])
        exported = self.store.export_markdown("CASE-FIG-01", snapshot)
        self.assertIn(EXTRACTION_NOTE, exported)
        self.assertIn("Disagreements recorded", exported)
        self.assertIn("on claim `marker-a`", exported)
        self.assertIn(DISSENT_TEXT, exported)
        with self.assertRaises(InvalidInput):
            self.store.record_scoped_dissent("CASE-FIG-01", snapshot, REVIEWER_C, "no-such-key", DISSENT_TEXT)
        with self.assertRaises(InvalidInput):
            self.store.record_scoped_dissent("CASE-FIG-01", snapshot, REVIEWER_C, "marker-a", "too short")

    def test_dissent_never_deletes_or_overwrites_majority_view(self):
        _, _, snapshot = self._draft()
        self.store.record_scoped_decision(
            "CASE-FIG-01", snapshot, REVIEWER_B, "extraction_accepted", EXTRACTION_NOTE)
        before = copy.deepcopy(self._scoped("CASE-FIG-01", snapshot)["decisions"])
        self.assertEqual(len(before), 1)
        self.store.record_scoped_dissent("CASE-FIG-01", snapshot, REVIEWER_C, "marker-a", DISSENT_TEXT)
        self.store.record_scoped_dissent(
            "CASE-FIG-01", snapshot, REVIEWER_C, "histology",
            "Second disagreement on another finding; the noted view must remain.")
        scoped = self._scoped("CASE-FIG-01", snapshot)
        self.assertEqual(scoped["decisions"], before)
        self.assertEqual(len(scoped["dissents"]), 2)
        exported = self.store.export_markdown("CASE-FIG-01", snapshot)
        self.assertIn(EXTRACTION_NOTE, exported)
        self.assertIn(DISSENT_TEXT, exported)

    def test_handoff_transfers_open_items_with_identical_basis_pins(self):
        source_id, _, snapshot = self._draft()
        decision = self.store.record_scoped_decision(
            "CASE-FIG-01", snapshot, REVIEWER_B, "extraction_accepted", EXTRACTION_NOTE)
        outcome = self.store.record_scoped_handoff("CASE-FIG-01", snapshot, REVIEWER_B, REVIEWER_C)
        self.assertEqual(outcome["snapshot_id"], snapshot)
        self.assertEqual(outcome["pinned_source_ids"], [source_id])
        self.assertEqual(outcome["prior_decision_ids"], [decision["decision_id"]])
        scoped = self._scoped("CASE-FIG-01", snapshot)
        self.assertEqual(len(scoped["handoffs"]), 1)
        row = scoped["handoffs"][0]
        self.assertEqual(row["from_reviewer"], REVIEWER_B)
        self.assertEqual(row["to_reviewer"], REVIEWER_C)
        self.assertEqual(row["source_version_ids"], [source_id])
        self.assertEqual(row["prior_decision_ids"], [decision["decision_id"]])
        self.assertEqual(scoped["assignee"], REVIEWER_C)
        # The handoff carries the open interpretation item; it settles nothing.
        self.assertEqual(scoped["open_items"], ["interpretation"])
        self.assertEqual(scoped["interpretation"], "unreviewed")
        # A handoff on an untouched draft pins an empty prior-decision list.
        fresh_source, _, fresh_snapshot = self._draft(FIG_IMAGING, "CASE-FIG-01")
        fresh = self.store.record_scoped_handoff("CASE-FIG-01", fresh_snapshot, REVIEWER_B, REVIEWER_C)
        self.assertEqual(fresh["pinned_source_ids"], [fresh_source])
        self.assertEqual(fresh["prior_decision_ids"], [])
        self.assertEqual(self._scoped("CASE-FIG-01", fresh_snapshot)["assignee"], REVIEWER_C)

    def test_handoff_appends_history_and_rewrites_nothing(self):
        _, _, snapshot = self._draft()
        self.store.record_scoped_decision(
            "CASE-FIG-01", snapshot, REVIEWER_B, "extraction_accepted", EXTRACTION_NOTE)
        self.store.record_scoped_dissent("CASE-FIG-01", snapshot, REVIEWER_C, "marker-a", DISSENT_TEXT)
        before = copy.deepcopy(self._scoped("CASE-FIG-01", snapshot))
        self.store.record_scoped_handoff("CASE-FIG-01", snapshot, REVIEWER_B, REVIEWER_C)
        mid = self._scoped("CASE-FIG-01", snapshot)
        self.assertEqual(mid["decisions"], before["decisions"])
        self.assertEqual(mid["dissents"], before["dissents"])
        self.assertEqual(len(mid["handoffs"]), 1)
        self.store.record_scoped_handoff("CASE-FIG-01", snapshot, REVIEWER_C, REVIEWER_B)
        after = self._scoped("CASE-FIG-01", snapshot)
        self.assertEqual(after["decisions"], before["decisions"])
        self.assertEqual(after["dissents"], before["dissents"])
        self.assertEqual(len(after["handoffs"]), 2)
        self.assertEqual(after["assignee"], REVIEWER_B)
        kinds = [event["kind"] for event in self.store.state("CASE-FIG-01")["events"]]
        self.assertIn("scoped_review_handoff", kinds)
        with self.assertRaisesRegex(InvalidInput, "different receiving reviewer"):
            self.store.record_scoped_handoff("CASE-FIG-01", snapshot, REVIEWER_B, REVIEWER_B)
        self.store.record_scoped_decision(
            "CASE-FIG-01", snapshot, REVIEWER_B, "interpretation_endorsed", INTERPRETATION_NOTE)
        with self.assertRaisesRegex(InvalidInput, "No open review items"):
            self.store.record_scoped_handoff("CASE-FIG-01", snapshot, REVIEWER_B, REVIEWER_C)

    def test_review_after_amendment_requires_rescoping_old_scope_does_not_carry(self):
        first_id, question, old_snapshot = self._draft()
        self.store.record_scoped_decision(
            "CASE-FIG-01", old_snapshot, REVIEWER_B, "extraction_accepted", EXTRACTION_NOTE)
        self.store.record_scoped_dissent("CASE-FIG-01", old_snapshot, REVIEWER_C, "marker-a", DISSENT_TEXT)
        amendment = self.store.import_report("CASE-FIG-01", FIG_AMENDED)
        self.assertEqual(amendment["invalidated_snapshots"], [old_snapshot])
        new_snapshot = self.store.create_snapshot(
            "CASE-FIG-01", question, "Replacement draft on the amended fictional source.",
            [amendment["source_id"]])
        old_scoped = self._scoped("CASE-FIG-01", old_snapshot)
        self.assertEqual(len(old_scoped["decisions"]), 1)
        self.assertEqual(old_scoped["decisions"][0]["source_version_ids"], [first_id])
        self.assertEqual(len(old_scoped["dissents"]), 1)
        new_scoped = self._scoped("CASE-FIG-01", new_snapshot)
        self.assertEqual(new_scoped["extraction"], "unreviewed")
        self.assertEqual(new_scoped["interpretation"], "unreviewed")
        self.assertEqual(new_scoped["decisions"], [])
        self.assertEqual(new_scoped["dissents"], [])
        self.assertEqual(new_scoped["handoffs"], [])
        self.assertEqual(new_scoped["open_items"], ["extraction", "interpretation"])
        old_export = self.store.export_markdown("CASE-FIG-01", old_snapshot)
        self.assertIn("State: **stale**", old_export)
        self.assertIn(EXTRACTION_NOTE, old_export)
        new_export = self.store.export_markdown("CASE-FIG-01", new_snapshot)
        self.assertIn("No scoped decisions recorded", new_export)
        self.assertNotIn(EXTRACTION_NOTE, new_export)
        # Re-scoping on the replacement draft is a fresh note, not a copy.
        fresh = self.store.record_scoped_decision(
            "CASE-FIG-01", new_snapshot, REVIEWER_B, "extraction_accepted",
            "Checked the amended wording against FIG-DOC-01 version 2.")
        self.assertEqual(fresh["pinned_source_ids"], [amendment["source_id"]])

    def test_brief_renders_scope_per_claim_and_flags_unreviewed(self):
        _, _, snapshot = self._draft()
        untouched = self.store.export_markdown("CASE-FIG-01", snapshot)
        self.assertIn("Extraction record state: unreviewed", untouched)
        self.assertIn("Interpretation record state: unreviewed", untouched)
        self.assertIn("Open items (no settled note recorded): extraction, interpretation", untouched)
        self.assertIn("No scoped decisions recorded", untouched)
        self.store.record_scoped_decision(
            "CASE-FIG-01", snapshot, REVIEWER_B, "extraction_accepted", EXTRACTION_NOTE)
        partial = self.store.export_markdown("CASE-FIG-01", snapshot)
        self.assertIn("Extraction record state: extraction_accepted", partial)
        self.assertIn("Open items (no settled note recorded): interpretation", partial)
        # Demo acknowledgment keeps its demo-only meaning; scoped notes are
        # never presented as clinical sign-off.
        self.assertIn(
            "An acknowledgment in this demo is not clinician credential verification or a clinical sign-off.",
            partial)
        self.assertIn("not a clinical sign-off, and not a treatment decision", partial)
        scoped_section = partial.split("## Scoped review")[1].split("## Source versions")[0]
        for banned in ("authorize", "prescribe", "order", "recommend", "approve", "direct-care"):
            self.assertNotIn(banned, scoped_section.lower())

    def test_cross_case_review_isolation(self):
        _, _, snapshot_one = self._draft(FIG_ORIGINAL, "CASE-FIG-01")
        self.store.record_scoped_decision(
            "CASE-FIG-01", snapshot_one, REVIEWER_B, "extraction_accepted", EXTRACTION_NOTE)
        self.store.record_scoped_dissent("CASE-FIG-01", snapshot_one, REVIEWER_C, "marker-a", DISSENT_TEXT)
        self.store.record_scoped_handoff("CASE-FIG-01", snapshot_one, REVIEWER_B, REVIEWER_C)
        _, _, snapshot_two = self._draft(FIG_OTHER_CASE, "CASE-FIG-02")
        scoped_two = self._scoped("CASE-FIG-02", snapshot_two)
        self.assertEqual(scoped_two["decisions"], [])
        self.assertEqual(scoped_two["dissents"], [])
        self.assertEqual(scoped_two["handoffs"], [])
        self.assertIsNone(scoped_two["assignee"])
        export_two = self.store.export_markdown("CASE-FIG-02", snapshot_two)
        for secret in (REVIEWER_B, REVIEWER_C, EXTRACTION_NOTE, DISSENT_TEXT):
            self.assertNotIn(secret, export_two)
            self.assertNotIn(secret, json.dumps(self.store.state("CASE-FIG-02")["snapshots"]))
        export_one = self.store.export_markdown("CASE-FIG-01", snapshot_one)
        self.assertIn(EXTRACTION_NOTE, export_one)


if __name__ == "__main__":
    unittest.main()
