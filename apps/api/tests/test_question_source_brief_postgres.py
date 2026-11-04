"""Actual PG16/HTTP source-question briefs over the existing canonical owners.

Only independently authored fixtures are used. No database fallback, source
download or clinical data is permitted. An unavailable PG fixture is a skip,
never evidence that the transactional acceptance cases passed.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import unittest
from unittest.mock import patch

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from oi_api.app import create_app
from oi_api import source_questions as question_owner
from oi_api import patients as patient_api

from http_support import running_server
import test_patients as patient_fixture
import test_source_questions as question_fixture
import test_source_versions as source_fixture
import test_question_source_brief as brief_fixture


CASE = "CASE-ALPHA"
QUESTION = "What remains unreported in this independently fictional source?"
TOKEN = patient_fixture.TOKEN_A


class QuestionSourceBriefPostgresTests(source_fixture.SourceVersionFixture):
    # Reuse fixture behavior without inheriting/discovering another test suite.
    path = staticmethod(question_fixture.SourceQuestionHTTPTests.path)
    model_path = staticmethod(question_fixture.SourceQuestionHTTPTests.model_path)
    world = question_fixture.SourceQuestionHTTPTests.world
    preflight = question_fixture.SourceQuestionHTTPTests.preflight
    prepared = question_fixture.SourceQuestionHTTPTests.prepared
    save = question_fixture.SourceQuestionHTTPTests.save
    listing = question_fixture.SourceQuestionHTTPTests.listing

    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend((
            "composer_context_read", "question_create", "question_read", "source_brief_export",
        ))
        self.write()

    @staticmethod
    def brief_path(patient, question, case=CASE):
        return f"/v1/patients/{patient}/cases/{case}/questions/{question}/brief"

    @staticmethod
    def brief_intent(preflight):
        return {
            "synthetic": True,
            "source_snapshot_contract": "oi.pg-source-world-model/1",
            "expected_source_snapshot_sha256": preflight["source_snapshot_sha256"],
            "expected_preflight_sha256": preflight["preflight_sha256"],
        }

    def seed(self, base):
        patient = self.setup_case(base)
        code, imported, _ = self.ingest(base, patient)
        self.assertEqual(code, 201, imported)
        preflight = self.prepared(base, patient, imported["source_id"], question=QUESTION)
        code, saved, _ = self.save(base, patient, preflight)
        self.assertEqual(code, 201, saved)
        return patient, saved["question_id"], preflight

    def brief(self, base, patient, question, preflight, *, token=TOKEN,
              case=CASE, overrides=None, headers=None):
        payload = {**self.brief_intent(preflight), **(overrides or {})}
        return patient_fixture.request(base, self.brief_path(patient, question, case),
                                       token=token, body=payload, headers=headers)

    def events(self):
        with self.engine.connect() as connection:
            return [tuple(row) for row in connection.execute(text(
                "SELECT event_type,metadata_json FROM identity.identity_domain_events ORDER BY id"
            )).all()]

    def question_rows(self):
        with self.engine.connect() as connection:
            return [dict(row) for row in connection.execute(text(
                "SELECT * FROM investigation.source_questions ORDER BY question_id"
            )).mappings().all()]

    def assert_withheld(self, result, expected_status, previous_events, previous_questions):
        status, payload, headers = result
        self.assertEqual(status, expected_status, payload)
        self.assertEqual(set(payload), {"detail"})
        self.assertEqual(headers["Cache-Control"], "no-store")
        public = json.dumps(payload, ensure_ascii=False)
        for private in (TOKEN, QUESTION, "Fictional café", "PRIVATE-BRIEF-CANARY"):
            self.assertNotIn(private, public)
        self.assertEqual(self.events(), previous_events)
        self.assertEqual(self.question_rows(), previous_questions)

    def test_real_question_brief_keeps_exact_source_and_commits_only_one_read_receipt(self):
        with running_server(create_app(self.settings)) as base:
            patient, question, preflight = self.seed(base)
            listed = self.listing(base, patient)[1]["questions"][0]
            prior_events, prior_questions = self.events(), self.question_rows()
            status, brief, headers = self.brief(base, patient, question, preflight)
            self.assertEqual(status, 200, brief)
            self.assertEqual(set(brief), brief_fixture.RESPONSE_FIELDS)
            self.assertEqual(brief["contract"], "oi.synthetic-source-brief/2")
            self.assertEqual(brief["patient_id"], patient)
            self.assertEqual(brief["case_id"], CASE)
            self.assertEqual(brief["question"], listed)
            self.assertEqual(brief["selected_source"], preflight["selected_source"])
            self.assertEqual(brief["source_snapshot_sha256"], preflight["source_snapshot_sha256"])
            self.assertEqual(brief["selected_source"]["line"], 8)
            self.assertEqual(brief["selected_source"]["version"], 1)
            self.assertEqual(brief["selected_source"]["reported_state"], "not-reported")
            self.assertEqual(brief["selected_source"]["sha256"],
                             hashlib.sha256(source_fixture.ORIGINAL.encode()).hexdigest())
            self.assertEqual(brief["body_sha256"], hashlib.sha256(brief["body"].encode()).hexdigest())
            self.assertEqual(brief["media_type"], "text/plain;charset=utf-8")
            self.assertEqual(headers["Cache-Control"], "no-store")
            self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
            self.assertEqual(int(headers["Content-Length"]), len(json.dumps(
                brief, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
            ).encode("utf-8")))
            self.assertLessEqual(int(headers["Content-Length"]), 65_536)
            for literal in (QUESTION, "Fictional café <script>literal</script>.",
                            "DOC-ONE", "2026-01-10", "2026-01-11", "not-reported"):
                self.assertIn(literal, brief["body"])
            for field in ("clinical_approval", "model_executed", "biomedical_evidence_included"):
                self.assertIs(brief[field], False)
            after = self.events()
            self.assertEqual(len(after), len(prior_events) + 1)
            self.assertEqual(after[:-1], prior_events)
            self.assertEqual(after[-1][0], "source.read_authorized")
            self.assertEqual(after[-1][1]["receipt_id"], brief["access_receipt_id"])
            self.assertEqual(after[-1][1]["case_id"], CASE)
            self.assertEqual(self.question_rows(), prior_questions)

            status, repeated, _ = self.brief(base, patient, question, preflight)
            self.assertEqual(status, 200, repeated)
            self.assertEqual(repeated["question"], brief["question"])
            self.assertEqual(repeated["source_snapshot_sha256"], brief["source_snapshot_sha256"])
            self.assertNotEqual(repeated["access_receipt_id"], brief["access_receipt_id"])
            self.assertEqual(len(self.events()), len(prior_events) + 2)
            self.assertEqual(self.question_rows(), prior_questions)

    def test_amendment_refuses_old_question_retains_original_and_fresh_question_survives_restart(self):
        with running_server(create_app(self.settings)) as base:
            patient, old_question, old_preflight = self.seed(base)
            old_source = old_preflight["selected_source"]["source_id"]
            code, amended, _ = self.ingest(base, patient, source_fixture.AMENDED)
            self.assertEqual(code, 201, amended)
            current = self.prepared(base, patient, amended["source_id"], line=9,
                                    question="What changed in this independently fictional amendment?")
            before, rows = self.events(), self.question_rows()
            self.assert_withheld(self.brief(base, patient, old_question, old_preflight), 409, before, rows)
            self.assert_withheld(self.brief(base, patient, old_question, current), 409, before, rows)
            code, original, _ = patient_fixture.request(
                base, self.url(patient) + "/" + old_source, token=TOKEN)
            self.assertEqual(code, 200, original)
            self.assertEqual(original["original_text"], source_fixture.ORIGINAL)
            self.assertEqual(original["state"], "superseded")
            retained = self.listing(base, patient)[1]["questions"][0]
            self.assertEqual(retained["question_id"], old_question)
            self.assertEqual(retained["source_id"], old_source)
            self.assertEqual(retained["source_context_state"], "source_reassessment_required")
            code, saved, _ = self.save(base, patient, current, request_key="BRIEF-AMENDED-QUESTION")
            self.assertEqual(code, 201, saved)
            new_question = saved["question_id"]
            code, ready, _ = self.brief(base, patient, new_question, current)
            self.assertEqual(code, 200, ready)
            self.assertEqual(ready["selected_source"]["version"], 2)
            self.assertIn("negative", ready["body"])
            self.assertNotIn("Fictional café", ready["body"])
        with running_server(create_app(self.settings)) as restarted:
            code, reopened, _ = self.brief(restarted, patient, new_question, current)
            self.assertEqual(code, 200, reopened)
            self.assertEqual(reopened["question"], ready["question"])
            self.assertEqual(reopened["selected_source"], ready["selected_source"])
            self.assertNotEqual(reopened["access_receipt_id"], ready["access_receipt_id"])

    def test_existing_question_export_needs_read_grants_without_new_work_permissions(self):
        """A prepared read must not require import, Composer or question-create authority."""
        with running_server(create_app(self.settings)) as base:
            patient, question, preflight = self.seed(base)
            self.creds[0]["actions"] = [
                "patient_read", "question_read", "source_read", "source_brief_export",
            ]
            self.write()
            before, rows = self.events(), self.question_rows()
            status, brief, _ = self.brief(base, patient, question, preflight)
            self.assertEqual(status, 200, brief)
            self.assertEqual(brief["question"]["question_id"], question)
            self.assertEqual(brief["selected_source"], preflight["selected_source"])
            self.assertEqual(len(self.events()), len(before) + 1)
            self.assertEqual(self.events()[-1][0], "source.read_authorized")
            self.assertEqual(self.question_rows(), rows)

    def test_wrong_patient_case_organization_question_and_grants_are_indistinguishable(self):
        with running_server(create_app(self.settings)) as base:
            patient, question, preflight = self.seed(base)
            other = self.setup_case(base, case="CASE-BETA", key="CREATE-BETA", source_subject="SUBJECT-BETA")
            before, rows = self.events(), self.question_rows()
            attempts = (
                self.brief(base, other, question, preflight, case="CASE-BETA"),
                self.brief(base, patient, question, preflight, case="CASE-ABSENT"),
                self.brief(base, patient, "QUESTION-" + "F" * 32, preflight),
                self.brief(base, patient, question, preflight, token=patient_fixture.TOKEN_B,
                           headers={"X-Actor": "ACTOR-ALPHA", "X-Organization": "ORG-ALPHA"}),
            )
            for result in attempts:
                self.assert_withheld(result, 404, before, rows)
            initial = deepcopy(self.creds)
            for action in ("patient_read", "question_read", "source_read", "source_brief_export"):
                with self.subTest(missing_action=action):
                    self.creds = deepcopy(initial)
                    self.creds[0]["actions"].remove(action)
                    self.write()
                    self.assert_withheld(self.brief(base, patient, question, preflight), 404, before, rows)
            for field, value in (("purpose", "research"), ("organization", "ORG-OTHER"), ("patient_ids", [])):
                with self.subTest(scope=field):
                    self.creds = deepcopy(initial)
                    self.creds[0][field] = value
                    self.write()
                    self.assert_withheld(self.brief(base, patient, question, preflight), 404, before, rows)

    def test_wrong_fingerprint_preflight_and_request_overposting_leave_no_receipt(self):
        with running_server(create_app(self.settings)) as base:
            patient, question, preflight = self.seed(base)
            before, rows = self.events(), self.question_rows()
            for field in ("expected_source_snapshot_sha256", "expected_preflight_sha256"):
                with self.subTest(stale=field):
                    self.assert_withheld(self.brief(base, patient, question, preflight,
                        overrides={field: "0" * 64}), 409, before, rows)
            invalid = (
                {"synthetic": False}, {"synthetic": 1},
                {"source_snapshot_contract": "oi.synthetic-postgres-world-model-sources/1"},
                {"expected_preflight_sha256": "e" * 64 + "\n"},
                {"expected_source_snapshot_sha256": "A" * 64},
                {"actor": "PRIVATE-BRIEF-CANARY"}, {"body": "PRIVATE-BRIEF-CANARY"},
                {"clinical_approval": True}, {"model_executed": True},
            )
            for change in invalid:
                with self.subTest(invalid=list(change)):
                    self.assert_withheld(self.brief(base, patient, question, preflight,
                        overrides=change), 422, before, rows)

    def test_persisted_legacy_contract_and_misbound_saved_intent_are_not_reinterpreted(self):
        with running_server(create_app(self.settings)) as base:
            patient, question, preflight = self.seed(base)
            original = self.question_rows()[0]
            variants = (
                {"source_snapshot_contract": "oi.synthetic-postgres-world-model-sources/1"},
                {"question": "A different fictional saved question with an old preflight."},
                {"preflight_sha256": "0" * 64},
            )
            for number, change in enumerate(variants, 1):
                with self.subTest(changed=list(change)):
                    # Existing immutable guards stay enabled. These complete
                    # INSERT fixtures are schema-legal legacy/corrupt intents,
                    # not a mutation of the successful canonical question.
                    row = {**original, **change,
                           "question_id": "QUESTION-" + f"{number:032X}",
                           "request_key": f"BRIEF-LEGACY-{number}"}
                    columns = [name for name in row if name != "created_at"]
                    with self.engine.begin() as connection:
                        connection.execute(text(
                            "INSERT INTO investigation.source_questions (" + ",".join(columns) +
                            ") VALUES (" + ",".join(":" + name for name in columns) + ")"
                        ), row)
                    before, rows = self.events(), self.question_rows()
                    supplied = {**preflight, "preflight_sha256": row["preflight_sha256"]}
                    self.assert_withheld(self.brief(base, patient, row["question_id"], supplied),
                                         409, before, rows)

    def test_final_authority_refresh_denies_revocation_actor_replacement_and_expiry(self):
        with running_server(create_app(self.settings)) as base:
            patient, question, preflight = self.seed(base)
            initial = deepcopy(self.creds)
            changes = [
                ("patient_read", {"actions": [a for a in initial[0]["actions"] if a != "patient_read"]}, 404),
                ("export", {"actions": [a for a in initial[0]["actions"] if a != "source_brief_export"]}, 404),
                ("question", {"actions": [a for a in initial[0]["actions"] if a != "question_read"]}, 404),
                ("source", {"actions": [a for a in initial[0]["actions"] if a != "source_read"]}, 404),
                ("actor", {"actor": "ACTOR-REPLACED"}, 404),
                ("organization", {"organization": "ORG-REPLACED"}, 404),
                ("patient", {"patient_ids": []}, 404),
                ("purpose", {"purpose": "research"}, 404),
                ("expiry", {"expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()}, 401),
            ]
            actual_serializer = patient_api.JSONResponse.render
            for label, change, expected in changes:
                with self.subTest(change=label):
                    self.creds = deepcopy(initial)
                    self.write()
                    before, rows = self.events(), self.question_rows()
                    prepared = []

                    def withdraw(response, content):
                        wire = actual_serializer(response, content)
                        if isinstance(content, dict) and content.get("contract") == "oi.synthetic-source-brief/2":
                            prepared.append(content["body_sha256"])
                            self.creds[0].update(change)
                            self.write()
                        return wire

                    with patch.object(patient_api.JSONResponse, "render", withdraw):
                        result = self.brief(base, patient, question, preflight)
                    self.assertEqual(len(prepared), 1, "Real JSON serialization must precede final revocation")
                    self.assert_withheld(result, expected, before, rows)

    def test_missing_or_malformed_authority_provider_after_render_withholds_body_and_receipt(self):
        with running_server(create_app(self.settings)) as base:
            patient, question, preflight = self.seed(base)
            actual_renderer = question_owner.render_source_brief
            for mode, expected in (("removed_credential", 401), ("missing_file", 503), ("malformed_file", 503)):
                with self.subTest(mode=mode):
                    self.write()
                    before, rows = self.events(), self.question_rows()

                    def unavailable(*args, **kwargs):
                        result = actual_renderer(*args, **kwargs)
                        if mode == "removed_credential":
                            saved = self.creds
                            self.creds = self.creds[1:]
                            self.write()
                            self.creds = saved
                        elif mode == "missing_file":
                            self.access.unlink()
                        else:
                            self.access.write_text("PRIVATE-BRIEF-CANARY")
                        return result

                    with patch.object(question_owner, "render_source_brief", unavailable):
                        result = self.brief(base, patient, question, preflight)
                    self.assert_withheld(result, expected, before, rows)

    def test_typed_response_failure_rolls_back_source_read_without_echoing_prepared_body(self):
        with running_server(create_app(self.settings)) as base:
            patient, question, preflight = self.seed(base)
            actual_renderer = question_owner.render_source_brief
            variants = (
                {"contract": "oi.synthetic-source-brief/1"}, {"clinical_approval": True},
                {"model_executed": True}, {"biomedical_evidence_included": True},
                {"body_sha256": "0" * 64}, {"body": "PRIVATE-BRIEF-CANARY"},
                {"unapproved_field": "PRIVATE-BRIEF-CANARY"},
            )
            for change in variants:
                with self.subTest(change=list(change)):
                    before, rows = self.events(), self.question_rows()

                    def malformed(*args, **kwargs):
                        return {**actual_renderer(*args, **kwargs), **change}

                    with patch.object(question_owner, "render_source_brief", malformed):
                        result = self.brief(base, patient, question, preflight)
                    self.assert_withheld(result, 503, before, rows)

    def test_complete_json_limit_fails_before_read_receipt_when_body_alone_fits(self):
        with running_server(create_app(self.settings)) as base:
            patient, question, preflight = self.seed(base)
            before, rows = self.events(), self.question_rows()
            actual_renderer = question_owner.render_source_brief
            sizes = []

            def oversized(*args, **kwargs):
                result = actual_renderer(*args, **kwargs)
                body = result["body"]
                body += "x" * (65_500 - len(body.encode("utf-8")))
                result.update(body=body, body_sha256=hashlib.sha256(body.encode()).hexdigest())
                sizes.append((len(body.encode()), len(json.dumps(result, ensure_ascii=False,
                                                               separators=(",", ":")).encode())))
                return result

            with patch.object(question_owner, "render_source_brief", oversized):
                result = self.brief(base, patient, question, preflight)
            self.assertEqual(len(sizes), 1)
            self.assertLess(sizes[0][0], 65_536)
            self.assertGreater(sizes[0][1], 65_536)
            self.assert_withheld(result, 503, before, rows)

    def test_actual_json_serialization_failure_and_oversize_cannot_commit_read_receipt(self):
        with running_server(create_app(self.settings)) as base:
            patient, question, preflight = self.seed(base)
            actual_serializer = patient_api.JSONResponse.render
            for failure in ("serializer_failure", "wire_size"):
                with self.subTest(failure=failure):
                    before, rows = self.events(), self.question_rows()
                    observed = []

                    def fail_preparation(response, content):
                        wire = actual_serializer(response, content)
                        if isinstance(content, dict) and content.get("contract") == "oi.synthetic-source-brief/2":
                            # Real source rendering, DTO validation, and JSON
                            # serialization all execute before this fault seam.
                            observed.append(len(wire))
                            if failure == "serializer_failure":
                                raise ValueError("PRIVATE-BRIEF-CANARY")
                            return wire + b" " * 65_536
                        return wire

                    with patch.object(patient_api.JSONResponse, "render", fail_preparation):
                        result = self.brief(base, patient, question, preflight)
                    self.assertEqual(len(observed), 1)
                    self.assertLessEqual(observed[0], 65_536)
                    self.assert_withheld(result, 503, before, rows)

    def test_receipt_insertion_failure_cannot_return_the_already_prepared_brief(self):
        with running_server(create_app(self.settings)) as base:
            patient, question, preflight = self.seed(base)
            before, rows = self.events(), self.question_rows()
            with self.engine.begin() as connection:
                connection.exec_driver_sql("""
                    CREATE FUNCTION identity.reject_brief_read_receipt() RETURNS trigger
                    LANGUAGE plpgsql AS $$ BEGIN
                    IF NEW.event_type='source.read_authorized' THEN
                        RAISE EXCEPTION 'PRIVATE-BRIEF-CANARY';
                    END IF;
                    RETURN NEW; END; $$;
                """)
                connection.exec_driver_sql(
                    "CREATE TRIGGER reject_brief_read_receipt BEFORE INSERT "
                    "ON identity.identity_domain_events FOR EACH ROW "
                    "EXECUTE FUNCTION identity.reject_brief_read_receipt()"
                )
            self.assert_withheld(self.brief(base, patient, question, preflight), 503, before, rows)

    def test_patient_and_binding_locks_remain_held_through_actual_brief_preparation(self):
        with running_server(create_app(self.settings)) as base:
            patient, question, preflight = self.seed(base)
            before, rows = self.events(), self.question_rows()
            actual_serializer = patient_api.JSONResponse.render
            targets = (
                ("patient", "SELECT patient_id FROM identity.identity_patients "
                            "WHERE patient_id=:patient FOR UPDATE NOWAIT", {"patient": patient}),
                ("binding", "SELECT case_id FROM coordination.patient_case_bindings "
                            "WHERE case_id=:case FOR UPDATE NOWAIT", {"case": CASE}),
            )

            def attempt(sql, parameters):
                with self.engine.connect() as connection:
                    try:
                        connection.execute(text(sql), parameters).scalar_one()
                    except DBAPIError as error:
                        detail = error.orig.args[0] if error.orig.args else None
                        return detail.get("C") if isinstance(detail, dict) else None
                return "acquired"

            observed = {}

            def prepare_under_locks(response, content):
                wire = actual_serializer(response, content)
                if isinstance(content, dict) and content.get("contract") == "oi.synthetic-source-brief/2":
                    observed["events"] = self.events()
                    observed["locks"] = [(name, attempt(sql, parameters)) for name, sql, parameters in targets]
                return wire

            with patch.object(patient_api.JSONResponse, "render", prepare_under_locks):
                status, result, _ = self.brief(base, patient, question, preflight)
            self.assertEqual(status, 200, result)
            self.assertEqual(observed["events"], before)
            self.assertEqual(observed["locks"], [("patient", "55P03"), ("binding", "55P03")])
            self.assertEqual(len(self.events()), len(before) + 1)
            self.assertEqual(self.question_rows(), rows)
            for name, sql, parameters in targets:
                with self.subTest(released=name):
                    self.assertEqual(attempt(sql, parameters), "acquired")


if __name__ == "__main__":
    unittest.main()
