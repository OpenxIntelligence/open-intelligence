"""Actual PG16 and HTTP image custody, using independently authored originals."""

from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import threading
import time
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import ProxyHandler, Request, build_opener

from sqlalchemy import text

from oi_api.app import create_app
from oi_api.images import PostgresSourceImages
from open_intelligence.postgres_registry import PostgresPatientRegistry
from http_support import running_server
from test_patients import TOKEN_A, TOKEN_B, request
from test_source_versions import SourceVersionFixture
from dicom_integrity_fixture import dicom_bytes


REPORT = (
    "OI-SYNTHETIC-REPORT/1\nPatient: CASE-ALPHA\nDocument: DOC-IMAGE\n"
    "Type: imaging\nEvent-Date: 2026-02-01\nIssued-At: 2026-02-02\n"
    "Finding: image|not-assessed|Independently authored engineering image; no clinical finding.\n"
)
AMENDED = REPORT.replace("2026-02-02\n", "2026-02-03\nAmends: DOC-IMAGE@1\n").replace(
    "no clinical finding.", "amended fictional report; no clinical finding.")


def image_bytes(**changes):
    values = dict(patient_id="SUBJECT-ALPHA", issuer="ORG-INSTITUTION/SYS-SYNTH",
                  study_uid="2.25.101", series_uid="2.25.102", sop_uid="2.25.103",
                  study_date="20260201")
    values.update(changes)
    return dicom_bytes(**values)


def image_request(base, path, *, token=TOKEN_A, raw=None, headers=None):
    selected = {"Authorization": "Bearer " + token}
    if raw is not None:
        selected["Content-Type"] = "application/dicom"
    selected.update(headers or {})
    opener = build_opener(ProxyHandler({}))
    try:
        response = opener.open(Request(base + path, data=raw, headers=selected), timeout=8)
    except HTTPError as error:
        response = error
    with response:
        content = response.read()
        result = content if response.headers.get_content_type() == "application/dicom" else json.loads(content)
        return response.status, result, response.headers


