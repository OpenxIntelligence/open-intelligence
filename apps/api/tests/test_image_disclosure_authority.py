"""Actual PG16/HTTP: image response preparation belongs inside source authority.

Uses the existing independently fictional image/source fixture. Production
renderers still run; only the credential change is injected after preparation.
No external PACS, patient record, new schema or alternate registry is used.

Preserves the final-preparation regressions from PR #253 against the combined
canonical source/question/image owner. The source fixture has no inherited test
methods; this file contributes four actual PostgreSQL/HTTP acceptance methods.
"""
import copy
from datetime import datetime, timedelta, timezone
import json
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from oi_api import patients as routes
from oi_api.app import create_app
from http_support import running_server
from test_patients import TOKEN_A
from test_source_versions import SourceVersionFixture
from test_image_custody import REPORT, image_bytes, image_request


def read_image_route(base, path):
    opener = build_opener(ProxyHandler({}))
    try:
        reply = opener.open(Request(base + path, headers={"Authorization": "Bearer " + TOKEN_A}), timeout=8)
    except HTTPError as error:
        reply = error
    with reply:
        raw = reply.read()
        if reply.headers.get_content_type() == "application/dicom":
            body = raw
        else:
            try:
                body = json.loads(raw)
            except ValueError:
                body = raw.decode("utf-8", errors="replace")
        return reply.status, body, reply.headers


