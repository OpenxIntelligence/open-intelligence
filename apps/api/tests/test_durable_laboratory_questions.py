"""PostgreSQL/HTTP acceptance for fictional FHIR-anchored questions.

Shares the patient, source, question and access-event owners with text questions.
The two explicit history contracts must never relabel one kind as the other.
"""
from copy import deepcopy
import hashlib
import json
import unittest
from unittest.mock import patch

from sqlalchemy import text

from http_support import running_server
from oi_api import laboratory_fhir_routes
from oi_api.app import create_app
from open_intelligence.postgres_registry import PostgresPatientRegistry
from test_laboratory_fhir_r4 import OBS, PATIENT, encode, example, resource
from test_patients import TOKEN_A, TOKEN_B, request
from test_source_versions import SourceVersionFixture

CASE = "CASE-ALPHA"
ABSENT = "Observation/FICTIONAL-OBS-B"
QUESTION = "What should I ask about this source-reported fictional observation?"
LAB_HISTORY = "/composer/laboratory-questions"


def two_observations(value):
    bundle = example()
    quantity = resource(bundle, "Observation")
    quantity["valueQuantity"]["value"] = value
    absent = deepcopy(quantity)
    absent["id"] = ABSENT.split("/")[1]
    absent["code"]["coding"][0]["code"] = "6690-2"
    del absent["valueQuantity"]
    absent["dataAbsentReason"] = {"coding": [{
        "system": "http://terminology.hl7.org/CodeSystem/data-absent-reason",
        "code": "not-performed",
    }]}
    bundle["entry"].append({
        "fullUrl": "urn:uuid:00000000-0000-4000-8000-000000000005", "resource": absent})
    resource(bundle, "DiagnosticReport")["result"].append({"reference": ABSENT})
    return encode(bundle).decode()


