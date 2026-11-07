"""Actual HTTP/PostgreSQL acceptance for independent, fictional transcription review."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from decimal import Decimal
import json
from unittest.mock import patch

from sqlalchemy import text

from http_support import running_server
from oi_api.app import create_app
from open_intelligence.postgres_registry import PostgresPatientRegistry
import test_durable_laboratory_questions as labs
import test_followthrough_http as tasks
from test_canonical_review_flow import create_question
from test_laboratory_fhir_r4 import REPORT, SPECIMEN, resource
from test_patients import TOKEN_A, TOKEN_B, request
from test_source_versions import SourceVersionFixture


ASK = "Please verify the source transcription for this fictional observation."
ANSWER = "I checked the transcription against the two fictional originals."
BASE_GRANTS = ("patient_read", "source_read", "source_original_read", "question_read", "followthrough_read")
REVIEW_GRANTS = ("review_queue_read", "review_return")


class LaboratoryAmendmentReviewHTTPTests(SourceVersionFixture):
    scope = labs.DurableLaboratoryQuestionHTTPTests.scope
    expect = labs.DurableLaboratoryQuestionHTTPTests.expect
    prepare = labs.DurableLaboratoryQuestionHTTPTests.prepare
    import_lab = labs.DurableLaboratoryQuestionHTTPTests.import_lab
    create_task = tasks.FollowthroughHTTPTests.create_task

    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend(("composer_context_read", "question_create", "question_read",
                                         "followthrough_read", "followthrough_create"))
        self.creds[1].update(organization=self.creds[0]["organization"],
                             actions=[*BASE_GRANTS, *REVIEW_GRANTS])
        self.write()
        self.base = self.enterContext(running_server(create_app(self.settings)))
        self.patient, self.path = self.scope(self.base)
        self.creds[1]["patient_ids"] = [self.patient]
        self.write()
        self.original = self.import_lab(self.base, self.path, value=Decimal("4.20"))
        prepared, fields = self.prepare(self.base, self.path, self.original["source_id"])
        self.qid = self.expect(201, self.base, self.path + labs.LAB_HISTORY,
                               {**fields, "request_key": "AMENDMENT-BASE-QUESTION"})["question_id"]
        status, saved, _ = self.create_task(self.base, self.patient, prepared, self.qid)
        self.assertEqual(status, 201, saved)
        self.prepared = prepared
        self.tid = saved["task_id"]
        self.detail = self.path + f"/followthrough/{self.tid}/laboratory-amendment-review"
        self.inbox = self.path + "/laboratory-amendment-requests"
        self.latest = self.original

    def amend(self, state="zero"):
        # Both observations use stable FHIR references. Remove just the selected
        # one to test "not present in report" separately from a reported absence.
        bundle = json.loads(labs.two_observations(0))
        obs = resource(bundle, "Observation")
        report = resource(bundle, "DiagnosticReport")
        if state == "absent":
            del obs["valueQuantity"]
            obs["dataAbsentReason"] = {"coding": [{
                "system": "http://terminology.hl7.org/CodeSystem/data-absent-reason",
                "code": "unknown"}]}
        elif state == "missing":
            bundle["entry"] = [e for e in bundle["entry"] if e["resource"] is not obs]
            report["result"] = [r for r in report["result"] if r["reference"] != labs.OBS]
        else:
            self.assertEqual(state, "zero")
        version = self.latest["version"] + 1
        report["issued"] = f"2026-04-{4 + version:02d}T12:00:00Z"
        if state != "missing":
            obs["issued"] = report["issued"]
        self.latest = self.expect(201, self.base, self.path + "/laboratory/fhir-r4/sources", {
            "synthetic": True, "request_key": f"NEXT-LAB-V{version}", "bundle_json": json.dumps(bundle),
            "expected_previous_source_id": self.latest["source_id"]})
        return self.latest

    def command(self, key, *, answering=None, **override):
        body = {"synthetic": True, "action": "request", "request_key": key, "reason": ASK,
                "expected_latest_source_id": self.latest["source_id"],
                "expected_latest_sha256": self.latest["original_sha256"]}
        if answering is not None:
            body.update(action="respond", request_id=answering, disposition="transcription_checked", reason=ANSWER)
        return {**body, **override}

    def post(self, cmd, token=TOKEN_A):
        return request(self.base, self.detail, token=token, body=cmd)[:2]

    def history(self, token=TOKEN_A):
        result = self.expect(200, self.base, self.detail, token=token)
        self.assertEqual((result["contract"], result["patient_id"], result["case_id"], result["question_id"],
                          result["task_id"], result["observation_reference"], result["clinical_approval"]),
                         ("oi.laboratory-amendment-review/1", self.patient, labs.CASE, self.qid,
                          self.tid, labs.OBS, False))
        for key in ("bundle_json", "original_text", "valueQuantity", labs.ABSENT):
            self.assertNotIn(key, json.dumps(result))
        return result

    def pending(self):
        result = self.expect(200, self.base, self.inbox, token=TOKEN_B)
        self.assertEqual((result["contract"], result["patient_id"], result["case_id"], result["clinical_approval"]),
                         ("oi.laboratory-amendment-inbox/1", self.patient, labs.CASE, False))
        return result["requests"]

    def state(self):
        with self.engine.connect() as db:
            return tuple(db.execute(text("""
                SELECT (SELECT count(*) FROM investigation.laboratory_amendment_reviews),
                       (SELECT count(*) FROM coordination.question_followthrough_events),
                       (SELECT count(*) FROM identity.identity_domain_events)
            """)).one())

    def refusal(self, code, *, cmd=None, token=TOKEN_A, path=None):
        before = self.state()
        status, body, headers = request(self.base, path or self.detail, body=cmd, token=token)
        self.assertEqual(status, code, body)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(set(body), {"detail"})
        for secret in (self.original["original_sha256"], self.qid, self.tid, labs.OBS, ASK, ANSWER):
            self.assertNotIn(secret, json.dumps(body))
        self.assertEqual(self.state(), before, "failure must roll back entries, task changes and access/audit events")

    def test_exact_lineage_preserves_precision_zero_reported_absence_and_missing_observation(self):
        self.refusal(409)
        first = self.original
        for outcome, value, absent in (("zero", "0", None), ("absent", None, "unknown"), ("missing", None, None)):
            latest = self.amend(outcome)
            result = self.history()
            original = result["original"]
            self.assertEqual((original["source_id"], original["version"], original["sha256"]),
                             (first["source_id"], 1, first["original_sha256"]))
            self.assertEqual((result["latest"]["source_id"], result["latest"]["version"], result["latest"]["sha256"],
                              result["latest"]["document_id"]),
                             (latest["source_id"], latest["version"], latest["original_sha256"], original["document_id"]))
            row = original["observation"]
            self.assertEqual((row["value_text"], row["loinc_code"], row["status"], row["unit_code"],
                              row["specimen_reference"], row["absent_reason"]),
                             ("4.20", "777-3", "reported_value", "10*9/L", SPECIMEN, None))
            self.assertTrue(row["effective_at"] and row["issued_at"])
            change = result["latest"]["observation"]
            if outcome == "missing":
                self.assertIsNone(change)
            else:
                self.assertEqual((change["value_text"], change["absent_reason"], change["loinc_code"],
                                  change["unit_code"], change["specimen_reference"]),
                                 (value, absent, "777-3", "10*9/L" if outcome == "zero" else None, SPECIMEN))
                self.assertEqual(change["status"], "reported_value" if outcome == "zero" else "reported_absent")
                self.assertEqual(change["effective_at"], row["effective_at"])
                self.assertNotEqual(change["issued_at"], row["issued_at"])
        # A later different report in the very same case contains the original
        # reference and value; neither may be used to fill the missing reference.
        independent = labs.two_observations(7).replace(REPORT.split("/")[1], "FICTIONAL-INDEPENDENT")
        self.expect(201, self.base, self.path + "/laboratory/fhir-r4/sources", {
            "synthetic": True, "request_key": "UNRELATED-REPORT", "bundle_json": independent})
        self.assertEqual(self.history(), result)

    def test_independent_request_response_concurrency_patient_readback_and_historical_retries(self):
        second = self.amend()
        body = self.command("ASK-INDEPENDENT")
        with ThreadPoolExecutor(2) as pool:
            replies = list(pool.map(lambda _: self.post(body), range(2)))
        fresh, replay = sorted(replies, reverse=True, key=lambda item: item[0])
        self.assertEqual((fresh[0], replay[0]), (201, 200), replies)
        asked = fresh[1]
        rid = asked["request_id"]
        self.assertRegex(rid, r"^VERIFY-[0-9A-F]{32}$")
        self.assertEqual(asked, {"entry_id": rid, "request_id": rid, "duplicate": False})
        self.assertEqual(replay[1], {**asked, "duplicate": True})
        self.assertEqual(self.pending(), [{"request_id": rid, "question_id": self.qid, "task_id": self.tid,
                                          "latest_source_id": second["source_id"]}])
        self.refusal(409, cmd={**body, "reason": "A different fictional intent."})
        self.refusal(409, cmd={**body, "request_key": "SECOND-ASK-SAME-BASIS"})
        reply = self.command("RESPOND-A", answering=rid)
        self.refusal(404, cmd=reply)  # Patient has no reviewer grants.
        self.creds[0]["actions"].extend(REVIEW_GRANTS)
        self.write()
        self.refusal(404, cmd=reply)  # Even a reviewer may not answer their own request.
        for grant in REVIEW_GRANTS:
            self.creds[0]["actions"].remove(grant)
        self.write()
        options = [reply, {**reply, "request_key": "RESPOND-B", "disposition": "needs_clarification"}]
        with ThreadPoolExecutor(2) as pool:
            replies = list(pool.map(lambda command: self.post(command, TOKEN_B), options))
        self.assertEqual(sorted(status for status, _ in replies), [201, 409], replies)
        winner = next(i for i, (status, _) in enumerate(replies) if status == 201)
        answered = replies[winner][1]
        self.assertRegex(answered["entry_id"], r"^VERIFY-[0-9A-F]{32}$")
        self.assertNotEqual(answered["entry_id"], rid)
        self.assertEqual((answered["request_id"], answered["duplicate"]), (rid, False))
        self.assertEqual(self.pending(), [])
        old = self.history()["entries"]
        self.assertEqual([(e["entry_id"], e["request_id"], e["action"], e["actor"], e["reason"], e["disposition"])
                          for e in old], [(rid, rid, "request", self.creds[0]["actor"], ASK, None),
                          (answered["entry_id"], rid, "respond", self.creds[1]["actor"], ANSWER, options[winner]["disposition"])])
        self.assertTrue(all(e["recorded_at"] and e["original_source_id"] == self.original["source_id"]
                            and e["latest_source_id"] == second["source_id"]
                            and e["latest_sha256"] == second["original_sha256"] for e in old))
        self.amend("absent")
        self.assertEqual(self.history()["entries"], old)
        self.assertEqual(self.post(body), (200, {**asked, "duplicate": True}))
        self.assertEqual(self.post(options[winner], TOKEN_B), (200, {**answered, "duplicate": True}))
        self.refusal(409, cmd={**options[winner], "reason": "Changed reviewer command."}, token=TOKEN_B)
        self.assertEqual(self.state()[:2], (2, 1))
        with self.engine.connect() as db:
            events = db.execute(text("""SELECT event_type,metadata_json FROM identity.identity_domain_events
                WHERE event_type IN ('investigation.laboratory_amendment.requested',
                                     'investigation.laboratory_amendment.responded') ORDER BY id""")).all()
        self.assertEqual([e[0] for e in events], ["investigation.laboratory_amendment.requested",
                                                 "investigation.laboratory_amendment.responded"])
        for _, metadata in events:
            for private in (ASK, ANSWER, "value_text"):
                self.assertNotIn(private, json.dumps(metadata))

    def test_further_amendment_cannot_retarget_an_unanswered_request(self):
        self.amend()
        body = self.command("ASK-OLD")
        asked = self.expect(201, self.base, self.detail, body)
        original_inbox = self.pending()
        stale = self.command("ANSWER-OLD", answering=asked["request_id"])
        self.amend("missing")
        self.assertEqual(self.pending(), original_inbox)
        self.refusal(409, cmd=stale, token=TOKEN_B)
        self.refusal(409, cmd=self.command("NEW-BASIS-OLD-REQUEST", answering=asked["request_id"]), token=TOKEN_B)
        self.assertEqual(self.post(body), (200, {**asked, "duplicate": True}))
        refreshed = self.expect(201, self.base, self.detail, self.command("ASK-NEW"))
        self.assertNotEqual(refreshed["request_id"], asked["request_id"])
        self.assertEqual({r["request_id"] for r in self.pending()}, {asked["request_id"], refreshed["request_id"]})
        self.assertIsNone(self.history()["latest"]["observation"])

    def test_independent_grants_forged_basis_wrong_scope_and_revoked_replays(self):
        status, other_task, _ = self.create_task(self.base, self.patient, self.prepared, self.qid,
                                                 request_key="SECOND-LAB-TASK")
        self.assertEqual(status, 201, other_task)
        self.amend()
        body = self.command("SCOPED-ASK")
        self.refusal(404, path=self.inbox)
        self.refusal(404, cmd=body, token=TOKEN_B)
        self.refusal(422, cmd={**body, "actor": self.creds[1]["actor"]})
        self.refusal(409, cmd={**body, "expected_latest_source_id": self.original["source_id"]})
        self.refusal(409, cmd={**body, "expected_latest_sha256": self.original["original_sha256"]})
        asked = self.expect(201, self.base, self.detail, body)
        reply = self.command("SCOPED-ANSWER", answering=asked["request_id"])
        self.refusal(404, cmd={**reply, "request_id": "VERIFY-" + "F"*32}, token=TOKEN_B)
        self.refusal(404, path=self.detail.replace(self.tid, other_task["task_id"]), cmd=reply, token=TOKEN_B)
        self.expect(201, self.base, f"/v1/patients/{self.patient}/case-bindings", {
            "synthetic": True, "case_id": "CASE-OTHER", "source_organization": "ORG-OTHER",
            "source_system": "SYS-OTHER", "source_subject_ref": "OTHER-FICTIONAL-SUBJECT",
            "review_ref": "REVIEW-OTHER"})
        other = self.detail.replace(labs.CASE, "CASE-OTHER")
        self.refusal(404, path=other)
        self.refusal(404, path=other, cmd=body)
        self.refusal(404, path=other, cmd=reply, token=TOKEN_B)
        self.assertEqual(self.expect(200, self.base, self.inbox.replace(labs.CASE, "CASE-OTHER"),
                                     token=TOKEN_B)["requests"], [])
        self.assertEqual([r["request_id"] for r in self.pending()], [asked["request_id"]])
        self.expect(201, self.base, self.detail, reply, TOKEN_B)
        # A real text task is still ineligible even when the actor can read its case sources.
        status, text_source, _ = self.ingest(self.base, self.patient)
        self.assertEqual(status, 201, text_source)
        text_id, _ = create_question(self, self.base, self.patient, text_source["source_id"])
        text_row, = self.expect(200, self.base, self.path + "/questions")["questions"]
        status, text_task, _ = self.create_task(self.base, self.patient, text_row, text_id,
                                                request_key="TEXT-TASK-LAB-BOUNDARY")
        self.assertEqual(status, 201, text_task)
        self.refusal(404, path=self.detail.replace(self.tid, text_task["task_id"]))
        for index, token, cmd, grants in ((0, TOKEN_A, body, (*BASE_GRANTS, "followthrough_create")),
                                         (1, TOKEN_B, reply, (*BASE_GRANTS, *REVIEW_GRANTS))):
            for grant in grants:
                with self.subTest(actor=index, missing=grant):
                    self.creds[index]["actions"].remove(grant)
                    self.write()
                    self.refusal(404, cmd=cmd, token=token)
                    if grant in BASE_GRANTS:
                        self.refusal(404, token=token)
                    if index == 1 and grant not in ("review_return",):
                        self.refusal(404, path=self.inbox, token=token)
                    self.creds[index]["actions"].append(grant)
                    self.write()
        self.expect(200, self.base, f"/v1/patients/{self.patient}/case-bindings/{labs.CASE}/revoke",
                    {"synthetic": True, "reason": "Withdraw this fictional laboratory case."})
        self.refusal(404, cmd=body)
        self.refusal(404, cmd=reply, token=TOKEN_B)
        self.refusal(404)
        self.refusal(404, path=self.inbox, token=TOKEN_B)

    def test_authority_loss_after_source_audit_rolls_back_both_commands_and_reads(self):
        self.amend()
        write_event = PostgresPatientRegistry.append_event

        def late(index, grant, *, token, cmd=None, path=None):
            seen = []
            def revoke(registry, patient, event, **fields):
                write_event(registry, patient, event, **fields)
                if event == "source.read_authorized":
                    self.creds[index]["actions"].remove(grant)
                    self.write()
                    seen.append(event)
            with patch.object(PostgresPatientRegistry, "append_event", revoke):
                self.refusal(404, token=token, cmd=cmd, path=path)
            self.assertEqual(seen, ["source.read_authorized"])
            self.creds[index]["actions"].append(grant)
            self.write()
        ask = self.command("LATE-ASK")
        late(0, "followthrough_create", token=TOKEN_A, cmd=ask)
        asked = self.expect(201, self.base, self.detail, ask)
        reply = self.command("LATE-ANSWER", answering=asked["request_id"])
        late(1, "review_return", token=TOKEN_B, cmd=reply)
        late(1, "review_queue_read", token=TOKEN_B, path=self.inbox)
        late(0, "source_original_read", token=TOKEN_A)
        self.assertEqual(self.state()[:2], (1, 1))
        self.expect(201, self.base, self.detail, reply, TOKEN_B)
        self.assertEqual(self.state()[:2], (2, 1))

    def test_persisted_reviewer_grant_is_required_and_revocation_blocks_even_an_exact_retry(self):
        self.amend()
        self.creds[0]["actions"].extend((*REVIEW_GRANTS, "patient_permissions_read", "patient_permissions_manage"))
        self.write()
        self.base = self.enterContext(running_server(create_app(replace(self.settings, require_persisted_grants=True))))
        permissions = f"/v1/patients/{self.patient}/permissions"

        def grant(key, actor, actions):
            return self.expect(200, self.base, permissions, {
                "synthetic": True, "request_key": key, "authority_ref": "FICTIONAL-AMENDMENT-AUTHORITY",
                "actor": actor, "purpose": "operations", "actions": list(actions), "relationship": "care_team",
                "expires_at": self.creds[0]["expires_at"]})

        body = self.command("PERSISTED-ASK")
        self.refusal(404, cmd=body)
        grant("GRANT-ASKER", self.creds[0]["actor"], (*BASE_GRANTS, "followthrough_create"))
        asked = self.expect(201, self.base, self.detail, body)
        self.refusal(404, path=self.inbox, token=TOKEN_B)
        grant("GRANT-READER", self.creds[1]["actor"], (*BASE_GRANTS, "review_queue_read"))
        self.assertEqual(self.pending()[0]["request_id"], asked["request_id"])
        answer = self.command("PERSISTED-ANSWER", answering=asked["request_id"])
        self.refusal(404, cmd=answer, token=TOKEN_B)
        response_grant = grant("GRANT-RESPONDER", self.creds[1]["actor"], ("review_return",))
        saved = self.expect(201, self.base, self.detail, answer, TOKEN_B)
        self.expect(200, self.base, permissions + f"/{response_grant['grant_id']}/revocations", {
            "synthetic": True, "request_key": "REVOKE-RESPONDER", "authority_ref": "FICTIONAL-AUTHORITY-WITHDRAWN",
            "expected_revision": 1})
        self.refusal(404, cmd=answer, token=TOKEN_B)
        self.assertEqual(self.history()["entries"][-1]["entry_id"], saved["entry_id"])
        self.assertEqual(self.pending(), [])
        self.assertEqual(self.state()[:2], (2, 1))