class ImageCustodyHTTPTests(SourceVersionFixture):
    def setUp(self):
        super().setUp()
        for credential in self.creds:
            credential["actions"].extend(["image_import", "image_read", "image_original_read"])
        self.write()

    def prepare(self, base):
        patient = self.setup_case(base)
        status, receipt, _ = self.ingest(base, patient, REPORT)
        self.assertEqual(status, 201)
        source = receipt["source_id"]
        return patient, source, self.url(patient) + "/" + source + "/images"

    def rows(self, sql):
        with self.engine.connect() as connection:
            return connection.execute(text(sql)).all()

    def events(self, suffix=""):
        return self.rows("SELECT event_type,metadata_json FROM identity.identity_domain_events "
                         "WHERE event_type LIKE 'image.%' " + suffix + " ORDER BY id")

    def test_exact_originals_idempotency_index_receipts_and_restart(self):
        originals = [image_bytes(), image_bytes(sop_uid="2.25.104", pixels=b"\x01\x00" * 4)]
        with running_server(create_app(self.settings)) as base:
            patient, source, path = self.prepare(base)
            ids = []
            for raw in originals:
                status, stored, _ = image_request(base, path, raw=raw)
                self.assertEqual((status, stored["result"]), (201, "imported"))
                self.assertEqual(stored["sha256"], hashlib.sha256(raw).hexdigest())
                self.assertEqual(stored["byte_count"], len(raw))
                self.assertFalse(stored["source_identity_verified"])
                ids.append(stored["image_id"])
                duplicate = image_request(base, path, raw=raw)
                self.assertEqual((duplicate[0], duplicate[1]["result"], duplicate[1]["image_id"]),
                                 (200, "duplicate", stored["image_id"]))
            status, index, _ = request(base, path, token=TOKEN_A)
            self.assertEqual(status, 200)
            self.assertEqual({item["image_id"] for item in index["images"]}, set(ids))
            receipts = [index["access_receipt_id"]]
            for image_id, raw in zip(ids, originals):
                code, retrieved, headers = image_request(base, path + "/" + image_id)
                self.assertEqual((code, retrieved), (200, raw))
                self.assertEqual(headers.get_content_type(), "application/dicom")
                self.assertEqual(headers["Cache-Control"], "no-store")
                self.assertIn('filename="original.dcm"', headers["Content-Disposition"])
                receipts.append(headers["X-OI-Access-Receipt"])
            self.assertEqual(len(set(receipts)), 3)
        with running_server(create_app(self.settings)) as base:
            for image_id, raw in zip(ids, originals):
                self.assertEqual(image_request(base, path + "/" + image_id)[:2], (200, raw))
        self.assertEqual(self.rows("SELECT count(*) FROM clinical_source.dicom_objects")[0][0], 2)
        self.assertEqual(self.rows("SELECT count(*) FROM clinical_source.source_image_links")[0][0], 2)
        events = self.events()
        self.assertEqual(sum(event[0] == "image.original_imported" for event in events), 2)
        for private in (TOKEN_A, "SUBJECT-ALPHA", "SYS-SYNTH", "2.25.103"):
            self.assertNotIn(private, json.dumps(events))

    def test_original_identity_date_and_parent_are_verified_before_custody(self):
        with running_server(create_app(self.settings)) as base:
            patient, source, path = self.prepare(base)
            for changes in ({"patient_id": "SUBJECT-BETA"}, {"issuer": "OTHER-SYSTEM"},
                            {"issuer": "SYS-SYNTH"},
                            {"study_date": "20260202"}):
                with self.subTest(changes=changes):
                    status, result, _ = image_request(base, path, raw=image_bytes(**changes))
                    self.assertEqual((status, result), (422, {"detail": "Invalid request"}))
            other = REPORT.replace("DOC-IMAGE", "DOC-NOT-IMAGE").replace("Type: imaging", "Type: clinical")
            other_id = self.ingest(base, patient, other)[1]["source_id"]
            self.assertEqual(image_request(base, self.url(patient) + "/" + other_id + "/images", raw=image_bytes())[0], 404)
            self.assertEqual(image_request(base, path, raw=b"\0" * 128 + b"DICM")[0], 422)
        self.assertEqual(self.rows("SELECT count(*) FROM clinical_source.dicom_objects")[0][0], 0)
        self.assertEqual(self.events(), [])

    def test_equal_subject_and_system_in_distinct_source_organizations_do_not_share_images(self):
        with running_server(create_app(self.settings)) as base:
            patient, source, path = self.prepare(base)
            self.assertEqual(image_request(base, path, raw=image_bytes())[0], 201)
            status, created, _ = request(base, "/v1/patients", token=TOKEN_A,
                                         body={"synthetic": True, "request_key": "OTHER-SOURCE-PATIENT"})
            self.assertEqual(status, 201)
            other = created["patient_id"]
            self.creds[0]["patient_ids"].append(other)
            self.write()
            self.assertEqual(request(base, f"/v1/patients/{other}/case-bindings", token=TOKEN_A, body={
                "synthetic": True, "case_id": "CASE-OTHER", "source_organization": "ORG-OTHER",
                "source_system": "SYS-SYNTH", "source_subject_ref": "SUBJECT-ALPHA",
                "review_ref": "REVIEW-SYNTH"})[0], 201)
            source_id = self.ingest(base, other, REPORT.replace("CASE-ALPHA", "CASE-OTHER"), case="CASE-OTHER")[1]["source_id"]
            other_path = self.url(other, "CASE-OTHER") + "/" + source_id + "/images"
            self.assertEqual(image_request(base, other_path, raw=image_bytes())[0], 422)
            other_bytes = image_bytes(issuer="ORG-OTHER/SYS-SYNTH", sop_uid="2.25.108")
            self.assertEqual(image_request(base, other_path, raw=other_bytes)[0], 201)

    def test_same_sop_changed_bytes_conflict_and_amendment_needs_explicit_new_link(self):
        raw = image_bytes()
        with running_server(create_app(self.settings)) as base:
            patient, source, path = self.prepare(base)
            image_id = image_request(base, path, raw=raw)[1]["image_id"]
            self.assertEqual(image_request(base, path, raw=image_bytes(pixels=b"\x02\x00" * 4))[0], 409)
            amended_source = self.ingest(base, patient, AMENDED)[1]["source_id"]
            amended_path = self.url(patient) + "/" + amended_source + "/images"
            for url, original in ((path, None), (path + "/" + image_id, None), (path, raw)):
                self.assertEqual(image_request(base, url, raw=original)[0], 404)
            self.assertEqual(request(base, amended_path, token=TOKEN_A)[1]["images"], [])
            self.assertEqual(image_request(base, amended_path + "/" + image_id)[0], 404)
            code, receipt, _ = image_request(base, amended_path, raw=raw)
            self.assertEqual((code, receipt["result"], receipt["image_id"]), (201, "linked", image_id))
            self.assertEqual(image_request(base, amended_path + "/" + image_id)[:2], (200, raw))
            # Historical text remains readable through its established owner.
            self.assertEqual(request(base, self.url(patient) + "/" + source, token=TOKEN_A)[1]["original_text"], REPORT)
        self.assertEqual(self.rows("SELECT count(*) FROM clinical_source.dicom_objects")[0][0], 1)
        self.assertEqual(self.rows("SELECT count(*) FROM clinical_source.source_image_links")[0][0], 2)

    def test_same_sop_changed_date_is_conflict_rather_than_stored_corruption(self):
        with running_server(create_app(self.settings)) as base:
            patient, source, path = self.prepare(base)
            self.assertEqual(image_request(base, path, raw=image_bytes())[0], 201)
            later = REPORT.replace("DOC-IMAGE", "DOC-LATER").replace("Event-Date: 2026-02-01", "Event-Date: 2026-02-02")
            source_id = self.ingest(base, patient, later)[1]["source_id"]
            new_path = self.url(patient) + "/" + source_id + "/images"
            self.assertEqual(image_request(base, new_path, raw=image_bytes(study_date="20260202"))[0], 409)
            self.assertEqual(self.rows("SELECT count(*) FROM clinical_source.source_image_links")[0][0], 1)

    def test_cross_patient_org_case_and_independent_grants_never_disclose_original(self):
        with running_server(create_app(self.settings)) as base:
            patient, source, path = self.prepare(base)
            image_id = image_request(base, path, raw=image_bytes())[1]["image_id"]
            other = self.setup_case(base, token=TOKEN_B, case="CASE-BETA", key="CREATE-BETA", source_subject="SUBJECT-BETA")
            for url, token in ((path, TOKEN_B), (path + "/" + image_id, TOKEN_B),
                               (path.replace(patient, other), TOKEN_A),
                               (path.replace("CASE-ALPHA", "CASE-BETA"), TOKEN_A)):
                self.assertEqual(image_request(base, url, token=token)[0], 404)
            initial = list(self.creds[0]["actions"])
            for action, url, raw in (("image_import", path, image_bytes()),
                                     ("image_read", path, None),
                                     ("image_original_read", path + "/" + image_id, None),
                                     ("patient_read", path + "/" + image_id, None)):
                self.creds[0]["actions"] = [item for item in initial if item != action]
                self.write()
                self.assertEqual(image_request(base, url, raw=raw)[0], 404)
            # Source-only legacy grants do not acquire any image permission.
            self.creds[0]["actions"] = [item for item in initial if not item.startswith("image_")]
            self.write()
            self.assertEqual(request(base, self.url(patient), token=TOKEN_A)[0], 200)
            self.assertEqual(image_request(base, path + "/" + image_id)[0], 404)
        self.assertEqual(self.events("AND event_type LIKE '%read_authorized'"), [])

    def test_late_authority_changes_withhold_import_index_and_original(self):
        fetchone = PostgresPatientRegistry._fetchone
        with running_server(create_app(self.settings)) as base:
            patient, source, path = self.prepare(base)
            image_id = image_request(base, path, raw=image_bytes())[1]["image_id"]
            initial = json.loads(json.dumps(self.creds))
            changes = [({"patient_ids": []}, 404), ({"actor": "ACTOR-CHANGED"}, 404),
                       ({"organization": "ORG-CHANGED"}, 404), ({"purpose": "research"}, 404),
                       ({"actions": ["patient_read", "source_read"]}, 404),
                       ({"expires_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()}, 401)]
            for change, expected in changes:
                for url, raw in ((path, None), (path + "/" + image_id, None), (path, image_bytes()),
                                 (path, image_bytes(sop_uid="2.25.106"))):
                    with self.subTest(change=list(change), endpoint=url.rsplit("/", 1)[-1], upload=raw is not None):
                        self.creds = json.loads(json.dumps(initial))
                        self.write()
                        def alter(registry, sql, params=()):
                            value = fetchone(registry, sql, params)
                            if "SELECT raw,sha256" in sql:
                                self.creds[0].update(change)
                                self.write()
                            return value
                        with patch.object(PostgresPatientRegistry, "_fetchone", alter):
                            status, result, _ = image_request(base, url, raw=raw)
                        self.assertEqual(status, expected)
                        self.assertNotIsInstance(result, bytes)
            self.assertEqual(self.events("AND event_type LIKE '%read_authorized'"), [])
            self.assertEqual(len(self.events()), 1)
            self.assertEqual(self.rows("SELECT count(*) FROM clinical_source.dicom_objects")[0][0], 1)

    def test_binding_revocation_and_purpose_mismatch_fail_closed(self):
        with running_server(create_app(self.settings)) as base:
            patient, source, path = self.prepare(base)
            image_id = image_request(base, path, raw=image_bytes())[1]["image_id"]
            self.creds[0]["purpose"] = "research"
            self.write()
            self.assertEqual(image_request(base, path + "/" + image_id)[0], 404)
            self.creds[0]["purpose"] = "operations"
            self.write()
            self.assertEqual(request(base, f"/v1/patients/{patient}/case-bindings/CASE-ALPHA/revoke", token=TOKEN_A,
                                     body={"synthetic": True, "reason": "Authored mapping withdrawal"})[0], 200)
            for url, raw in ((path, None), (path + "/" + image_id, None), (path, image_bytes())):
                self.assertEqual(image_request(base, url, raw=raw)[0], 404)
            self.assertEqual(self.events("AND event_type LIKE '%read_authorized'"), [])

    def test_late_authority_withdrawal_rolls_back_an_explicit_amendment_link(self):
        fetch = PostgresPatientRegistry._fetchone
        with running_server(create_app(self.settings)) as base:
            patient, source, path = self.prepare(base)
            image_request(base, path, raw=image_bytes())
            new_source = self.ingest(base, patient, AMENDED)[1]["source_id"]
            new_path = self.url(patient) + "/" + new_source + "/images"
            def withdraw(registry, sql, params=()):
                result = fetch(registry, sql, params)
                if "SELECT raw,sha256" in sql:
                    self.creds[0]["patient_ids"] = []
                    self.write()
                return result
            with patch.object(PostgresPatientRegistry, "_fetchone", withdraw):
                self.assertEqual(image_request(base, new_path, raw=image_bytes())[0], 404)
            self.assertEqual(self.rows("SELECT count(*) FROM clinical_source.source_image_links")[0][0], 1)
            self.assertEqual(len(self.events()), 1)

    def test_event_failure_rolls_back_import_and_withholds_index_and_original(self):
        with running_server(create_app(self.settings)) as base:
            patient, source, path = self.prepare(base)
            image_id = image_request(base, path, raw=image_bytes())[1]["image_id"]
            with self.engine.begin() as connection:
                connection.exec_driver_sql("""CREATE FUNCTION identity.fail_image_event() RETURNS trigger
                    LANGUAGE plpgsql AS $$ BEGIN IF NEW.event_type LIKE 'image.%' THEN
                    RAISE EXCEPTION 'PRIVATE-IMAGE-EVENT-FAILURE'; END IF; RETURN NEW; END; $$;
                    CREATE TRIGGER fail_image_event BEFORE INSERT ON identity.identity_domain_events
                    FOR EACH ROW EXECUTE FUNCTION identity.fail_image_event();""")
            for url, raw in ((path, image_bytes(sop_uid="2.25.105")), (path, None), (path + "/" + image_id, None)):
                self.assertEqual(image_request(base, url, raw=raw)[:2],
                                 (503, {"detail": "Patient registry unavailable"}))
            self.assertEqual(len(self.events()), 1)
            self.assertEqual(self.rows("SELECT count(*) FROM clinical_source.dicom_objects")[0][0], 1)

    def test_database_immutability_and_cross_case_links_are_guarded(self):
        with running_server(create_app(self.settings)) as base:
            patient, source, path = self.prepare(base)
            image_id = image_request(base, path, raw=image_bytes())[1]["image_id"]
            other = self.setup_case(base, token=TOKEN_B, case="CASE-BETA", key="CREATE-BETA", source_subject="SUBJECT-BETA")
            other_source = self.ingest(base, other, REPORT.replace("CASE-ALPHA", "CASE-BETA"), case="CASE-BETA", token=TOKEN_B)[1]["source_id"]
            for sql in ("UPDATE clinical_source.dicom_objects SET sha256=repeat('0',64)",
                        "DELETE FROM clinical_source.dicom_objects", "DELETE FROM clinical_source.source_image_links",
                        "UPDATE clinical_source.source_image_links SET created_at=now()"):
                with self.subTest(sql=sql), self.assertRaises(Exception):
                    with self.engine.begin() as connection:
                        connection.exec_driver_sql(sql)
            with self.assertRaises(Exception), self.engine.begin() as connection:
                connection.execute(text("INSERT INTO clinical_source.source_image_links(source_id,image_id) VALUES (:s,:i)"),
                                   {"s": other_source, "i": image_id})
            self.assertEqual(image_request(base, path + "/" + image_id)[:2], (200, image_bytes()))

    def test_stored_byte_or_metadata_corruption_is_unavailable_even_with_rehashed_bytes(self):
        # Authorized fixture DBA disables one immutability trigger solely to
        # exercise defense-in-depth on reads; ordinary writes cannot do this.
        with running_server(create_app(self.settings)) as base:
            patient, source, path = self.prepare(base)
            image_id = image_request(base, path, raw=image_bytes())[1]["image_id"]
            original = image_bytes()
            corrupt = image_bytes(patient_id="SUBJECT-OTHER")
            for raw, digest in ((original[:-2] + b"XX", hashlib.sha256(original).hexdigest()),
                                (corrupt, hashlib.sha256(corrupt).hexdigest())):
                with self.engine.begin() as connection:
                    connection.exec_driver_sql("ALTER TABLE clinical_source.dicom_objects DISABLE TRIGGER oi_image_update_guard")
                    connection.execute(text("UPDATE clinical_source.dicom_objects SET raw=:raw,sha256=:sha,byte_count=:n WHERE image_id=:id"),
                                       {"raw": raw, "sha": digest, "n": len(raw), "id": image_id})
                    connection.exec_driver_sql("ALTER TABLE clinical_source.dicom_objects ENABLE TRIGGER oi_image_update_guard")
                self.assertEqual(image_request(base, path + "/" + image_id)[:2],
                                 (503, {"detail": "Patient registry unavailable"}))
            self.assertEqual(self.events("AND event_type LIKE '%read_authorized'"), [])

    def test_caller_metadata_overrides_and_unsupported_transport_are_rejected(self):
        with running_server(create_app(self.settings)) as base:
            patient, source, path = self.prepare(base)
            for query in ("?sha256=" + "a" * 64, "?sop_uid=2.25.999", "?url=http://127.0.0.1/"):
                self.assertEqual(image_request(base, path + query, raw=image_bytes())[0], 422)
            for headers in ({"Content-Type": "application/octet-stream"}, {"Content-Encoding": "gzip"}):
                self.assertEqual(image_request(base, path, raw=image_bytes(), headers=headers)[0], 415)
            self.assertEqual(self.events(), [])

    def test_local_read_and_amendment_are_serialized_before_later_reads_are_denied(self):
        """Observe the actual PG lock, without claiming distributed revocation."""
        entered, release = threading.Event(), threading.Event()
        validate = PostgresSourceImages._validated_object
        with running_server(create_app(self.settings)) as base:
            patient, source, path = self.prepare(base)
            image_id = image_request(base, path, raw=image_bytes())[1]["image_id"]
            def pause(owner, row, parent, binding):
                original = validate(owner, row, parent, binding)
                entered.set()
                if not release.wait(6):
                    raise RuntimeError("Authored synchronization timeout")
                return original
            with ThreadPoolExecutor(max_workers=2) as pool:
                with patch.object(PostgresSourceImages, "_validated_object", pause):
                    reading = pool.submit(image_request, base, path + "/" + image_id)
                    try:
                        self.assertTrue(entered.wait(5))
                        amendment = pool.submit(self.ingest, base, patient, AMENDED)
                        deadline = time.monotonic() + 1.5
                        blocked = False
                        while time.monotonic() < deadline:
                            blocked = bool(self.rows(
                                "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                                "AND wait_event_type='Lock' AND query LIKE '%patient_case_bindings%'")[0][0])
                            if blocked:
                                break
                            time.sleep(0.01)
                        self.assertTrue(blocked, "Amendment did not reach the held canonical case lock")
                        self.assertFalse(amendment.done())
                    finally:
                        release.set()
                    self.assertEqual(reading.result(timeout=6)[:2], (200, image_bytes()))
                    self.assertEqual(amendment.result(timeout=6)[0], 201)
            self.assertEqual(image_request(base, path + "/" + image_id)[0], 404)
            events = self.rows("SELECT event_type FROM identity.identity_domain_events ORDER BY id")
            self.assertEqual([row[0] for row in events][-2:],
                             ["image.original_read_authorized", "source.original.imported"])

    def test_case_object_and_byte_budgets_reject_new_objects_but_keep_identical_retries(self):
        with running_server(create_app(self.settings)) as base:
            patient, source, path = self.prepare(base)
            raw = image_bytes()
            image_request(base, path, raw=raw)
            for policy, limit in (("MAX_CASE_IMAGES", 1), ("MAX_CASE_IMAGE_BYTES", len(raw))):
                with self.subTest(policy=policy), patch("oi_api.images." + policy, limit):
                    self.assertEqual(image_request(base, path, raw=image_bytes(sop_uid="2.25.107"))[0], 409)
                    self.assertEqual(image_request(base, path, raw=raw)[0], 200)
            self.assertEqual(self.rows("SELECT count(*) FROM clinical_source.dicom_objects")[0][0], 1)
