"""Synthetic PostgreSQL/HTTP acceptance for tasks on saved FHIR observations."""
import json
from unittest.mock import patch

from sqlalchemy import text

from http_support import running_server
from oi_api.app import create_app
from open_intelligence.postgres_registry import PostgresPatientRegistry
from test_canonical_review_flow import create_question
import test_durable_laboratory_questions as laboratory
import test_followthrough_http as followthrough
from test_patients import TOKEN_A, TOKEN_B, request
from test_source_versions import SourceVersionFixture

V2 = "application/vnd.open-intelligence.followthrough.v2+json"


class LaboratoryFollowthroughHTTPTests(SourceVersionFixture):
    scope = laboratory.DurableLaboratoryQuestionHTTPTests.scope
    expect = laboratory.DurableLaboratoryQuestionHTTPTests.expect
    prepare = laboratory.DurableLaboratoryQuestionHTTPTests.prepare
    import_lab = laboratory.DurableLaboratoryQuestionHTTPTests.import_lab
    task_path = staticmethod(followthrough.FollowthroughHTTPTests.task_path)
    create_task = followthrough.FollowthroughHTTPTests.create_task
    transition = followthrough.FollowthroughHTTPTests.transition
    counts = followthrough.FollowthroughHTTPTests.counts

    def setUp(self):
        super().setUp()
        for credential in self.creds:
            credential["actions"].extend(("composer_context_read", "question_create", "question_read",
                                          "followthrough_read", "followthrough_create", "followthrough_update"))
        self.write()
        self.base = self.enterContext(running_server(create_app(self.settings)))
        self.patient, self.path = self.scope(self.base)
        self.source = self.import_lab(self.base, self.path)

    def saved_question(self, reference=laboratory.OBS):
        prepared, fields = self.prepare(self.base, self.path, self.source["source_id"], reference)
        saved = self.expect(201, self.base, self.path + laboratory.LAB_HISTORY,
                            {**fields, "request_key": "SAVE-LAB-" + reference.split("/")[1]})
        return saved["question_id"], prepared

    def create(self, qid, prepared, **fields):
        return self.create_task(self.base, self.patient, prepared, qid, **fields)

    def record(self, task, status, revision, **fields):
        return self.transition(self.base, self.patient, task, status, revision, **fields)

    def read(self, *, version=2, case=laboratory.CASE, token=TOKEN_A):
        return request(self.base, self.task_path(self.patient, case), token=token,
                       headers={"Accept": V2} if version == 2 else {})

    def listing(self, version=2):
        status, result, headers = self.read(version=version)
        self.assertEqual(status, 200, result)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("accept", {s.strip().lower() for s in headers["Vary"].split(",")})
        self.assertEqual(headers.get_content_type(), V2 if version == 2 else "application/json")
        self.assertEqual(result["contract"], f"oi.pg-question-followthrough/{version}")
        self.assertFalse(result["clinical_approval"])
        self.assertFalse(result["external_notification_sent"])
        return result

    def rejected(self, expected, perform, *secrets):
        before = self.counts()
        status, result, headers = perform()
        self.assertEqual(status, expected, result)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(set(result), {"detail"})
        for value in (*secrets, laboratory.OBS, laboratory.QUESTION, followthrough.TITLE,
                      self.source["source_id"], self.source["original_sha256"]):
            self.assertNotIn(value, json.dumps(result))
        self.assertEqual(self.counts(), before, "refusal must not commit a task, task event, or audit receipt")

    def test_mixed_tasks_preserve_v1_text_and_v2_observation_origin_and_current_transitions(self):
        code, note, _ = self.ingest(self.base, self.patient)
        self.assertEqual(code, 201, note)
        text_id, _ = create_question(self, self.base, self.patient, note["source_id"])
        text_row, = self.expect(200, self.base, self.path + "/questions")["questions"]
        code, text_task, _ = self.create(text_id, text_row, request_key="CREATE-TEXT-TASK",
                                         title="Inspect the fictional text source")
        self.assertEqual(code, 201, text_task)
        old_text, = self.listing(1)["tasks"]
        qid, prepared = self.saved_question()
        _, sibling = self.saved_question(laboratory.ABSENT)
        for change in ({"expected_source_snapshot_sha256": "0" * 64},
                       {"expected_preflight_sha256": sibling["preflight_sha256"]}):
            self.rejected(409, lambda: self.create(qid, prepared, **change), qid)
        status, task, _ = self.create(qid, prepared)
        self.assertEqual(status, 201, task)
        tid = task["task_id"]
        self.assertEqual(self.create(qid, prepared)[:2], (200, {**task, "duplicate": True}))
        self.rejected(409, lambda: self.create(qid, prepared, title="Changed fictional intent"), qid, tid)
        self.rejected(409, lambda: self.record(tid, "completed", 1), qid, tid)
        receipts = [task]
        for rev, state in enumerate(("assigned", "acknowledged", "completed"), 1):
            code, changed, _ = self.record(tid, state, rev)
            self.assertEqual((code, changed["revision"]), (201, rev + 1))
            receipts.append(changed)
            self.assertEqual(self.record(tid, state, rev)[:2], (200, {**changed, "duplicate": True}))
        self.rejected(409, lambda: self.record(tid, "completed", 3, reason="Different fictional intent"), tid)
        legacy = self.listing(1)
        self.assertEqual(legacy["tasks"], [old_text])
        self.assertEqual(old_text["source_line"], 8)
        self.assertNotIn("observation_reference", old_text)
        for value in (qid, tid, laboratory.OBS, followthrough.TITLE):
            self.assertNotIn(value, json.dumps(legacy))
        v2 = self.listing()
        self.assertNotEqual(v2["access_receipt_id"], legacy["access_receipt_id"])
        rows = {item["task_id"]: item for item in v2["tasks"]}
        self.assertEqual(set(rows), {text_task["task_id"], tid})
        self.assertEqual({k: rows[text_task["task_id"]][k] for k in old_text}, old_text)
        self.assertIsNone(rows[text_task["task_id"]].get("observation_reference"))
        row = rows[tid]
        expected = {"patient_id": self.patient, "case_id": laboratory.CASE, "question_id": qid,
                    "source_id": self.source["source_id"], "source_version": 1,
                    "source_line": None, "observation_reference": laboratory.OBS,
                    "source_sha256": self.source["original_sha256"],
                    "source_snapshot_contract": prepared["source_snapshot_contract"],
                    "source_snapshot_sha256": prepared["source_snapshot_sha256"],
                    "preflight_sha256": prepared["preflight_sha256"], "status": "completed",
                    "revision": 4, "source_context_state": "current_unreviewed_question",
                    "clinical_approval": False, "needs_recheck": False}
        self.assertEqual({k: row[k] for k in expected}, expected)
        self.assertEqual([(e["event_id"], e["revision"], e["status"], e["actor_label"]) for e in row["history"]],
                         [(r["event_id"], r["revision"], s, "ACTOR-ALPHA") for r, s in
                          zip(receipts, ("created", "assigned", "acknowledged", "completed"), strict=True)])
        for value in (laboratory.ABSENT, laboratory.QUESTION, "Fictional plasma sample", "valueQuantity"):
            self.assertNotIn(value, json.dumps(v2))

    def test_amendment_keeps_original_history_and_replay_but_refuses_new_work_and_completion(self):
        qid, prepared = self.saved_question()
        code, first, _ = self.create(qid, prepared)
        self.assertEqual(code, 201, first)
        tid = first["task_id"]
        self.assertEqual(self.record(tid, "assigned", 1)[0], 201)
        code, acknowledged, _ = self.record(tid, "acknowledged", 2)
        self.assertEqual(code, 201, acknowledged)
        before, = self.listing()["tasks"]
        self.source = self.import_lab(self.base, self.path, value=1, previous=self.source["source_id"])
        self.rejected(409, lambda: self.create(qid, prepared, request_key="STALE-NEW-TASK"), qid, tid)
        self.rejected(409, lambda: self.record(tid, "completed", 3), qid, tid)
        self.assertEqual(self.create(qid, prepared)[:2], (200, {**first, "duplicate": True}))
        self.assertEqual(self.record(tid, "acknowledged", 2)[:2], (200, {**acknowledged, "duplicate": True}))
        historical, = self.listing()["tasks"]
        self.assertEqual(historical, {**before, "source_context_state": "source_reassessment_required",
                                      "needs_recheck": True})
        ledger = self.expect(200, self.base, self.path + laboratory.LAB_HISTORY)
        self.assertEqual(ledger["questions"][0]["source_context_state"], "source_reassessment_required")
        # Separately prepared amendment, same literal and FHIR resource reference, different version and hash.
        current, fields = self.prepare(self.base, self.path, self.source["source_id"])
        newer = self.expect(201, self.base, self.path + laboratory.LAB_HISTORY,
                            {**fields, "request_key": "SAVE-AMENDED-QUESTION"})["question_id"]
        code, fresh, _ = self.create(newer, current, request_key="TASK-AFTER-FRESH-PREPARATION")
        self.assertEqual(code, 201, fresh)
        by_task = {t["task_id"]: t for t in self.listing()["tasks"]}
        self.assertEqual(by_task[tid], historical)
        row = by_task[fresh["task_id"]]
        self.assertEqual((row["question_id"], row["source_version"], row["source_id"], row["source_sha256"],
                          row["observation_reference"], row["preflight_sha256"], row["needs_recheck"]),
                         (newer, 2, self.source["source_id"], self.source["original_sha256"],
                          laboratory.OBS, current["preflight_sha256"], False))

    def test_wrong_case_revoked_binding_and_independent_grants_hide_reads_and_retries(self):
        qid, prepared = self.saved_question()
        code, receipt, _ = self.create(qid, prepared)
        self.assertEqual(code, 201, receipt)
        tid = receipt["task_id"]
        self.assertEqual(self.record(tid, "assigned", 1)[0], 201)
        operations = (
            ("followthrough_read", lambda **scope: self.read(version=1, **scope)),
            ("followthrough_read", lambda **scope: self.read(version=2, **scope)),
            ("followthrough_create", lambda **scope: self.create(qid, prepared, **scope)),
            ("followthrough_update", lambda **scope: self.record(tid, "assigned", 1, **scope)),
        )
        # A second active case for the same authorized patient may read its own empty ledger.
        # Replaying a known question or task from the first case must still be refused.
        other_case = "CASE-OTHER-ACTIVE"
        self.expect(201, self.base, f"/v1/patients/{self.patient}/case-bindings", {
            "synthetic": True, "case_id": other_case, "source_organization": "ORG-INSTITUTION",
            "source_system": "SYS-SYNTH", "source_subject_ref": "OTHER-FICTIONAL-SUBJECT",
            "review_ref": "REVIEW-OTHER-CASE"})
        for version in (1, 2):
            status, other, _ = self.read(version=version, case=other_case)
            self.assertEqual((status, other["tasks"]), (200, []))
            for value in (qid, tid, laboratory.OBS):
                self.assertNotIn(value, json.dumps(other))
        self.rejected(404, lambda: self.create(qid, prepared, case=other_case), qid, tid)
        self.rejected(404, lambda: self.record(tid, "assigned", 1, case=other_case), qid, tid)
        self.creds[1]["patient_ids"] = [self.patient]
        self.write()
        for _, perform in operations:
            for scope in ({"case": "CASE-BETA"}, {"token": TOKEN_B}):
                self.rejected(404, lambda: perform(**scope), qid, tid)
        for grant in ("patient_read", "question_read", "source_read", "followthrough_read",
                      "followthrough_create", "followthrough_update"):
            with self.subTest(missing=grant):
                self.creds[0]["actions"].remove(grant)
                self.write()
                for action, perform in operations:
                    if grant in ("patient_read", "question_read", "source_read", action):
                        self.rejected(404, perform, qid, tid)
                self.creds[0]["actions"].append(grant)
                self.write()
        self.expect(200, self.base, f"/v1/patients/{self.patient}/case-bindings/{laboratory.CASE}/revoke",
                    {"synthetic": True, "reason": "Withdraw the fictional laboratory binding."})
        for _, perform in operations:
            self.rejected(404, perform, qid, tid)

    def test_wrong_organization_on_last_lab_event_withholds_both_lists_and_receipts(self):
        qid, prepared = self.saved_question()
        status, created, _ = self.create(qid, prepared)
        self.assertEqual(status, 201, created)
        tid = created["task_id"]
        status, assigned, _ = self.record(tid, "assigned", 1)
        self.assertEqual(status, 201, assigned)
        self.assertEqual(self.listing()["tasks"][0]["revision"], 2)
        self.assertEqual(self.listing(1)["tasks"], [])
        # Simulate a damaged restore in this disposable database. An event query
        # restricted to the old organization would silently lose the last revision.
        with self.engine.begin() as db:
            db.exec_driver_sql("ALTER TABLE coordination.question_followthrough_events "
                               "DISABLE TRIGGER oi_followthrough_event_immutable")
            event_id = db.execute(text("UPDATE coordination.question_followthrough_events "
                                       "SET origin_org='ORG-WRONG-FIXTURE' WHERE event_id=:event_id "
                                       "RETURNING event_id"), {"event_id": assigned["event_id"]}).scalar_one()
            self.assertEqual(event_id, assigned["event_id"])
            db.exec_driver_sql("ALTER TABLE coordination.question_followthrough_events "
                               "ENABLE TRIGGER oi_followthrough_event_immutable")
        for version in (1, 2):
            self.rejected(503, lambda: self.read(version=version), qid, tid, assigned["event_id"])

    def test_revocation_after_access_audit_rolls_back_create_transition_replay_and_typed_read(self):
        qid, prepared = self.saved_question()
        code, saved, _ = self.create(qid, prepared)
        self.assertEqual(code, 201, saved)
        tid = saved["task_id"]
        original = PostgresPatientRegistry.append_event
        for grant, perform in (
            ("followthrough_create", lambda: self.create(qid, prepared, request_key="LATE-NEW-TASK")),
            ("followthrough_create", lambda: self.create(qid, prepared)),
            ("followthrough_update", lambda: self.record(tid, "assigned", 1)),
            ("followthrough_read", self.read),
        ):
            with self.subTest(grant=grant, command=perform):
                audited = []
                def revoke(registry, patient, kind, **details):
                    original(registry, patient, kind, **details)
                    if kind == "source.read_authorized":
                        audited.append(details["receipt_id"])
                        self.creds[0]["actions"].remove(grant)
                        self.write()
                with patch.object(PostgresPatientRegistry, "append_event", revoke):
                    self.rejected(404, perform, qid, tid)
                self.assertEqual(len(audited), 1)
                self.creds[0]["actions"].append(grant)
                self.write()
        row, = self.listing()["tasks"]
        self.assertEqual((row["task_id"], row["revision"], row["history"][0]["event_id"]),
                         (tid, 1, saved["event_id"]))
        self.assertEqual(self.record(tid, "assigned", 1)[0], 201)
