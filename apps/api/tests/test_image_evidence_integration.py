"""Actual PostgreSQL/HTTP acceptance across existing image and evidence owners.

Only independently authored report, DICOM and metadata fixtures are used. These
tests add no patient/evidence store and do not inherit another test suite. The
shared PostgreSQL fixture skips when its disposable PG16 database is unavailable;
such a skip is not transactional acceptance.
"""
import hashlib
import json
import unittest

from http_support import running_server
from oi_api.app import create_app
from oi_api.database import Database
from oi_api.evidence_catalog import (
    append_rights_decision, fictional_records, seed_fictional_records,
)
from open_intelligence.postgres_registry import PostgresPatientRegistry
from test_image_custody import AMENDED, REPORT, image_bytes, image_request
import test_image_question_integration as image_questions
import test_image_review_integration as image_reviews
from test_patients import TOKEN_A, TOKEN_B, request
from test_source_versions import SourceVersionFixture


ANCHORS = (
    "question_id", "patient_id", "case_id", "source_id", "source_line",
    "source_version", "source_sha256", "source_snapshot_contract",
    "source_snapshot_sha256", "preflight_sha256",
)
HISTORY_OWNERS = ("questions", "returns", "tasks", "task_events", "evidence_links")


class ImageEvidenceIntegrationHTTPTests(SourceVersionFixture):
    case_path = staticmethod(image_questions.ImageQuestionIntegrationHTTPTests.case_path)
    image_path = image_questions.ImageQuestionIntegrationHTTPTests.image_path
    read_json = image_questions.ImageQuestionIntegrationHTTPTests.read_json
    prepare_question = image_questions.ImageQuestionIntegrationHTTPTests.prepare_question
    question_intent = staticmethod(image_questions.ImageQuestionIntegrationHTTPTests.question_intent)
    save_question = image_questions.ImageQuestionIntegrationHTTPTests.save_question
    rows = image_questions.ImageQuestionIntegrationHTTPTests.rows
    queue = image_reviews.ImageReviewIntegrationHTTPTests.queue
    return_url = image_reviews.ImageReviewIntegrationHTTPTests.return_url
    return_question = image_reviews.ImageReviewIntegrationHTTPTests.return_question

    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend((
            "composer_context_read", "question_create", "question_read",
            "review_packet_read", "source_brief_export", "review_queue_read", "review_return",
            "image_import", "image_read", "image_original_read",
            "followthrough_create", "followthrough_read", "followthrough_update",
            "evidence_read", "evidence_link",
        ))
        self.write()
        database = Database(self.settings)
        try:
            with database.registry_connection() as connection:
                seed_fictional_records(
                    PostgresPatientRegistry(connection, lambda *args: False),
                    fictional_records(), recorded_by="FIXTURE-AUTHOR",
                )
        finally:
            database.close()

    def durable_state(self):
        """Full existing rows detect partial effects, including audit tails."""
        tables = {
            "sources": ("clinical_source.source_versions", "source_id"),
            "assertions": ("clinical_source.assertions", "assertion_id"),
            "images": ("clinical_source.dicom_objects", "image_id"),
            "image_links": ("clinical_source.source_image_links", "source_id,image_id"),
            "questions": ("investigation.source_questions", "question_id"),
            "returns": ("investigation.question_review_receipts", "receipt_id"),
            "tasks": ("coordination.question_followthrough_tasks", "task_id"),
            "task_events": ("coordination.question_followthrough_events", "task_id,revision"),
            "evidence_catalog": ("investigation.evidence_catalog_records", "record_id,version"),
            "evidence_rights": ("investigation.evidence_rights_decisions", "record_id,version,revision"),
            "evidence_links": ("investigation.question_evidence_links", "link_id"),
            "bindings": ("coordination.patient_case_bindings", "case_id"),
        }
        state = {name: self.rows(f"SELECT * FROM {table} ORDER BY {order}")
                 for name, (table, order) in tables.items()}
        state["events"] = self.rows(
            "SELECT id,event_type,metadata_json,patient_id,occurred_at "
            "FROM identity.identity_domain_events ORDER BY id")
        return state

    def assert_preserved(self, before, after, *, except_for=()):
        for owner in before.keys() - set(except_for):
            self.assertEqual(after[owner], before[owner], owner)

    def command(self, base, path, body):
        status, receipt, _ = request(base, path, token=TOKEN_A, body=body)
        self.assertEqual(status, 201, receipt)
        self.assertFalse(receipt["duplicate"])
        return path, body, {**receipt, "duplicate": True}

    def retry(self, base, writes):
        before = self.durable_state()
        for path, body, receipt in writes:
            self.assertEqual(request(base, path, token=TOKEN_A, body=body)[:2], (200, receipt))
        after = self.durable_state()
        self.assert_preserved(before, after, except_for={"events"})
        self.assertEqual(after["events"][:len(before["events"])], before["events"])
        added = after["events"][len(before["events"]):]
        self.assertEqual([row[1] for row in added], ["source.read_authorized"] * len(writes))
        self.assertEqual(len({row[2]["receipt_id"] for row in added}), len(writes))

    def denied(self, base, operations, *, status=404, token=TOKEN_A):
        before = self.durable_state()
        for path, body in operations:
            code, value, headers = request(base, path, token=token, body=body)
            self.assertEqual(code, status, value)
            self.assertEqual(set(value), {"detail"})
            self.assertEqual(headers.get("Cache-Control"), "no-store")
            self.assertNotIn("X-OI-Access-Receipt", headers)
        self.assertEqual(self.durable_state(), before)

    @staticmethod
    def context_intent(prepared):
        return {
            "synthetic": True, "source_snapshot_contract": prepared["source_snapshot_contract"],
            "expected_source_snapshot_sha256": prepared["source_snapshot_sha256"],
            "expected_preflight_sha256": prepared["preflight_sha256"],
        }

    def packet_and_brief(self, base, patient, question, prepared):
        path = self.case_path(patient) + "/questions/" + question
        packet = self.read_json(base, path + "/source-review-packet")
        self.assertEqual(packet["contract"], "oi.synthetic-question-source-review-packet/1")
        self.assertEqual((packet["patient_id"], packet["case_id"], packet["question_id"]),
                         (patient, "CASE-ALPHA", question))
        selected = packet["selected_statement"]
        original = prepared["selected_source"]
        self.assertEqual((selected["source_id"], selected["source_line"],
                          selected["document_version"], selected["source_sha256"]),
                         (original["source_id"], original["line"], original["version"], original["sha256"]))
        self.assertEqual(selected["source_statement"], original["statement"])
        self.assertIsNone(selected["clinical_meaning"])
        self.assertFalse(packet["medical_interpretation_performed"])
        self.assertFalse(packet["clinical_approval"])
        status, brief, _ = request(base, path + "/brief", token=TOKEN_A,
                                   body=self.context_intent(prepared))
        self.assertEqual(status, 200, brief)
        self.assertEqual(brief["contract"], "oi.synthetic-source-brief/2")
        self.assertEqual(brief["question"]["question_id"], question)
        self.assertEqual(brief["selected_source"], original)
        self.assertEqual(brief["source_snapshot_sha256"], prepared["source_snapshot_sha256"])
        self.assertEqual(brief["body_sha256"], hashlib.sha256(brief["body"].encode()).hexdigest())
        self.assertIn(original["statement"], brief["body"])
        for field in ("clinical_approval", "model_executed", "biomedical_evidence_included"):
            self.assertFalse(brief[field])
        return packet, brief

    def populate_question(self, base, patient, source, *, version=1):
        prefix = self.case_path(patient)
        world = self.read_json(base, prefix + "/world-model")
        prepared = self.prepare_question(
            base, patient, source, world, line=7 if version == 1 else 8,
            question=image_questions.QUESTION if version == 1 else image_questions.REVISED_QUESTION)
        question, question_body = self.save_question(base, patient, prepared, f"CONNECTED-QUESTION-V{version}")
        question_path = prefix + "/questions/" + question
        packet, brief = self.packet_and_brief(base, patient, question, prepared)
        item = next(row for row in self.queue(base, patient)["items"] if row["question_id"] == question)
        returned_body, returned = self.return_question(base, patient, item, f"CONNECTED-RETURN-V{version}")
        task = self.command(base, question_path + "/followthrough", {
            **self.context_intent(prepared), "request_key": f"CONNECTED-TASK-V{version}",
            "title": "Prepare the independently fictional image discussion",
            "detail": "Bring the original report, image reference and unresolved source question.",
            "owner_label": "", "due_date": None, "review_trigger": "When the source changes",
            "reason": "Record the fictional preparation step.",
        })
        task_id = task[2]["task_id"]
        transitions = []
        for revision, status in enumerate(("assigned", "acknowledged"), 1):
            transitions.append(self.command(base, prefix + f"/followthrough/{task_id}/transitions", {
                "synthetic": True, "request_key": f"CONNECTED-TASK-V{version}-REV-{revision + 1}",
                "expected_revision": revision, "status": status,
                "owner_label": "Fictional coordinator" if status == "assigned" else "",
                "reason": "Record the attributed fictional preparation status.",
            }))
        status, search, _ = request(base, question_path + "/evidence-search", token=TOKEN_A,
                                    body={"synthetic": True, "query": "continuity"})
        self.assertEqual(status, 200, search)
        self.assertFalse(search["content_appraised"])
        self.assertFalse(search["model_executed"])
        self.assertEqual(len(search["records"]), 1)
        metadata = search["records"][0]
        self.assertEqual(metadata["citation"], "FICT-RECORD-CONTINUITY@1")
        self.assertEqual(metadata["availability"], "metadata_only")
        citation = self.command(base, question_path + "/evidence-links", {
            **self.context_intent(prepared), "request_key": f"CONNECTED-EVIDENCE-V{version}",
            "citation": metadata["citation"], "expected_metadata_sha256": metadata["metadata_sha256"],
        })
        tasks = self.read_json(base, prefix + "/followthrough")
        task_row = next(row for row in tasks["tasks"] if row["task_id"] == task_id)
        question_row = next(row for row in self.read_json(base, prefix + "/questions")["questions"]
                            if row["question_id"] == question)
        self.assertEqual({key: task_row[key] for key in ANCHORS},
                         {key: question_row[key] for key in ANCHORS})
        self.assertEqual([row["status"] for row in task_row["history"]],
                         ["created", "assigned", "acknowledged"])
        self.assertEqual([row["event_id"] for row in task_row["history"]],
                         [write[2]["event_id"] for write in (task, *transitions)])
        self.assertFalse(task_row["needs_recheck"])
        self.assertFalse(tasks["clinical_approval"])
        self.assertFalse(tasks["external_notification_sent"])
        links = self.read_json(base, citation[0])["links"]
        self.assertEqual(links[0]["record"], metadata)
        writes = [(prefix + "/questions", question_body, {"question_id": question, "duplicate": True}),
                  (self.return_url(patient, question), returned_body, returned), task, *transitions, citation]
        return {"patient": patient, "source": source, "question": question, "prepared": prepared,
                "world": world, "packet": packet, "brief": brief, "task": task_row, "links": links,
                "metadata": metadata, "writes": writes, "citation": citation,
                "question_path": question_path}

    def populated_case(self, base):
        patient = self.setup_case(base)
        status, source, _ = self.ingest(base, patient, REPORT)
        self.assertEqual(status, 201, source)
        source_id = source["source_id"]
        original = self.read_json(base, self.url(patient) + "/" + source_id)
        self.assertEqual(original["original_text"], REPORT)
        self.assertEqual(original["sha256"], hashlib.sha256(REPORT.encode()).hexdigest())
        raw = image_bytes()
        status, image, _ = image_request(base, self.image_path(patient, source_id), raw=raw)
        self.assertEqual((status, image["result"]), (201, "imported"))
        self.assertEqual(image["sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(image_request(base, self.image_path(patient, source_id) + "/" + image["image_id"])[:2],
                         (200, raw))
        return self.populate_question(base, patient, source_id), image, raw

    def test_connected_lifecycle_keeps_original_anchors_across_image_activity_and_amendment(self):
        with running_server(create_app(self.settings)) as base:
            flow, image, raw = self.populated_case(base)
            patient, question, source = (flow[key] for key in ("patient", "question", "source"))
            prefix = self.case_path(patient)
            image_path = self.image_path(patient, source)
            queue = self.queue(base, patient)
            before = self.durable_state()
            second_raw = image_bytes(sop_uid="2.25.104", pixels=b"\x01\x00" * 4)
            status, second, _ = image_request(base, image_path, raw=second_raw)
            self.assertEqual((status, second["result"]), (201, "imported"))
            self.assertEqual(image_request(base, image_path, raw=raw)[:2], (200, {**image, "result": "duplicate"}))
            index = self.read_json(base, image_path)
            self.assertEqual({row["image_id"] for row in index["images"]}, {image["image_id"], second["image_id"]})
            self.assertEqual(image_request(base, image_path + "/" + second["image_id"])[:2], (200, second_raw))
            world = self.read_json(base, prefix + "/world-model")
            self.assertEqual(world["snapshot_fingerprint"], flow["world"]["snapshot_fingerprint"])
            self.assertEqual(self.prepare_question(base, patient, source, world)["preflight_sha256"],
                             flow["prepared"]["preflight_sha256"])
            packet, brief = self.packet_and_brief(base, patient, question, flow["prepared"])
            self.assertEqual(packet["packet_sha256"], flow["packet"]["packet_sha256"])
            self.assertEqual(brief["question"], flow["brief"]["question"])
            self.assertEqual(self.read_json(base, prefix + "/followthrough")["tasks"], [flow["task"]])
            self.assertEqual(self.read_json(base, flow["citation"][0])["links"], flow["links"])
            self.assertEqual(self.queue(base, patient)["items"], queue["items"])
            self.assertEqual(self.queue(base, patient)["receipts"], queue["receipts"])
            self.assert_preserved(before, self.durable_state(), except_for={"images", "image_links", "events"})

            status, amendment, _ = self.ingest(base, patient, AMENDED)
            self.assertEqual((status, amendment["version"]), (201, 2))
            current_source = amendment["source_id"]
            historical = self.durable_state()
            for owner in HISTORY_OWNERS:
                self.assertEqual(historical[owner], before[owner], owner)
            task = self.read_json(base, prefix + "/followthrough")["tasks"][0]
            self.assertEqual(task, {**flow["task"], "source_context_state": "source_reassessment_required",
                                    "needs_recheck": True})
            old_links = self.read_json(base, flow["citation"][0])
            self.assertEqual(old_links["source_context_state"], "source_reassessment_required")
            self.assertEqual(old_links["links"], flow["links"])
            old_packet = self.read_json(base, flow["question_path"] + "/source-review-packet")
            self.assertEqual(old_packet["original_anchor"]["source_id"], source)
            self.assertEqual(old_packet["source_context_state"], "source_reassessment_required")
            self.assertIsNone(old_packet["selected_statement"])
            self.assertEqual(self.queue(base, patient)["receipts"], queue["receipts"])
            # Only exact old intent is recoverable; none of these historical
            # contexts authorizes a fresh question, return, task or citation.
            stale = [(path, {**body, "request_key": body["request_key"] + "-FRESH"})
                     for path, body, _ in (flow["writes"][0], flow["writes"][1],
                                           flow["writes"][2], flow["citation"])]
            stale.append((flow["question_path"] + "/brief", self.context_intent(flow["prepared"])))
            self.denied(base, stale, status=409)
            self.retry(base, flow["writes"])
            current_path = self.image_path(patient, current_source)
            before_link = self.durable_state()
            self.assertEqual(image_request(base, image_path + "/" + image["image_id"])[0], 404)
            self.assertEqual(image_request(base, current_path + "/" + image["image_id"])[0], 404)
            self.assertEqual(self.durable_state(), before_link)
            for old, original in ((image, raw), (second, second_raw)):
                code, linked, _ = image_request(base, current_path, raw=original)
                self.assertEqual((code, linked["result"], linked["image_id"]), (201, "linked", old["image_id"]))
            self.assert_preserved(before_link, self.durable_state(), except_for={"image_links", "events"})
            self.assertEqual(self.read_json(base, prefix + "/followthrough")["tasks"], [task])
            self.assertEqual(self.read_json(base, flow["citation"][0])["links"], flow["links"])
            self.assertEqual(self.read_json(base, flow["question_path"] + "/source-review-packet")["packet_sha256"],
                             old_packet["packet_sha256"])
            self.denied(base, stale, status=409)

            fresh = self.populate_question(base, patient, current_source, version=2)
            self.assertNotEqual(fresh["question"], question)
            self.assertNotEqual(fresh["prepared"]["source_snapshot_sha256"], flow["prepared"]["source_snapshot_sha256"])
            self.assertNotEqual(fresh["writes"][1][2]["receipt_id"], flow["writes"][1][2]["receipt_id"])
            self.assertNotEqual(fresh["task"]["task_id"], task["task_id"])
            self.assertNotEqual(fresh["citation"][2]["link_id"], flow["citation"][2]["link_id"])
            current_state = self.durable_state()
            for owner in HISTORY_OWNERS:
                for row in historical[owner]:
                    self.assertIn(row, current_state[owner], owner)
            tasks = self.read_json(base, prefix + "/followthrough")["tasks"]
            final_queue = self.queue(base, patient)
            self.assertEqual(len(final_queue["receipts"]), 2)
            self.assertEqual(len(current_state["images"]), 2)
            self.assertEqual(len(current_state["image_links"]), 4)
            self.retry(base, flow["writes"] + fresh["writes"])

        with running_server(create_app(self.settings)) as restarted:
            self.assertEqual(self.read_json(restarted, prefix + "/followthrough")["tasks"], tasks)
            self.assertEqual(self.queue(restarted, patient)["receipts"], final_queue["receipts"])
            for item in (flow, fresh):
                self.assertEqual(self.read_json(restarted, item["citation"][0])["links"], item["links"])
            self.assertEqual(image_request(restarted, current_path + "/" + image["image_id"])[:2], (200, raw))
            self.assertEqual(self.read_json(restarted, self.url(patient) + "/" + source)["original_text"], REPORT)
            self.retry(restarted, flow["writes"] + fresh["writes"])

    def test_independent_grants_and_rights_revocation_preserve_other_owner_history(self):
        with running_server(create_app(self.settings)) as base:
            flow, image, raw = self.populated_case(base)
            patient = flow["patient"]
            prefix = self.case_path(patient)
            image_path = self.image_path(patient, flow["source"])
            all_actions = list(self.creds[0]["actions"])
            self.creds[0]["actions"] = [action for action in all_actions if not action.startswith("image_")]
            self.write()
            before = self.durable_state()
            for path, original in ((image_path, None), (image_path, raw),
                                   (image_path + "/" + image["image_id"], None)):
                self.assertEqual(image_request(base, path, raw=original)[0], 404)
            self.assertEqual(self.durable_state(), before)
            self.assertEqual(self.read_json(base, prefix + "/followthrough")["tasks"], [flow["task"]])
            self.assertEqual(self.read_json(base, flow["citation"][0])["links"], flow["links"])
            for missing, denied_operations in (
                ("followthrough_read", [(prefix + "/followthrough", None)]),
                ("followthrough_create", [flow["writes"][2][:2]]),
                ("followthrough_update", [flow["writes"][3][:2]]),
                ("evidence_read", [(flow["citation"][0], None), flow["citation"][:2],
                                   (flow["question_path"] + "/evidence-search", {"synthetic": True, "query": "continuity"})]),
                ("evidence_link", [flow["citation"][:2]]),
            ):
                with self.subTest(missing=missing):
                    self.creds[0]["actions"] = [action for action in all_actions if action != missing]
                    self.write()
                    self.denied(base, denied_operations)
                    self.assertEqual(image_request(base, image_path + "/" + image["image_id"])[:2], (200, raw))
                    if missing.startswith("evidence_"):
                        self.assertEqual(self.read_json(base, prefix + "/followthrough")["tasks"], [flow["task"]])
                    else:
                        self.assertEqual(self.read_json(base, flow["citation"][0])["links"], flow["links"])
            self.creds[0]["actions"] = list(all_actions)
            self.write()
            self.denied(base, [(prefix + "/followthrough", None), (flow["citation"][0], None)], token=TOKEN_B)

            before = self.durable_state()
            database = Database(self.settings)
            try:
                with database.registry_connection() as connection:
                    append_rights_decision(
                        PostgresPatientRegistry(connection, lambda *args: False),
                        "FICT-RECORD-CONTINUITY", "1",
                        permissions={"metadata": {"store": "allowed", "display": "allowed"}},
                        revoked=True, superseded=False, recorded_by="FIXTURE-REVIEWER",
                        reason="Withdraw the independently fictional metadata display rights",
                    )
            finally:
                database.close()
            self.assert_preserved(before, self.durable_state(), except_for={"evidence_rights"})
            self.assertEqual(len(self.durable_state()["evidence_rights"]), len(before["evidence_rights"]) + 1)
            redacted = self.read_json(base, flow["citation"][0])
            self.assertEqual(redacted["links"], [{**flow["links"][0], "status": "rights_restricted", "record": None}])
            for restricted in (flow["metadata"]["title"], flow["metadata"]["link"]):
                self.assertNotIn(restricted, json.dumps(redacted))
            status, search, _ = request(base, flow["question_path"] + "/evidence-search", token=TOKEN_A,
                                        body={"synthetic": True, "query": "continuity"})
            self.assertEqual((status, search["records"]), (200, []))
            self.denied(base, [(flow["citation"][0], {**flow["citation"][1], "request_key": "NEW-REVOKED-CITATION"})])
            self.retry(base, flow["writes"])
            self.assertEqual(self.read_json(base, prefix + "/followthrough")["tasks"], [flow["task"]])
            self.assertEqual(image_request(base, image_path + "/" + image["image_id"])[:2], (200, raw))
            self.creds[0]["actions"].remove("image_original_read")
            self.write()
            before = self.durable_state()
            self.assertEqual(image_request(base, image_path + "/" + image["image_id"])[0], 404)
            self.assertEqual(self.durable_state(), before)
            self.assertEqual(self.read_json(base, flow["citation"][0])["links"], redacted["links"])
            self.creds[0]["actions"] = list(all_actions)
            self.write()

            status, revoked, _ = request(base, f"/v1/patients/{patient}/case-bindings/CASE-ALPHA/revoke",
                                         token=TOKEN_A, body={"synthetic": True, "reason": "Withdraw the fictional combined case binding"})
            self.assertEqual((status, revoked["duplicate"]), (200, False))
            operations = [(prefix + "/followthrough", None), (flow["citation"][0], None),
                          (flow["question_path"] + "/source-review-packet", None),
                          (flow["question_path"] + "/brief", self.context_intent(flow["prepared"])),
                          (flow["question_path"] + "/evidence-search", {"synthetic": True, "query": "continuity"})]
            operations.extend((path, body) for path, body, _ in flow["writes"])
            self.denied(base, operations)
            before = self.durable_state()
            self.assertEqual(image_request(base, image_path, raw=raw)[0], 404)
            self.assertEqual(image_request(base, image_path + "/" + image["image_id"])[0], 404)
            self.assertEqual(self.durable_state(), before)

    def test_real_failed_image_audit_rolls_back_relink_without_touching_committed_history(self):
        with running_server(create_app(self.settings)) as base:
            flow, image, raw = self.populated_case(base)
            status, amendment, _ = self.ingest(base, flow["patient"], AMENDED)
            self.assertEqual(status, 201, amendment)
            path = self.image_path(flow["patient"], amendment["source_id"])
            before = self.durable_state()
            with self.engine.begin() as connection:
                connection.exec_driver_sql("""
                    CREATE FUNCTION identity.reject_connected_image_link() RETURNS trigger
                    LANGUAGE plpgsql AS $$ BEGIN
                        IF NEW.event_type='image.source_linked' THEN
                            RAISE EXCEPTION 'INDEPENDENT-FICTIONAL-IMAGE-LINK-FAILURE';
                        END IF;
                        RETURN NEW;
                    END; $$;
                    CREATE TRIGGER reject_connected_image_link
                    BEFORE INSERT ON identity.identity_domain_events
                    FOR EACH ROW EXECUTE FUNCTION identity.reject_connected_image_link();
                """)
            try:
                self.assertEqual(image_request(base, path, raw=raw)[:2],
                                 (503, {"detail": "Patient registry unavailable"}))
                self.assertEqual(self.durable_state(), before)
                self.retry(base, flow["writes"])
                after_retry = self.durable_state()
                for owner in HISTORY_OWNERS:
                    self.assertEqual(after_retry[owner], before[owner], owner)
            finally:
                with self.engine.begin() as connection:
                    connection.exec_driver_sql("DROP TRIGGER reject_connected_image_link ON identity.identity_domain_events")
                    connection.exec_driver_sql("DROP FUNCTION identity.reject_connected_image_link()")
            before_retry = self.durable_state()
            status, linked, _ = image_request(base, path, raw=raw)
            self.assertEqual((status, linked["result"], linked["image_id"]), (201, "linked", image["image_id"]))
            self.assert_preserved(before_retry, self.durable_state(), except_for={"image_links", "events"})
            self.assertEqual(image_request(base, path + "/" + image["image_id"])[:2], (200, raw))
            task = self.read_json(base, self.case_path(flow["patient"]) + "/followthrough")["tasks"][0]
            self.assertEqual(task["history"], flow["task"]["history"])
            self.assertTrue(task["needs_recheck"])
            self.assertEqual(self.read_json(base, flow["citation"][0])["links"], flow["links"])


if __name__ == "__main__":
    unittest.main()
