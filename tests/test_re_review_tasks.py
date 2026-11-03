"""B-02: owned re-review tasks on every invalidation (gap G-02).

Fictional fixtures only (CASE-FIG-01, CASE-FIG-02, FICTIONAL-NAVIGATOR-A).
Nothing here is clinical: tasks record which earlier draft went stale, what
superseded it, the mechanical finding-key diff, and a fictional owner label.
"""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence.__main__ import Handler, seed
from open_intelligence.changes import changes_since_review
from open_intelligence.store import CaseStore, InvalidInput

FIG_ORIGINAL = b"""OI-SYNTHETIC-REPORT/1
Patient: CASE-FIG-01
Document: FIG-PATH-01
Type: pathology
Event-Date: 2026-06-01
Issued-At: 2026-06-02
Specimen: FIG-SPEC-01
Finding: fig-marker|reported|Fictional pathology note records fig-marker as present.
Finding: fig-margin|indeterminate|Fictional note cannot assess fig-margin from this specimen.
"""

FIG_AMENDED = b"""OI-SYNTHETIC-REPORT/1
Patient: CASE-FIG-01
Document: FIG-PATH-01
Type: pathology
Event-Date: 2026-06-01
Issued-At: 2026-06-09
Specimen: FIG-SPEC-01
Amends: FIG-PATH-01@1
Finding: fig-marker|negative|Fictional amended note records fig-marker as negative.
Finding: fig-newkey|reported|Fictional amended note adds a fig-newkey observation.
"""

FIG_AMENDED_V3 = b"""OI-SYNTHETIC-REPORT/1
Patient: CASE-FIG-01
Document: FIG-PATH-01
Type: pathology
Event-Date: 2026-06-01
Issued-At: 2026-06-15
Specimen: FIG-SPEC-01
Amends: FIG-PATH-01@2
Finding: fig-marker|negative|Fictional amended note records fig-marker as negative.
Finding: fig-newkey|reported|Fictional amended note adds a fig-newkey observation.
Finding: fig-margin|pending|Fictional note records fig-margin as pending reassessment.
"""

FIG_OTHER_DOC = b"""OI-SYNTHETIC-REPORT/1
Patient: CASE-FIG-01
Document: FIG-IMG-01
Type: imaging
Event-Date: 2026-06-03
Issued-At: 2026-06-04
Finding: fig-lesion|reported|Fictional imaging note records a fig-lesion observation.
"""

FIG02_REPORT = b"""OI-SYNTHETIC-REPORT/1
Patient: CASE-FIG-02
Document: FIG2-PATH-01
Type: pathology
Event-Date: 2026-06-01
Issued-At: 2026-06-02
Finding: fig2-marker|reported|Fictional pathology note for the unrelated case.
"""

FIG_CHANGED_NO_AMENDS = b"""OI-SYNTHETIC-REPORT/1
Patient: CASE-FIG-01
Document: FIG-PATH-01
Type: pathology
Event-Date: 2026-06-01
Issued-At: 2026-06-20
Specimen: FIG-SPEC-01
Finding: fig-marker|reported|Fictional pathology note records fig-marker as present.
Finding: fig-margin|indeterminate|Fictional note cannot assess fig-margin from this specimen.
Finding: fig-extra|reported|Changed bytes without an Amends line must be rejected.
"""

EVID_V1 = b"""OI-SYNTHETIC-EVIDENCE/1
Evidence: FIG-EVID-01
Title: Fictional example study summary
Issued-At: 2026-05-10
Rights: original-synthetic
Statement: A fictional example statement used only to exercise re-review tasks.
"""

EVID_V2 = b"""OI-SYNTHETIC-EVIDENCE/1
Evidence: FIG-EVID-01
Title: Fictional example study summary
Issued-At: 2026-05-10
Rights: original-synthetic
Statement: A fictional replacement statement that supersedes the first version.
Amends: FIG-EVID-01@1
"""

EVID_WITHDRAW = b"""OI-SYNTHETIC-EVIDENCE/1
Evidence: FIG-EVID-02
Title: Fictional example flagged for withdrawal
Issued-At: 2026-05-11
Rights: original-synthetic
Statement: A fictional statement used only to exercise evidence withdrawal.
"""

EXPECTED_DIFF_V1_V2 = {
    "added_finding_keys": ["fig-newkey"],
    "removed_finding_keys": ["fig-margin"],
    "reported_state_changes": [
        {"finding_key": "fig-marker", "previous_reported_state": "reported",
         "reported_state": "negative"},
    ],
}

