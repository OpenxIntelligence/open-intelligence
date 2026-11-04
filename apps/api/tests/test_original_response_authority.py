"""Actual original-source disclosure boundary; fictional records only."""
from contextlib import contextmanager
from copy import deepcopy
import json
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, build_opener

from fastapi.responses import JSONResponse
from pydantic import TypeAdapter
from sqlalchemy import text

from oi_api.app import create_app
from oi_api import patients
from http_support import running_server
from test_patients import TOKEN_A
from test_source_versions import ORIGINAL, AMENDED, SourceVersionFixture


class OriginalResponseAuthorityTests(SourceVersionFixture):
    def events(self):
        with self.engine.connect() as connection:
            return [tuple(row) for row in connection.execute(text(
                "SELECT event_type,metadata_json FROM identity.identity_domain_events ORDER BY id"
            ))]

    def get(self, base, path):
        req = Request(base + path, headers={"Authorization": "Bearer " + TOKEN_A})
        try:
            response = build_opener(ProxyHandler({})).open(req, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read()
            try:
                result = json.loads(raw)
            except ValueError:
                result = {"unparsed": raw.decode("utf-8")}
            return response.status, result, response.headers

    def originals(self, base):
        patient = self.setup_case(base)
        first = self.ingest(base, patient)[1]["source_id"]
        second = self.ingest(base, patient, AMENDED)[1]["source_id"]
        return patient, [self.url(patient) + "/" + sid for sid in (first, second)]

    @contextmanager
    def after_encoding(self, action):
        """Observe actual FastAPI typed encoding and explicit JSON encoding."""
        render, dump = JSONResponse.render, TypeAdapter.dump_json
        original_type = patients.OriginalSource
        calls = []
        def matches(value):
            return (isinstance(value, original_type) or
                    isinstance(value, dict) and "original_text" in value and "source_id" in value)
        def rendered(response, value):
            result = render(response, value)
            if matches(value):
                calls.append("json"); action()
            return result
        def typed(adapter, value, *args, **kwargs):
            result = dump(adapter, value, *args, **kwargs)
            if matches(value):
                calls.append("typed"); action()
            return result
        with patch.object(JSONResponse, "render", rendered), patch.object(TypeAdapter, "dump_json", typed):
            yield calls

    def assert_withheld(self, response, before, expected=503):
        status, payload, headers = response
        self.assertEqual(status, expected, payload)
        self.assertEqual(set(payload), {"detail"})
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertNotIn("Fictional", json.dumps(payload))
        self.assertNotIn("PRIVATE-ORIGINAL", json.dumps(payload))
        self.assertEqual(self.events(), before)

    def test_revocation_during_actual_encoding_withholds_current_and_historical_original(self):
        with running_server(create_app(self.settings)) as base:
            _, paths = self.originals(base)
            initial = deepcopy(self.creds)
            for path in paths:
                for change in ("patient_read", "source_original_read", "patient_ids", "actor", "organization", "purpose"):
                    with self.subTest(path=path, change=change):
                        self.creds = deepcopy(initial); self.write()
                        before = self.events()
                        def revoke():
                            if change in ("patient_read", "source_original_read"):
                                self.creds[0]["actions"].remove(change)
                            elif change == "patient_ids":
                                self.creds[0][change] = []
                            else:
                                self.creds[0][change] = "research" if change == "purpose" else "CHANGED"
                            self.write()
                        with self.after_encoding(revoke) as calls:
                            response = self.get(base, path)
                        self.assertEqual(len(calls), 1)
                        self.assert_withheld(response, before, 404)

    def test_encoding_failure_withholds_original_and_rolls_back_read_receipt(self):
        with running_server(create_app(self.settings)) as base:
            _, paths = self.originals(base)
            for path in paths:
                with self.subTest(path=path):
                    before = self.events()
                    def fail():
                        raise ValueError("PRIVATE-ORIGINAL-ENCODER")
                    with self.after_encoding(fail) as calls:
                        response = self.get(base, path)
                    self.assertEqual(len(calls), 1)
                    self.assert_withheld(response, before)

    def test_typed_response_failure_does_not_commit_a_read_receipt(self):
        with running_server(create_app(self.settings)) as base:
            _, paths = self.originals(base)
            for path in paths:
                with self.subTest(path=path):
                    before = self.events()
                    with patch.object(patients, "OriginalSource", side_effect=ValueError("PRIVATE-ORIGINAL-DTO")):
                        response = self.get(base, path)
                    self.assert_withheld(response, before)

    def test_successful_encoding_keeps_patient_and_binding_locked_until_receipt(self):
        with running_server(create_app(self.settings)) as base:
            patient, paths = self.originals(base)
            for path, expected in zip(paths, (ORIGINAL, AMENDED)):
                with self.subTest(path=path):
                    before = self.events()
                    locks = []
                    def inspect():
                        for statement in (
                            "SELECT patient_id FROM identity.identity_patients WHERE patient_id=:p FOR UPDATE NOWAIT",
                            "SELECT case_id FROM coordination.patient_case_bindings WHERE patient_id=:p FOR UPDATE NOWAIT",
                        ):
                            with self.engine.connect() as connection:
                                try:
                                    connection.execute(text(statement), {"p": patient}).all()
                                    locks.append(False)
                                except Exception as error:
                                    # pg8000's SQLSTATE is in the original exception payload.
                                    original = getattr(error, "orig", error)
                                    detail = original.args[0] if original.args else None
                                    if not isinstance(detail, dict) or detail.get("C") != "55P03":
                                        raise
                                    locks.append(True)
                    with self.after_encoding(inspect) as calls:
                        status, result, _ = self.get(base, path)
                    self.assertEqual(len(calls), 1)
                    self.assertEqual(status, 200, result)
                    self.assertEqual(result["original_text"], expected)
                    self.assertEqual(locks, [True, True])
                    after = self.events()
                    self.assertEqual(after[:-1], before)
                    self.assertEqual(after[-1][0], "source.original_read_authorized")
                    self.assertEqual(after[-1][1]["receipt_id"], result["access_receipt_id"])
