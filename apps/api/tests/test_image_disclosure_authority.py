"""Actual PG16/HTTP: image response preparation belongs inside source authority.

Uses the existing independently fictional image/source fixture. Production
renderers still run; only the credential change is injected after preparation.
No external PACS, patient record, new schema or alternate registry is used.

Preserves the final-preparation regressions from PR #253 against the combined
canonical source/question/image owner. The source fixture has no inherited test
methods. Encoding and deferred-commit regressions also preserve the completed
#253 response boundary across the combined owner's image import paths.
"""
import copy
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from fastapi import routing as fastapi_routing
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from oi_api import patients as routes
from oi_api.app import create_app
from http_support import running_server
from test_patients import TOKEN_A
from test_source_versions import SourceVersionFixture
from test_image_custody import AMENDED, REPORT, image_bytes, image_request


def read_image_route(base, path, *, raw=None):
    opener = build_opener(ProxyHandler({}))
    headers = {"Authorization": "Bearer " + TOKEN_A}
    if raw is not None:
        headers["Content-Type"] = "application/dicom"
    try:
        reply = opener.open(Request(base + path, headers=headers, data=raw), timeout=8)
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

    def custody_state(self):
        """Observe durable object/link/event identity, without copying raw bytes."""
        with self.engine.connect() as connection:
            objects = connection.execute(text(
                "SELECT image_id,case_id,sha256,byte_count FROM clinical_source.dicom_objects "
                "ORDER BY image_id"
            )).all()
            links = connection.execute(text(
                "SELECT source_id,image_id FROM clinical_source.source_image_links "
                "ORDER BY source_id,image_id"
            )).all()
            events = connection.execute(text(
                "SELECT id,event_type,metadata_json FROM identity.identity_domain_events "
                "WHERE event_type LIKE 'image.%' ORDER BY id"
            )).all()
        return {"objects": [tuple(row) for row in objects],
                "links": [tuple(row) for row in links],
                "events": [(row[0], row[1], dict(row[2])) for row in events]}

    def prepare_encoding_operations(self, base, suffix):
        # Each failure mode has an independently qualified fictional case. A
        # failing baseline import must not turn another mode's new import into
        # a duplicate and obscure which response boundary is being exercised.
        case = "CASE-JSON-" + suffix
        subject = "SUBJECT-JSON-" + suffix
        patient = self.setup_case(base, case=case, key="CREATE-JSON-" + suffix,
                                  source_subject=subject)
        status, first_source, _ = self.ingest(
            base, patient, REPORT.replace("CASE-ALPHA", case), case=case)
        self.assertEqual(status, 201)
        old_path = self.url(patient, case) + "/" + first_source["source_id"] + "/images"
        first = image_bytes(patient_id=subject)
        second = image_bytes(patient_id=subject, sop_uid="2.25.104")
        for raw in (first, second):
            self.assertEqual(image_request(base, old_path, raw=raw)[0], 201)
        status, amended, _ = self.ingest(
            base, patient, AMENDED.replace("CASE-ALPHA", case), case=case)
        self.assertEqual(status, 201)
        path = self.url(patient, case) + "/" + amended["source_id"] + "/images"
        status, linked, _ = image_request(base, path, raw=first)
        self.assertEqual((status, linked["result"]), (201, "linked"))
        return (
            ("new_object", path, image_bytes(patient_id=subject, sop_uid="2.25.105"),
             "image_import", "imported"),
            ("identical_retry", path, first, "image_import", "duplicate"),
            ("explicit_relink", path, second, "image_import", "linked"),
            ("index", path, None, "image_read", None),
        )

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

    @contextmanager
    def observe_json_encoding(self, effect):
        """Observe actual encoded bytes on both existing framework paths.

        The unfixed typed-DTO route uses FastAPI's Pydantic dump_json fast path
        and skips JSONResponse.render. The prepared-response fix uses the real
        JSONResponse constructor and skips framework response serialization.
        Both wrappers run the original encoder first; error envelopes and
        intermediate dictionaries do not trigger the injected effect.
        """
        original_render = JSONResponse.render
        original_serialize = fastapi_routing.serialize_response

        def observe(encoded):
            if not isinstance(encoded, (bytes, str)):
                return
            envelope = json.loads(encoded)
            if isinstance(envelope, dict) and (
                    "images" in envelope or
                    {"image_id", "result"} <= envelope.keys()):
                effect(encoded)

        async def serialize(*args, **kwargs):
            encoded = await original_serialize(*args, **kwargs)
            if kwargs.get("dump_json") is True:
                observe(encoded)
            return encoded

        def render(response, content):
            encoded = original_render(response, content)
            observe(encoded)
            return encoded

        with patch.object(fastapi_routing, "serialize_response", serialize), \
                patch.object(JSONResponse, "render", render):
            yield

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

    def test_json_encoding_finishes_before_authority_recheck(self):
        # Observe both the unfixed Pydantic fast path and the prepared response,
        # so red evidence is disclosure/rollback failure after real encoding.
        with running_server(create_app(self.settings)) as base:
            for mode, status in (("WITHDRAW", 404), ("FAIL", 503)):
                operations = self.prepare_encoding_operations(base, mode)
                initial = copy.deepcopy(self.creds)
                for name, path, raw, action, expected_result in operations:
                    with self.subTest(mode=mode, operation=name):
                        before = self.custody_state()
                        reads_before = self.read_events()
                        rendered = []

                        def after_encoding(encoded):
                            rendered.append(encoded)
                            if mode == "FAIL":
                                raise RuntimeError("PRIVATE-IMAGE-PREPARE")
                            self.creds[0]["actions"].remove(action)
                            self.write()

                        try:
                            with self.observe_json_encoding(after_encoding):
                                result = read_image_route(base, path, raw=raw)
                        finally:
                            self.creds = copy.deepcopy(initial)
                            self.write()
                        self.assertEqual(len(rendered), 1)
                        envelope = json.loads(rendered[0])
                        if name == "index":
                            self.assertTrue(envelope["images"])
                        else:
                            self.assertEqual(envelope["result"], expected_result)
                        self.assert_withheld(result, status, reads_before)
                        if mode == "FAIL":
                            self.assertEqual(result[1], {"detail": "Patient registry unavailable"})
                        self.assertEqual(self.custody_state(), before)

    def test_deferred_database_commit_failure_withholds_already_prepared_response(self):
        with running_server(create_app(self.settings)) as base:
            _, path, image_id, raw = self.prepare(base)
            with self.engine.begin() as connection:
                connection.exec_driver_sql("""
                    CREATE FUNCTION identity.fail_image_disclosure_commit() RETURNS trigger
                    LANGUAGE plpgsql AS $$ BEGIN
                    IF NEW.event_type IN ('image.read_authorized','image.original_read_authorized') THEN
                        RAISE EXCEPTION 'PRIVATE-IMAGE-PREPARE';
                    END IF;
                    RETURN NEW; END; $$;
                """)
                connection.exec_driver_sql("""
                    CREATE CONSTRAINT TRIGGER reject_image_disclosure_commit
                    AFTER INSERT ON identity.identity_domain_events
                    DEFERRABLE INITIALLY DEFERRED
                    FOR EACH ROW EXECUTE FUNCTION identity.fail_image_disclosure_commit()
                """)
            try:
                for kind, url in (("index", path), ("binary", path + "/" + image_id)):
                    with self.subTest(kind=kind):
                        before = self.custody_state()
                        reads_before = self.read_events()
                        prepared = []
                        observer = (
                            self.observe_json_encoding(prepared.append)
                            if kind == "index" else
                            self.observe_preparation(kind, lambda: prepared.append(True))
                        )
                        with observer:
                            result = read_image_route(base, url)
                        self.assertEqual(len(prepared), 1)
                        if kind == "index":
                            self.assertTrue(json.loads(prepared[0])["images"])
                        self.assert_withheld(result, 503, reads_before)
                        self.assertEqual(result[1], {"detail": "Patient registry unavailable"})
                        self.assertEqual(self.custody_state(), before)
            finally:
                # Runs before SourceVersionFixture.tearDown drops the identity
                # schema. An addCleanup callback would run after tearDown.
                with self.engine.begin() as connection:
                    connection.exec_driver_sql(
                        "DROP TRIGGER IF EXISTS reject_image_disclosure_commit "
                        "ON identity.identity_domain_events")
                    connection.exec_driver_sql(
                        "DROP FUNCTION IF EXISTS identity.fail_image_disclosure_commit()")
            # A failed commit must not poison a subsequent legitimate request.
            self.assertEqual(read_image_route(base, path)[0], 200)
            self.assertEqual(read_image_route(base, path + "/" + image_id)[:2], (200, raw))