class ImageDisclosureAuthorityTests(SourceVersionFixture):
    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend(["image_import", "image_read", "image_original_read"])
        self.write()

    def prepare(self, base):
        patient = self.setup_case(base)
        status, receipt, _ = self.ingest(base, patient, REPORT)
        self.assertEqual(status, 201)
        path = self.url(patient) + "/" + receipt["source_id"] + "/images"
        raw = image_bytes()
        status, image, _ = image_request(base, path, raw=raw)
        self.assertEqual(status, 201)
        return patient, path, image["image_id"], raw

    def read_events(self):
        with self.engine.connect() as connection:
            rows = connection.execute(text(
                "SELECT event_type,metadata_json FROM identity.identity_domain_events "
                "WHERE event_type IN ('image.read_authorized','image.original_read_authorized') ORDER BY id"
            )).all()
        # The canonical PostgreSQL journal uses JSONB. SQLAlchemy returns its
        # decoded mapping, not JSON text or a serializable SQLAlchemy Row.
        return [(row[0], dict(row[1])) for row in rows]

    def assert_withheld(self, result, status, before):
        self.assertEqual(result[0], status)
        self.assertIsInstance(result[1], dict)
        self.assertEqual(set(result[1]), {"detail"})
        self.assertEqual(result[2]["Cache-Control"], "no-store")
        self.assertNotIn("X-OI-Access-Receipt", result[2])
        for secret in ("PRIVATE-IMAGE-PREPARE", TOKEN_A, "2.25.103", "DICM"):
            self.assertNotIn(secret, json.dumps(result[1]))
        self.assertEqual(self.read_events(), before)

    def observe_preparation(self, kind, effect):
        """Keep the real constructor, but inspect/change authority afterwards."""
        name = "SourceImageIndex" if kind == "index" else "Response"
        original = getattr(routes, name)
        def prepare(*args, **kwargs):
            prepared = original(*args, **kwargs)
            if kind == "index" or kwargs.get("media_type") == "application/dicom":
                effect()
            return prepared
        return patch.object(routes, name, side_effect=prepare)

    def test_late_grant_or_identity_change_withholds_prepared_index_and_binary(self):
        with running_server(create_app(self.settings)) as base:
            patient, path, image_id, raw = self.prepare(base)
            initial = copy.deepcopy(self.creds)
            for kind, url, action in (("index", path, "image_read"),
                                      ("binary", path + "/" + image_id, "image_original_read")):
                changes = [
                    ({"actions": [a for a in initial[0]["actions"] if a != action]}, 404),
                    ({"actions": [a for a in initial[0]["actions"] if a != "patient_read"]}, 404),
                    ({"patient_ids": []}, 404), ({"actor": "ACTOR-CHANGED"}, 404),
                    ({"organization": "ORG-CHANGED"}, 404), ({"purpose": "research"}, 404),
                    ({"expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()}, 401),
                ]
                for change, status in changes:
                    with self.subTest(kind=kind, change=list(change)):
                        self.creds = copy.deepcopy(initial)
                        self.write()
                        before = self.read_events()
                        def withdraw():
                            self.creds[0].update(change)
                            self.write()
                        with self.observe_preparation(kind, withdraw) as prepared:
                            result = read_image_route(base, url)
                        prepared.assert_called_once()
                        self.assert_withheld(result, status, before)
            self.creds = copy.deepcopy(initial)
            self.write()
            self.assertEqual(read_image_route(base, path + "/" + image_id)[:2], (200, raw))

    def test_preparation_failure_rolls_back_receipt_and_returns_sanitized_error(self):
        with running_server(create_app(self.settings)) as base:
            patient, path, image_id, _ = self.prepare(base)
            for kind, url in (("index", path), ("binary", path + "/" + image_id)):
                with self.subTest(kind=kind):
                    before = self.read_events()
                    def fail():
                        raise RuntimeError("PRIVATE-IMAGE-PREPARE")
                    with self.observe_preparation(kind, fail) as prepared:
                        result = read_image_route(base, url)
                    prepared.assert_called_once()
                    self.assert_withheld(result, 503, before)

    def test_original_owner_locks_and_uncommitted_receipt_cover_response_preparation(self):
        with running_server(create_app(self.settings)) as base:
            patient, path, image_id, raw = self.prepare(base)
            for kind, url in (("index", path), ("binary", path + "/" + image_id)):
                with self.subTest(kind=kind):
                    before = self.read_events()
                    seen = {}
                    def observe():
                        seen["events"] = self.read_events()
                        seen["locks"] = []
                        for sql, params in (
                            ("SELECT patient_id FROM identity.identity_patients WHERE patient_id=:p FOR UPDATE NOWAIT", {"p": patient}),
                            ("SELECT case_id FROM coordination.patient_case_bindings WHERE case_id=:c FOR UPDATE NOWAIT", {"c": "CASE-ALPHA"}),
                        ):
                            with self.engine.connect() as connection:
                                try:
                                    connection.execute(text(sql), params).scalar_one()
                                except DBAPIError as error:
                                    details = error.orig.args[0] if error.orig.args else None
                                    seen["locks"].append(details.get("C") if isinstance(details, dict) else None)
                                else:
                                    seen["locks"].append("acquired")
                    with self.observe_preparation(kind, observe) as prepared:
                        status, body, headers = read_image_route(base, url)
                    prepared.assert_called_once()
                    self.assertEqual(status, 200)
                    self.assertEqual(seen["events"], before)
                    self.assertEqual(seen["locks"], ["55P03", "55P03"])
                    receipt = body["access_receipt_id"] if kind == "index" else headers["X-OI-Access-Receipt"]
                    after = self.read_events()
                    self.assertEqual(len(after), len(before) + 1)
                    self.assertEqual(after[-1][1]["receipt_id"], receipt)
                    if kind == "binary":
                        self.assertEqual(body, raw)

    def test_missing_provider_during_preparation_withholds_bytes_and_receipt(self):
        with running_server(create_app(self.settings)) as base:
            patient, path, image_id, _ = self.prepare(base)
            for kind, url in (("index", path), ("binary", path + "/" + image_id)):
                with self.subTest(kind=kind):
                    self.write()
                    before = self.read_events()
                    with self.observe_preparation(kind, self.access.unlink) as prepared:
                        result = read_image_route(base, url)
                    prepared.assert_called_once()
                    self.assert_withheld(result, 503, before)
            self.write()
