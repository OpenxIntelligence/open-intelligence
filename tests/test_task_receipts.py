"""B-09: option dependencies, preparation tasks, and action receipts (G-09).

Fictional cases only (CASE-FIG-01, CASE-FIG-02). Receipts are ledger
records pinned to the basis a task acted on, never proof of real-world
completion. Nothing here auto-completes a task or auto-approves an
option. Descriptive-only language throughout.
"""
import json
import tempfile
import unittest
from pathlib import Path

from open_intelligence import CaseStore, InvalidInput


def fig_report(case_id, document_id, finding_quote, amends_version=None):
    lines = [
        "OI-SYNTHETIC-REPORT/1",
        f"Patient: {case_id}",
        f"Document: {document_id}",
        "Type: pathology",
        "Event-Date: 2026-06-01",
        "Issued-At: 2026-06-02",
    ]
    if amends_version is not None:
        lines.append(f"Amends: {document_id}@{amends_version}")
    lines.append(f"Finding: fig-note|reported|{finding_quote}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def fig_evidence(evidence_key, statement, amends_version=None):
    lines = [
        "OI-SYNTHETIC-EVIDENCE/1",
        f"Evidence: {evidence_key}",
        "Title: Fictional receipt-test evidence note",
        "Issued-At: 2026-06-03",
        "Rights: original-synthetic",
    ]
    if amends_version is not None:
        lines.append(f"Amends: {evidence_key}@{amends_version}")
    lines.append(f"Statement: {statement}")
    return ("\n".join(lines) + "\n").encode("utf-8")


OWNER = "FICTIONAL-NAVIGATOR-A"
ACTOR = "FICTIONAL-REVIEWER-B"
RATIONALE = "A human-authored fictional note on applicability for receipt tests."


class TaskReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / "receipts.sqlite")
        self.store.add_case("CASE-FIG-01", "Fictional receipt case one")
        self.store.add_case("CASE-FIG-02", "Fictional receipt case two")
        self.src1 = self.store.import_report(
            "CASE-FIG-01",
            fig_report("CASE-FIG-01", "FIG-PATH-01", "Fictional original note for receipt tests."))
        self.src2 = self.store.import_report(
            "CASE-FIG-02",
            fig_report("CASE-FIG-02", "FIG-PATH-02", "Fictional unrelated-case note for receipt tests."))
        self.q1 = self.store.add_question(
            "CASE-FIG-01", "What preparation work is recorded for this fictional case?")
        self.q2 = self.store.add_question(
            "CASE-FIG-02", "What preparation work is recorded for the other fictional case?")
        self.snap1 = self.store.create_snapshot(
            "CASE-FIG-01", self.q1, "A human-authored fictional draft for receipt tests.",
            [self.src1["source_id"]])
        self.snap2 = self.store.create_snapshot(
            "CASE-FIG-02", self.q2, "A human-authored fictional draft for the other case.",
            [self.src2["source_id"]])

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _option(self, case="CASE-FIG-01", snapshot=None, label="Fictional discussion item"):
        base = self.snap1 if case == "CASE-FIG-01" else self.snap2
        return self.store.create_option(
            case, snapshot or base, label,
            "A fictional item discussed for preparation-tracking purposes only.", "unknown")

    def _view_option(self, case, option_id):
        for option in self.store.option_view(case)["options"]:
            if option["id"] == option_id:
                return option
        self.fail(f"option {option_id} missing from {case} view")

    def _task(self, case, option, label="Fictional preparation step", owner=OWNER):
        return self.store.add_preparation_task(case, option, label, owner)

    def _task_events(self, case, task_id, kind):
        found = []
        for event in self.store.state(case)["events"]:
            if event["kind"] != kind:
                continue
            details = json.loads(event["details"])
            if details.get("task_id") == task_id:
                found.append(details)
        return found

    def _task_row(self, case, option_id, task_id):
        for task in self._view_option(case, option_id)["preparation_tasks"]:
            if task["id"] == task_id:
                return task
        self.fail(f"task {task_id} missing from option {option_id}")

    # -- B-09 behavior 1 -------------------------------------------------

    def test_task_lifecycle_persists_with_status_events(self):
        option = self._option()
        task = self._task("CASE-FIG-01", option)
        for status in ("in_progress", "blocked", "in_progress", "done"):
            self.store.set_preparation_task_status("CASE-FIG-01", task, status)
        self.assertEqual(self._task_row("CASE-FIG-01", option, task)["status"], "done")
        changes = self._task_events("CASE-FIG-01", task, "preparation_task_status_changed")
        self.assertEqual(len(changes), 4)
        chain = [(d["previous_status"], d["status"]) for d in reversed(changes)]
        self.assertEqual(chain, [("not_started", "in_progress"), ("in_progress", "blocked"),
                                 ("blocked", "in_progress"), ("in_progress", "done")])
        # Lifecycle churn on an unreviewed option does not rewrite review state.
        self.assertEqual(self._view_option("CASE-FIG-01", option)["review_state"], "current")
        # Existing guards still hold.
        with self.assertRaises(InvalidInput):
            self.store.set_preparation_task_status("CASE-FIG-01", task, "finished")
        with self.assertRaisesRegex(InvalidInput, "not in this case"):
            self.store.set_preparation_task_status("CASE-FIG-02", task, "in_progress")

    # -- B-09 behavior 2 -------------------------------------------------

    def test_done_transition_writes_receipt_pinned_to_basis(self):
        evidence = self.store.import_synthetic_evidence(
            fig_evidence("EVID-FIG-BASIS", "An independently authored fictional statement for basis tests."))
        assessment = self.store.assess_synthetic_evidence(
            "CASE-FIG-01", self.q1, evidence["evidence_version_id"],
            "context", "limited", RATIONALE)
        option = self._option()
        self.store.add_option_dependency(
            "CASE-FIG-01", option, "source", source_version_id=self.src1["source_id"])
        self.store.add_option_dependency(
            "CASE-FIG-01", option, "evidence_assessment", evidence_assessment_id=assessment)
        task = self._task("CASE-FIG-01", option)
        outcome = self.store.set_preparation_task_status(
            "CASE-FIG-01", task, "done", acting_label=ACTOR)
        receipt = self.store.get_task_receipt("CASE-FIG-01", task)
        self.assertIsNotNone(receipt)
        self.assertEqual(receipt["task_id"], task)
        self.assertEqual(receipt["option_id"], option)
        self.assertEqual(receipt["case_id"], "CASE-FIG-01")
        self.assertEqual(receipt["owner_label"], OWNER)
        self.assertEqual(receipt["acting_label"], ACTOR)
        self.assertEqual(receipt["snapshot_id"], self.snap1)
        self.assertEqual(receipt["source_version_ids"], [self.src1["source_id"]])
        self.assertEqual(receipt["evidence_version_ids"], [evidence["evidence_version_id"]])
        self.assertTrue(receipt["recorded_at"])
        self.assertEqual(outcome["receipt_id"], receipt["id"])
        # The receipted event carries the same pinned basis.
        receipted = self._task_events("CASE-FIG-01", task, "task_completion_receipted")
        self.assertEqual(len(receipted), 1)
        self.assertEqual(receipted[0]["receipt_id"], receipt["id"])
        self.assertEqual(receipted[0]["snapshot_id"], self.snap1)
        self.assertEqual(receipted[0]["source_version_ids"], [self.src1["source_id"]])
        self.assertEqual(receipted[0]["evidence_version_ids"], [evidence["evidence_version_id"]])
        # An omitted acting label defaults to the owner's label.
        task2 = self._task("CASE-FIG-01", option, label="Fictional second step")
        self.store.set_preparation_task_status("CASE-FIG-01", task2, "done")
        self.assertEqual(self.store.get_task_receipt("CASE-FIG-01", task2)["acting_label"], OWNER)

    # -- B-09 behavior 2 (immutability) ----------------------------------

    def test_receipts_immutable_never_edited_or_deleted(self):
        option = self._option()
        task = self._task("CASE-FIG-01", option)
        self.store.set_preparation_task_status("CASE-FIG-01", task, "done", acting_label=ACTOR)
        before = dict(self.store.get_task_receipt("CASE-FIG-01", task))
        # Leaving done and re-entering preserves the original row exactly,
        # even when a different acting label is offered.
        self.store.set_preparation_task_status("CASE-FIG-01", task, "in_progress")
        outcome = self.store.set_preparation_task_status(
            "CASE-FIG-01", task, "done", acting_label="FICTIONAL-NAVIGATOR-A")
        self.assertEqual(outcome["receipt_id"], before["id"])
        self.assertEqual(self.store.get_task_receipt("CASE-FIG-01", task), before)
        self.assertEqual(
            len(self._task_events("CASE-FIG-01", task, "task_completion_receipted")), 1)
        # No update or delete path exists on the store.
        for name in ("update_task_receipt", "delete_task_receipt", "edit_task_receipt",
                     "amend_task_receipt", "remove_task_receipt"):
            self.assertFalse(hasattr(self.store, name), f"unexpected mutator {name}")
        # An amendment preserves the receipt and cannot overwrite it: a
        # re-completion on the superseded basis is rejected instead.
        self.store.add_option_dependency(
            "CASE-FIG-01", option, "source", source_version_id=self.src1["source_id"])
        self.store.import_report(
            "CASE-FIG-01",
            fig_report("CASE-FIG-01", "FIG-PATH-01", "Fictional amended note for receipt tests.",
                       amends_version=1))
        self.assertEqual(self.store.get_task_receipt("CASE-FIG-01", task), before)
        self.store.set_preparation_task_status("CASE-FIG-01", task, "in_progress")
        with self.assertRaisesRegex(InvalidInput, "superseded"):
            self.store.set_preparation_task_status("CASE-FIG-01", task, "done")
        self.assertEqual(self.store.get_task_receipt("CASE-FIG-01", task), before)

    # -- B-09 behavior 3 (documented rule: reject) ------------------------

    def test_completion_on_superseded_basis_rejected_or_flagged(self):
        option = self._option()
        self.store.add_option_dependency(
            "CASE-FIG-01", option, "source", source_version_id=self.src1["source_id"])
        first = self._task("CASE-FIG-01", option, label="Fictional on-time step")
        self.store.set_preparation_task_status("CASE-FIG-01", first, "done")
        first_receipt = dict(self.store.get_task_receipt("CASE-FIG-01", first))
        amended = self.store.import_report(
            "CASE-FIG-01",
            fig_report("CASE-FIG-01", "FIG-PATH-01", "Fictional amended note for basis tests.",
                       amends_version=1))
        late = self._task("CASE-FIG-01", option, label="Fictional late step")
        with self.assertRaisesRegex(InvalidInput, "superseded"):
            self.store.set_preparation_task_status("CASE-FIG-01", late, "done")
        # Rejection writes nothing: status, events, and receipts untouched.
        self.assertEqual(self._task_row("CASE-FIG-01", option, late)["status"], "not_started")
        self.assertEqual(self._task_events("CASE-FIG-01", late, "preparation_task_status_changed"), [])
        self.assertEqual(self._task_events("CASE-FIG-01", late, "task_completion_receipted"), [])
        self.assertIsNone(self.store.get_task_receipt("CASE-FIG-01", late))
        self.assertEqual(self.store.get_task_receipt("CASE-FIG-01", first), first_receipt)
        # A withdrawn evidence premise rejects the same way.
        evidence = self.store.import_synthetic_evidence(
            fig_evidence("EVID-FIG-WDRAW", "An independently authored fictional statement for withdrawal tests."))
        assessment = self.store.assess_synthetic_evidence(
            "CASE-FIG-01", self.q1, evidence["evidence_version_id"],
            "context", "limited", RATIONALE)
        ev_question = self.store.add_question(
            "CASE-FIG-01", "What does the fictional evidence note add after the amendment?")
        ev_snap = self.store.create_snapshot(
            "CASE-FIG-01", ev_question, "A human-authored fictional draft on the current source.",
            [amended["source_id"]])
        ev_option = self._option(snapshot=ev_snap, label="Fictional evidence-bound item")
        self.store.add_option_dependency(
            "CASE-FIG-01", ev_option, "evidence_assessment", evidence_assessment_id=assessment)
        self.store.withdraw_synthetic_evidence(
            evidence["evidence_version_id"], "Fictional test withdrawal for receipt-slice verification.")
        ev_task = self._task("CASE-FIG-01", ev_option, label="Fictional evidence-bound step")
        with self.assertRaisesRegex(InvalidInput, "superseded"):
            self.store.set_preparation_task_status("CASE-FIG-01", ev_task, "done")
        self.assertIsNone(self.store.get_task_receipt("CASE-FIG-01", ev_task))
        # An invalid acting label is rejected before any write (input
        # validation precedes the basis check, so the label error wins even
        # though this basis is also superseded).
        self.store.set_preparation_task_status("CASE-FIG-01", first, "in_progress")
        with self.assertRaisesRegex(InvalidInput, "acting label"):
            self.store.set_preparation_task_status("CASE-FIG-01", first, "done", acting_label="x")
        self.assertEqual(self._task_row("CASE-FIG-01", option, first)["status"], "in_progress")
        self.assertEqual(self.store.get_task_receipt("CASE-FIG-01", first), first_receipt)

    # -- B-09 behavior 4 (exactness) -------------------------------------

    def test_stale_dependency_flags_exactly_the_dependent_options(self):
        other = self.store.import_report(
            "CASE-FIG-01",
            fig_report("CASE-FIG-01", "FIG-IMG-01", "Fictional imaging note for flag tests."))
        other_question = self.store.add_question(
            "CASE-FIG-01", "What does the fictional imaging note discuss?")
        other_snap = self.store.create_snapshot(
            "CASE-FIG-01", other_question, "A human-authored fictional imaging draft.",
            [other["source_id"]])
        dependent = self._option(label="Fictional dependent item")
        self.store.add_option_dependency(
            "CASE-FIG-01", dependent, "source", source_version_id=self.src1["source_id"])
        independent = self._option(snapshot=other_snap, label="Fictional independent item")
        self.store.add_option_dependency(
            "CASE-FIG-01", independent, "source", source_version_id=other["source_id"])
        bare = self._option(snapshot=other_snap, label="Fictional bare item")
        result = self.store.import_report(
            "CASE-FIG-01",
            fig_report("CASE-FIG-01", "FIG-PATH-01", "Fictional amended note for flag tests.",
                       amends_version=1))
        self.assertEqual(result["invalidated_options"], [dependent])
        flag = self._view_option("CASE-FIG-01", dependent)["dependency_loss"]
        self.assertTrue(flag["derived"])
        self.assertTrue(flag["present"])
        self.assertEqual(len(flag["causes"]), 1)
        self.assertIn("FIG-PATH-01@1", flag["causes"][0])
        self.assertIn("superseded", flag["causes"][0])
        self.assertIn("dependency #", flag["causes"][0])
        self.assertEqual(self._view_option("CASE-FIG-01", independent)["review_state"], "current")
        for clean in (independent, bare):
            clean_flag = self._view_option("CASE-FIG-01", clean)["dependency_loss"]
            self.assertTrue(clean_flag["derived"])
            self.assertFalse(clean_flag["present"])
            self.assertEqual(clean_flag["causes"], [])
        # Evidence withdrawal flags exactly its own dependent.
        evidence = self.store.import_synthetic_evidence(
            fig_evidence("EVID-FIG-FLAG", "An independently authored fictional statement for flag tests."))
        assessment = self.store.assess_synthetic_evidence(
            "CASE-FIG-01", self.q1, evidence["evidence_version_id"],
            "context", "limited", RATIONALE)
        ev_question = self.store.add_question(
            "CASE-FIG-01", "What does the post-amendment fictional evidence note add?")
        ev_snap = self.store.create_snapshot(
            "CASE-FIG-01", ev_question, "A human-authored fictional draft on the current source.",
            [result["source_id"]])
        ev_dependent = self._option(snapshot=ev_snap, label="Fictional evidence-flagged item")
        self.store.add_option_dependency(
            "CASE-FIG-01", ev_dependent, "evidence_assessment", evidence_assessment_id=assessment)
        self.store.withdraw_synthetic_evidence(
            evidence["evidence_version_id"], "Fictional test withdrawal for flag-slice verification.")
        ev_flag = self._view_option("CASE-FIG-01", ev_dependent)["dependency_loss"]
        self.assertTrue(ev_flag["present"])
        self.assertIn("EVID-FIG-FLAG", ev_flag["causes"][0])
        self.assertIn("withdrawn", ev_flag["causes"][0])
        self.assertFalse(self._view_option("CASE-FIG-01", independent)["dependency_loss"]["present"])
        self.assertFalse(self._view_option("CASE-FIG-01", bare)["dependency_loss"]["present"])

    # -- B-09 behaviors 4-5 (causes, recomputation, no stored threats) ---

    def test_flag_carries_cause_and_clears_on_replacement(self):
        option = self._option(label="Fictional task-flagged item")
        task = self._task("CASE-FIG-01", option)
        dep = self.store.add_option_dependency(
            "CASE-FIG-01", option, "preparation_task", preparation_task_id=task)
        self.store.set_preparation_task_status("CASE-FIG-01", task, "blocked")
        flag = self._view_option("CASE-FIG-01", option)["dependency_loss"]
        self.assertTrue(flag["present"])
        self.assertIn(f"dependency #{dep}", flag["causes"][0])
        self.assertIn(f"task #{task}", flag["causes"][0])
        self.assertIn("blocked", flag["causes"][0])
        # Derived flags clear on recomputation; nothing stored a threat row.
        self.store.set_preparation_task_status("CASE-FIG-01", task, "in_progress")
        cleared = self._view_option("CASE-FIG-01", option)["dependency_loss"]
        self.assertFalse(cleared["present"])
        self.assertEqual(cleared["causes"], [])
        self.assertEqual(self._view_option("CASE-FIG-01", option)["threats"], [])
        # A withdrawn prerequisite flags its dependent with a cause.
        prerequisite = self._option(label="Fictional prerequisite item")
        follower = self._option(label="Fictional follower item")
        follower_dep = self.store.add_option_dependency(
            "CASE-FIG-01", follower, "option", depends_on_option_id=prerequisite)
        self.store.review_option(
            "CASE-FIG-01", prerequisite, ACTOR, "withdraw",
            "Withdrawn for fictional flag-slice verification.")
        follower_flag = self._view_option("CASE-FIG-01", follower)["dependency_loss"]
        self.assertTrue(follower_flag["present"])
        self.assertIn(f"dependency #{follower_dep}", follower_flag["causes"][0])
        self.assertIn(f"option #{prerequisite}", follower_flag["causes"][0])
        self.assertIn("withdrawn", follower_flag["causes"][0])
        # A needs-review prerequisite flags its dependent as needs review.
        seeded = self._option(label="Fictional seeded item")
        self.store.add_option_dependency(
            "CASE-FIG-01", seeded, "source", source_version_id=self.src1["source_id"])
        watcher = self._option(label="Fictional watcher item")
        self.store.add_option_dependency(
            "CASE-FIG-01", watcher, "option", depends_on_option_id=seeded)
        amended = self.store.import_report(
            "CASE-FIG-01",
            fig_report("CASE-FIG-01", "FIG-PATH-01", "Fictional amended note for cause tests.",
                       amends_version=1))
        watcher_flag = self._view_option("CASE-FIG-01", watcher)["dependency_loss"]
        self.assertTrue(watcher_flag["present"])
        self.assertIn(f"option #{seeded}", watcher_flag["causes"][0])
        self.assertIn("needs review", watcher_flag["causes"][0])
        # Review state and derived flags stay separate: an option whose own
        # snapshot went stale reopens for review without a dependency loss.
        reopened = self._view_option("CASE-FIG-01", option)
        self.assertEqual(reopened["review_state"], "needs_review")
        self.assertFalse(reopened["dependency_loss"]["present"])
        # A replacement proposal on current inputs carries no flag.
        question = self.store.add_question(
            "CASE-FIG-01", "What is discussed after the amendment in this fictional case?")
        fresh = self.store.create_snapshot(
            "CASE-FIG-01", question, "A human-authored post-amendment fictional draft.",
            [amended["source_id"]])
        replacement = self._option(snapshot=fresh, label="Fictional replacement item")
        self.store.add_option_dependency(
            "CASE-FIG-01", replacement, "source", source_version_id=amended["source_id"])
        replacement_view = self._view_option("CASE-FIG-01", replacement)
        self.assertEqual(replacement_view["review_state"], "current")
        self.assertFalse(replacement_view["dependency_loss"]["present"])
        self.assertEqual(replacement_view["dependency_loss"]["causes"], [])
        # Still no automatic threat rows anywhere in the case.
        for viewed in self.store.option_view("CASE-FIG-01")["options"]:
            self.assertEqual(viewed["threats"], [])

    # -- B-09 behaviors 5 and 9 (no automation) --------------------------

    def test_no_automatic_threat_rows_or_completions(self):
        evidence = self.store.import_synthetic_evidence(
            fig_evidence("EVID-FIG-AUTO", "An independently authored fictional statement for automation tests."))
        assessment = self.store.assess_synthetic_evidence(
            "CASE-FIG-01", self.q1, evidence["evidence_version_id"],
            "context", "limited", RATIONALE)
        option = self._option()
        self.store.add_option_dependency(
            "CASE-FIG-01", option, "source", source_version_id=self.src1["source_id"])
        self.store.add_option_dependency(
            "CASE-FIG-01", option, "evidence_assessment", evidence_assessment_id=assessment)
        first = self._task("CASE-FIG-01", option, label="Fictional waiting step")
        second = self._task("CASE-FIG-01", option, label="Fictional started step")
        self.store.set_preparation_task_status("CASE-FIG-01", second, "in_progress")
        threat = self.store.add_optionality_threat(
            "CASE-FIG-01", option, "dependency_loss",
            "A human-entered fictional note that a depended-upon item may change.")
        other = self._option(label="Fictional review-only item")
        self.store.review_option(
            "CASE-FIG-01", other, ACTOR, "approve",
            "Review of this fictional discussion item for the test record.")
        # Amendments, withdrawals, dependencies, and reviews fire around the
        # tasks without completing anything or writing threat rows.
        amended = self.store.import_report(
            "CASE-FIG-01",
            fig_report("CASE-FIG-01", "FIG-PATH-01", "Fictional amended note for automation tests.",
                       amends_version=1))
        self.store.withdraw_synthetic_evidence(
            evidence["evidence_version_id"], "Fictional test withdrawal for automation verification.")
        self.store.add_option_dependency(
            "CASE-FIG-01", other, "source", source_version_id=amended["source_id"])
        self.assertEqual(self._task_row("CASE-FIG-01", option, first)["status"], "not_started")
        self.assertEqual(self._task_row("CASE-FIG-01", option, second)["status"], "in_progress")
        self.assertIsNone(self.store.get_task_receipt("CASE-FIG-01", first))
        self.assertIsNone(self.store.get_task_receipt("CASE-FIG-01", second))
        for viewed in self.store.option_view("CASE-FIG-01")["options"]:
            for task in viewed["preparation_tasks"]:
                self.assertNotEqual(task["status"], "done")
        kinds = [event["kind"] for event in self.store.state("CASE-FIG-01")["events"]]
        self.assertNotIn("task_completion_receipted", kinds)
        threats = self._view_option("CASE-FIG-01", option)["threats"]
        self.assertEqual([row["id"] for row in threats], [threat])
        self.assertEqual(
            threats[0]["description"],
            "A human-entered fictional note that a depended-upon item may change.")

    # -- B-09 behavior 6 (open vs receipted packet) -----------------------

    def test_packet_lists_open_vs_receipted_tasks(self):
        option = self._option()
        waiting = self._task("CASE-FIG-01", option, label="Fictional waiting step")
        started = self._task("CASE-FIG-01", option, label="Fictional started step")
        stuck = self._task("CASE-FIG-01", option, label="Fictional stuck step")
        finished = self._task("CASE-FIG-01", option, label="Fictional finished step")
        dropped = self._task("CASE-FIG-01", option, label="Fictional dropped step")
        self.store.set_preparation_task_status("CASE-FIG-01", started, "in_progress")
        self.store.set_preparation_task_status("CASE-FIG-01", stuck, "blocked")
        self.store.set_preparation_task_status("CASE-FIG-01", finished, "done", acting_label=ACTOR)
        self.store.set_preparation_task_status("CASE-FIG-01", dropped, "cancelled")
        view = self._view_option("CASE-FIG-01", option)
        self.assertEqual(view["open_task_ids"], [waiting, started, stuck])
        self.assertEqual(view["receipted_task_ids"], [finished])
        by_id = {task["id"]: task for task in view["preparation_tasks"]}
        receipt = self.store.get_task_receipt("CASE-FIG-01", finished)
        self.assertEqual(by_id[finished]["receipt_id"], receipt["id"])
        self.assertEqual(by_id[finished]["receipt_marker"], "receipted")
        for task_id in (waiting, started, stuck, dropped):
            self.assertIsNone(by_id[task_id]["receipt_id"])
            self.assertEqual(by_id[task_id]["receipt_marker"], "no_receipt")
        # A cancelled task is terminal, so it is marked but not listed as open.
        self.assertNotIn(dropped, view["open_task_ids"])
        # Two reads of the same packet are identical.
        self.assertEqual(self.store.option_view("CASE-FIG-01"), self.store.option_view("CASE-FIG-01"))
        # A pre-slice done row (inserted as the old code stored it: status
        # only, no receipt) is labeled, never backfilled silently.
        legacy = self.store.db.execute(
            """INSERT INTO preparation_tasks
            (case_id,option_id,label,owner_label,status,lead_time_days,created_at)
            VALUES (?,?,?,?,?,?,?)""",
            ("CASE-FIG-01", option, "Fictional legacy step", OWNER,
             "done", None, "2026-06-04T00:00:00+00:00"))
        legacy_id = int(legacy.lastrowid)
        self.store.db.commit()
        legacy_row = self._task_row("CASE-FIG-01", option, legacy_id)
        self.assertEqual(legacy_row["status"], "done")
        self.assertIsNone(legacy_row["receipt_id"])
        self.assertEqual(legacy_row["receipt_marker"], "receipt_predates_slice")
        self.assertIsNone(self.store.get_task_receipt("CASE-FIG-01", legacy_id))
        relisted = self._view_option("CASE-FIG-01", option)
        self.assertNotIn(legacy_id, relisted["receipted_task_ids"])
        self.assertNotIn(legacy_id, relisted["open_task_ids"])

    # -- B-09 behavior 7 (held options keep receipts) --------------------

    def test_contradicted_option_held_with_receipts_visible(self):
        option = self._option()
        task = self._task("CASE-FIG-01", option)
        self.store.set_preparation_task_status("CASE-FIG-01", task, "done", acting_label=ACTOR)
        receipt_id = self.store.get_task_receipt("CASE-FIG-01", task)["id"]
        evidence = self.store.import_synthetic_evidence(
            fig_evidence("EVID-FIG-HELD", "An independently authored fictional statement for held tests."))
        assessment = self.store.assess_synthetic_evidence(
            "CASE-FIG-01", self.q1, evidence["evidence_version_id"],
            "contradicts", "limited", RATIONALE)
        self.store.add_option_dependency(
            "CASE-FIG-01", option, "evidence_assessment", evidence_assessment_id=assessment)
        held = self._view_option("CASE-FIG-01", option)
        self.assertEqual(held["derived_epistemic_status"], "contradicted")
        self.assertEqual(held["display_operational_status"], "held")
        self.assertEqual(held["operational_status"], "proposed")
        # Held by contradiction is not dependency loss: the premise is current.
        self.assertFalse(held["dependency_loss"]["present"])
        self.assertEqual(self._task_row("CASE-FIG-01", option, task)["receipt_id"], receipt_id)
        self.assertTrue(held["dependencies"])
        self.store.review_option(
            "CASE-FIG-01", option, ACTOR, "reject",
            "Rejected because the linked fictional note contradicts it.")
        rejected = self._view_option("CASE-FIG-01", option)
        self.assertEqual(rejected["operational_status"], "rejected")
        self.assertEqual(len(rejected["review_events"]), 1)
        self.assertEqual(rejected["review_events"][0]["action"], "reject")
        self.assertEqual(self._task_row("CASE-FIG-01", option, task)["receipt_id"], receipt_id)
        self.assertTrue(rejected["dependencies"])

    # -- B-09 behavior 8 (case isolation) --------------------------------

    def test_tasks_receipts_flags_case_isolated(self):
        option = self._option()
        self.store.add_option_dependency(
            "CASE-FIG-01", option, "source", source_version_id=self.src1["source_id"])
        task = self._task("CASE-FIG-01", option)
        self.store.set_preparation_task_status("CASE-FIG-01", task, "done", acting_label=ACTOR)
        receipt_id = self.store.get_task_receipt("CASE-FIG-01", task)["id"]
        other_option = self._option(case="CASE-FIG-02")
        other_task = self._task("CASE-FIG-02", other_option, label="Fictional other-case step")
        self.store.import_report(
            "CASE-FIG-01",
            fig_report("CASE-FIG-01", "FIG-PATH-01", "Fictional amended note for isolation tests.",
                       amends_version=1))
        self.assertTrue(self._view_option("CASE-FIG-01", option)["dependency_loss"]["present"])
        other_view = self._view_option("CASE-FIG-02", other_option)
        self.assertEqual(other_view["review_state"], "current")
        self.assertFalse(other_view["dependency_loss"]["present"])
        self.assertEqual(other_view["open_task_ids"], [other_task])
        self.assertEqual(other_view["receipted_task_ids"], [])
        for task_row in other_view["preparation_tasks"]:
            self.assertIsNone(task_row["receipt_id"])
        self.assertIsNone(self.store.get_task_receipt("CASE-FIG-02", task))
        # The other case completes its own work independently.
        self.store.set_preparation_task_status("CASE-FIG-02", other_task, "done")
        other_receipt = self.store.get_task_receipt("CASE-FIG-02", other_task)
        self.assertEqual(other_receipt["case_id"], "CASE-FIG-02")
        self.assertNotEqual(other_receipt["id"], receipt_id)
        self.assertEqual(
            self._view_option("CASE-FIG-02", other_option)["receipted_task_ids"], [other_task])

    # -- B-09 behavior 8 (global evidence fan-out exception) -------------

    def test_evidence_fanout_stays_global_and_asserted(self):
        evidence = self.store.import_synthetic_evidence(
            fig_evidence("EVID-FIG-SHARED", "An independently authored fictional statement shared by two cases."))
        first_assessment = self.store.assess_synthetic_evidence(
            "CASE-FIG-01", self.q1, evidence["evidence_version_id"],
            "context", "limited", RATIONALE)
        second_assessment = self.store.assess_synthetic_evidence(
            "CASE-FIG-02", self.q2, evidence["evidence_version_id"],
            "context", "limited", RATIONALE)
        first_snap = self.store.create_snapshot(
            "CASE-FIG-01", self.q1, "A human-authored fictional draft bound to shared evidence.",
            [self.src1["source_id"]], evidence_assessment_ids=[first_assessment])
        second_snap = self.store.create_snapshot(
            "CASE-FIG-02", self.q2, "A human-authored fictional draft bound to shared evidence.",
            [self.src2["source_id"]], evidence_assessment_ids=[second_assessment])
        first_option = self._option(snapshot=first_snap, label="Fictional first-case item")
        self.store.add_option_dependency(
            "CASE-FIG-01", first_option, "evidence_assessment",
            evidence_assessment_id=first_assessment)
        second_option = self._option(case="CASE-FIG-02", snapshot=second_snap,
                                     label="Fictional second-case item")
        self.store.add_option_dependency(
            "CASE-FIG-02", second_option, "evidence_assessment",
            evidence_assessment_id=second_assessment)
        task = self._task("CASE-FIG-01", first_option)
        self.store.set_preparation_task_status("CASE-FIG-01", task, "done", acting_label=ACTOR)
        receipt_id = self.store.get_task_receipt("CASE-FIG-01", task)["id"]
        result = self.store.withdraw_synthetic_evidence(
            evidence["evidence_version_id"], "Fictional test withdrawal shared across two cases.")
        # The fan-out is global exactly as today: both cases invalidated.
        self.assertEqual(sorted(result["invalidated_snapshots"]), sorted([first_snap, second_snap]))
        self.assertEqual(sorted(result["invalidated_options"]), sorted([first_option, second_option]))
        self.assertEqual(self._view_option("CASE-FIG-01", first_option)["review_state"], "needs_review")
        self.assertEqual(self._view_option("CASE-FIG-02", second_option)["review_state"], "needs_review")
        self.assertTrue(self._view_option("CASE-FIG-01", first_option)["dependency_loss"]["present"])
        self.assertTrue(self._view_option("CASE-FIG-02", second_option)["dependency_loss"]["present"])
        # The exception is not widened: tasks and receipts stay case-scoped.
        for task_row in self._view_option("CASE-FIG-02", second_option)["preparation_tasks"]:
            self.assertIsNone(task_row["receipt_id"])
        self.assertEqual(self._view_option("CASE-FIG-02", second_option)["receipted_task_ids"], [])
        self.assertIsNone(self.store.get_task_receipt("CASE-FIG-02", task))
        self.assertEqual(self.store.get_task_receipt("CASE-FIG-01", task)["id"], receipt_id)

    # -- B-09 behaviors 1-2 alongside existing review history ------------

    def test_review_events_preserved_alongside_receipts(self):
        option = self._option()
        self.store.add_option_dependency(
            "CASE-FIG-01", option, "source", source_version_id=self.src1["source_id"])
        task = self._task("CASE-FIG-01", option)
        self.store.set_preparation_task_status("CASE-FIG-01", task, "done", acting_label=ACTOR)
        receipt_id = self.store.get_task_receipt("CASE-FIG-01", task)["id"]
        self.store.review_option(
            "CASE-FIG-01", option, ACTOR, "approve",
            "Review of this fictional discussion item for the test record.")
        reviewed = self._view_option("CASE-FIG-01", option)
        self.assertEqual(reviewed["operational_status"], "reviewed")
        self.assertEqual(reviewed["review_state"], "current")
        self.assertEqual(len(reviewed["review_events"]), 1)
        self.assertEqual(reviewed["review_events"][0]["action"], "approve")
        self.assertEqual(reviewed["review_events"][0]["reviewer_label"], ACTOR)
        self.assertEqual(self._task_row("CASE-FIG-01", option, task)["receipt_id"], receipt_id)
        # An amendment reopens review and flags the loss while preserving
        # both the endorsement history and the completion receipt.
        self.store.import_report(
            "CASE-FIG-01",
            fig_report("CASE-FIG-01", "FIG-PATH-01", "Fictional amended note for history tests.",
                       amends_version=1))
        reopened = self._view_option("CASE-FIG-01", option)
        self.assertEqual(reopened["review_state"], "needs_review")
        self.assertTrue(reopened["dependency_loss"]["present"])
        self.assertEqual(len(reopened["review_events"]), 1)
        self.assertEqual(reopened["review_events"][0]["action"], "approve")
        self.assertEqual(self._task_row("CASE-FIG-01", option, task)["receipt_id"], receipt_id)
        self.assertIsNotNone(self.store.get_task_receipt("CASE-FIG-01", task))

    # -- B-09 acceptance chain -------------------------------------------

    def test_end_to_end_chain_propose_depend_receipt_amend_flag_reconfirm(self):
        option = self._option(label="Fictional chained item")
        self.store.add_option_dependency(
            "CASE-FIG-01", option, "source", source_version_id=self.src1["source_id"])
        task = self._task("CASE-FIG-01", option)
        self.store.set_preparation_task_status("CASE-FIG-01", task, "done", acting_label=ACTOR)
        receipt_id = self.store.get_task_receipt("CASE-FIG-01", task)["id"]
        snapshot_bound = self._option(label="Fictional snapshot-bound item")
        amended = self.store.import_report(
            "CASE-FIG-01",
            fig_report("CASE-FIG-01", "FIG-PATH-01", "Fictional amended note for chain tests.",
                       amends_version=1))
        flagged = self._view_option("CASE-FIG-01", option)
        self.assertEqual(flagged["review_state"], "needs_review")
        self.assertTrue(flagged["dependency_loss"]["present"])
        # The preserved rule still holds: a stale source premise needs a new
        # proposal, not a pointer reconfirmation.
        question = self.store.add_question(
            "CASE-FIG-01", "What is discussed after the amendment in this fictional case?")
        fresh = self.store.create_snapshot(
            "CASE-FIG-01", question, "A human-authored post-amendment fictional draft.",
            [amended["source_id"]])
        with self.assertRaisesRegex(InvalidInput, "not current"):
            self.store.review_option(
                "CASE-FIG-01", option, ACTOR, "reconfirm",
                "Re-review against the post-amendment fictional draft.", fresh)
        replacement = self._option(snapshot=fresh, label="Fictional chained replacement")
        self.store.add_option_dependency(
            "CASE-FIG-01", replacement, "source", source_version_id=amended["source_id"])
        self.store.review_option(
            "CASE-FIG-01", replacement, ACTOR, "approve",
            "Review of this fictional replacement item for the test record.")
        replacement_view = self._view_option("CASE-FIG-01", replacement)
        self.assertEqual(replacement_view["operational_status"], "reviewed")
        self.assertFalse(replacement_view["dependency_loss"]["present"])
        # An option invalidated through its snapshot alone reconfirms on a
        # fresh draft, keeping the original association visible.
        self.assertEqual(
            self._view_option("CASE-FIG-01", snapshot_bound)["review_state"], "needs_review")
        self.store.review_option(
            "CASE-FIG-01", snapshot_bound, ACTOR, "reconfirm",
            "Re-review against the post-amendment fictional draft.", fresh)
        reconfirmed = self._view_option("CASE-FIG-01", snapshot_bound)
        self.assertEqual(reconfirmed["review_state"], "current")
        self.assertFalse(reconfirmed["dependency_loss"]["present"])
        self.assertIn(self.snap1, reconfirmed["associated_snapshot_ids"])
        # The original chain keeps its receipt, dependencies, and flag; the
        # other fictional case is untouched throughout.
        original = self._view_option("CASE-FIG-01", option)
        self.assertEqual(self._task_row("CASE-FIG-01", option, task)["receipt_id"], receipt_id)
        self.assertTrue(original["dependencies"])
        self.assertTrue(original["dependency_loss"]["present"])
        other_option = self._option(case="CASE-FIG-02")
        other_view = self._view_option("CASE-FIG-02", other_option)
        self.assertEqual(other_view["review_state"], "current")
        self.assertFalse(other_view["dependency_loss"]["present"])
        self.assertEqual(other_view["preparation_tasks"], [])


if __name__ == "__main__":
    unittest.main()
