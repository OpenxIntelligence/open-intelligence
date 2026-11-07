import json
import logging
import socket
import unittest
from unittest.mock import patch

from oi_api.app import create_app
from oi_api.config import ConfigurationError, Settings
from oi_api.contracts import DatabaseStatus

from http_support import get_json, running_server


class SettingsTests(unittest.TestCase):
    def test_unconfigured_is_an_explicit_supported_state(self):
        settings = Settings.from_env({})
        self.assertIsNone(settings.database_url)
        self.assertEqual(settings.environment, "synthetic")

    def test_only_synthetic_environment_is_enabled(self):
        for value in ("production", "pilot", "", "synthetic "):
            with self.subTest(value=value), self.assertRaises(ConfigurationError):
                Settings.from_env({"OI_API_ENVIRONMENT": value})

    def test_invalid_url_and_timeout_never_echo_credentials(self):
        secret = "do-not-log-this-password"
        invalid = [
            {"OI_API_DATABASE_URL": f"sqlite:///{secret}"},
            {"OI_API_DATABASE_URL": f"postgresql+psycopg://user:{secret}@db/example"},
            {"OI_API_DATABASE_URL": f"postgresql+pg8000://user:{secret}@db:bad/example"},
            {"OI_API_DATABASE_URL": ""},
            {"OI_API_CONNECT_TIMEOUT_SECONDS": secret},
            {"OI_API_CONNECT_TIMEOUT_SECONDS": "0"},
            {"OI_API_CONNECT_TIMEOUT_SECONDS": "30"},
            {"OI_API_CONNECT_TIMEOUT_SECONDS": "nan"},
        ]
        for env in invalid:
            with self.subTest(keys=list(env)):
                with self.assertRaises(ConfigurationError) as caught:
                    Settings.from_env(env)
                self.assertNotIn(secret, str(caught.exception))
                self.assertIsNone(caught.exception.__cause__)

    def test_valid_url_is_not_visible_in_settings_repr(self):
        settings = Settings.from_env({
            "OI_API_DATABASE_URL": "postgresql+pg8000://user:secret@localhost/example",
        })
        self.assertNotIn("secret", repr(settings))
        self.assertEqual(settings.connect_timeout_seconds, 2.0)


