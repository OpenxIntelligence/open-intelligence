"""Actual disposable Compose acceptance for H1 original-image custody.

Reuses the canonical registry, source, access-fixture and Compose owners. All
objects are independently authored by the stdlib-only test fixture generator;
no patient images, external PACS, optional codecs or new service are involved.
The returned receipts attest prepared disclosure, not delivery to a client.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener
import uuid


ROOT = Path(__file__).resolve().parents[3]
BASE = "http://127.0.0.1:8000"
CASE = "CASE-COMPOSE-IMAGE"
SUBJECT = "SUBJECT-IMAGE-COMPOSE"
SOURCE_SYSTEM = "SYS-IMAGE-COMPOSE"
ISSUER = "ORG-IMAGE-SOURCE/" + SOURCE_SYSTEM
STUDY = "2.25.112026110301"
SERIES = "2.25.112026110302"
SOPS = ("2.25.112026110303", "2.25.112026110304")
MAX_IMAGE_BYTES = 2_097_152
ACCESS_EVENTS = "'image.read_authorized','image.original_read_authorized'"
IMAGE_FIELDS = {
    "image_id", "source_id", "case_id", "sha256", "byte_count",
    "study_uid", "series_uid", "sop_uid", "modality", "study_date",
}
ORIGINAL = (
    "OI-SYNTHETIC-REPORT/1\nPatient: CASE-COMPOSE-IMAGE\nDocument: IMG-COMPOSE\n"
    "Type: imaging\nEvent-Date: 2026-05-17\nIssued-At: 2026-05-18\n"
    "Finding: image|pending|Independently fictional image review is pending.\n"
)
AMENDED = (
    "OI-SYNTHETIC-REPORT/1\nPatient: CASE-COMPOSE-IMAGE\nDocument: IMG-COMPOSE\n"
    "Type: imaging\nEvent-Date: 2026-05-17\nIssued-At: 2026-05-19\n"
    "Amends: IMG-COMPOSE@1\n"
    "Finding: image|not-assessed|Independently fictional amended image review is not assessed.\n"
)


def authored_originals():
    # Share the security owner's independent fixture; do not import vendor data
    # or construct a second DICOM parser in this acceptance helper.
    sys.path.insert(0, str(ROOT / "apps/api/tests"))
    from dicom_integrity_fixture import dicom_bytes

    return tuple(dicom_bytes(patient_id=SUBJECT, issuer=ISSUER,
                             study_uid=STUDY, series_uid=SERIES, sop_uid=sop,
                             study_date="20260517",
                             pixels=bytes((offset, 0, offset + 1, 0,
                                           offset + 2, 0, offset + 3, 0)))
                 for sop, offset in zip(SOPS, (0, 10)))


def main():
    if shutil.which("docker") is None:
        raise RuntimeError("Docker CLI is required for actual image Compose acceptance")
    originals = authored_originals()
    assert len(originals) == 2 and originals[0] != originals[1]
    assert all(0 < len(raw) <= MAX_IMAGE_BYTES for raw in originals)
    project = "oi-h1-image-proof-" + uuid.uuid4().hex[:12]
    compose = ["docker", "compose", "--project-name", project,
               "--file", str(ROOT / "apps/api/compose.yaml"),
               "--file", str(ROOT / "apps/api/compose.synthetic-access.yaml")]
    with tempfile.TemporaryDirectory(prefix="oi-synthetic-image-access-") as directory:
        access = Path(directory)
        access.chmod(0o755)
        env = dict(os.environ, OI_API_ACCESS_DIRECTORY=directory)
        token = secrets.token_urlsafe(32)
        # Image actions are independent; source_read/source_original_read are
        # deliberately absent even for successful list and original reads.
        actions = ["patient_create", "patient_read", "case_binding_create",
                   "case_binding_revoke", "source_import", "image_import",
                   "image_read", "image_original_read"]
        credential = {
            "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
            "actor": "ACTOR-IMAGE-PROOF", "organization": "ORG-IMAGE-PROOF",
            "purpose": "operations", "actions": list(actions), "patient_ids": [],
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        }
        expected_access = []
        image_ids = []

        def save_access():
            pending = access / "access.new"
            pending.write_text(json.dumps({"version": "oi.synthetic-access/1",
                                           "credentials": [credential]}))
            pending.chmod(0o644)
            pending.replace(access / "access.json")

        def command(args, *, check=True, **kwargs):
            return subprocess.run(compose + args, cwd=ROOT, env=env,
                                  check=check, timeout=180, **kwargs)

        def query(sql, database="oi_api_synthetic"):
            result = command(["exec", "-T", "db", "psql", "-X", "-U", "oi_api",
                              "-d", database, "-v", "ON_ERROR_STOP=1", "-At", "-c", sql],
                             capture_output=True, text=True)
            return json.loads(result.stdout)

        def request(path, body=None, *, dicom=False, authenticated=True):
            headers = {"Authorization": "Bearer " + token} if authenticated else {}
            if body is None:
                data = None
            elif dicom:
                assert type(body) is bytes
                headers["Content-Type"] = "application/dicom"
                data = body
            else:
                headers["Content-Type"] = "application/json"
                data = json.dumps(body).encode("utf-8")
            req = Request(BASE + path, headers=headers, data=data)
            try:
                response = build_opener(ProxyHandler({})).open(req, timeout=5)
            except HTTPError as exc:
                response = exc
            with response:
                assert response.headers.get("Cache-Control") == "no-store"
                raw = response.read(MAX_IMAGE_BYTES + 1)
                assert len(raw) <= MAX_IMAGE_BYTES, "Response exceeded the image boundary"
                media_type = response.headers.get_content_type()
                if media_type == "application/dicom":
                    value = raw
                else:
                    assert media_type == "application/json", "Unexpected response media type"
                    value = json.loads(raw)
                return response.status, value, response.headers

        def ready():
            deadline = time.monotonic() + 45
            while True:
                try:
                    status, value, _ = request("/health/ready", authenticated=False)
                    if status == 200 and value["status"] == "ready":
                        return
                except (OSError, URLError, TimeoutError):
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError("Synthetic image API did not become ready")
                time.sleep(0.25)

        def history(database="oi_api_synthetic"):
            return query(
                "SELECT COALESCE(json_agg(e ORDER BY e.id),'[]'::json) FROM "
                "(SELECT id,patient_id,event_type,metadata_json,occurred_at "
                "FROM identity.identity_domain_events WHERE event_type IN ("
                + ACCESS_EVENTS + ")) e", database)

        def remember(receipt, event_type):
            assert type(receipt) is str and re.fullmatch(r"ACCESS-[0-9A-F]{32}", receipt), \
                "Invalid opaque access receipt"
            expected_access.append((receipt, event_type))

        def check_history():
            rows = history()
            assert [(row["metadata_json"]["receipt_id"], row["event_type"])
                    for row in rows] == expected_access, "Returned image receipts differ from durable history"
            assert all(row["patient_id"] == patient for row in rows)
            assert len({receipt for receipt, _ in expected_access}) == len(expected_access)
            encoded = json.dumps(rows, ensure_ascii=False)
            assert token not in encoded and "Independently fictional" not in encoded
            for row in rows:
                metadata = row["metadata_json"]
                assert not ({"raw", "original", "original_bytes", "pixels", "token", "bearer"} & metadata.keys())
                assert all(type(value) in (str, int, bool, type(None)) for value in metadata.values())
                assert all(not isinstance(value, str) or len(value) <= 128 for value in metadata.values())
            return rows

        def collection(source_id):
            return source_path + "/" + source_id + "/images"

        def metadata(value, source_id, index):
            assert set(value) == IMAGE_FIELDS, "Image metadata contract changed"
            assert re.fullmatch(r"IMG-[0-9A-F]{32}", value["image_id"])
            assert (value["source_id"], value["case_id"]) == (source_id, CASE)
            assert value["sha256"] == hashlib.sha256(originals[index]).hexdigest()
            assert type(value["byte_count"]) is int and value["byte_count"] == len(originals[index])
            assert (value["study_uid"], value["series_uid"], value["sop_uid"]) == (
                STUDY, SERIES, SOPS[index])
            assert (value["modality"], value["study_date"]) == ("CT", "2026-05-17")

        def ingest_image(source_id, index, result):
            status, value, _ = request(collection(source_id), originals[index], dicom=True)
            assert status == (200 if result == "duplicate" else 201), "Image intake failed"
            assert set(value) == IMAGE_FIELDS | {
                "result", "synthetic", "source_identity_verified", "clinical_interpretation"}
            assert value["result"] == result
            assert value["synthetic"] is True and value["source_identity_verified"] is False
            assert value["clinical_interpretation"] is False
            metadata({key: value[key] for key in IMAGE_FIELDS}, source_id, index)
            if len(image_ids) > index:
                assert value["image_id"] == image_ids[index], "Relinking duplicated original-image identity"
            else:
                image_ids.append(value["image_id"])

        def read_images(source_id):
            status, value, _ = request(collection(source_id))
            assert status == 200, "Image index unavailable"
            assert set(value) == {"patient_id", "case_id", "source_id", "images",
                                  "access_receipt_id", "synthetic", "source_identity_verified"}
            assert (value["patient_id"], value["case_id"], value["source_id"]) == (patient, CASE, source_id)
            assert value["synthetic"] is True and value["source_identity_verified"] is False
            remember(value["access_receipt_id"], "image.read_authorized")
            assert len(value["images"]) == 2
            by_id = {item["image_id"]: item for item in value["images"]}
            assert set(by_id) == set(image_ids)
            for index, image_id in enumerate(image_ids):
                metadata(by_id[image_id], source_id, index)

        def read_originals(source_id):
            for index, image_id in enumerate(image_ids):
                status, raw, headers = request(collection(source_id) + "/" + image_id)
                assert status == 200 and headers.get_content_type() == "application/dicom"
                assert type(raw) is bytes and raw == originals[index], "Original DICOM bytes changed"
                remember(headers.get("X-OI-Access-Receipt"), "image.original_read_authorized")

        def denied(source_id, *, index=True, original=True, ingest=False, authenticated=True):
            before = check_history()
            requests = []
            if index:
                requests.append((collection(source_id), None))
            if original:
                requests.extend((collection(source_id) + "/" + image_id, None) for image_id in image_ids)
            if ingest:
                requests.append((collection(source_id), originals[0]))
            for path, body in requests:
                status, value, headers = request(path, body, dicom=body is not None,
                                                 authenticated=authenticated)
                assert status == (404 if authenticated else 401), "Image denial did not fail closed"
                assert type(value) is dict and set(value) == {"detail"}
                assert headers.get("X-OI-Access-Receipt") is None
            assert history() == before, "Denied image request minted an access receipt"

        def snapshot(database="oi_api_synthetic"):
            # Exact allowlisted metadata and raw digests, never image bodies in
            # a snapshot/log/artifact. PG16 sha256(bytea) needs no extension.
            return query("""
                SELECT json_build_object(
                  'objects', (SELECT json_agg(o ORDER BY o.image_id) FROM
                    (SELECT image_id,case_id,sha256,byte_count,
                      encode(sha256(raw),'hex') AS raw_sha256,octet_length(raw) AS raw_length,
                      patient_id,issuer,study_uid,series_uid,sop_uid,sop_class_uid,
                      transfer_syntax_uid,study_date,modality,rows,columns,created_at
                     FROM clinical_source.dicom_objects) o),
                  'links', (SELECT json_agg(l ORDER BY l.source_id,l.image_id) FROM
                    (SELECT source_id,image_id,created_at FROM clinical_source.source_image_links) l),
                  'sources', (SELECT json_agg(s ORDER BY s.document_id,s.version) FROM
                    (SELECT source_id,case_id,document_id,version,sha256,
                      encode(sha256(raw),'hex') AS raw_sha256,octet_length(raw) AS byte_count,
                      kind,event_date,issued_at,state,supersedes_id
                     FROM clinical_source.source_versions) s),
                  'bindings', (SELECT json_agg(b ORDER BY b.case_id) FROM
                    (SELECT case_id,patient_id,origin_org,source_organization,source_system,
                      source_subject_ref,review_ref,purpose,status,revision,created_at,
                      revoked_at,revoked_by,revocation_reason FROM coordination.patient_case_bindings) b),
                  'patients', (SELECT json_agg(p ORDER BY p.patient_id) FROM
                    (SELECT patient_id,origin_org,created_at,created_by,status,revision
                     FROM identity.identity_patients) p),
                  'events', (SELECT json_agg(e ORDER BY e.id) FROM
                    (SELECT id,patient_id,event_type,metadata_json,occurred_at
                     FROM identity.identity_domain_events) e),
                  'revision', (SELECT version_num FROM public.alembic_version))
            """, database)

        def verify_stored_originals(database="oi_api_synthetic"):
            # Compare the two fixture originals after real pg_restore as bytes,
            # not only their stored digest columns. Captured data is never logged.
            values = query("""SELECT json_agg(o ORDER BY o.image_id) FROM
                (SELECT image_id,encode(raw,'hex') AS original_hex
                 FROM clinical_source.dicom_objects) o""", database)
            assert len(values) == 2
            by_id = {row["image_id"]: bytes.fromhex(row["original_hex"]) for row in values}
            assert set(by_id) == set(image_ids)
            for image_id, original in zip(image_ids, originals):
                assert by_id[image_id] == original, "Stored or restored original bytes changed"

        save_access()
        try:
            command(["config", "--quiet"])
            command(["up", "--build", "--detach", "api"])
            ready()
            status, created, _ = request("/v1/patients", {
                "synthetic": True, "request_key": "CREATE-IMAGE-COMPOSE-PROOF"})
            assert status == 201 and created["duplicate"] is False
            patient = created["patient_id"]
            assert re.fullmatch(r"PAT-[0-9A-F]{32}", patient)
            credential["patient_ids"] = [patient]
            save_access()
            patient_path = "/v1/patients/" + patient
            status, binding, _ = request(patient_path + "/case-bindings", {
                "synthetic": True, "case_id": CASE, "source_organization": "ORG-IMAGE-SOURCE",
                "source_system": SOURCE_SYSTEM, "source_subject_ref": SUBJECT,
                "review_ref": "REVIEW-IMAGE-COMPOSE"})
            assert status == 201 and binding["patient_id"] == patient
            assert binding["source_identity_verified"] is False
            source_path = patient_path + "/cases/" + CASE + "/sources"
            status, receipt, _ = request(source_path, {"synthetic": True, "original_text": ORIGINAL})
            assert (status, receipt["result"], receipt["version"]) == (201, "imported", 1)
            source_one = receipt["source_id"]
            assert re.fullmatch(r"SRC-[0-9A-F]{32}", source_one)
            for index in range(2):
                ingest_image(source_one, index, "imported")
            before_retry = snapshot()
            for index in range(2):
                ingest_image(source_one, index, "duplicate")
            assert snapshot() == before_retry, "Idempotent image retries changed durable state"
            read_images(source_one)
            read_originals(source_one)
            check_history()

            for missing, arguments in (
                ("image_import", {"index": False, "original": False, "ingest": True}),
                ("image_read", {"original": False}),
                ("image_original_read", {"index": False}),
                ("patient_read", {"ingest": True}),
            ):
                credential["actions"] = [action for action in actions if action != missing]
                save_access()
                denied(source_one, **arguments)
            credential["actions"] = list(actions)
            credential["patient_ids"] = []
            save_access()
            denied(source_one, ingest=True)
            credential["patient_ids"] = [patient]
            credential["purpose"] = "research"
            save_access()
            denied(source_one, ingest=True)
            credential["purpose"] = "operations"
            save_access()
            denied(source_one, ingest=True, authenticated=False)

            for service in ("api", "db"):
                before = snapshot()
                command(["restart", service])
                ready()
                assert snapshot() == before, "Restart changed image originals, links or history"
                read_images(source_one)
                read_originals(source_one)
                check_history()
                verify_stored_originals()
                print("Two exact image originals and access receipts survived " + service + " restart")

            status, receipt, _ = request(source_path, {"synthetic": True, "original_text": AMENDED})
            assert (status, receipt["result"], receipt["version"]) == (201, "imported", 2)
            source_two = receipt["source_id"]
            assert re.fullmatch(r"SRC-[0-9A-F]{32}", source_two) and source_two != source_one
            denied(source_one, ingest=True)
            for index in range(2):
                ingest_image(source_two, index, "linked")
            before_retry = snapshot()
            for index in range(2):
                ingest_image(source_two, index, "duplicate")
            assert snapshot() == before_retry, "Duplicate source-image links changed history"
            read_images(source_two)
            read_originals(source_two)
            denied(source_one)
            check_history()
            state = snapshot()
            assert len(state["objects"]) == 2 and len(state["links"]) == 4
            assert {(row["source_id"], row["image_id"]) for row in state["links"]} == {
                (source_id, image_id) for source_id in (source_one, source_two) for image_id in image_ids}
            assert [row["state"] for row in state["sources"]] == ["superseded", "current"]
            assert state["sources"][1]["supersedes_id"] == source_one
            for source, original in zip(state["sources"], (ORIGINAL, AMENDED)):
                assert source["sha256"] == source["raw_sha256"] == hashlib.sha256(original.encode()).hexdigest()
            event_kinds = [row["event_type"] for row in state["events"]]
            assert event_kinds.count("image.original_imported") == 2
            assert event_kinds.count("image.source_linked") == 2

            status, revoked, _ = request(patient_path + "/case-bindings/" + CASE + "/revoke", {
                "synthetic": True, "reason": "Withdraw the independently fictional image Compose binding"})
            assert status == 200 and revoked["duplicate"] is False
            denied(source_one, ingest=True)
            denied(source_two, ingest=True)
            before = snapshot()
            assert before["revision"] == "0008_questions_images_merge"
            assert before["bindings"][0]["status"] == "revoked"
            for row in before["objects"]:
                assert row["sha256"] == row["raw_sha256"]
                assert row["byte_count"] == row["raw_length"]
                assert (row["patient_id"], row["issuer"], row["study_date"]) == (
                    SUBJECT, ISSUER, "2026-05-17")
            verify_stored_originals()
            dump = command(["exec", "-T", "db", "pg_dump", "-U", "oi_api", "-d",
                            "oi_api_synthetic", "--format=custom"], capture_output=True).stdout
            restored_database = "oi_api_test_images_restore"
            command(["exec", "-T", "db", "createdb", "-U", "oi_api", restored_database])
            command(["exec", "-T", "db", "pg_restore", "-U", "oi_api", "-d", restored_database,
                     "--exit-on-error", "--no-owner"], input=dump)
            assert snapshot(restored_database) == before, "Restore changed image custody or authority history"
            assert history(restored_database) == check_history()
            verify_stored_originals(restored_database)
            print("PASS: exact synthetic DICOM HTTP originals, independent grants, distinct access receipts, "
                  "API/DB restart, amendment denial, explicit same-object relinking, "
                  "binding revocation and actual PostgreSQL dump/restore")
        except Exception:
            command(["logs", "--no-color", "--tail", "80"], check=False)
            raise
        finally:
            command(["down", "--volumes"], check=False)


if __name__ == "__main__":
    main()
