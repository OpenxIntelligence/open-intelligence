"""OI-019: synthetic cases for option-preservation evaluation.

These tests verify software behaviour only, not clinical correctness. All
cases, reports, and evidence items are independently authored fiction; see
``examples/synthetic/oi019-readme.md`` for the element map, the explicit
unknowns, and the reviewer guide.

What is pinned here, beyond the existing store contract:

* A T0-only replay sees no T1/T2 document, finding, or wording, and the
  baseline "ordinary case brief" contains no treatment-recommendation
  wording.
* After the full T0/T1/T2 timeline, the preservation item is still a
  discussion only (no decision recorded, feasibility unknown), the trial
  criterion is still hypothetical only (no actual trial identified,
  applicability and any treatment effect unknown), the Marker A-positive
  candidate is still invalid on the face of the record, and the pending
  imaging comparison is still a no-threat control.
* A reviewer can recover every supporting / contradicting / context
  assessment, with its evidence key, version, and rationale, from
  ``CaseStore.state()``.
* Wrong-patient, duplicate, out-of-order, and cross-case behaviour stays
  correct, using the existing store rules unchanged.
"""

import tempfile
import unittest
from pathlib import Path

from open_intelligence import CaseStore, InvalidInput

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "synthetic"

A = "CASE-OI019-A"
B = "CASE-OI019-B"

A_T0 = ["oi019-a-t0-pathology.txt", "oi019-a-t0-imaging.txt"]
B_T0 = ["oi019-b-t0-pathology.txt", "oi019-b-t0-imaging.txt"]
A_T1 = "oi019-a-t1-clinical.txt"
A_T2 = "oi019-a-t2-clinical-amended.txt"
B_T1 = "oi019-b-t1-clinical.txt"
B_T2 = "oi019-b-t2-clinical-amended.txt"

# Wording a brief or snapshot must never contain. The store export header
# itself says "treatment recommendation", so this list targets directive
# recommendation phrasing, not the word "recommendation" in a disclaimer.
BANNED_RECOMMENDATION_PHRASES = (
    "should receive",
    "is recommended",
    "must undergo",
    "should undergo",
    "treatment of choice",
    "is advised",
)


def fixture(name):
    return (SAMPLE / name).read_bytes()


def assert_no_recommendation(testcase, text):
    # Fixture and export disclaimers legitimately contain the word
    # "recommendation" ("no clinical recommendation is stated"), so this
    # check targets directive recommendation phrasing, not that word.
    lowered = text.lower()
    for phrase in BANNED_RECOMMENDATION_PHRASES:
        testcase.assertNotIn(phrase, lowered)


class OptionPreservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / "oi019.sqlite")
        self.store.add_case(A, "Fictional OI-019 case A")
        self.store.add_case(B, "Fictional OI-019 case B")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def import_files(self, case_id, names):
        results = {}
        for name in names:
            outcome = self.store.import_report(case_id, fixture(name))
            self.assertEqual(outcome["result"], "imported", name)
            results[name] = outcome
        return results

    def import_t0(self):
        a = self.import_files(A, A_T0)
        b = self.import_files(B, B_T0)
        return a, b

    def import_evidence(self, name):
        outcome = self.store.import_synthetic_evidence(fixture(name))
        self.assertIn(outcome["result"], ("imported", "duplicate"))
        return outcome["evidence_version_id"]

    def test_t0_replay_cannot_see_t1_t2_and_baseline_brief_has_no_recommendation(self):
        a, b = self.import_t0()
        a_sources = [r["source_id"] for r in a.values()]
        b_sources = [r["source_id"] for r in b.values()]

        qa = self.store.add_question(A, "What is the ordinary case brief for this fictional case at T0?")
        qb = self.store.add_question(B, "What is the ordinary case brief for this fictional case at T0?")
        brief_a = ("Ordinary case brief at T0: fictional sample shows a descriptive lesion "
                   "finding pending further review; Marker A was not reported; fictional "
                   "reference lesion measured as 24 mm; prior-image comparison pending.")
        brief_b = ("Ordinary case brief at T0: fictional sample shows a descriptive lesion "
                   "finding pending further review; Marker A reported negative; fictional "
                   "reference lesion measured as 18 mm; prior-image comparison pending.")
        sa = self.store.create_snapshot(A, qa, brief_a, a_sources)
        sb = self.store.create_snapshot(B, qb, brief_b, b_sources)

        for case_id, snapshot_id in ((A, sa), (B, sb)):
            state = self.store.state(case_id)
            keys = {item["finding_key"] for item in state["assertions"]}
            self.assertNotIn("preservation-discussion", keys)
            self.assertNotIn("preservation-decision", keys)
            self.assertNotIn("hypothetical-criterion", keys)
            self.assertNotIn("candidate-assay-option", keys)
            self.assertNotIn("treatment-effect-on-criterion", keys)
            self.assertEqual({s["document_id"] for s in state["sources"]},
                             {"PATH-OI019-A", "IMG-OI019-A"} if case_id == A
                             else {"PATH-OI019-B", "IMG-OI019-B"})
            export = self.store.export_markdown(case_id, snapshot_id)
            # "trial" alone is excluded here: the store's own export
            # boilerplate mentions it ("no real ... trial was appraised").
            # The T1-specific terms below, plus the raw source texts, are
            # the actual leakage check.
            for forbidden in ("CLIN-OI019", "preservation", "hypothetical",
                              "candidate", "planned operation",
                              "planned treatment"):
                self.assertNotIn(forbidden, export)
            for source in state["sources"]:
                raw = self.store.source_text(case_id, source["id"])
                for forbidden in ("CLIN-OI019", "preservation", "hypothetical",
                                  "trial", "candidate"):
                    self.assertNotIn(forbidden, raw)
            assert_no_recommendation(self, export)
            snapshot = [s for s in state["snapshots"] if s["id"] == snapshot_id][0]
            self.assertEqual(snapshot["source_ids"],
                             a_sources if case_id == A else b_sources)

    def test_full_timeline_keeps_discussion_hypothetical_invalid_and_control_framing(self):
        self.import_t0()
        a_t1 = self.import_files(A, [A_T1])[A_T1]
        b_t1 = self.import_files(B, [B_T1])[B_T1]
        a_t2 = self.import_files(A, [A_T2])[A_T2]
        b_t2 = self.import_files(B, [B_T2])[B_T2]
        self.assertEqual(a_t2["version"], 2)
        self.assertEqual(b_t2["version"], 2)

        q_discuss = self.store.add_question(
            A, "What was discussed about preserving a sample before the planned operation, and what remains unknown?")
        q_criterion = self.store.add_question(
            B, "What hypothetical trial criterion was described, and would planned treatment affect it?")
        q_invalid = self.store.add_question(
            B, "Is the Marker A-positive candidate option valid on this fictional record?")
        q_control = self.store.add_question(
            A, "What does the pending imaging comparison threaten?")

        ev_discuss = self.import_evidence("oi019-evidence-discussion.txt")
        ev_hypo = self.import_evidence("oi019-evidence-hypothetical.txt")
        ev_invalid = self.import_evidence("oi019-evidence-invalid.txt")
        ev_control = self.import_evidence("oi019-evidence-control.txt")

        assess_discuss = self.store.assess_synthetic_evidence(
            A, q_discuss, ev_discuss, "supports", "limited",
            "Fictional note supports discussion-only framing; feasibility and future use "
            "remain unknown, so it cannot support a decision.")
        assess_hypo = self.store.assess_synthetic_evidence(
            B, q_criterion, ev_hypo, "supports", "limited",
            "Fictional note supports hypothetical-only framing; no actual trial is "
            "identified and any treatment effect is unknown.")
        assess_invalid = self.store.assess_synthetic_evidence(
            B, q_invalid, ev_invalid, "contradicts", "not_applicable",
            "Record reports Marker A negative, so a Marker A-positive sample option is "
            "contradicted and not applicable on this record.")
        assess_control = self.store.assess_synthetic_evidence(
            A, q_control, ev_control, "context", "applicable",
            "Pending comparison is context only; it threatens no option and remains pending.")

        s_discuss = self.store.create_snapshot(
            A, q_discuss,
            "Discussion only: preserving an additional tissue sample at the planned "
            "operation was discussed, not decided; feasibility unknown; quantity not "
            "stated; no decision recorded in the amended note.",
            [a_t2["source_id"]], [assess_discuss])
        s_criterion = self.store.create_snapshot(
            B, q_criterion,
            "Hypothetical only: a future trial criterion that might require a "
            "pre-treatment sample was described; no actual trial is identified; "
            "applicability unknown; whether planned treatment would affect it is unknown.",
            [b_t2["source_id"]], [assess_hypo])
        s_invalid = self.store.create_snapshot(
            B, q_invalid,
            "Invalid on the face of the record: the candidate option requires a Marker "
            "A-positive sample, while the T0 pathology reports Marker A negative; the "
            "option is contradicted and not applicable.",
            [b_t2["source_id"]], [assess_invalid])
        s_control = self.store.create_snapshot(
            A, q_control,
            "Control: the imaging comparison remains pending; it threatens no option "
            "and is not a candidate.",
            [a_t2["source_id"]], [assess_control])

        # Reviewer view: every assessment recoverable with relation and rationale.
        by_key = {}
        for assessment in self.store.state(A)["evidence_assessments"]:
            by_key[assessment["evidence_key"]] = assessment
        for assessment in self.store.state(B)["evidence_assessments"]:
            by_key[assessment["evidence_key"]] = assessment
        self.assertEqual((by_key["EVID-OI019-DISCUSSION"]["relation"],
                          by_key["EVID-OI019-DISCUSSION"]["applicability"]),
                         ("supports", "limited"))
        self.assertEqual((by_key["EVID-OI019-HYPOTHETICAL"]["relation"],
                          by_key["EVID-OI019-HYPOTHETICAL"]["applicability"]),
                         ("supports", "limited"))
        self.assertEqual((by_key["EVID-OI019-INVALID"]["relation"],
                          by_key["EVID-OI019-INVALID"]["applicability"]),
                         ("contradicts", "not_applicable"))
        self.assertEqual((by_key["EVID-OI019-CONTROL"]["relation"],
                          by_key["EVID-OI019-CONTROL"]["applicability"]),
                         ("context", "applicable"))
        self.assertIn("Marker A negative", by_key["EVID-OI019-INVALID"]["rationale"])

        # Current assertions still carry the guarded framings after T2.
        a_assert = {x["finding_key"]: x["certainty"]
                    for x in self.store.state(A)["assertions"]}
        self.assertEqual(a_assert["preservation-discussion"], "reported")
        self.assertEqual(a_assert["preservation-decision"], "not-reported")
        self.assertEqual(a_assert["preservation-feasibility"], "indeterminate")
        self.assertEqual(a_assert["comparison"], "pending")
        b_assert = {x["finding_key"]: x["certainty"]
                    for x in self.store.state(B)["assertions"]}
        self.assertEqual(b_assert["hypothetical-criterion"], "reported")
        self.assertEqual(b_assert["criterion-applicability"], "indeterminate")
        self.assertEqual(b_assert["treatment-effect-on-criterion"], "indeterminate")
        self.assertEqual(b_assert["marker-a"], "negative")
        self.assertEqual(b_assert["comparison"], "pending")

        # No snapshot at any cutoff invents a treatment recommendation, and
        # the discussion / hypothetical snapshots never harden into decisions.
        for case_id, snapshot_id in ((A, s_discuss), (B, s_criterion),
                                     (B, s_invalid), (A, s_control)):
            export = self.store.export_markdown(case_id, snapshot_id)
            assert_no_recommendation(self, export)
        discuss_export = self.store.export_markdown(A, s_discuss)
        self.assertIn("not decided", discuss_export)
        self.assertIn("feasibility unknown", discuss_export)
        self.assertNotIn("decision was made", discuss_export)
        criterion_export = self.store.export_markdown(B, s_criterion)
        self.assertIn("no actual trial is identified", criterion_export)
        self.assertIn("unknown", criterion_export)
        invalid_export = self.store.export_markdown(B, s_invalid)
        self.assertIn("Marker A negative", invalid_export)
        self.assertIn("not applicable", invalid_export)

    def test_t2_amendment_supersedes_t1_without_promoting_the_discussion(self):
        self.import_t0()
        t1 = self.import_files(A, [A_T1])[A_T1]
        question = self.store.add_question(
            A, "What was discussed about preserving a sample before the planned operation?")
        draft = self.store.create_snapshot(
            A, question,
            "Discussion only: preserving an additional tissue sample was discussed, not decided.",
            [t1["source_id"]])
        update = self.import_files(A, [A_T2])[A_T2]
        self.assertEqual(update["invalidated_snapshots"], [draft])

        state = self.store.state(A)
        versions = {s["version"]: s for s in state["sources"]
                    if s["document_id"] == "CLIN-OI019-A"}
        self.assertEqual(versions[1]["state"], "superseded")
        self.assertEqual(versions[2]["state"], "current")
        self.assertEqual({s["id"]: s["state"] for s in state["snapshots"]}[draft], "stale")

        # Superseded T1 text stays in history (old export) but is excluded
        # from a new snapshot built on the current T2 version.
        old_export = self.store.export_markdown(A, draft)
        self.assertIn("**stale**", old_export)
        self.assertIn("possibly preserving an additional tissue sample", old_export)
        replacement = self.store.create_snapshot(
            A, question,
            "Discussion only, as amended: the preservation item was a discussion only, "
            "not a decision; feasibility remains undetermined.",
            [update["source_id"]])
        new_export = self.store.export_markdown(A, replacement)
        self.assertIn("was a discussion only, not a decision", new_export)
        self.assertNotIn("possibly preserving an additional tissue sample", new_export)
        assert_no_recommendation(self, new_export)

    def test_wrong_patient_duplicate_out_of_order_and_cross_case_stay_correct(self):
        a_t0, b_t0 = self.import_t0()
        events_before = len(self.store.state(A)["events"])

        wrong = fixture("oi019-wrong-patient.txt")
        first = self.store.import_report(A, wrong)
        self.assertEqual(first["result"], "quarantined")
        self.assertEqual(first["reason"], "patient_mismatch")
        again = self.store.import_report(A, wrong)
        self.assertEqual(again["result"], "quarantined")
        self.assertTrue(again["duplicate"])
        self.assertEqual(again["quarantine_id"], first["quarantine_id"])
        self.assertEqual(len(self.store.state(A)["quarantines"]), 1)

        duplicate = self.store.import_report(A, fixture("oi019-a-t0-pathology.txt"))
        self.assertEqual(duplicate["result"], "duplicate")
        self.assertEqual(duplicate["version"], 1)
        self.assertEqual(len(self.store.state(A)["events"]),
                         events_before + 1)  # only the first quarantine added an event

        # Out of order: a T2 amendment with no T1 original in the store.
        with self.assertRaisesRegex(InvalidInput, "First document version cannot have Amends"):
            self.store.import_report(B, fixture("oi019-b-t2-clinical-amended.txt"))
        # Wrong amendment target after the T1 original exists.
        self.import_files(B, [B_T1])
        bad_amends = fixture("oi019-b-t2-clinical-amended.txt").replace(
            b"CLIN-OI019-B@1", b"CLIN-OI019-B@3")
        with self.assertRaisesRegex(InvalidInput, "Amends"):
            self.store.import_report(B, bad_amends)
        self.assertEqual(len([s for s in self.store.state(B)["sources"]
                              if s["document_id"] == "CLIN-OI019-B"]), 1)

        # Cross-case: a snapshot for A may not cite B's current source.
        question = self.store.add_question(A, "What is the ordinary case brief for this fictional case at T0?")
        with self.assertRaisesRegex(InvalidInput, "belongs to another case"):
            self.store.create_snapshot(A, question, "Cross-case citation must fail.",
                                       [b_t0["oi019-b-t0-pathology.txt"]["source_id"]])

        # Duplicate evidence is a noop with the same version id.
        first_ev = self.import_evidence("oi019-evidence-discussion.txt")
        second_ev = self.import_evidence("oi019-evidence-discussion.txt")
        self.assertEqual(first_ev, second_ev)


if __name__ == "__main__":
    unittest.main()
