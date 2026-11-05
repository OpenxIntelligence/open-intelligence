"""Human returns of executed, source-verified briefs with current supporting evidence."""
import unittest

from sqlalchemy import text

from http_support import running_server
from oi_api.app import create_app
from oi_api.authored_evidence_contracts import ReturnEvidenceRun
from oi_api.worker import run_once
from test_authored_evidence_authority import observe_evidence_encoding
from test_authored_evidence_postgres import EvidenceFixture, evidence_text
from test_patients import TOKEN_A, request


class EvidenceRunContractTests(unittest.TestCase):
    def test_route_and_handoff_require_all_three_exact_fingerprints(self):
        path = ("/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}"
                "/evidence-reports/{report_id}/runs/{run_id}/return-for-verification")
        operation = create_app().openapi()["paths"][path]["post"]
        self.assertEqual(operation["security"], [{"SyntheticFixture": []}])
        body = dict(synthetic=True, request_key="RETURN-ONE", reason="Compare these fictional references again.",
                    expected_result_sha256="a"*64, expected_report_snapshot_sha256="b"*64,
                    expected_queue_fingerprint="c"*64)
        ReturnEvidenceRun(**body)
        for field in ("expected_result_sha256", "expected_report_snapshot_sha256", "expected_queue_fingerprint"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                ReturnEvidenceRun(**{key: value for key, value in body.items() if key != field})


class EvidenceRunReviewTests(EvidenceFixture):
    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend(("source_brief_export", "review_queue_read", "review_return"))
        self.write()

    def inputs(self, base, *, work=True):
        state = self.support_report(base)
        patient, question = state["patient"], state["question"]
        source = state["prepared"]["snapshot"]["question"]
        path = self.prefix(patient, question)
        queue_path = f"/v1/patients/{patient}/cases/CASE-ALPHA/review-queue"
        queue = request(base, queue_path, token=TOKEN_A)[1]
        code, receipt, _ = request(base, path + "/runs", token=TOKEN_A, body=dict(
            synthetic=True, request_key="RUN-ONE", source_snapshot_contract=source["source_snapshot_contract"],
            expected_source_snapshot_sha256=source["source_snapshot_sha256"],
            expected_preflight_sha256=source["preflight_sha256"]))
        self.assertEqual(code, 201, receipt)
        run_id = receipt["run"]["run_id"]
        digest = "0"*64
        if work:
            self.assertEqual(run_once(self.settings, lambda: TOKEN_A, patient, "CASE-ALPHA")["status"], "completed")
            code, result, _ = request(base, path + "/runs/" + run_id + "/result", token=TOKEN_A)
            self.assertEqual(code, 200, result)
            digest = result["result_sha256"]
        command = dict(synthetic=True, request_key="RETURN-COMPARISON", reason="Please independently verify this fictional comparison.",
                       expected_queue_fingerprint=queue["items"][0]["queue_fingerprint"],
                       expected_result_sha256=digest, expected_report_snapshot_sha256=state["prepared"]["snapshot_sha256"])
        route = f'{path}/evidence-reports/{state["report_id"]}/runs/{run_id}/return-for-verification'
        return state, run_id, command, route, queue_path

    def test_completed_run_is_bound_to_the_existing_inbox_and_retries_once(self):
        with running_server(create_app(self.settings)) as base:
            state, run_id, command, route, queue = self.inputs(base)
            def send(**changes):
                return request(base, route, token=TOKEN_A, body={**command, **changes})
            for field in ("expected_result_sha256", "expected_report_snapshot_sha256", "expected_queue_fingerprint"):
                with self.subTest(field=field):
                    self.assertEqual(send(**{field: "f"*64})[0], 409)
            code, receipt, _ = send()
            self.assertEqual(code, 201, receipt)
            self.assertEqual(receipt["verification"], "matched_current_source_and_evidence")
            self.assertFalse(receipt["clinical_approval"])
            code, retry, _ = send()
            self.assertEqual((code, retry), (200, {**receipt, "duplicate": True}))
            self.assertEqual(send(reason="A different reason is a different intent.")[0], 409)
            item = request(base, queue, token=TOKEN_A)[1]["items"][0]
            self.assertEqual((item["review_state"], item["current_return_receipt_id"], item["return_count"]),
                             ("returned_for_independent_verification", receipt["receipt_id"], 1))
            with self.engine.connect() as conn:
                (event,) = conn.execute(text("SELECT metadata_json FROM identity.identity_domain_events "
                                            "WHERE event_type='investigation.review.returned_for_verification'")).scalars()
            self.assertEqual((event["run_id"], event["result_sha256"], event["report_id"], event["report_snapshot_sha256"]),
                             (run_id, command["expected_result_sha256"], state["report_id"], command["expected_report_snapshot_sha256"]))
            self.assertEqual(event["attempt"], 1)

    def test_pending_denied_changed_and_withdrawn_inputs_cannot_create_a_return(self):
        with running_server(create_app(self.settings)) as base:
            state, _, command, route, queue = self.inputs(base, work=False)
            send = lambda: request(base, route, token=TOKEN_A, body=command)
            self.assertEqual(send()[0], 409)
            patient, question = state["patient"], state["question"]
            run_once(self.settings, lambda: TOKEN_A, patient, "CASE-ALPHA")
            run_url = route.split("/evidence-reports", 1)[0] + "/runs/" + route.split("/runs/")[1].split("/")[0]
            command["expected_result_sha256"] = request(base, run_url, token=TOKEN_A)[1]["result_sha256"]
            for action in ("source_brief_export", "review_return", "review_queue_read", "evidence_report_export",
                           "authored_evidence_read"):
                with self.subTest(action=action):
                    self.creds[0]["actions"].remove(action)
                    self.write()
                    self.assert_denied(send())
                    self.creds[0]["actions"].append(action)
                    self.write()
            def revoke_after_encoding(_):
                self.creds[0]["actions"].remove("review_return")
                self.write()
            with observe_evidence_encoding(lambda value: "report_snapshot_sha256" in value and "receipt_id" in value,
                                          revoke_after_encoding):
                self.assert_denied(send())
            self.creds[0]["actions"].append("review_return")
            self.write()
            status, revised, _ = self.imported(base, patient, question, key="IMPORT-AMEND",
                raw=evidence_text(amends=1))
            self.assertEqual(status, 201, revised)
            self.assertEqual(send()[0], 409)
            self.assertEqual(self.withdrawn(base, patient, question, revised["evidence_id"])[0], 201)
            self.assert_denied(send())
            self.assertEqual(request(base, queue, token=TOKEN_A)[1]["receipts"], [])
            with self.engine.connect() as conn:
                self.assertEqual(conn.execute(text("SELECT count(*) FROM identity.identity_domain_events "
                    "WHERE event_type='investigation.review.returned_for_verification'")).scalar_one(), 0)