class HTTPContractTests(unittest.TestCase):
    def test_non_loopback_host_is_rejected(self):
        with running_server(create_app(Settings.from_env({}))) as base:
            for host in ("example.com", "localhost.evil.example", "10.0.0.2", "user@localhost"):
                with self.subTest(host=host):
                    status, body, headers = get_json(base, "/health", {"Host": host})
                    self.assertEqual(status, 400)
                    self.assertEqual(body, {"detail": "Loopback Host required"})
                    self.assertEqual(headers["Cache-Control"], "no-store")
            status, _, _ = get_json(base, "/health", {"Host": "localhost:8000"})
            self.assertEqual(status, 200)

    def test_liveness_and_version_do_not_require_database(self):
        with running_server(create_app(Settings.from_env({}))) as base:
            status, body, headers = get_json(base, "/health")
            self.assertEqual((status, body), (200, {"status": "ok"}))
            self.assertEqual(headers["Cache-Control"], "no-store")
            status, body, _ = get_json(base, "/v1")
            self.assertEqual(status, 200)
            self.assertEqual(body["product"], "Open Intelligence")
            self.assertEqual(body["api_version"], "v1")
            self.assertEqual(body["stage"], "synthetic_patient_registry")
            self.assertEqual(body["authentication"], "deny_all")
            self.assertFalse(body["patient_data_enabled"])
            self.assertTrue(body["synthetic_registry_enabled"])
            self.assertEqual(body["capabilities"], ["synthetic_patient_create", "synthetic_patient_read", "synthetic_record_request_create", "synthetic_record_request_list", "synthetic_record_request_cancel", "synthetic_record_request_receive", "synthetic_case_binding_create", "synthetic_case_binding_list", "synthetic_case_binding_revoke", "synthetic_source_import", "synthetic_source_list", "synthetic_source_original_read", "synthetic_source_world_model_read", "synthetic_source_composer_preflight", "synthetic_source_question_create", "synthetic_source_question_list", "synthetic_image_import", "synthetic_image_list", "synthetic_image_original_read", "synthetic_source_review_queue_read", "synthetic_source_review_return", "synthetic_source_question_brief", "synthetic_source_review_packet_read", "synthetic_question_followthrough_read", "synthetic_question_followthrough_create", "synthetic_question_followthrough_update", "synthetic_question_evidence_search", "synthetic_question_evidence_link", "synthetic_question_evidence_list", "synthetic_question_evidence_read", "synthetic_question_evidence_import", "synthetic_question_evidence_assess", "synthetic_question_evidence_withdraw", "synthetic_question_evidence_original_read", "synthetic_question_evidence_report", "synthetic_laboratory_question_preflight", "synthetic_laboratory_question_save", "synthetic_laboratory_question_history", "synthetic_laboratory_question_evidence_metadata", "synthetic_laboratory_source_citation_report", "synthetic_ehr_encounters", "synthetic_ehr_note_drafts", "synthetic_ehr_encounter_source_links", "synthetic_source_brief_run_enqueue", "synthetic_source_brief_run_read", "synthetic_source_brief_run_cancel", "synthetic_source_brief_run_result"])

    def test_missing_database_is_unready_not_a_fake_pass(self):
        with running_server(create_app(Settings.from_env({}))) as base:
            status, body, headers = get_json(base, "/health/ready")
        self.assertEqual(status, 503)
        self.assertEqual(body["status"], "not_ready")
        self.assertEqual(body["database"]["status"], "unconfigured")
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_unreachable_database_does_not_break_liveness_or_leak_secrets(self):
        # A bound, non-listening socket guarantees there is no database at this port.
        with socket.socket() as closed_port:
            closed_port.bind(("127.0.0.1", 0))
            port = closed_port.getsockname()[1]
            settings = Settings.from_env({
                "OI_API_DATABASE_URL": f"postgresql+pg8000://user:secret-canary@127.0.0.1:{port}/synthetic",
                "OI_API_CONNECT_TIMEOUT_SECONDS": "0.2",
            })
            records = []

            class Capture(logging.Handler):
                def emit(self, record):
                    records.append(self.format(record))

            handler = Capture()
            logger = logging.getLogger()
            logger.addHandler(handler)
            try:
                with running_server(create_app(settings)) as base:
                    status, body, _ = get_json(base, "/health/ready")
                    live_status, _, _ = get_json(base, "/health")
            finally:
                logger.removeHandler(handler)
        self.assertEqual(status, 503)
        self.assertEqual(body["database"]["status"], "unavailable")
        self.assertEqual(live_status, 200)
        observed = json.dumps(body) + "\n".join(records)
        self.assertNotIn("secret-canary", observed)
        self.assertNotIn("postgresql+pg8000", observed)

    def test_dependency_state_controls_readiness_http_status(self):
        for state in ("unsupported_version", "schema_mismatch", "unavailable", "ready"):
            with self.subTest(state=state):
                with patch("oi_api.database.Database.check", return_value=DatabaseStatus(status=state)):
                    with running_server(create_app(Settings.from_env({}))) as base:
                        status, body, _ = get_json(base, "/health/ready")
                self.assertEqual(status, 200 if state == "ready" else 503)
                self.assertEqual(body["status"], "ready" if state == "ready" else "not_ready")

    def test_openapi_is_local_versioned_and_describes_failure(self):
        with running_server(create_app(Settings.from_env({}))) as base:
            status, schema, _ = get_json(base, "/v1/openapi.json")
            for path in ("/docs", "/redoc", "/openapi.json"):
                missing_status, _, _ = get_json(base, path)
                self.assertEqual(missing_status, 404)
        self.assertEqual(status, 200)
        evidence_return = ("/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}/"
                           "evidence-reports/{report_id}/runs/{run_id}/return-for-verification")
        self.assertEqual(set(schema["paths"]), {
            evidence_return,
            "/v1/patients/{patient_id}/permissions",
            "/v1/patients/{patient_id}/permissions/{grant_id}/revocations",
            "/v1/patients/{patient_id}/encounters",
            "/v1/patients/{patient_id}/encounters/events",
            "/v1/patients/{patient_id}/encounters/{encounter_id}/transitions",
            "/v1/patients/{patient_id}/encounters/{encounter_id}/cases/{case_id}/source-links",
            "/v1/patients/{patient_id}/encounters/{encounter_id}/notes",
            "/v1/patients/{patient_id}/encounters/{encounter_id}/notes/{note_key}/versions",
            "/health",
            "/health/ready",
            "/v1",
            "/v1/patients",
            "/v1/patients/{patient_id}",
            "/v1/patients/{patient_id}/suspensions",
            "/v1/patients/{patient_id}/case-bindings",
            "/v1/patients/{patient_id}/case-bindings/{case_id}/revoke",
            "/v1/patients/{patient_id}/cases/{case_id}/composer/source-preflight",
            "/v1/patients/{patient_id}/cases/{case_id}/composer/laboratory-preflight",
            "/v1/patients/{patient_id}/cases/{case_id}/composer/laboratory-questions",
            "/v1/patients/{patient_id}/cases/{case_id}/composer/laboratory-questions/{question_id}/evidence-search",
            "/v1/patients/{patient_id}/cases/{case_id}/composer/laboratory-questions/{question_id}/source-citation-report",
            "/v1/patients/{patient_id}/cases/{case_id}/composer/laboratory-questions/{question_id}/evidence-links",
            "/v1/patients/{patient_id}/cases/{case_id}/documents",
            "/v1/patients/{patient_id}/cases/{case_id}/documents/preview",
            "/v1/patients/{patient_id}/cases/{case_id}/documents/{source_id}",
            "/v1/patients/{patient_id}/cases/{case_id}/documents/{source_id}/annotations",
            "/v1/patients/{patient_id}/cases/{case_id}/documents/{source_id}/original",
            "/v1/patients/{patient_id}/cases/{case_id}/documents/{source_id}/selections/{revision_id}/{selection_key}",
            "/v1/patients/{patient_id}/cases/{case_id}/laboratory/fhir-r4/preview",
            "/v1/patients/{patient_id}/cases/{case_id}/laboratory/fhir-r4/sources",
            "/v1/patients/{patient_id}/cases/{case_id}/followthrough",
            "/v1/patients/{patient_id}/cases/{case_id}/followthrough/{task_id}/transitions",
            "/v1/patients/{patient_id}/cases/{case_id}/followthrough/{task_id}/laboratory-amendment-review",
            "/v1/patients/{patient_id}/cases/{case_id}/laboratory-amendment-requests",
            "/v1/patients/{patient_id}/cases/{case_id}/questions",
            "/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}/manual-passages",
            "/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}/brief",
            "/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}/runs",
            "/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}/runs/{run_id}",
            "/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}/runs/{run_id}/cancel",
            "/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}/runs/{run_id}/result",
            "/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}/evidence",
            "/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}/evidence-assessments",
            "/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}/evidence-links",
            "/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}/evidence-reports",
            "/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}/evidence-reports/{report_id}",
            "/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}/evidence-search",
            "/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}/evidence/{evidence_id}/original",
            "/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}/evidence/{evidence_id}/withdraw",
            "/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}/followthrough",
            "/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}/return-for-verification",
            "/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}/source-review-packet",
            "/v1/patients/{patient_id}/cases/{case_id}/review-queue",
            "/v1/patients/{patient_id}/cases/{case_id}/sources",
            "/v1/patients/{patient_id}/cases/{case_id}/sources/{source_id}",
            "/v1/patients/{patient_id}/cases/{case_id}/sources/{source_id}/images",
            "/v1/patients/{patient_id}/cases/{case_id}/sources/{source_id}/images/{image_id}",
            "/v1/patients/{patient_id}/cases/{case_id}/sources/{source_id}/images/{image_id}/preview",
            "/v1/patients/{patient_id}/cases/{case_id}/world-model",
            "/v1/patients/{patient_id}/cases/{case_id}/world-model/history",
            "/v1/patients/{patient_id}/record-requests",
            "/v1/patients/{patient_id}/record-requests/{request_id}/cancel",
            "/v1/patients/{patient_id}/record-requests/{request_id}/receive",
        })
        laboratory = schema["paths"]["/v1/patients/{patient_id}/cases/{case_id}/composer/laboratory-preflight"]["post"]
        self.assertEqual(laboratory["operationId"], "prepare_fictional_laboratory_question_v1")
        self.assertEqual(laboratory["security"], [{"SyntheticFixture": []}])
        self.assertIn("503", laboratory["responses"])
        preview = schema["paths"]["/v1/patients/{patient_id}/cases/{case_id}/laboratory/fhir-r4/preview"]["post"]
        self.assertEqual(preview["operationId"], "preview_fictional_fhir_r4_lab_v1")
        self.assertEqual(preview["security"], [{"SyntheticFixture": []}])
        self.assertIn("503", preview["responses"])
        self.assertEqual(schema["paths"]["/v1/patients"]["post"]["security"], [{"SyntheticFixture": []}])
        self.assertEqual(schema["paths"]["/v1/patients/{patient_id}/cases/{case_id}/world-model"]["get"]["security"], [{"SyntheticFixture": []}])
        queue = schema["paths"]["/v1/patients/{patient_id}/cases/{case_id}/review-queue"]["get"]
        returning = schema["paths"]["/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}/return-for-verification"]["post"]
        governed = schema["paths"][evidence_return]["post"]
        self.assertEqual(governed["operationId"], "return_evidence_run_for_verification_v1")
        self.assertEqual(governed["security"], [{"SyntheticFixture": []}])
        self.assertTrue({"200", "201", "404", "409", "503"}.issubset(governed["responses"]))
        self.assertEqual(queue["operationId"], "list_source_question_review_queue_v1")
        self.assertEqual(returning["operationId"], "return_source_question_for_verification_v1")
        self.assertEqual(queue["security"], [{"SyntheticFixture": []}])
        self.assertEqual(returning["security"], [{"SyntheticFixture": []}])
        self.assertEqual(schema["paths"]["/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}/source-review-packet"]["get"]["operationId"], "read_question_source_review_packet_v1")
        self.assertEqual(schema["paths"]["/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}/source-review-packet"]["get"]["security"], [{"SyntheticFixture": []}])
        image_preview = schema["paths"]["/v1/patients/{patient_id}/cases/{case_id}/sources/{source_id}/images/{image_id}/preview"]["get"]
        self.assertEqual(image_preview["operationId"], "preview_source_image_v1")
        self.assertEqual(image_preview["security"], [{"SyntheticFixture": []}])
        self.assertIn("503", image_preview["responses"])
        self.assertIn("image/png", image_preview["responses"]["200"]["content"])
        self.assertIn("503", schema["paths"]["/health/ready"]["get"]["responses"])
        suspension = schema["paths"]["/v1/patients/{patient_id}/suspensions"]["post"]
        self.assertEqual(suspension["security"], [{"SyntheticFixture": []}])
        self.assertEqual(suspension["operationId"], "suspend_patient_access_v1")
        for status in ("401", "404", "409", "422", "503"):
            self.assertIn(status, suspension["responses"])
        self.assertFalse(schema["components"]["schemas"]["Readiness"]["additionalProperties"])
        for suffix, method in (("evidence-search", "post"), ("evidence-links", "post"), ("evidence-links", "get")):
            operation = schema["paths"]["/v1/patients/{patient_id}/cases/{case_id}/questions/{question_id}/" + suffix][method]
            self.assertEqual(operation["security"], [{"SyntheticFixture": []}])
            self.assertIn("503", operation["responses"])
            laboratory = schema["paths"]["/v1/patients/{patient_id}/cases/{case_id}/composer/laboratory-questions/{question_id}/" + suffix][method]
            self.assertEqual(laboratory["security"], operation["security"])
            self.assertNotEqual(laboratory["operationId"], operation["operationId"])


if __name__ == "__main__":
    unittest.main()
