"""Actual Compose recovery of canonical questions and original-image custody.

Reuses the canonical registry, source, access-fixture and Compose owners. All
objects are independently authored by the stdlib-only test fixture generator;
no patient images, external PACS, optional codecs or new service are involved.
The returned receipts attest prepared disclosure, not delivery to a client.
Both populated domains are reopened through the API after a real pg_restore;
this is neither a model investigation nor a clinical review handoff.
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
EXPECTED_SCHEMA_REVISION = "0008_merge_image_questions"
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
QUESTIONS = (
    "What remains unresolved in this independently fictional imaging report?",
    "What changed in the independently fictional amended imaging report?",
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
        image_actions = ["patient_create", "patient_read", "case_binding_create",
                         "case_binding_revoke", "source_import", "image_import",
                         "image_read", "image_original_read"]
        question_actions = ["source_read", "composer_context_read",
                            "question_create", "question_read"]
        actions = image_actions + question_actions
        credential = {
            "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
            "actor": "ACTOR-IMAGE-PROOF", "organization": "ORG-IMAGE-PROOF",
            "purpose": "operations", "actions": list(actions), "patient_ids": [],
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        }
        expected_access = []
        image_ids = []
        expected_questions = {}
        question_intents = {}
        source_access_receipts = set()
        active_database = "oi_api_synthetic"

        def save_access():
            pending = access / "access.new"
            pending.write_text(json.dumps({"version": "oi.synthetic-access/1",
                                           "credentials": [credential]}))
            pending.chmod(0o644)
            pending.replace(access / "access.json")

        def command(args, *, check=True, **kwargs):
            return subprocess.run(compose + args, cwd=ROOT, env=env,
                                  check=check, timeout=180, **kwargs)

        def query(sql, database=None):
            result = command(["exec", "-T", "db", "psql", "-X", "-U", "oi_api",
                              "-d", database or active_database,
                              "-v", "ON_ERROR_STOP=1", "-At", "-c", sql],
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

        def history(database=None):
            return query(
                "SELECT COALESCE(json_agg(e ORDER BY e.id),'[]'::json) FROM "
                "(SELECT id,patient_id,event_type,metadata_json,occurred_at "
                "FROM identity.identity_domain_events WHERE event_type IN ("
                + ACCESS_EVENTS + ")) e", database)

        def remember(receipt, event_type):
            assert type(receipt) is str and re.fullmatch(r"ACCESS-[0-9A-F]{32}", receipt), \
                "Invalid opaque access receipt"
            expected_access.append((receipt, event_type))

        def remember_source_access(value):
            receipt = value["access_receipt_id"]
            assert type(receipt) is str and re.fullmatch(r"ACCESS-[0-9A-F]{32}", receipt)
            assert receipt not in source_access_receipts
            assert receipt not in {item[0] for item in expected_access}
            source_access_receipts.add(receipt)

        def prepare_question(source_id, version, original, *, expected_fingerprint=None):
            status, world, _ = request(case_path + "/world-model")
            assert status == 200 and world["contract"] == "oi.pg-source-world-model/1"
            assert (world["patient_id"], world["case_id"]) == (patient, CASE)
            assert world["clinical_interpretation"] is False
            assert world["composer_execution_authorized"] is False
            remember_source_access(world)
            fingerprint = world["snapshot_fingerprint"]
            assert re.fullmatch(r"[0-9a-f]{64}", fingerprint)
            if expected_fingerprint is not None:
                assert fingerprint == expected_fingerprint, "Image activity changed source context"
            line = 7 if version == 1 else 8
            payload = {
                "synthetic": True, "source_id": source_id, "source_line": line,
                "question": QUESTIONS[version - 1],
                "expected_source_snapshot_sha256": fingerprint,
            }
            status, prepared, _ = request(case_path + "/composer/source-preflight", payload)
            assert status == 200 and prepared["contract"] == "oi.synthetic-source-composer-preflight/2"
            assert (prepared["patient_id"], prepared["case_id"]) == (patient, CASE)
            assert prepared["source_snapshot_contract"] == "oi.pg-source-world-model/1"
            assert prepared["source_snapshot_sha256"] == fingerprint
            assert prepared["question"] == QUESTIONS[version - 1]
            assert prepared["model_execution_authorized"] is False
            assert prepared["durable_review_connected"] is False
            assert prepared["clinical_approval"] is False
            anchor = prepared["selected_source"]
            assert (anchor["source_id"], anchor["version"], anchor["line"]) == (source_id, version, line)
            assert anchor["sha256"] == hashlib.sha256(original.encode()).hexdigest()
            assert anchor["statement"] == original.splitlines()[line - 1].split("|", 2)[2]
            assert re.fullmatch(r"[0-9a-f]{64}", prepared["preflight_sha256"])
            remember_source_access(prepared)
            return payload, prepared

        def create_question(source_id, version, original):
            payload, prepared = prepare_question(source_id, version, original)
            intent = {
                **payload, "request_key": "COMPOSE-QUESTION-V" + str(version),
                "expected_preflight_sha256": prepared["preflight_sha256"],
            }
            status, saved, _ = request(case_path + "/questions", intent)
            assert status == 201 and saved["duplicate"] is False
            question_id = saved["question_id"]
            assert re.fullmatch(r"QUESTION-[0-9A-F]{32}", question_id)
            assert question_id not in expected_questions
            expected_questions[question_id] = {
                "question_id": question_id, "patient_id": patient, "case_id": CASE,
                "question": QUESTIONS[version - 1], "source_id": source_id,
                "source_line": payload["source_line"], "source_version": version,
                "source_sha256": hashlib.sha256(original.encode()).hexdigest(),
                "source_snapshot_contract": "oi.pg-source-world-model/1",
                "source_snapshot_sha256": prepared["source_snapshot_sha256"],
                "preflight_sha256": prepared["preflight_sha256"],
                "source_context_state": "current_unreviewed_question",
                "human_review_state": "not_submitted",
                "clinical_approval": False, "model_executed": False,
            }
            question_intents[question_id] = intent
            read_questions()
            return question_id

        def read_questions():
            status, value, _ = request(case_path + "/questions")
            assert status == 200 and value["contract"] == "oi.synthetic-source-questions/2"
            assert (value["patient_id"], value["case_id"]) == (patient, CASE)
            assert value["synthetic"] is True
            assert value["clinical_review_connected"] is False and value["clinical_approval"] is False
            remember_source_access(value)
            rows = {row["question_id"]: row for row in value["questions"]}
            assert len(rows) == len(value["questions"]) == len(expected_questions)
            assert set(rows) == set(expected_questions), "Recovered question identity changed"
            for question_id, expected in expected_questions.items():
                if "created_at" not in expected:
                    created = rows[question_id]["created_at"]
                    assert datetime.fromisoformat(created.replace("Z", "+00:00")).tzinfo is not None
                    expected["created_at"] = created
                assert rows[question_id] == expected, "Question anchors, status or history changed"
            return value["access_receipt_id"]

        def retry_questions():
            before = snapshot()
            creation_events = [row for row in before["events"]
                               if row["event_type"] == "investigation.question.created"]
            for question_id, intent in question_intents.items():
                status, value, _ = request(case_path + "/questions", intent)
                assert status == 200 and value == {"question_id": question_id, "duplicate": True}
            after = snapshot()
            assert after["questions"] == before["questions"], "Retry rewrote a question"
            assert [row for row in after["events"]
                    if row["event_type"] == "investigation.question.created"] == creation_events
            # A successful retry still authorizes source disclosure and records
            # a fresh source receipt; it must not mint another question event.
            added = after["events"][len(before["events"]):]
            assert len(added) == len(question_intents)
            assert all(row["event_type"] == "source.read_authorized" for row in added)

        def denied_question_requests(paths, *, authenticated=True):
            before = snapshot()
            for path, body in paths:
                status, value, headers = request(path, body, authenticated=authenticated)
                assert status == (404 if authenticated else 401), "Question denial did not fail closed"
                assert type(value) is dict and set(value) == {"detail"}
                assert headers.get("X-OI-Access-Receipt") is None
            assert snapshot() == before, "Denied question request changed durable state"

        def denied_questions():
            paths = [(case_path + "/questions", None), (case_path + "/world-model", None)]
            for intent in question_intents.values():
                paths.append((case_path + "/questions", intent))
                paths.append((case_path + "/composer/source-preflight", {
                    key: value for key, value in intent.items()
                    if key not in {"request_key", "expected_preflight_sha256"}
                }))
            denied_question_requests(paths)

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

        def snapshot(database=None):
            # Exact allowlisted metadata and content digests; neither image
            # bodies nor question text enters snapshots/logs/artifacts. Reopened
            # HTTP responses separately check literal text and original bytes.
            # PG16 sha256(bytea) needs no extension.
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
                  'questions', (SELECT COALESCE(json_agg(q ORDER BY q.question_id),'[]'::json) FROM
                    (SELECT question_id,patient_id,case_id,origin_org,request_key,
                      intent_sha256,actor,purpose,
                      encode(sha256(convert_to(question,'UTF8')),'hex') AS question_sha256,
                      octet_length(question) AS question_byte_count,
                      source_id,source_line,source_sha256,source_version,
                      source_snapshot_sha256,preflight_sha256,created_at,source_snapshot_contract
                     FROM investigation.source_questions) q),
                  'events', (SELECT json_agg(e ORDER BY e.id) FROM
                    (SELECT id,patient_id,event_type,metadata_json,occurred_at
                     FROM identity.identity_domain_events) e),
                  'revision', (SELECT version_num FROM public.alembic_version))
            """, database)

        def verify_stored_originals(database=None):
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

        def check_question_history():
            state = snapshot()
            assert len(state["questions"]) == len(expected_questions) > 0
            assert {row["question_id"] for row in state["questions"]} == set(expected_questions)
            for row in state["questions"]:
                expected = expected_questions[row["question_id"]]
                assert row["question_sha256"] == hashlib.sha256(expected["question"].encode()).hexdigest()
                assert row["question_byte_count"] == len(expected["question"].encode())
                for key in ("patient_id", "case_id", "source_id", "source_line", "source_sha256",
                            "source_version", "source_snapshot_sha256", "preflight_sha256",
                            "source_snapshot_contract"):
                    assert row[key] == expected[key], "Persisted question provenance changed"
            creation = [row for row in state["events"]
                        if row["event_type"] == "investigation.question.created"]
            assert len(creation) == len(expected_questions)
            assert {row["metadata_json"]["question_id"] for row in creation} == set(expected_questions)
            for row in creation:
                expected = expected_questions[row["metadata_json"]["question_id"]]
                assert row["patient_id"] == expected["patient_id"]
                for key in ("case_id", "source_id", "source_line",
                            "source_snapshot_sha256", "source_snapshot_contract"):
                    assert row["metadata_json"][key] == expected[key]
            source_receipts = [row["metadata_json"]["receipt_id"] for row in state["events"]
                               if row["event_type"] == "source.read_authorized"]
            assert len(source_receipts) == len(set(source_receipts))
            assert source_access_receipts <= set(source_receipts)
            assert not (set(source_receipts) & {item[0] for item in expected_access})
            audit = json.dumps(state["events"], ensure_ascii=False)
            assert token not in audit and all(question not in audit for question in QUESTIONS)
            return state

        def restore_database(database):
            assert re.fullmatch(r"oi_api_test_[a-z_]+", database)
            before = check_question_history()
            assert before["revision"] == EXPECTED_SCHEMA_REVISION
            dump = command(["exec", "-T", "db", "pg_dump", "-U", "oi_api", "-d",
                            active_database, "--format=custom"], capture_output=True).stdout
            command(["exec", "-T", "db", "createdb", "-U", "oi_api", database])
            command(["exec", "-T", "db", "pg_restore", "-U", "oi_api", "-d", database,
                     "--exit-on-error", "--no-owner"], input=dump)
            assert snapshot(database) == before, "Restore changed populated question/image custody or audit history"
            assert history(database) == check_history()
            verify_stored_originals(database)
            return before

        def use_restored_database(database):
            nonlocal active_database
            assert re.fullmatch(r"oi_api_test_[a-z_]+", database)
            # Recreate the same API service with one test-only setting override.
            # --no-deps avoids running migration against an already restored DB.
            override = access / "restored-api.compose.json"
            override.write_text(json.dumps({"services": {"api": {"environment": {
                "OI_API_DATABASE_URL": "postgresql+pg8000://oi_api:oi_h1_synthetic_only@db:5432/" + database,
            }}}}))
            if str(override) not in compose:
                compose.extend(("--file", str(override)))
            command(["config", "--quiet"])
            command(["up", "--detach", "--no-deps", "--force-recreate", "api"])
            active_database = database
            ready()
            # Check the recreated API container's selected DB without exposing
            # the URL/fixture credential. A new HTTP receipt below also proves
            # that actual requests write to this DB rather than the source DB.
            command(["exec", "-T", "api", "python", "-c",
                     "import sys; from oi_api.config import Settings; "
                     "from sqlalchemy.engine import make_url; "
                     "assert make_url(Settings.from_env().database_url).database == sys.argv[1], "
                     "'Restored API database selection mismatch'", database])

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
            case_path = patient_path + "/cases/" + CASE
            source_path = case_path + "/sources"
            status, receipt, _ = request(source_path, {"synthetic": True, "original_text": ORIGINAL})
            assert (status, receipt["result"], receipt["version"]) == (201, "imported", 1)
            source_one = receipt["source_id"]
            assert re.fullmatch(r"SRC-[0-9A-F]{32}", source_one)
            question_one = create_question(source_one, 1, ORIGINAL)
            first_fingerprint = expected_questions[question_one]["source_snapshot_sha256"]
            for index in range(2):
                ingest_image(source_one, index, "imported")
            before_retry = snapshot()
            for index in range(2):
                ingest_image(source_one, index, "duplicate")
            assert snapshot() == before_retry, "Idempotent image retries changed durable state"
            read_images(source_one)
            read_originals(source_one)
            _, prepared = prepare_question(source_one, 1, ORIGINAL,
                                           expected_fingerprint=first_fingerprint)
            assert prepared["preflight_sha256"] == expected_questions[question_one]["preflight_sha256"]
            read_questions()
            retry_questions()
            check_history()
            check_question_history()

            for missing, arguments in (
                ("image_import", {"index": False, "original": False, "ingest": True}),
                ("image_read", {"original": False}),
                ("image_original_read", {"index": False}),
                ("patient_read", {"ingest": True}),
            ):
                credential["actions"] = [action for action in actions if action != missing]
                save_access()
                denied(source_one, **arguments)
                if missing == "patient_read":
                    denied_questions()
                else:
                    read_questions()
            for missing, body in (("question_read", None),
                                  ("question_create", question_intents[question_one])):
                credential["actions"] = [action for action in actions if action != missing]
                save_access()
                denied_question_requests([(case_path + "/questions", body)])
                read_images(source_one)
                read_originals(source_one)
            # Image reads still succeed with no source disclosure, Composer or
            # question grant. Their grants cannot authorize the question path.
            credential["actions"] = list(image_actions)
            save_access()
            denied_questions()
            read_images(source_one)
            read_originals(source_one)
            credential["actions"] = list(actions)
            credential["patient_ids"] = []
            save_access()
            denied(source_one, ingest=True)
            denied_questions()
            credential["patient_ids"] = [patient]
            credential["purpose"] = "research"
            save_access()
            denied(source_one, ingest=True)
            denied_questions()
            credential["purpose"] = "operations"
            save_access()
            denied(source_one, ingest=True, authenticated=False)
            denied_question_requests([(case_path + "/questions", None)], authenticated=False)

            for service in ("api", "db"):
                before = snapshot()
                command(["restart", service])
                ready()
                assert snapshot() == before, "Restart changed populated question/image custody or history"
                read_images(source_one)
                read_originals(source_one)
                read_questions()
                retry_questions()
                check_history()
                check_question_history()
                verify_stored_originals()
                print("Populated v1 question, exact image originals and receipts survived " + service + " restart")

            status, receipt, _ = request(source_path, {"synthetic": True, "original_text": AMENDED})
            assert (status, receipt["result"], receipt["version"]) == (201, "imported", 2)
            source_two = receipt["source_id"]
            assert re.fullmatch(r"SRC-[0-9A-F]{32}", source_two) and source_two != source_one
            original_question_row = snapshot()["questions"]
            expected_questions[question_one]["source_context_state"] = "source_reassessment_required"
            read_questions()
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
            assert snapshot()["questions"] == original_question_row, "Relinking rewrote the historical question"
            read_questions()
            question_two = create_question(source_two, 2, AMENDED)
            assert question_two != question_one
            second_fingerprint = expected_questions[question_two]["source_snapshot_sha256"]
            assert second_fingerprint != first_fingerprint
            retry_questions()
            check_history()
            state = check_question_history()
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
            assert event_kinds.count("investigation.question.created") == 2

            # Both historical and current questions now exist. Restart the
            # actual services with this populated amended state before backup.
            for service in ("api", "db"):
                before = snapshot()
                command(["restart", service])
                ready()
                assert snapshot() == before, "Restart changed amended question/image history"
                read_questions()
                retry_questions()
                read_images(source_two)
                read_originals(source_two)
                denied(source_one)
                check_history()
                check_question_history()
                print("Historical v1/current v2 questions and linked image originals survived " + service + " restart")

            # Restore an ACTIVE populated case and then recreate the same API
            # against that database, so reopened states and retries are served
            # from restored rows rather than from the still-running source DB.
            source_database = active_database
            restored_database = "oi_api_test_images_questions_restore"
            before = restore_database(restored_database)
            assert before["bindings"][0]["status"] == "active"
            assert len(before["questions"]) == 2
            use_restored_database(restored_database)
            assert snapshot() == before, "Recreated API changed restored data before reads"
            restored_receipt = read_questions()
            receipt_query = (
                "SELECT to_json(count(*)) FROM identity.identity_domain_events "
                "WHERE event_type='source.read_authorized' AND metadata_json->>'receipt_id'='"
                + restored_receipt + "'"
            )
            assert query(receipt_query) == 1, "Restored HTTP response lacks a receipt in the restored DB"
            assert query(receipt_query, source_database) == 0, "HTTP still used the pre-restore DB"
            retry_questions()
            read_images(source_two)
            read_originals(source_two)
            denied(source_one, ingest=True)
            _, prepared = prepare_question(source_two, 2, AMENDED,
                                           expected_fingerprint=second_fingerprint)
            assert prepared["preflight_sha256"] == expected_questions[question_two]["preflight_sha256"]
            credential["actions"] = [action for action in actions if action != "question_read"]
            save_access()
            denied_question_requests([(case_path + "/questions", None)])
            read_originals(source_two)
            credential["actions"] = list(actions)
            save_access()
            read_questions()
            check_history()
            check_question_history()
            print("Active restored API reopened exact v1/v2 questions, original images and idempotent retries")

            status, revoked, _ = request(patient_path + "/case-bindings/" + CASE + "/revoke", {
                "synthetic": True, "reason": "Withdraw the independently fictional image Compose binding"})
            assert status == 200 and revoked["duplicate"] is False
            denied(source_one, ingest=True)
            denied(source_two, ingest=True)
            denied_questions()
            before = snapshot()
            assert before["revision"] == EXPECTED_SCHEMA_REVISION
            assert before["bindings"][0]["status"] == "revoked"
            for row in before["objects"]:
                assert row["sha256"] == row["raw_sha256"]
                assert row["byte_count"] == row["raw_length"]
                assert (row["patient_id"], row["issuer"], row["study_date"]) == (
                    SUBJECT, ISSUER, "2026-05-17")
            verify_stored_originals()
            for service in ("api", "db"):
                command(["restart", service])
                ready()
                assert snapshot() == before, "Restart changed restored revocation/history"
                denied(source_one, ingest=True)
                denied(source_two, ingest=True)
                denied_questions()
            # Retain the original revoked-state backup proof as well. A second
            # tiny restore must not reactivate the binding or disclose either
            # image originals or questions, and denied reads mint no receipts.
            revoked_database = "oi_api_test_images_questions_revoked"
            assert restore_database(revoked_database) == before
            use_restored_database(revoked_database)
            assert snapshot() == before
            denied(source_one, ingest=True)
            denied(source_two, ingest=True)
            denied_questions()
            assert snapshot() == before, "Restored revoked access changed durable history"
            print("PASS: populated canonical v1/v2 questions and exact synthetic DICOM originals; "
                  "independent grants, immutable anchors, distinct receipts, API/DB restart, "
                  "amendment reassessment, explicit same-object relinking, active restored HTTP/retries, "
                  "and revoked restored denial through actual PostgreSQL dump/restore")
        except Exception:
            command(["logs", "--no-color", "--tail", "80"], check=False)
            raise
        finally:
            command(["down", "--volumes"], check=False)


if __name__ == "__main__":
    main()
