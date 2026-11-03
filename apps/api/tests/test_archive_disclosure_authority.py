"""Actual PostgreSQL/HTTP convergence; controlled archive, never a live PACS.

Exercise both transaction phases using the existing independently fictional
source/image fixture. Production binary response construction still executes.
"""
import copy
from datetime import datetime, timedelta, timezone
import json
from unittest.mock import Mock, patch
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


def read_original(base, path):
    opener = build_opener(ProxyHandler({}))
    try:
        reply = opener.open(Request(base + path, headers={
            "Authorization": "Bearer " + TOKEN_A}), timeout=8)
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


class ArchiveDisclosureAuthorityTests(SourceVersionFixture):
    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend([
            "image_import", "image_read", "image_original_read"])
        self.write()
        self.raw = image_bytes()
        self.archive = Mock()
        self.archive.read.return_value = self.raw

    def prepare(self, base):
        patient = self.setup_case(base)
        status, source, _ = self.ingest(base, patient, REPORT)
        self.assertEqual(status, 201)
        path = self.url(patient) + "/" + source["source_id"] + "/images"
        status, image, _ = image_request(base, path, raw=self.raw)
        self.assertEqual(status, 201)
        self.archive.read.assert_not_called()
        return patient, path + "/" + image["image_id"]

    def events(self):
        with self.engine.connect() as connection:
            return connection.execute(text(
                "SELECT metadata_json FROM identity.identity_domain_events "
                "WHERE event_type='image.original_read_authorized' ORDER BY id"
            )).scalars().all()

    def withheld(self, result, status, before, *, unavailable_detail="Patient registry unavailable"):
        self.assertEqual(result[0], status)
        if status == 503:
            self.assertEqual(result[1], {"detail": unavailable_detail})
        self.assertIsInstance(result[1], dict)
        self.assertEqual(set(result[1]), {"detail"})
        self.assertEqual(result[2]["Cache-Control"], "no-store")
        self.assertNotIn("X-OI-Access-Receipt", result[2])
        for secret in ("PRIVATE-ARCHIVE-PREPARE", TOKEN_A, "2.25.103", "DICM"):
            self.assertNotIn(secret, json.dumps(result[1]))
        self.assertEqual(self.events(), before)

    def preparing(self, effect):
        original = routes.Response
        def construct(*args, **kwargs):
            prepared = original(*args, **kwargs)
            if kwargs.get("media_type") == "application/dicom":
                effect()
            return prepared
        return patch.object(routes, "Response", side_effect=construct)

    def locks(self, patient):
        observed = []
        for sql, params in (
            ("SELECT patient_id FROM identity.identity_patients WHERE patient_id=:p FOR UPDATE NOWAIT", {"p": patient}),
            ("SELECT case_id FROM coordination.patient_case_bindings WHERE case_id=:c FOR UPDATE NOWAIT", {"c": "CASE-ALPHA"}),
        ):
            with self.engine.connect() as connection:
                try:
                    connection.execute(text(sql), params).scalar_one()
                except DBAPIError as error:
                    details = error.orig.args[0] if error.orig.args else None
                    observed.append(details.get("C") if isinstance(details, dict) else None)
                else:
                    observed.append("acquired")
        return observed

    def test_late_authority_after_remote_response_preparation_withholds_bytes(self):
        with running_server(create_app(self.settings, image_archive=self.archive)) as base:
            _, path = self.prepare(base)
            initial = copy.deepcopy(self.creds)
            changes = [
                ({"actions": [a for a in initial[0]["actions"] if a != "image_original_read"]}, 404),
                ({"actions": [a for a in initial[0]["actions"] if a != "patient_read"]}, 404),
                ({"patient_ids": []}, 404), ({"actor": "ACTOR-CHANGED"}, 404),
                ({"organization": "ORG-CHANGED"}, 404), ({"purpose": "research"}, 404),
                ({"expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()}, 401),
            ]
            for change, status in changes:
                with self.subTest(change=list(change)):
                    self.creds = copy.deepcopy(initial)
                    self.write()
                    before = self.events()
                    calls = self.archive.read.call_count
                    def withdraw():
                        self.creds[0].update(change)
                        self.write()
                    with self.preparing(withdraw):
                        result = read_original(base, path)
                    self.assertEqual(self.archive.read.call_count, calls + 1)
                    self.withheld(result, status, before)
            self.creds = initial
            self.write()
            self.assertEqual(read_original(base, path)[:2], (200, self.raw))

    def test_missing_provider_after_remote_preparation_withholds_receipt(self):
        with running_server(create_app(self.settings, image_archive=self.archive)) as base:
            _, path = self.prepare(base)
            before = self.events()
            with self.preparing(self.access.unlink):
                result = read_original(base, path)
            self.archive.read.assert_called_once()
            # Authentication preserves its own sanitized provider-unavailable
            # contract; this is not a database/response-construction failure.
            self.withheld(result, 503, before,
                          unavailable_detail="Access service unavailable")

    def test_failed_remote_response_construction_rolls_back_read_receipt(self):
        with running_server(create_app(self.settings, image_archive=self.archive)) as base:
            _, path = self.prepare(base)
            before = self.events()
            def fail():
                raise RuntimeError("PRIVATE-ARCHIVE-PREPARE")
            with self.preparing(fail):
                result = read_original(base, path)
            self.archive.read.assert_called_once()
            self.withheld(result, 503, before)

    def test_locks_are_free_during_fetch_and_held_through_preparation(self):
        with running_server(create_app(self.settings, image_archive=self.archive)) as base:
            patient, path = self.prepare(base)
            before = self.events()
            seen = {}
            def fetch(*identifiers):
                seen["identifiers"] = identifiers
                seen["fetch_locks"] = self.locks(patient)
                seen["fetch_events"] = self.events()
                return self.raw
            def prepare():
                seen["prepare_locks"] = self.locks(patient)
                seen["prepare_events"] = self.events()
            self.archive.read.side_effect = fetch
            with self.preparing(prepare):
                result = read_original(base, path)
            self.assertEqual(result[:2], (200, self.raw))
            self.assertEqual(seen["identifiers"], ("2.25.101", "2.25.102", "2.25.103"))
            self.assertEqual(seen["fetch_locks"], ["acquired", "acquired"])
            self.assertEqual(seen["fetch_events"], before)
            self.assertEqual(seen["prepare_locks"], ["55P03", "55P03"])
            self.assertEqual(seen["prepare_events"], before)
            after = self.events()
            self.assertEqual(len(after), len(before) + 1)
            self.assertEqual(after[-1]["receipt_id"], result[2]["X-OI-Access-Receipt"])

    def test_deferred_commit_failure_withholds_prepared_remote_response(self):
        with running_server(create_app(self.settings, image_archive=self.archive)) as base:
            _, path = self.prepare(base)
            with self.engine.begin() as connection:
                connection.exec_driver_sql("""
                    CREATE FUNCTION identity.fail_archive_disclosure_commit() RETURNS trigger
                    LANGUAGE plpgsql AS $$ BEGIN
                    IF NEW.event_type='image.original_read_authorized' THEN
                        RAISE EXCEPTION 'PRIVATE-ARCHIVE-PREPARE';
                    END IF;
                    RETURN NEW; END; $$;
                """)
                connection.exec_driver_sql("""
                    CREATE CONSTRAINT TRIGGER reject_archive_disclosure_commit
                    AFTER INSERT ON identity.identity_domain_events
                    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
                    EXECUTE FUNCTION identity.fail_archive_disclosure_commit()
                """)
            before = self.events()
            prepared = []
            with self.preparing(lambda: prepared.append(True)):
                result = read_original(base, path)
            self.archive.read.assert_called_once()
            self.assertEqual(prepared, [True])
            self.withheld(result, 503, before)

    def test_patient_suspension_during_fetch_withholds_and_prevents_next_fetch(self):
        with running_server(create_app(self.settings, image_archive=self.archive)) as base:
            patient, path = self.prepare(base)
            before = self.events()
            def suspend(*identifiers):
                with self.engine.begin() as connection:
                    connection.execute(text(
                        "UPDATE identity.identity_patients SET status='suspended',revision=revision+1 "
                        "WHERE patient_id=:p"), {"p": patient})
                return self.raw
            self.archive.read.side_effect = suspend
            self.withheld(read_original(base, path), 404, before)
            self.archive.read.assert_called_once()
            self.archive.read.reset_mock()
            self.withheld(read_original(base, path), 404, before)
            self.archive.read.assert_not_called()
