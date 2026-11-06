"""Reusable entry points preserve existing authentication and scope checks."""

from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import Mock

from fastapi import HTTPException
from starlette.requests import Request
from oi_api.access import Principal


def principal():
    return Principal(actor="actor", organization="organization", purpose="operations",
                     actions={"patient_read", "patient_create"}, patient_ids={"patient"},
                     expires_at=datetime.now(timezone.utc) + timedelta(minutes=5))


class ExecutionAccessSeamTests(unittest.TestCase):
    def test_http_header_boundary_preserves_exactly_one_bearer(self):
        from oi_api.access import authenticate_request
        provider = Mock()
        context = principal()
        provider.authenticate.return_value = context
        valid = (b"authorization", b"Bearer " + b"a" * 32)
        for headers in ([], [valid, valid], [(b"authorization", b"Basic " + b"a" * 32)],
                        [(b"authorization", b"Bearer  " + b"a" * 32)]):
            with self.assertRaises(HTTPException) as error:
                authenticate_request(Request({"type": "http", "headers": headers}), provider)
            self.assertEqual(error.exception.status_code, 401)
            self.assertEqual(error.exception.headers, {"WWW-Authenticate": "Bearer"})
        provider.authenticate.assert_not_called()
        self.assertIs(authenticate_request(Request({"type": "http", "headers": [valid]}), provider), context)

    def test_token_entry_rechecks_provider_and_rejects_expiry(self):
        from oi_api.access import authenticate_token
        context = principal()
        provider = Mock()
        provider.authenticate.return_value = context
        self.assertIs(authenticate_token("a" * 32, provider), context)
        provider.authenticate.return_value = context.model_copy(update={
            "expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)})
        with self.assertRaises(HTTPException) as error:
            authenticate_token("a" * 32, provider)
        self.assertEqual(error.exception.status_code, 401)
        self.assertEqual(provider.authenticate.call_count, 2)

    def test_token_errors_keep_existing_status_and_hide_provider_details(self):
        from oi_api.access import authenticate_token
        provider = Mock()
        with self.assertRaises(HTTPException) as error:
            authenticate_token("short", provider)
        self.assertEqual(error.exception.status_code, 401)
        provider.authenticate.assert_not_called()
        for returned, failure, status in ((None, None, 401), ({}, None, 503),
                                         (None, RuntimeError("secret"), 503)):
            provider.authenticate.return_value = returned
            provider.authenticate.side_effect = failure
            with self.assertRaises(HTTPException) as error:
                authenticate_token("a" * 32, provider)
            self.assertEqual(error.exception.status_code, status)
            self.assertNotIn("secret", error.exception.detail)

    def test_registry_principal_scope_and_live_organization_check(self):
        from oi_api.registry_context import registry_for_principal
        connection = Mock(autocommit=False)
        cursor = connection.cursor.return_value
        cursor.fetchone.return_value = ("organization",)
        registry = registry_for_principal(connection, principal())
        allow = registry.authorizer
        self.assertTrue(allow("actor", "organization", "patient_create", "operations"))
        self.assertTrue(allow("actor", "patient", "patient_read", "operations"))
        cursor.fetchone.return_value = ("other-organization",)
        self.assertFalse(allow("actor", "patient", "patient_read", "operations"))
        cursor.fetchone.return_value = None
        self.assertFalse(allow("actor", "patient", "patient_read", "operations"))
        for actor, subject, action, purpose in (
                ("other", "patient", "patient_read", "operations"),
                ("actor", "other", "patient_read", "operations"),
                ("actor", "patient", "source_read", "operations"),
                ("actor", "patient", "patient_read", "research"),
                ("actor", "other", "patient_create", "operations")):
            self.assertFalse(allow(actor, subject, action, purpose))
        self.assertEqual(cursor.close.call_count, 3)
        connection.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