class DurableLaboratoryQuestionHTTPTests(SourceVersionFixture):
    def setUp(self):
        super().setUp()
        for principal in self.creds:
            principal["actions"].extend(("composer_context_read", "question_create", "question_read"))
        self.write()

    def scope(self, base):
        pid = self.setup_case(base, source_subject=PATIENT.split("/")[1])
        return pid, f"/v1/patients/{pid}/cases/{CASE}"

    def expect(self, expected, base, path, body=None, token=TOKEN_A):
        status, result, headers = request(base, path, token=token, body=body)
        self.assertEqual(status, expected, (path, result))
        self.assertEqual(headers["Cache-Control"], "no-store")
        return result

    def import_lab(self, base, path, value=0, previous=None):
        raw = two_observations(value)
        command = {"synthetic": True, "request_key": "IMPORT-LAB-" + str(value),
                   "bundle_json": raw, "expected_previous_source_id": previous}
        imported = self.expect(201, base, path + "/laboratory/fhir-r4/sources", command)
        self.assertEqual(imported["original_sha256"], hashlib.sha256(raw.encode()).hexdigest())
        return imported

    def prepare(self, base, path, sid, reference=OBS, question=QUESTION):
        world = self.expect(200, base, path + "/world-model")
        command = {"synthetic": True, "source_id": sid, "observation_reference": reference,
                   "expected_source_snapshot_sha256": world["snapshot_fingerprint"],
                   "question": question}
        preview = self.expect(200, base, path + "/composer/laboratory-preflight", command)
        self.assertEqual(preview["selected_source"]["resource_reference"], reference)
        self.assertFalse(preview["durable_question_created"])
        return preview, {**command, "expected_preflight_sha256": preview["preflight_sha256"]}

    def counts(self):
        with self.engine.connect() as db:
            return tuple(db.execute(text("""
                SELECT (SELECT count(*) FROM investigation.source_questions),
                       (SELECT count(*) FROM identity.identity_domain_events
                         WHERE event_type='investigation.question.created'),
                       (SELECT count(*) FROM identity.identity_domain_events
                         WHERE event_type='source.read_authorized')
            """)).one())

    def test_numeric_zero_and_absent_sibling_require_their_own_exact_preparation(self):
        with running_server(create_app(self.settings)) as base:
            pid, path = self.scope(base)
            source = self.import_lab(base, path)
            old, first = self.prepare(base, path, source["source_id"])
            absent, second = self.prepare(base, path, source["source_id"], ABSENT)
            self.assertEqual((old["selected_source"]["value_text"],
                              old["selected_source"]["absent_reason"]), ("0", None))
            self.assertEqual((absent["selected_source"]["value_text"],
                              absent["selected_source"]["absent_reason"]), (None, "not-performed"))
            self.assertNotEqual(old["preflight_sha256"], absent["preflight_sha256"])
            ledger = path + LAB_HISTORY
            before = self.counts()
            first.update(request_key="QUESTION-LAB-ZERO")
            saved = self.expect(201, base, ledger, first)
            self.assertEqual(saved, {"question_id": saved["question_id"], "duplicate": False})
            self.assertRegex(saved["question_id"], r"^QUESTION-[0-9A-F]{32}$")
            self.assertEqual(self.expect(200, base, ledger, first), {**saved, "duplicate": True})
            after_retry = self.counts()
            self.assertEqual(after_retry, (before[0]+1, before[1]+1, before[2]+2))
            for key in (first["request_key"], "FRESH-KEY-WRONG-ANCHOR"):
                self.expect(409, base, ledger, {**first, "request_key": key,
                                                "observation_reference": ABSENT})
            self.expect(409, base, ledger, {**first, "request_key": "FRESH-BAD-HASH",
                                            "expected_preflight_sha256": "0"*64})
            self.assertEqual(self.counts(), after_retry)
            other = self.expect(201, base, ledger, {**second, "request_key": "QUESTION-LAB-ABSENT"})
            history = self.expect(200, base, ledger)
            self.assertEqual((history["patient_id"], history["case_id"]), (pid, CASE))
            self.assertRegex(history["access_receipt_id"], r"^ACCESS-[0-9A-F]{32}$")
            self.assertEqual(len(history["questions"]), 2)
            items = {row["question_id"]: row for row in history["questions"]}
            for receipt, prepared, ref in ((saved, old, OBS), (other, absent, ABSENT)):
                row = items[receipt["question_id"]]
                expected = {"question": QUESTION, "source_id": source["source_id"],
                            "source_version": 1, "source_sha256": source["original_sha256"],
                            "observation_reference": ref,
                            "source_snapshot_sha256": prepared["source_snapshot_sha256"],
                            "preflight_sha256": prepared["preflight_sha256"],
                            "source_context_state": "current_unreviewed_question"}
                self.assertEqual({k: row[k] for k in expected}, expected)
                self.assertNotIn("source_line", row)
            with self.engine.connect() as db:
                audit = db.execute(text("""SELECT metadata_json FROM identity.identity_domain_events
                    WHERE event_type='investigation.question.created'""")).scalars().all()
                self.assertEqual({(e["question_id"], e["observation_reference"]) for e in audit},
                                 {(saved["question_id"], OBS), (other["question_id"], ABSENT)})
                self.assertTrue(all("source_line" not in e and "question" not in e for e in audit))

    def test_amendment_preserves_original_identity_and_new_key_requires_fresh_preparation(self):
        with running_server(create_app(self.settings)) as base:
            _, path = self.scope(base)
            ledger = path + LAB_HISTORY
            one = self.import_lab(base, path)
            _, v1 = self.prepare(base, path, one["source_id"])
            old_cmd = {**v1, "request_key": "QUESTION-LAB-V1"}
            a = self.expect(201, base, ledger, old_cmd)
            old_row, = self.expect(200, base, ledger)["questions"]
            two = self.import_lab(base, path, value=1, previous=one["source_id"])
            self.assertNotEqual(two["source_id"], one["source_id"])
            self.expect(409, base, ledger, {**old_cmd, "request_key": "STALE-NEW-KEY"})
            self.assertEqual(self.expect(200, base, ledger, old_cmd), {**a, "duplicate": True})
            after_amend, = self.expect(200, base, ledger)["questions"]
            self.assertEqual(after_amend, {**old_row, "source_context_state": "source_reassessment_required"})
            _, v2 = self.prepare(base, path, two["source_id"])
            self.expect(409, base, ledger, {**v2, "request_key": old_cmd["request_key"]})
            fresh = self.expect(201, base, ledger, {**v2, "request_key": "QUESTION-LAB-V2"})
            self.assertNotEqual(fresh["question_id"], a["question_id"])
            rows = {r["question_id"]: r for r in self.expect(200, base, ledger)["questions"]}
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[a["question_id"]], after_amend)
            self.assertEqual((rows[fresh["question_id"]]["source_id"],
                              rows[fresh["question_id"]]["source_version"],
                              rows[fresh["question_id"]]["source_context_state"]),
                             (two["source_id"], 2, "current_unreviewed_question"))
            self.assertEqual(self.counts()[:2], (2, 2))

    def test_mixed_case_preserves_text_wire_contract_and_shared_idempotency_namespace(self):
        with running_server(create_app(self.settings)) as base:
            pid, path = self.scope(base)
            code, text_source, _ = self.ingest(base, pid)
            self.assertEqual(code, 201, text_source)
            lab = self.import_lab(base, path)
            _, lab_fields = self.prepare(base, path, lab["source_id"])
            text_fields = {"synthetic": True, "source_id": text_source["source_id"],
                           "source_line": 8, "question": "What was reported on this fictional text line?",
                           "expected_source_snapshot_sha256": lab_fields["expected_source_snapshot_sha256"]}
            text_preview = self.expect(200, base, path + "/composer/source-preflight", text_fields)
            text_cmd = {**text_fields, "request_key": "SHARED-TEXT-KEY",
                        "expected_preflight_sha256": text_preview["preflight_sha256"]}
            t = self.expect(201, base, path + "/questions", text_cmd)
            old_history = self.expect(200, base, path + "/questions")
            self.assertEqual(old_history["contract"], "oi.synthetic-source-questions/2")
            self.assertEqual(self.expect(200, base, path + LAB_HISTORY)["questions"], [])
            self.expect(409, base, path + LAB_HISTORY, {**lab_fields, "request_key": "SHARED-TEXT-KEY"})
            l = self.expect(201, base, path + LAB_HISTORY, {**lab_fields, "request_key": "SHARED-LAB-KEY"})
            self.expect(409, base, path + "/questions", {**text_cmd, "request_key": "SHARED-LAB-KEY"})
            self.assertEqual(self.expect(200, base, path + "/questions", text_cmd), {**t, "duplicate": True})
            history = self.expect(200, base, path + "/questions")
            self.assertEqual(old_history["questions"], history["questions"])
            self.assertEqual([r["source_line"] for r in history["questions"]], [8])
            self.assertEqual([r["question_id"] for r in self.expect(200, base, path + LAB_HISTORY)["questions"]],
                             [l["question_id"]])
            self.assertEqual(self.counts()[:2], (2, 2))

    def test_revoked_binding_actions_and_cross_scope_deny_history_and_exact_replay(self):
        with running_server(create_app(self.settings)) as base:
            pid, path = self.scope(base)
            source = self.import_lab(base, path)
            _, fields = self.prepare(base, path, source["source_id"])
            cmd = {**fields, "request_key": "PERMISSION-QUESTION"}
            ledger = path + LAB_HISTORY
            receipt = self.expect(201, base, ledger, cmd)
            def denied(target, body=None, token=TOKEN_A):
                before = self.counts()
                data = self.expect(404, base, target, body, token)
                self.assertNotIn(receipt["question_id"], json.dumps(data))
                self.assertNotIn(QUESTION, json.dumps(data))
                self.assertEqual(self.counts(), before)
            for action in ("patient_read", "source_read", "question_create", "composer_context_read", "question_read"):
                with self.subTest(action=action):
                    self.creds[0]["actions"].remove(action)
                    self.write()
                    if action != "question_read":
                        denied(ledger, cmd)
                    else:
                        self.assertTrue(self.expect(200, base, ledger, cmd)["duplicate"])
                    if action not in ("question_create", "composer_context_read"):
                        denied(ledger)
                    else:
                        self.assertEqual(self.expect(200, base, ledger)["questions"][0]["question_id"],
                                         receipt["question_id"])
                    self.creds[0]["actions"].append(action)
                    self.write()
            self.creds[1]["patient_ids"] = [pid]
            self.write()
            denied(ledger, cmd, TOKEN_B)
            denied(ledger, token=TOKEN_B)
            wrong = ledger.replace(CASE, "CASE-OTHER")
            denied(wrong, cmd)
            denied(wrong)
            self.expect(200, base, f"/v1/patients/{pid}/case-bindings/{CASE}/revoke",
                        {"synthetic": True, "reason": "Fictional revoked laboratory mapping."})
            denied(ledger, cmd)
            denied(ledger)

    def test_deferred_database_commit_failure_withholds_prepared_history_new_save_and_replay(self):
        with running_server(create_app(self.settings)) as base:
            _, path = self.scope(base)
            source = self.import_lab(base, path)
            _, fields = self.prepare(base, path, source["source_id"])
            ledger = path + LAB_HISTORY
            saved_cmd = {**fields, "request_key": "BEFORE-DEFERRED-FAILURE"}
            first = self.expect(201, base, ledger, saved_cmd)
            fresh_cmd = {**fields, "request_key": "FRESH-AT-DEFERRED-FAILURE"}
            # This trigger fails at actual PG commit, after the response and audit
            # inserts are prepared. A mocked store or generic 503 is insufficient.
            with self.engine.begin() as db:
                db.exec_driver_sql("""
                    CREATE FUNCTION identity.refuse_lab_question_commit() RETURNS trigger
                    LANGUAGE plpgsql AS $$ BEGIN
                    RAISE EXCEPTION 'FICTIONAL-DEFERRED-LAB-COMMIT';
                    END; $$""")
                db.exec_driver_sql("""
                    CREATE CONSTRAINT TRIGGER refuse_lab_question_commit
                    AFTER INSERT ON identity.identity_domain_events
                    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
                    WHEN (NEW.event_type='source.read_authorized')
                    EXECUTE FUNCTION identity.refuse_lab_question_commit()""")
            try:
                real_response = laboratory_fhir_routes.JSONResponse
                for command in (fresh_cmd, saved_cmd, None):
                    before = self.counts()
                    prepared_bytes = []
                    def observe(*args, **kwargs):
                        response = real_response(*args, **kwargs)
                        prepared_bytes.append(response.body)
                        return response
                    with patch.object(laboratory_fhir_routes, "JSONResponse", observe):
                        result = self.expect(503, base, ledger, command)
                    self.assertEqual(result, {"detail": "Patient registry unavailable"})
                    encoded, = (json.loads(body) for body in prepared_bytes)
                    if command is None:
                        self.assertEqual(encoded["questions"][0]["question_id"], first["question_id"])
                    elif command == saved_cmd:
                        self.assertEqual(encoded, {**first, "duplicate": True})
                    else:
                        self.assertFalse(encoded["duplicate"])
                        self.assertNotEqual(encoded["question_id"], first["question_id"])
                    self.assertEqual(self.counts(), before)
            finally:
                with self.engine.begin() as db:
                    db.exec_driver_sql("DROP TRIGGER refuse_lab_question_commit ON identity.identity_domain_events")
                    db.exec_driver_sql("DROP FUNCTION identity.refuse_lab_question_commit()")
            self.assertFalse(self.expect(201, base, ledger, fresh_cmd)["duplicate"])

    def test_authority_loss_after_source_access_event_rolls_back_both_write_and_read(self):
        with running_server(create_app(self.settings)) as base:
            _, path = self.scope(base)
            source = self.import_lab(base, path)
            _, fields = self.prepare(base, path, source["source_id"])
            cmd = {**fields, "request_key": "LATE-AUTHORITY-QUESTION"}
            ledger = path + LAB_HISTORY
            original = PostgresPatientRegistry.append_event
            for grant, body in (("question_create", cmd), ("question_read", None)):
                with self.subTest(grant=grant):
                    before = self.counts()
                    seen = []
                    def revoke_after_audit(registry, patient_id, kind, **refs):
                        original(registry, patient_id, kind, **refs)
                        if kind == "source.read_authorized":
                            self.creds[0]["actions"].remove(grant)
                            self.write()
                            seen.append(kind)
                    with patch.object(PostgresPatientRegistry, "append_event", revoke_after_audit):
                        result = self.expect(404, base, ledger, body)
                    self.assertEqual(seen, ["source.read_authorized"])
                    self.assertNotIn(QUESTION, json.dumps(result))
                    self.assertEqual(self.counts(), before)
                    self.creds[0]["actions"].append(grant)
                    self.write()
                    if body:
                        self.expect(201, base, ledger, cmd)
            self.assertEqual(self.counts()[:2], (1, 1))


if __name__ == "__main__":
    unittest.main()
