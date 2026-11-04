"""Question-bound operational follow-through through the actual H1 HTTP boundary.

Original synthetic fixtures only. Completion records attributed work, never a
clinical approval. PostgreSQL cases use the existing disposable owner fixture.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import unittest
from unittest.mock import patch

from sqlalchemy import text

from http_support import running_server
from oi_api.app import create_app
from oi_api.config import Settings
from oi_api.request_limits import PatientRequestLimit
from test_patients import TOKEN_A, TOKEN_B, request
from test_source_versions import SourceVersionFixture, AMENDED
import test_source_questions as question_fixtures

TITLE = "Gather questions for the next visit"
REASON = "Record the agreed next preparation step."
PREFIX = "/v1/patients/PAT-FICTION/cases/CASE-ALPHA"


class FollowthroughBoundaryTests(unittest.TestCase):
    def test_followthrough_routes_require_authentication_without_a_database(self):
        with running_server(create_app(Settings.from_env({}))) as base:
            for path, body in (
                (PREFIX + "/followthrough", None),
                (PREFIX + "/questions/QUESTION-FICTION/followthrough", {}),
                (PREFIX + "/followthrough/TASK-FICTION/transitions", {}),
            ):
                with self.subTest(path=path):
                    code, data, headers = request(base, path, body=body)
                    self.assertEqual(code, 401)
                    self.assertNotIn("TASK-", json.dumps(data))
                    self.assertEqual(headers.get("Cache-Control"), "no-store")

    def test_both_commands_bound_declared_and_chunked_bodies_before_parsing(self):
        async def exercise(route, declared):
            sent = []
            async def downstream(scope, receive, send):
                sent.append("unbounded")
            chunks = iter([
                {"type": "http.request", "body": b"x" * 8000, "more_body": True},
                {"type": "http.request", "body": b"x" * 8000, "more_body": True},
                {"type": "http.request", "body": b"x" * 1000, "more_body": False},
            ])
            async def receive():
                return next(chunks)
            async def send(message):
                sent.append(message)
            await PatientRequestLimit(downstream)({
                "type": "http", "method": "POST", "path": route,
                "headers": [(b"content-length", b"17000")] if declared else [],
            }, receive, send)
            self.assertNotIn("unbounded", sent)
            self.assertEqual(sent[0]["status"], 413)
            self.assertEqual(json.loads(sent[1]["body"]), {"detail": "Request body too large"})
        for route in (PREFIX + "/questions/QUESTION-FICTION/followthrough",
                      PREFIX + "/followthrough/TASK-FICTION/transitions"):
            for declared in (True, False):
                with self.subTest(route=route, declared=declared):
                    asyncio.run(exercise(route, declared))


class FollowthroughHTTPTests(SourceVersionFixture):
    world = question_fixtures.SourceQuestionHTTPTests.world
    model_path = staticmethod(question_fixtures.SourceQuestionHTTPTests.model_path)
    path = staticmethod(question_fixtures.SourceQuestionHTTPTests.path)
    preflight = question_fixtures.SourceQuestionHTTPTests.preflight
    prepared = question_fixtures.SourceQuestionHTTPTests.prepared
    save = question_fixtures.SourceQuestionHTTPTests.save

    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend([
            "composer_context_read", "question_create", "question_read",
            "followthrough_read", "followthrough_create", "followthrough_update",
        ])
        self.write()

    @staticmethod
    def task_path(patient, case="CASE-ALPHA"):
        return f"/v1/patients/{patient}/cases/{case}/followthrough"

    def question(self, base):
        patient = self.setup_case(base)
        source = self.ingest(base, patient)[1]["source_id"]
        preflight = self.prepared(base, patient, source)
        code, result, _ = self.save(base, patient, preflight)
        self.assertEqual(code, 201)
        return patient, source, preflight, result["question_id"]

    def create_task(self, base, patient, preflight, question_id, *,
                    case="CASE-ALPHA", token=TOKEN_A, **overrides):
        body = {
            "synthetic": True, "request_key": "TASK-CREATE-ONE", "title": TITLE,
            "detail": "Bring the previous source and the unresolved question.",
            "owner_label": "Fictional coordinator", "due_date": "2026-01-01",
            "review_trigger": "When the amended source becomes available", "reason": REASON,
            "source_snapshot_contract": "oi.pg-source-world-model/1",
            "expected_source_snapshot_sha256": preflight["source_snapshot_sha256"],
            "expected_preflight_sha256": preflight["preflight_sha256"],
        }
        body.update(overrides)
        return request(base, f"/v1/patients/{patient}/cases/{case}/questions/"
                       f"{question_id}/followthrough", token=token, body=body)

    def tasks(self, base, patient, *, case="CASE-ALPHA", token=TOKEN_A):
        return request(base, self.task_path(patient, case), token=token)

    def transition(self, base, patient, task, status, revision, *,
                   case="CASE-ALPHA", token=TOKEN_A, **overrides):
        key_status = status.upper() if isinstance(status, str) else "INVALID"
        body = {"synthetic": True, "request_key": f"TASK-{key_status}-{revision}",
                "expected_revision": revision, "status": status,
                "owner_label": "Fictional coordinator" if status == "assigned" else "",
                "reason": "Record the next agreed operational status."}
        body.update(overrides)
        return request(base, self.task_path(patient, case) + f"/{task}/transitions",
                       token=token, body=body)

    def counts(self):
        with self.engine.connect() as connection:
            return tuple(connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
                         for table in ("coordination.question_followthrough_tasks",
                                       "coordination.question_followthrough_events",
                                       "identity.identity_domain_events"))

    def test_actual_lifecycle_idempotency_source_anchor_and_restart(self):
        with running_server(create_app(self.settings)) as base:
            patient, source, preflight, qid = self.question(base)
            status, created, _ = self.create_task(base, patient, preflight, qid)
            self.assertEqual((status, created["revision"], created["duplicate"]), (201, 1, False))
            task_id = created["task_id"]
            self.assertEqual(self.create_task(base, patient, preflight, qid)[1], {**created, "duplicate": True})
            self.assertEqual(self.transition(base, patient, task_id, "completed", 1)[0], 409)
            for revision, status in enumerate(("assigned", "acknowledged", "completed"), 1):
                code, receipt, _ = self.transition(base, patient, task_id, status, revision)
                self.assertEqual((code, receipt["revision"]), (201, revision + 1))
                self.assertEqual(self.transition(base, patient, task_id, status, revision)[1],
                                 {**receipt, "duplicate": True})
            code, listing, headers = self.tasks(base, patient)
            self.assertEqual(code, 200)
            self.assertEqual(headers.get("Cache-Control"), "no-store")
            task = listing["tasks"][0]
            self.assertEqual((task["task_id"], task["question_id"], task["source_id"]), (task_id, qid, source))
            self.assertEqual((task["source_version"], task["source_line"]), (1, 8))
            self.assertEqual(task["source_sha256"], preflight["selected_source"]["sha256"])
            self.assertEqual((task["status"], task["revision"]), ("completed", 4))
            self.assertEqual([e["status"] for e in task["history"]],
                             ["created", "assigned", "acknowledged", "completed"])
            self.assertTrue(all(e["actor_label"] == "ACTOR-ALPHA" for e in task["history"]))
            self.assertFalse(task["is_overdue"])
            self.assertFalse(task["clinical_approval"])
            self.assertFalse(listing["external_notification_sent"])
            self.assertEqual(self.transition(base, patient, task_id, "assigned", 4)[0], 409)
        with running_server(create_app(self.settings)) as restarted:
            saved = self.tasks(restarted, patient)[1]["tasks"][0]
            self.assertEqual(saved["history"], task["history"])

    def test_amendment_flags_open_work_and_retains_completed_deferred_history(self):
        with running_server(create_app(self.settings)) as base:
            patient, source, preflight, qid = self.question(base)
            ids = [self.create_task(base, patient, preflight, qid,
                                   request_key=f"TASK-CREATE-{i}")[1]["task_id"] for i in range(3)]
            for revision, status in enumerate(("assigned", "acknowledged", "completed"), 1):
                self.assertEqual(self.transition(base, patient, ids[1], status, revision)[0], 201)
            self.assertEqual(self.transition(base, patient, ids[2], "deferred", 1)[0], 201)
            before = {t["task_id"]: t for t in self.tasks(base, patient)[1]["tasks"]}
            self.assertEqual(self.ingest(base, patient, AMENDED)[0], 201)
            after = {t["task_id"]: t for t in self.tasks(base, patient)[1]["tasks"]}
            self.assertTrue(after[ids[0]]["needs_recheck"])
            for task_id in ids:
                self.assertEqual(after[task_id]["source_id"], source)
                self.assertEqual(after[task_id]["history"], before[task_id]["history"])
                self.assertEqual(after[task_id]["source_context_state"], "source_reassessment_required")
            self.assertFalse(after[ids[1]]["needs_recheck"])
            self.assertFalse(after[ids[2]]["needs_recheck"])
            self.assertEqual(self.create_task(base, patient, preflight, qid, request_key="AFTER-AMENDMENT")[0], 409)
            self.assertEqual(self.create_task(base, patient, preflight, qid, request_key="TASK-CREATE-0")[0], 200)

    def test_independent_grants_wrong_patient_case_question_and_changed_intent(self):
        with running_server(create_app(self.settings)) as base:
            patient, _, preflight, qid = self.question(base)
            task_id = self.create_task(base, patient, preflight, qid)[1]["task_id"]
            self.assertEqual(self.create_task(base, patient, preflight, qid, title="Changed intent")[0], 409)
            for action, perform in (
                ("followthrough_read", lambda: self.tasks(base, patient)),
                ("followthrough_create", lambda: self.create_task(base, patient, preflight, qid)),
                ("followthrough_update", lambda: self.transition(base, patient, task_id, "assigned", 1)),
            ):
                self.creds[0]["actions"].remove(action)
                self.write()
                before = self.counts()
                self.assertEqual(perform()[0], 404)
                self.assertEqual(self.counts(), before)
                self.creds[0]["actions"].append(action)
                self.write()
            for overrides in ({"token": TOKEN_B}, {"case": "CASE-BETA"}):
                before = self.counts()
                self.assertEqual(self.tasks(base, patient, **overrides)[0], 404)
                self.assertEqual(self.create_task(base, patient, preflight, qid, **overrides)[0], 404)
                self.assertEqual(self.transition(base, patient, task_id, "assigned", 1, **overrides)[0], 404)
                self.assertEqual(self.counts(), before)
            self.assertEqual(self.create_task(base, patient, preflight,
                "QUESTION-" + "A" * 32, request_key="UNKNOWN-QUESTION")[0], 404)

    def test_bad_input_and_concurrent_replays_do_not_skip_acknowledgement(self):
        with running_server(create_app(self.settings)) as base:
            patient, _, preflight, qid = self.question(base)
            for bad in ({"title": "x"}, {"due_date": None, "review_trigger": ""},
                        {"reason": "bad\u202etext"}, {"due_date": "2026-02-30"},
                        {"owner_label": "first\nsecond"}):
                with self.subTest(bad=bad):
                    before = self.counts()
                    self.assertEqual(self.create_task(base, patient, preflight, qid, **bad)[0], 422)
                    self.assertEqual(self.counts(), before)
            with ThreadPoolExecutor(max_workers=2) as pool:
                created = list(pool.map(lambda _: self.create_task(base, patient, preflight, qid), range(2)))
            self.assertEqual(sorted(r[0] for r in created), [200, 201])
            self.assertEqual(len({r[1]["task_id"] for r in created}), 1)
            tid = created[0][1]["task_id"]
            for bad in ({"status": []}, {"expected_revision": True}, {"owner_label": ""}):
                before = self.counts()
                values = {"status": "assigned", "revision": 1, **bad}
                self.assertEqual(self.transition(base, patient, tid, **values)[0], 422)
                self.assertEqual(self.counts(), before)
            with ThreadPoolExecutor(max_workers=2) as pool:
                assigned = list(pool.map(lambda _: self.transition(base, patient, tid, "assigned", 1), range(2)))
            self.assertEqual(sorted(r[0] for r in assigned), [200, 201])
            self.assertEqual(len({r[1]["event_id"] for r in assigned}), 1)
            self.assertEqual(self.transition(base, patient, tid, "deferred", 1,
                                            request_key="STALE-REVISION")[0], 409)

    def test_actual_encoding_revocation_and_failure_roll_back_task_and_audit(self):
        from oi_api import followthrough_routes
        with running_server(create_app(self.settings)) as base:
            patient, _, preflight, qid = self.question(base)
            render = followthrough_routes.JSONResponse.render
            def revoke(response, content):
                body = render(response, content)
                if isinstance(content, dict) and "task_id" in content:
                    self.creds[0]["actions"].remove("followthrough_create")
                    self.write()
                return body
            before = self.counts()
            with patch.object(followthrough_routes.JSONResponse, "render", revoke):
                result = self.create_task(base, patient, preflight, qid)
            self.assertEqual(result[0], 404)
            self.assertNotIn(TITLE, json.dumps(result[1]))
            self.assertEqual(self.counts(), before)
            self.creds[0]["actions"].append("followthrough_create")
            self.write()
            def fail_task_encoding(response, content):
                if isinstance(content, dict) and "task_id" in content:
                    raise ValueError("Injected encoder failure")
                return render(response, content)
            with patch.object(followthrough_routes.JSONResponse, "render", fail_task_encoding):
                self.assertEqual(self.create_task(base, patient, preflight, qid)[0], 503)
            self.assertEqual(self.counts(), before)

    def test_list_and_transition_refresh_authority_after_actual_serialization(self):
        from oi_api import followthrough_routes
        with running_server(create_app(self.settings)) as base:
            patient, _, preflight, qid = self.question(base)
            tid = self.create_task(base, patient, preflight, qid)[1]["task_id"]
            render = followthrough_routes.JSONResponse.render
            for action, perform in (
                ("followthrough_read", lambda: self.tasks(base, patient)),
                ("followthrough_update", lambda: self.transition(base, patient, tid, "assigned", 1)),
            ):
                def revoke(response, content):
                    body = render(response, content)
                    if isinstance(content, dict) and ("tasks" in content or "task_id" in content):
                        self.creds[0]["actions"].remove(action)
                        self.write()
                    return body
                before = self.counts()
                with patch.object(followthrough_routes.JSONResponse, "render", revoke):
                    result = perform()
                self.assertEqual(result[0], 404)
                self.assertNotIn(TITLE, json.dumps(result[1]))
                self.assertEqual(self.counts(), before)
                self.creds[0]["actions"].append(action)
                self.write()

    def test_journal_failure_rolls_back_new_task(self):
        from open_intelligence.postgres_registry import PostgresPatientRegistry
        with running_server(create_app(self.settings)) as base:
            patient, _, preflight, qid = self.question(base)
            original = PostgresPatientRegistry.append_event
            def fail(registry, patient_id, event_type, **payload):
                if event_type.startswith("coordination.followthrough."):
                    raise RuntimeError("Injected task journal failure")
                return original(registry, patient_id, event_type, **payload)
            before = self.counts()
            with patch.object(PostgresPatientRegistry, "append_event", fail):
                self.assertEqual(self.create_task(base, patient, preflight, qid)[0], 503)
            self.assertEqual(self.counts(), before)
