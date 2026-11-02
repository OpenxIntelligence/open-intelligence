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
            self.assertEqual(body["stage"], "synthetic_shell")
            self.assertEqual(body["authentication"], "not_implemented")
            self.assertFalse(body["patient_data_enabled"])
            self.assertEqual(body["capabilities"], [])

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
            for path in ("/docs", "/redoc", "/openapi.json", "/v1/patients"):
                missing_status, _, _ = get_json(base, path)
                self.assertEqual(missing_status, 404)
        self.assertEqual(status, 200)
        self.assertEqual(set(schema["paths"]), {"/health", "/health/ready", "/v1"})
        self.assertIn("503", schema["paths"]["/health/ready"]["get"]["responses"])
        self.assertFalse(schema["components"]["schemas"]["Readiness"]["additionalProperties"])


if __name__ == "__main__":
    unittest.main()