NO_CHANGE_NOTE = (
    "No change needed: the amended wording restates the same recorded "
    "observation, so the earlier draft still reflects the source."
)


def _fig01(store):
    store.add_case("CASE-FIG-01", "Fictional case one")
    return store.import_report("CASE-FIG-01", FIG_ORIGINAL)


def _reviewed_snapshot(store, case, question, source_ids, **kwargs):
    question_id = store.add_question(case, question)
    snapshot_id = store.create_snapshot(case, question_id, "Human draft summary for testing.", source_ids, **kwargs)
    store.acknowledge_demo_review(case, snapshot_id, "FICTIONAL-REVIEWER-B")
    return question_id, snapshot_id


def _event_id_for(store, case, kind, predicate):
    for event in store.state(case)["events"]:
        if event["kind"] != kind:
            continue
        if predicate(json.loads(event["details"])):
            return event["id"]
    raise AssertionError(f"no {kind} event found")


class ReReviewTaskTests(unittest.TestCase):
    def test_amendment_creates_one_task_per_newly_stale_snapshot(self):
        store = CaseStore(":memory:")
        original = _fig01(store)
        question_id = store.add_question("CASE-FIG-01", "What does the fictional record show?")
        reviewed = store.create_snapshot("CASE-FIG-01", question_id, "Human draft summary for testing.",
                                         [original["source_id"]])
        store.acknowledge_demo_review("CASE-FIG-01", reviewed, "FICTIONAL-REVIEWER-B")
        draft = store.create_snapshot("CASE-FIG-01", question_id, "Second human draft for testing.",
                                      [original["source_id"]])
        result = store.import_report("CASE-FIG-01", FIG_AMENDED,
                                     assignee_label="FICTIONAL-NAVIGATOR-A", due_date="2999-12-31")
        self.assertEqual(result["result"], "imported")
        self.assertCountEqual(result["invalidated_snapshots"], [reviewed, draft])
        tasks = store.list_re_review_tasks("CASE-FIG-01")
        self.assertEqual(len(tasks), 2)
        self.assertCountEqual([task["snapshot_id"] for task in tasks], [reviewed, draft])
        for task in tasks:
            self.assertEqual(task["status"], "open")
            self.assertEqual(task["cause"], "source_amendment")
            self.assertEqual(task["case_id"], "CASE-FIG-01")
            self.assertEqual(task["question_id"], question_id)
            self.assertEqual(task["assignee_label"], "FICTIONAL-NAVIGATOR-A")
            self.assertEqual(task["due_date"], "2999-12-31")
            self.assertFalse(task["overdue"])
            self.assertEqual(task["superseding_source_version_id"], result["source_id"])
            self.assertEqual(task["superseded_source_version_id"], original["source_id"])
            self.assertTrue(task["created_at"])
            self.assertIsNone(task["closed_at"])
            self.assertIsNone(task["close_note"])
            self.assertIsNone(task["closing_snapshot_id"])
        event_id = _event_id_for(store, "CASE-FIG-01", "source_imported",
                                 lambda details: details["source_id"] == result["source_id"])
        self.assertEqual({task["invalidating_event_id"] for task in tasks}, {event_id})

    def test_task_payload_pins_old_snapshot_new_version_and_key_diff(self):
        store = CaseStore(":memory:")
        original = _fig01(store)
        _, snapshot_id = _reviewed_snapshot(store, "CASE-FIG-01", "What does the fictional record show?",
                                            [original["source_id"]])
        result = store.import_report("CASE-FIG-01", FIG_AMENDED)
        tasks = store.list_re_review_tasks("CASE-FIG-01")
        self.assertEqual(len(tasks), 1)
        task = tasks[0]
        self.assertEqual(task["snapshot_id"], snapshot_id)
        self.assertEqual(task["superseding_source_version_id"], result["source_id"])
        self.assertEqual(task["finding_key_diff"], EXPECTED_DIFF_V1_V2)
        # The pinned diff is exactly the projection's mechanical diff, not a
        # second computation with its own shape.
        projection = changes_since_review(store, "CASE-FIG-01")
        self.assertEqual(len(projection["amendments"]), 1)
        self.assertEqual(projection["amendments"][0]["finding_key_diff"], task["finding_key_diff"])

    def test_unaffected_snapshots_and_other_case_get_no_tasks(self):
        store = CaseStore(":memory:")
        original = _fig01(store)
        other = store.import_report("CASE-FIG-01", FIG_OTHER_DOC)
        store.add_case("CASE-FIG-02", "Fictional case two")
        fig02 = store.import_report("CASE-FIG-02", FIG02_REPORT)
        _, affected = _reviewed_snapshot(store, "CASE-FIG-01", "What does the fictional record show?",
                                         [original["source_id"]])
        _, untouched = _reviewed_snapshot(store, "CASE-FIG-01", "What does the other document show?",
                                          [other["source_id"]])
        _, fig02_snapshot = _reviewed_snapshot(store, "CASE-FIG-02", "What does the unrelated case show?",
                                               [fig02["source_id"]])
        store.import_report("CASE-FIG-01", FIG_AMENDED)
        tasks = store.list_re_review_tasks("CASE-FIG-01")
        self.assertEqual([task["snapshot_id"] for task in tasks], [affected])
        self.assertEqual(store.list_re_review_tasks("CASE-FIG-02"), [])
        states = {row["id"]: row["state"] for row in store.state("CASE-FIG-01")["snapshots"]}
        self.assertEqual(states[untouched], "reviewed_in_demo")
        fig02_rows = store.state("CASE-FIG-02")["snapshots"]
        self.assertEqual([(row["id"], row["state"]) for row in fig02_rows],
                         [(fig02_snapshot, "reviewed_in_demo")])
        # A later amendment creates a task only for the newly stale snapshot;
        # the already-stale snapshot gets no second task.
        question_id = store.add_question("CASE-FIG-01", "What does the amended record show?")
        current = [s["id"] for s in store.state("CASE-FIG-01")["sources"]
                   if s["state"] == "current" and s["document_id"] == "FIG-PATH-01"]
        replacement = store.create_snapshot("CASE-FIG-01", question_id, "Replacement draft on version two.",
                                            current)
        store.acknowledge_demo_review("CASE-FIG-01", replacement, "FICTIONAL-REVIEWER-B")
        store.import_report("CASE-FIG-01", FIG_AMENDED_V3)
        tasks = store.list_re_review_tasks("CASE-FIG-01")
        self.assertEqual(len(tasks), 2)
        self.assertCountEqual([task["snapshot_id"] for task in tasks], [affected, replacement])

    def test_task_close_rejected_without_draft_or_note(self):
        store = CaseStore(":memory:")
        original = _fig01(store)
        _, snapshot_id = _reviewed_snapshot(store, "CASE-FIG-01", "What does the fictional record show?",
                                            [original["source_id"]])
        store.import_report("CASE-FIG-01", FIG_AMENDED)
        task_id = store.list_re_review_tasks("CASE-FIG-01")[0]["id"]
        with self.assertRaises(InvalidInput):
            store.close_re_review_task("CASE-FIG-01", task_id)
        with self.assertRaises(InvalidInput):
            store.close_re_review_task("CASE-FIG-01", task_id, closing_snapshot_id=None, no_change_note=None)
        with self.assertRaises(InvalidInput):
            store.close_re_review_task("CASE-FIG-01", task_id,
                                       closing_snapshot_id=snapshot_id, no_change_note=NO_CHANGE_NOTE)
        with self.assertRaises(InvalidInput):
            store.close_re_review_task("CASE-FIG-01", task_id, no_change_note="too short")
        with self.assertRaises(InvalidInput):
            store.close_re_review_task("CASE-FIG-01", task_id, no_change_note="x" * 601)
        with self.assertRaises(InvalidInput):
            store.close_re_review_task("CASE-FIG-01", task_id, closing_snapshot_id="not-an-id")
        self.assertEqual(store.list_re_review_tasks("CASE-FIG-01")[0]["status"], "open")

    def test_task_close_rejected_with_superseded_basis_draft(self):
        store = CaseStore(":memory:")
        original = _fig01(store)
        question_id = store.add_question("CASE-FIG-01", "What does the fictional record show?")
        stale_draft = store.create_snapshot("CASE-FIG-01", question_id, "Draft on version one for testing.",
                                            [original["source_id"]])
        store.acknowledge_demo_review("CASE-FIG-01", stale_draft, "FICTIONAL-REVIEWER-B")
        store.import_report("CASE-FIG-01", FIG_AMENDED)
        task_id = store.list_re_review_tasks("CASE-FIG-01")[0]["id"]
        with self.assertRaises(InvalidInput):
            store.close_re_review_task("CASE-FIG-01", task_id, closing_snapshot_id=stale_draft)
        # A draft for a different question is rejected even on current sources.
        current = [s["id"] for s in store.state("CASE-FIG-01")["sources"] if s["state"] == "current"]
        other_question = store.add_question("CASE-FIG-01", "An unrelated fictional question here?")
        wrong_question = store.create_snapshot("CASE-FIG-01", other_question, "Draft for another question.",
                                               current)
        with self.assertRaises(InvalidInput):
            store.close_re_review_task("CASE-FIG-01", task_id, closing_snapshot_id=wrong_question)
        with self.assertRaises(InvalidInput):
            store.close_re_review_task("CASE-FIG-01", task_id, closing_snapshot_id=999999)
        self.assertEqual(store.list_re_review_tasks("CASE-FIG-01")[0]["status"], "open")
        # Positive control: a same-question draft on current sources closes it.
        replacement = store.create_snapshot("CASE-FIG-01", question_id, "Replacement draft on version two.",
                                            current)
        outcome = store.close_re_review_task("CASE-FIG-01", task_id, closing_snapshot_id=replacement)
        self.assertEqual(outcome, {"result": "task_closed", "task_id": task_id, "status": "done"})

    def test_duplicate_and_rejected_imports_create_no_tasks(self):
        store = CaseStore(":memory:")
        original = _fig01(store)
        _reviewed_snapshot(store, "CASE-FIG-01", "What does the fictional record show?",
                           [original["source_id"]])
        duplicate = store.import_report("CASE-FIG-01", FIG_ORIGINAL)
        self.assertEqual(duplicate["result"], "duplicate")
        self.assertEqual(store.list_re_review_tasks("CASE-FIG-01"), [])
        with self.assertRaises(InvalidInput):
            store.import_report("CASE-FIG-01", FIG_CHANGED_NO_AMENDS)
        self.assertEqual(store.list_re_review_tasks("CASE-FIG-01"), [])
        quarantined = store.import_report("CASE-FIG-01", FIG02_REPORT)
        self.assertEqual(quarantined["result"], "quarantined")
        self.assertEqual(store.list_re_review_tasks("CASE-FIG-01"), [])

    def test_evidence_and_rights_invalidation_create_tasks_with_cause(self):
        store = CaseStore(":memory:")
        original = _fig01(store)
        store.add_case("CASE-FIG-02", "Fictional case two")
        current = [original["source_id"]]
        rationale = "Fictional human-authored rationale recorded for testing only."

        def _evidence_snapshot(question, evidence_version_id):
            question_id = store.add_question("CASE-FIG-01", question)
            assessment_id = store.assess_synthetic_evidence(
                "CASE-FIG-01", question_id, evidence_version_id,
                "context", "applicable", rationale)
            snapshot_id = store.create_snapshot(
                "CASE-FIG-01", question_id, "Human draft summary for testing.", current,
                evidence_assessment_ids=[assessment_id])
            store.acknowledge_demo_review("CASE-FIG-01", snapshot_id, "FICTIONAL-REVIEWER-B")
            return question_id, snapshot_id

        def _broker_snapshot(question, rights_source_id):
            question_id = store.add_question("CASE-FIG-01", question)
            link = store.create_broker_link("CASE-FIG-01", question_id, rights_source_id,
                                            "context", "applicable", rationale)
            snapshot_id = store.create_snapshot(
                "CASE-FIG-01", question_id, "Human draft summary for testing.", current,
                broker_link_ids=[link["broker_link_id"]])
            store.acknowledge_demo_review("CASE-FIG-01", snapshot_id, "FICTIONAL-REVIEWER-B")
            return question_id, snapshot_id, link["broker_link_id"]

        with self.subTest("evidence amendment"):
            imported = store.import_synthetic_evidence(EVID_V1)
            _, snapshot_id = _evidence_snapshot("What does the fictional evidence state?",
                                                imported["evidence_version_id"])
            amended = store.import_synthetic_evidence(EVID_V2, assignee_label="FICTIONAL-REVIEWER-C")
            self.assertEqual(amended["invalidated_snapshots"], [snapshot_id])
            tasks = [task for task in store.list_re_review_tasks("CASE-FIG-01")
                     if task["snapshot_id"] == snapshot_id]
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0]["cause"], "evidence_change")
            self.assertEqual(tasks[0]["evidence_version_id"], imported["evidence_version_id"])
            self.assertEqual(tasks[0]["assignee_label"], "FICTIONAL-REVIEWER-C")
            self.assertEqual(tasks[0]["finding_key_diff"], {"added_finding_keys": [],
                                                            "removed_finding_keys": [],
                                                            "reported_state_changes": []})
            event_id = _event_id_for(store, "CASE-FIG-01", "evidence_invalidated",
                                     lambda details: details["evidence_version_id"] == imported["evidence_version_id"])
            self.assertEqual(tasks[0]["invalidating_event_id"], event_id)

        with self.subTest("evidence withdrawal"):
            imported = store.import_synthetic_evidence(EVID_WITHDRAW)
            _, snapshot_id = _evidence_snapshot("What does the withdrawn evidence state?",
                                                imported["evidence_version_id"])
            withdrawn = store.withdraw_synthetic_evidence(
                imported["evidence_version_id"], "Fictional withdrawal reason for testing.")
            self.assertEqual(withdrawn["invalidated_snapshots"], [snapshot_id])
            tasks = [task for task in store.list_re_review_tasks("CASE-FIG-01")
                     if task["snapshot_id"] == snapshot_id]
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0]["cause"], "evidence_change")

        with self.subTest("rights revocation"):
            rights_id = store.register_rights_source(
                "FIG-RIGHTS-01", "Fictional Owner", "v1", "2026-01-05", {})["rights_source_id"]
            _, snapshot_id, _ = _broker_snapshot("What does the broker source state?", rights_id)
            revoked = store.revoke_rights_source(rights_id, "Fictional revocation reason for testing.")
            self.assertEqual(revoked["invalidated_snapshots"], [snapshot_id])
            tasks = [task for task in store.list_re_review_tasks("CASE-FIG-01")
                     if task["snapshot_id"] == snapshot_id]
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0]["cause"], "revocation")
            self.assertEqual(tasks[0]["rights_source_id"], rights_id)
            self.assertIsNone(tasks[0]["superseding_rights_source_id"])

        with self.subTest("rights correction"):
            rights_id = store.register_rights_source(
                "FIG-RIGHTS-02", "Fictional Owner", "v1", "2026-01-05", {})["rights_source_id"]
            _, snapshot_id, _ = _broker_snapshot("What does the corrected source state?", rights_id)
            corrected = store.correct_rights_source(
                rights_id, "v2", {}, "Fictional correction reason for testing.")
            self.assertEqual(corrected["invalidated_snapshots"], [snapshot_id])
            tasks = [task for task in store.list_re_review_tasks("CASE-FIG-01")
                     if task["snapshot_id"] == snapshot_id]
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0]["cause"], "correction")
            self.assertEqual(tasks[0]["rights_source_id"], rights_id)
            self.assertEqual(tasks[0]["superseding_rights_source_id"], corrected["rights_source_id"])

        with self.subTest("broker re-review"):
            rights_id = store.register_rights_source(
                "FIG-RIGHTS-03", "Fictional Owner", "v1", "2026-01-05", {})["rights_source_id"]
            _, snapshot_id, link_id = _broker_snapshot("What does the re-reviewed link state?", rights_id)
            reviewed = store.review_broker_link("CASE-FIG-01", link_id, "context", "limited", rationale)
            self.assertEqual(reviewed["invalidated_snapshots"], [snapshot_id])
            tasks = [task for task in store.list_re_review_tasks("CASE-FIG-01")
                     if task["snapshot_id"] == snapshot_id]
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0]["cause"], "review")
            self.assertEqual(tasks[0]["broker_link_id"], link_id)
            self.assertEqual(tasks[0]["rights_source_id"], rights_id)

        self.assertEqual(store.list_re_review_tasks("CASE-FIG-02"), [])

    def test_task_lifecycle_visible_in_history_after_completion(self):
        store = CaseStore(":memory:")
        original = _fig01(store)
        question_id = store.add_question("CASE-FIG-01", "What does the fictional record show?")
        first = store.create_snapshot("CASE-FIG-01", question_id, "First human draft for testing.",
                                      [original["source_id"]])
        store.acknowledge_demo_review("CASE-FIG-01", first, "FICTIONAL-REVIEWER-B")
        second = store.create_snapshot("CASE-FIG-01", question_id, "Second human draft for testing.",
                                       [original["source_id"]])
        store.acknowledge_demo_review("CASE-FIG-01", second, "FICTIONAL-REVIEWER-B")
        store.import_report("CASE-FIG-01", FIG_AMENDED)
        by_snapshot = {task["snapshot_id"]: task for task in store.list_re_review_tasks("CASE-FIG-01")}
        self.assertEqual(set(by_snapshot), {first, second})
        current = [s["id"] for s in store.state("CASE-FIG-01")["sources"] if s["state"] == "current"]
        replacement = store.create_snapshot("CASE-FIG-01", question_id, "Replacement draft on version two.",
                                            current)
        store.close_re_review_task("CASE-FIG-01", by_snapshot[first]["id"], closing_snapshot_id=replacement)
        store.close_re_review_task("CASE-FIG-01", by_snapshot[second]["id"], no_change_note=NO_CHANGE_NOTE)
        tasks = store.list_re_review_tasks("CASE-FIG-01")
        self.assertEqual(len(tasks), 2)
        done = {task["snapshot_id"]: task for task in tasks}
        self.assertEqual(done[first]["status"], "done")
        self.assertEqual(done[first]["closing_snapshot_id"], replacement)
        self.assertIsNone(done[first]["close_note"])
        self.assertTrue(done[first]["closed_at"])
        self.assertEqual(done[second]["status"], "done")
        self.assertEqual(done[second]["close_note"], NO_CHANGE_NOTE)
        self.assertIsNone(done[second]["closing_snapshot_id"])
        self.assertTrue(done[second]["closed_at"])
        closes = [event for event in store.state("CASE-FIG-01")["events"]
                  if event["kind"] == "re_review_task_closed"]
        self.assertEqual(len(closes), 2)
        modes = {json.loads(event["details"])["mode"] for event in closes}
        self.assertEqual(modes, {"draft", "note"})
        with self.assertRaises(InvalidInput):
            store.close_re_review_task("CASE-FIG-01", by_snapshot[first]["id"],
                                       no_change_note=NO_CHANGE_NOTE)

    def test_tasks_never_auto_approve_stale_snapshot(self):
        store = CaseStore(":memory:")
        original = _fig01(store)
        question_id = store.add_question("CASE-FIG-01", "What does the fictional record show?")
        prior = store.create_snapshot("CASE-FIG-01", question_id, "Human draft summary for testing.",
                                      [original["source_id"]])
        store.acknowledge_demo_review("CASE-FIG-01", prior, "FICTIONAL-REVIEWER-B")
        store.import_report("CASE-FIG-01", FIG_AMENDED)
        task_id = store.list_re_review_tasks("CASE-FIG-01")[0]["id"]
        current = [s["id"] for s in store.state("CASE-FIG-01")["sources"] if s["state"] == "current"]
        replacement = store.create_snapshot("CASE-FIG-01", question_id, "Replacement draft on version two.",
                                            current)
        store.close_re_review_task("CASE-FIG-01", task_id, closing_snapshot_id=replacement)
        states = {row["id"]: row["state"] for row in store.state("CASE-FIG-01")["snapshots"]}
        self.assertEqual(states[prior], "stale")
        self.assertEqual(states[replacement], "draft")
        questions = {row["id"]: row["state"] for row in store.state("CASE-FIG-01")["questions"]}
        self.assertEqual(questions[question_id], "open")

    def test_overdue_computed_from_due_date_only(self):
        store = CaseStore(":memory:")
        original = _fig01(store)
        question_id = store.add_question("CASE-FIG-01", "What does the fictional record show?")
        first = store.create_snapshot("CASE-FIG-01", question_id, "First human draft for testing.",
                                      [original["source_id"]])
        store.acknowledge_demo_review("CASE-FIG-01", first, "FICTIONAL-REVIEWER-B")
        with self.assertRaises(InvalidInput):
            store.import_report("CASE-FIG-01", FIG_AMENDED, due_date="not-a-date")
        self.assertEqual(store.list_re_review_tasks("CASE-FIG-01"), [])
        store.import_report("CASE-FIG-01", FIG_AMENDED, due_date="2000-01-01")
        tasks = store.list_re_review_tasks("CASE-FIG-01")
        self.assertEqual(len(tasks), 1)
        self.assertTrue(tasks[0]["overdue"])
        current = [s["id"] for s in store.state("CASE-FIG-01")["sources"]
                   if s["state"] == "current" and s["document_id"] == "FIG-PATH-01"]
        second = store.create_snapshot("CASE-FIG-01", question_id, "Second human draft for testing.",
                                       current)
        store.acknowledge_demo_review("CASE-FIG-01", second, "FICTIONAL-REVIEWER-B")
        store.import_report("CASE-FIG-01", FIG_AMENDED_V3)
        by_snapshot = {task["snapshot_id"]: task for task in store.list_re_review_tasks("CASE-FIG-01")}
        self.assertEqual(set(by_snapshot), {first, second})
        self.assertTrue(by_snapshot[first]["overdue"])
        self.assertFalse(by_snapshot[second]["overdue"])
        # Closing clears the flag only by completing the task; the row stays.
        store.close_re_review_task("CASE-FIG-01", by_snapshot[first]["id"], no_change_note=NO_CHANGE_NOTE)
        by_snapshot = {task["snapshot_id"]: task for task in store.list_re_review_tasks("CASE-FIG-01")}
        self.assertEqual(len(by_snapshot), 2)
        self.assertFalse(by_snapshot[first]["overdue"])
        self.assertEqual(by_snapshot[first]["status"], "done")


class ReReviewTaskHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / "server.sqlite")
        seed(cls.path)
        bound_handler = type("BoundHandlerForReReviewTest", (Handler,), {"db_path": cls.path})
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), bound_handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def request(self, path, data=None):
        values = {"Content-Type": "application/json"} if data is not None else {}
        request = Request(f"http://127.0.0.1:{self.port}{path}",
                          data=None if data is None else json.dumps(data).encode(), headers=values)
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as err:
            return err.code, json.loads(err.read())

    def test_task_list_route_errors(self):
        status, _ = self.request("/api/cases/CASE-NOPE/re-review-tasks")
        self.assertEqual(status, 422)
        status, _ = self.request("/api/cases/CASE-ALPHA/re-review-tasks/999999/close", {})
        self.assertEqual(status, 422)

    def test_task_lifecycle_over_http(self):
        status, tasks = self.request("/api/cases/CASE-ALPHA/re-review-tasks")
        self.assertEqual(status, 200)
        self.assertEqual(tasks, [])
        status, state = self.request("/api/cases/CASE-ALPHA/state")
        self.assertEqual(status, 200)
        current = [s["id"] for s in state["sources"] if s["state"] == "current"]
        status, created = self.request("/api/cases/CASE-ALPHA/questions",
                                       {"question": "What does the fictional record show?"})
        self.assertEqual(status, 201)
        status, draft = self.request("/api/cases/CASE-ALPHA/snapshots",
                                     {"question_id": created["question_id"],
                                      "summary": "Human draft summary for testing.",
                                      "source_ids": current})
        self.assertEqual(status, 201)
        status, _ = self.request(f"/api/cases/CASE-ALPHA/snapshots/{draft['snapshot_id']}/review",
                                 {"reviewer_label": "FICTIONAL-REVIEWER-B"})
        self.assertEqual(status, 200)
        status, example = self.request("/api/examples/amendment")
        self.assertEqual(status, 200)
        status, imported = self.request("/api/cases/CASE-ALPHA/imports", {"text": example["text"]})
        self.assertEqual(status, 200)
        self.assertEqual(imported["invalidated_snapshots"], [draft["snapshot_id"]])
        status, tasks = self.request("/api/cases/CASE-ALPHA/re-review-tasks")
        self.assertEqual(status, 200)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["status"], "open")
        self.assertEqual(tasks[0]["cause"], "source_amendment")
        status, _ = self.request(f"/api/cases/CASE-ALPHA/re-review-tasks/{tasks[0]['id']}/close", {})
        self.assertEqual(status, 422)
        status, closed = self.request(f"/api/cases/CASE-ALPHA/re-review-tasks/{tasks[0]['id']}/close",
                                      {"no_change_note": NO_CHANGE_NOTE})
        self.assertEqual(status, 200)
        self.assertEqual(closed["status"], "done")
        status, tasks = self.request("/api/cases/CASE-ALPHA/re-review-tasks")
        self.assertEqual(status, 200)
        self.assertEqual(tasks[0]["status"], "done")
        self.assertEqual(tasks[0]["close_note"], NO_CHANGE_NOTE)
        status, other = self.request("/api/cases/CASE-BETA/re-review-tasks")
        self.assertEqual(status, 200)
        self.assertEqual(other, [])


if __name__ == "__main__":
    unittest.main()
