"""Actual Compose recovery of images, questions, returns, tasks and citations.

Reuses the canonical registry, source, access-fixture and Compose owners. All
objects are independently authored by the stdlib-only test fixture generator;
no patient images, external PACS, optional codecs or new service are involved.
The returned receipts attest prepared disclosure, not delivery to a client.
All populated domains are reopened through the API after real pg_restore.
Metadata uses the existing independently fictional catalog and rights owner.
Tasks and verification returns are operational records, without clinical approval.
The restored API then uses an explicit bounded file-archive test fixture. This
proves archive invocation and fail-closed recovery, not live-PACS qualification
or backup of an external archive.
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
EXPECTED_SCHEMA_REVISION = "0011_image_evidence_merge"
QUEUE_CONTRACT = "oi.synthetic-question-review-return-queue/2"
RETURN_FINGERPRINT_CONTRACT = "oi.synthetic-source-review-return/2"
RETURN_REASON = "Please independently verify this fictional imaging source and its uncertainty."
TASK_CONTRACT = "oi.pg-question-followthrough/1"
EVIDENCE_CONTRACT = "oi.pg-question-evidence-links/1"
QUESTION_ANCHORS = (
    "question_id", "patient_id", "case_id", "source_id", "source_line",
    "source_sha256", "source_version", "source_snapshot_contract",
    "source_snapshot_sha256", "preflight_sha256",
)
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
        review_actions = ["review_queue_read", "review_return"]
        task_actions = ["followthrough_create", "followthrough_read", "followthrough_update"]
        evidence_actions = ["evidence_read", "evidence_link"]
        actions = image_actions + question_actions + review_actions + task_actions + evidence_actions
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
        queue_fingerprints = {}
        return_intents = {}
        expected_return_history = {}
        expected_tasks = {}
        task_intents = []
        evidence_intents = {}
        expected_citations = {}
        evidence_metadata = None
        metadata_rights_revoked = False
        source_access_receipts = set()
        active_database = "oi_api_synthetic"
        archive_enabled = False
        archive_directory = access / "archive-originals"
        archive_calls = access / "archive-calls.jsonl"

        def archive_history():
            if not archive_calls.exists():
                return []
            raw = archive_calls.read_bytes()
            assert len(raw) <= 100_000, "Acceptance archive trace exceeded its bound"
            rows = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
            for row in rows:
                assert set(row) == {"study_uid", "series_uid", "sop_uid"}
                assert (row["study_uid"], row["series_uid"]) == (STUDY, SERIES)
                assert row["sop_uid"] in SOPS, "Archive received noncanonical identifiers"
            return rows

        def use_archive_fixture():
            nonlocal archive_enabled
            archive_directory.mkdir()
            archive_directory.chmod(0o755)
            entries = []
            for index, (sop, raw) in enumerate(zip(SOPS, originals)):
                filename = f"{index:02}.dcm"
                path = archive_directory / filename
                path.write_bytes(raw)
                path.chmod(0o644)
                entries.append({"study_uid": STUDY, "series_uid": SERIES,
                                "sop_uid": sop, "filename": filename})
            manifest = archive_directory / "manifest.json"
            manifest.write_text(json.dumps({"contract": "oi.synthetic-archive-acceptance/1",
                                            "independently_authored": True, "objects": entries}))
            manifest.chmod(0o644)
            archive_calls.write_text("")
            # The container's unprivileged UID may append this synthetic trace
            # only. The fixture module and original objects are separate RO binds.
            archive_calls.chmod(0o666)
            override = access / "archive-api.compose.json"
            override.write_text(json.dumps({"services": {"api": {
                "command": ["python", "-m", "uvicorn",
                            "archive_acceptance_app:create_acceptance_app", "--factory",
                            "--host", "0.0.0.0", "--port", "8000", "--no-access-log",
                            "--no-proxy-headers"],
                "volumes": [
                    {"type": "bind", "source": str(ROOT / "apps/api/tools/archive_acceptance_app.py"),
                     "target": "/app/archive_acceptance_app.py", "read_only": True},
                    {"type": "bind", "source": str(archive_directory),
                     "target": "/run/oi-acceptance-archive", "read_only": True},
                    {"type": "bind", "source": str(archive_calls),
                     "target": "/run/oi-acceptance-archive-calls.jsonl", "read_only": False},
                ],
            }}}))
            compose.extend(("--file", str(override)))
            archive_enabled = True

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

        def remember_source_access(value, field="access_receipt_id"):
            receipt = value[field]
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

        def return_path(question_id):
            return case_path + "/questions/" + question_id + "/return-for-verification"

        def read_review_queue():
            status, value, _ = request(case_path + "/review-queue")
            assert status == 200 and value["contract"] == QUEUE_CONTRACT
            assert (value["patient_id"], value["case_id"]) == (patient, CASE)
            remember_source_access(value)
            for flag in ("clinical_approval", "reviewer_identity_verified",
                         "external_notification_sent", "review_completion_supported"):
                assert value[flag] is False
            rows = {row["question_id"]: row for row in value["items"]}
            assert len(rows) == len(value["items"]) == len(expected_questions)
            assert set(rows) == set(expected_questions)
            for question_id, expected in expected_questions.items():
                item = rows[question_id]
                for field in ("question_id", "patient_id", "case_id", "question", "source_id",
                              "source_line", "source_sha256", "source_version",
                              "source_snapshot_sha256", "source_snapshot_contract",
                              "preflight_sha256", "created_at", "source_context_state"):
                    assert item[field] == expected[field], "Review queue changed its question anchor"
                assert item["queue_fingerprint_contract"] == RETURN_FINGERPRINT_CONTRACT
                assert item["clinical_approval"] is False and item["reviewer_identity_verified"] is False
                prior = return_intents.get(question_id)
                current = expected["source_context_state"] == "current_unreviewed_question"
                if current:
                    fingerprint = item["queue_fingerprint"]
                    assert re.fullmatch(r"[0-9a-f]{64}", fingerprint)
                    queue_fingerprints.setdefault(question_id, fingerprint)
                    assert fingerprint == queue_fingerprints[question_id], \
                        "Image/access/return activity changed the review fingerprint"
                    assert item["review_state"] == ("returned_for_independent_verification" if prior
                                                     else "awaiting_independent_verification")
                    assert item["current_return_receipt_id"] == (prior[1]["receipt_id"] if prior else None)
                    assert (item["return_count"], item["prior_return_count"]) == (int(prior is not None), 0)
                else:
                    assert item["review_state"] == "source_reassessment_required"
                    assert item["queue_fingerprint"] is None and item["current_return_receipt_id"] is None
                    assert (item["return_count"], item["prior_return_count"]) == (0, int(prior is not None))
            receipts = {row["receipt_id"]: row for row in value["receipts"]}
            assert len(receipts) == len(value["receipts"]) == len(return_intents)
            assert set(receipts) == {saved["receipt_id"] for _, saved in return_intents.values()}
            for question_id, (intent, saved) in return_intents.items():
                receipt = receipts[saved["receipt_id"]]
                assert receipt["question_id"] == question_id
                assert receipt["queue_fingerprint"] == intent["expected_queue_fingerprint"]
                assert receipt["source_snapshot_sha256"] == expected_questions[question_id]["source_snapshot_sha256"]
                assert receipt["source_snapshot_contract"] == "oi.pg-source-world-model/1"
                assert receipt["queue_fingerprint_contract"] == RETURN_FINGERPRINT_CONTRACT
                assert receipt["action"] == "returned" and receipt["reason"] == RETURN_REASON
                assert receipt["actor_label"] == credential["actor"]
                assert datetime.fromisoformat(receipt["created_at"].replace("Z", "+00:00")).tzinfo is not None
                for flag in ("clinical_approval", "reviewer_identity_verified", "external_notification_sent"):
                    assert receipt[flag] is False
                expected_return_history.setdefault(receipt["receipt_id"], receipt)
                assert receipt == expected_return_history[receipt["receipt_id"]], \
                    "Amendment, relinking or recovery rewrote an immutable return"
            return value

        def return_question(question_id, version):
            value = read_review_queue()
            item = next(row for row in value["items"] if row["question_id"] == question_id)
            assert item["review_state"] == "awaiting_independent_verification"
            intent = {"synthetic": True, "request_key": "COMPOSE-IMAGE-RETURN-V" + str(version),
                      "expected_queue_fingerprint": item["queue_fingerprint"], "reason": RETURN_REASON}
            status, saved, _ = request(return_path(question_id), intent)
            assert status == 201 and saved["duplicate"] is False
            assert saved["question_id"] == question_id
            assert re.fullmatch(r"REVIEW-[0-9A-F]{32}", saved["receipt_id"])
            assert saved["receipt_id"] not in expected_return_history
            return_intents[question_id] = (intent, {**saved, "duplicate": True})
            read_review_queue()

        def retry_returns():
            before = snapshot()
            returned_events = [row for row in before["events"]
                               if row["event_type"] == "investigation.review.returned_for_verification"]
            for question_id, (intent, saved) in return_intents.items():
                status, value, _ = request(return_path(question_id), intent)
                assert (status, value) == (200, saved), "Retry changed the original return identity"
            after = snapshot()
            assert after["review_receipts"] == before["review_receipts"], "Retry rewrote a return"
            assert [row for row in after["events"]
                    if row["event_type"] == "investigation.review.returned_for_verification"] == returned_events
            added = after["events"][len(before["events"]):]
            assert len(added) == len(return_intents)
            assert all(row["event_type"] == "source.read_authorized" for row in added)

        def question_context(question_id):
            question = expected_questions[question_id]
            return {
                "synthetic": True,
                "source_snapshot_contract": question["source_snapshot_contract"],
                "expected_source_snapshot_sha256": question["source_snapshot_sha256"],
                "expected_preflight_sha256": question["preflight_sha256"],
            }

        def write_task(path, body, question_id, revision):
            status, receipt, _ = request(path, body)
            assert status == 201 and receipt["duplicate"] is False
            assert receipt["question_id"] == question_id and receipt["revision"] == revision
            assert re.fullmatch(r"TASK-[0-9A-F]{32}", receipt["task_id"])
            assert re.fullmatch(r"TASK-EVENT-[0-9A-F]{32}", receipt["event_id"])
            assert receipt["event_id"] not in {item[2]["event_id"] for item in task_intents}
            task_intents.append((path, body, {**receipt, "duplicate": True}))
            return receipt

        def create_followthrough(question_id, version):
            path = case_path + "/questions/" + question_id + "/followthrough"
            body = {
                **question_context(question_id), "request_key": "COMPOSE-IMAGE-TASK-V" + str(version),
                "title": "Prepare the independently fictional imaging discussion",
                "detail": "Bring the original image reference and its source question.",
                "owner_label": "", "due_date": None,
                "review_trigger": "When another source version arrives",
                "reason": "Record the fictional preparation step.",
            }
            receipt = write_task(path, body, question_id, 1)
            task_id = receipt["task_id"]
            assert task_id not in expected_tasks
            for revision, status in enumerate(("assigned", "acknowledged"), 2):
                write_task(case_path + "/followthrough/" + task_id + "/transitions", {
                    "synthetic": True, "request_key": "COMPOSE-IMAGE-TASK-V" + str(version) + "-REV-" + str(revision),
                    "expected_revision": revision - 1, "status": status,
                    "owner_label": "Fictional coordinator" if status == "assigned" else "",
                    "reason": "Record the attributed fictional preparation status.",
                }, question_id, revision)
            expected_tasks[task_id] = None
            read_followthrough()

        def read_followthrough():
            status, value, _ = request(case_path + "/followthrough")
            assert status == 200 and value["contract"] == TASK_CONTRACT
            assert (value["patient_id"], value["case_id"]) == (patient, CASE)
            assert value["evaluated_on"] == datetime.now(timezone.utc).date().isoformat()
            assert value["synthetic"] is True
            assert value["clinical_approval"] is value["external_notification_sent"] is False
            remember_source_access(value)
            rows = {row["task_id"]: row for row in value["tasks"]}
            assert len(rows) == len(value["tasks"]) == len(expected_tasks)
            assert set(rows) == set(expected_tasks), "Recovery changed task identity"
            for task_id, row in rows.items():
                if expected_tasks[task_id] is None:
                    expected_tasks[task_id] = row
                original = expected_tasks[task_id]
                question = expected_questions[row["question_id"]]
                current = question["source_context_state"] == "current_unreviewed_question"
                assert row == {**original, "source_context_state": question["source_context_state"],
                               "needs_recheck": not current}, "Recovery/relink changed task provenance or history"
                assert all(row[field] == question[field] for field in QUESTION_ANCHORS)
                assert [event["status"] for event in row["history"]] == ["created", "assigned", "acknowledged"]
                assert [event["event_id"] for event in row["history"]] == [
                    saved["event_id"] for _, _, saved in task_intents if saved["task_id"] == task_id]
                assert all(event["actor_label"] == credential["actor"] for event in row["history"])
                assert row["is_overdue"] is row["is_due_soon"] is row["clinical_approval"] is False
            return value

        def evidence_path(question_id):
            return case_path + "/questions/" + question_id + "/evidence-links"

        def create_evidence(question_id, version):
            nonlocal evidence_metadata
            status, search, _ = request(case_path + "/questions/" + question_id + "/evidence-search", {
                "synthetic": True, "query": "continuity",
            })
            assert status == 200 and len(search["records"]) == 1
            assert search["contract"] == "oi.pg-question-evidence-search/1"
            assert search["content_appraised"] is search["model_executed"] is search["clinical_approval"] is False
            remember_source_access(search, "source_access_receipt_id")
            record = search["records"][0]
            assert record["citation"] == "FICT-RECORD-CONTINUITY@1"
            assert record["source_kind"] == "fictional" and record["availability"] == "metadata_only"
            if evidence_metadata is None:
                evidence_metadata = record
            assert record == evidence_metadata, "Question context changed the exact metadata version"
            body = {
                **question_context(question_id), "request_key": "COMPOSE-IMAGE-EVIDENCE-V" + str(version),
                "citation": record["citation"], "expected_metadata_sha256": record["metadata_sha256"],
            }
            status, receipt, _ = request(evidence_path(question_id), body)
            assert status == 201 and receipt["duplicate"] is False
            assert re.fullmatch(r"EVIDENCE-LINK-[0-9A-F]{32}", receipt["link_id"])
            assert receipt["citation"] == record["citation"]
            assert receipt["metadata_sha256"] == record["metadata_sha256"]
            assert receipt["link_id"] not in {item[1]["link_id"] for item in evidence_intents.values()}
            evidence_intents[question_id] = (body, {**receipt, "duplicate": True})
            read_citations()

        def read_citations():
            responses = {}
            for question_id, (_, receipt) in evidence_intents.items():
                status, value, _ = request(evidence_path(question_id))
                assert status == 200 and value["contract"] == EVIDENCE_CONTRACT
                assert (value["patient_id"], value["case_id"], value["question_id"]) == (patient, CASE, question_id)
                assert value["source_context_state"] == expected_questions[question_id]["source_context_state"]
                assert value["model_executed"] is value["content_appraised"] is value["clinical_approval"] is False
                remember_source_access(value, "source_access_receipt_id")
                assert len(value["links"]) == 1 and value["links"][0]["link_id"] == receipt["link_id"]
                row = value["links"][0]
                if question_id not in expected_citations:
                    assert row["record"] == evidence_metadata and row["status"] == "available"
                    expected_citations[question_id] = row
                original = expected_citations[question_id]
                expected = {**original, "status": "rights_restricted", "record": None} if metadata_rights_revoked else original
                assert row == expected, "Recovery changed citation identity or disclosed revoked metadata"
                if metadata_rights_revoked:
                    encoded = json.dumps(value)
                    assert evidence_metadata["title"] not in encoded and evidence_metadata["link"] not in encoded
                responses[question_id] = value
            return responses

        def retry_followthrough_and_evidence():
            before = snapshot()
            writes = list(task_intents) + [(evidence_path(qid), body, receipt)
                                          for qid, (body, receipt) in evidence_intents.items()]
            for path, body, receipt in writes:
                status, value, _ = request(path, body)
                assert (status, value) == (200, receipt), "Retry changed a task event or citation identity"
            after = snapshot()
            for owner in before.keys() - {"events"}:
                assert after[owner] == before[owner], "Retry changed durable " + owner
            assert after["events"][:len(before["events"])] == before["events"]
            added = after["events"][len(before["events"]):]
            assert len(added) == len(writes)
            assert all(row["event_type"] == "source.read_authorized" for row in added)

        def connected_requests(missing=None):
            operations = [({"followthrough_read"}, case_path + "/followthrough", None)]
            for path, body, _ in task_intents:
                grant = "followthrough_update" if path.endswith("/transitions") else "followthrough_create"
                operations.append(({grant}, path, body))
            for question_id, (body, _) in evidence_intents.items():
                operations.extend((
                    ({"evidence_read"}, evidence_path(question_id), None),
                    ({"evidence_read", "evidence_link"}, evidence_path(question_id), body),
                    ({"evidence_read"}, case_path + "/questions/" + question_id + "/evidence-search",
                     {"synthetic": True, "query": "continuity"}),
                ))
            return [(path, body) for required, path, body in operations if missing is None or missing in required]

        def revoke_metadata_rights():
            nonlocal metadata_rights_revoked
            before = snapshot()
            # Reuse the trusted fixture-governance port. No HTTP caller can
            # grant metadata rights or turn this catalog into biomedical data.
            command(["exec", "-T", "api", "python", "-c", '''
from oi_api.config import Settings
from oi_api.database import Database
from oi_api.evidence_catalog import append_rights_decision
from open_intelligence.postgres_registry import PostgresPatientRegistry
database = Database(Settings.from_env())
try:
    with database.registry_connection() as connection:
        append_rights_decision(PostgresPatientRegistry(connection, lambda *args: False),
            'FICT-RECORD-CONTINUITY', '1', permissions={'metadata': {'store': 'allowed', 'display': 'allowed'}},
            revoked=True, superseded=False, recorded_by='FIXTURE-IMAGE-RESTORE-REVIEWER',
            reason='Withdraw independently fictional metadata rights for combined recovery verification')
finally:
    database.close()
'''])
            metadata_rights_revoked = True
            after = snapshot()
            for owner in before.keys() - {"evidence_rights"}:
                assert after[owner] == before[owner], "Metadata withdrawal changed another owner: " + owner
            assert len(after["evidence_rights"]) == len(before["evidence_rights"]) + 1
            read_citations()

        def check_restricted_metadata(question_id):
            assert metadata_rights_revoked
            status, value, _ = request(case_path + "/questions/" + question_id + "/evidence-search", {
                "synthetic": True, "query": "continuity",
            })
            assert status == 200 and value["records"] == []
            remember_source_access(value, "source_access_receipt_id")
            encoded = json.dumps(value)
            assert evidence_metadata["title"] not in encoded and evidence_metadata["link"] not in encoded
            before = snapshot()
            body, _ = evidence_intents[question_id]
            assert request(evidence_path(question_id), {
                **body, "request_key": "COMPOSE-IMAGE-REVOKED-NEW-CITATION",
            })[0] == 404
            assert snapshot() == before, "Revoked metadata permitted a new link or access receipt"

        def denied_reviews(*, queue=True, returning=True, authenticated=True):
            before = snapshot()
            requests = [(case_path + "/review-queue", None)] if queue else []
            if returning:
                requests.extend((return_path(qid), intent) for qid, (intent, _) in return_intents.items())
            for path, body in requests:
                status, value, headers = request(path, body, authenticated=authenticated)
                assert status == (404 if authenticated else 401), "Review denial did not fail closed"
                assert type(value) is dict and set(value) == {"detail"}
                assert headers.get("X-OI-Access-Receipt") is None
            assert snapshot() == before, "Denied review request changed a receipt or durable history"

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
            calls_before = archive_history()
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
            assert archive_history() == calls_before, "Image index invoked the original archive"

        def read_originals(source_id):
            calls_before = archive_history()
            receipts = []
            for index, image_id in enumerate(image_ids):
                status, raw, headers = request(collection(source_id) + "/" + image_id)
                assert status == 200 and headers.get_content_type() == "application/dicom"
                assert type(raw) is bytes and raw == originals[index], "Original DICOM bytes changed"
                remember(headers.get("X-OI-Access-Receipt"), "image.original_read_authorized")
                receipts.append(headers.get("X-OI-Access-Receipt"))
            expected = [{"study_uid": STUDY, "series_uid": SERIES, "sop_uid": sop}
                        for sop in SOPS] if archive_enabled else []
            assert archive_history() == calls_before + expected, "Original HTTP bypassed the selected archive path"
            return receipts

        def denied(source_id, *, index=True, original=True, ingest=False, authenticated=True):
            before = check_history()
            calls_before = archive_history()
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
            assert archive_history() == calls_before, "Denied image request invoked the archive"

        def archive_failure(source_id, *, missing):
            path = archive_directory / "00.dcm"
            before = snapshot()
            calls_before = archive_history()
            try:
                if missing:
                    path.unlink()
                else:
                    path.write_bytes(originals[0][:-1] + bytes([originals[0][-1] ^ 1]))
                status, value, headers = request(collection(source_id) + "/" + image_ids[0])
                assert (status, value) == (503, {"detail": "Patient registry unavailable"})
                assert headers.get("X-OI-Access-Receipt") is None
                assert snapshot() == before, "Archive failure changed custody, question, task, citation or receipt history"
                assert archive_history() == calls_before + [
                    {"study_uid": STUDY, "series_uid": SERIES, "sop_uid": SOPS[0]}]
            finally:
                path.write_bytes(originals[0])
                path.chmod(0o644)
            verify_stored_originals()

        def snapshot(database=None):
            # Existing owner rows and exact content digests; neither image
            # bodies nor question text enters snapshots/logs/artifacts. Task
            # text and metadata are the independently fictional fixture only.
            # Reopened HTTP separately checks literal text and original bytes.
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
                  'review_receipts', (SELECT COALESCE(json_agg(r ORDER BY r.receipt_id),'[]'::json) FROM
                    (SELECT receipt_id,question_id,patient_id,case_id,origin_org,request_key,
                      intent_sha256,queue_fingerprint,source_snapshot_sha256,actor,purpose,action,
                      encode(sha256(convert_to(reason,'UTF8')),'hex') AS reason_sha256,
                      octet_length(reason) AS reason_byte_count,created_at,
                      source_snapshot_contract,queue_fingerprint_contract
                     FROM investigation.question_review_receipts) r),
                  'tasks', (SELECT COALESCE(json_agg(t ORDER BY t.task_id),'[]'::json)
                    FROM coordination.question_followthrough_tasks t),
                  'task_events', (SELECT COALESCE(json_agg(t ORDER BY t.task_id,t.revision),'[]'::json)
                    FROM coordination.question_followthrough_events t),
                  'evidence_catalog', (SELECT COALESCE(json_agg(m ORDER BY m.record_id,m.version),'[]'::json)
                    FROM investigation.evidence_catalog_records m),
                  'evidence_rights', (SELECT COALESCE(json_agg(r ORDER BY r.record_id,r.version,r.revision),'[]'::json)
                    FROM investigation.evidence_rights_decisions r),
                  'evidence_links', (SELECT COALESCE(json_agg(l ORDER BY l.link_id),'[]'::json)
                    FROM investigation.question_evidence_links l),
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
            assert RETURN_REASON not in audit
            assert len(state["review_receipts"]) == len(return_intents)
            assert {row["receipt_id"] for row in state["review_receipts"]} == set(expected_return_history)
            for row in state["review_receipts"]:
                expected = expected_return_history[row["receipt_id"]]
                assert row["reason_sha256"] == hashlib.sha256(RETURN_REASON.encode()).hexdigest()
                assert row["reason_byte_count"] == len(RETURN_REASON.encode())
                assert (row["patient_id"], row["case_id"]) == (patient, CASE)
                for field in ("receipt_id", "question_id", "queue_fingerprint", "source_snapshot_sha256",
                              "source_snapshot_contract", "queue_fingerprint_contract", "action"):
                    assert row[field] == expected[field], "Persisted return provenance changed"
            returns = [row for row in state["events"]
                       if row["event_type"] == "investigation.review.returned_for_verification"]
            assert len(returns) == len(return_intents)
            assert {row["metadata_json"]["receipt_id"] for row in returns} == set(expected_return_history)
            assert len(state["tasks"]) == len(expected_tasks)
            assert {row["task_id"] for row in state["tasks"]} == set(expected_tasks)
            for row in state["tasks"]:
                expected = expected_tasks[row["task_id"]]
                for field in QUESTION_ANCHORS:
                    assert row[field] == expected[field], "Stored task anchor changed"
            assert len(state["task_events"]) == len(task_intents)
            assert {row["event_id"] for row in state["task_events"]} == {
                receipt["event_id"] for _, _, receipt in task_intents}
            task_events = [row for row in state["events"]
                           if row["event_type"].startswith("coordination.followthrough.")]
            assert len(task_events) == len(task_intents), "Task retries duplicated business history"
            assert {row["metadata_json"]["task_event_id"] for row in task_events} == {
                receipt["event_id"] for _, _, receipt in task_intents}
            assert len(state["evidence_catalog"]) == 2
            assert len(state["evidence_rights"]) == 2 + int(metadata_rights_revoked)
            assert len(state["evidence_links"]) == len(evidence_intents)
            for row in state["evidence_links"]:
                question_id = row["question_id"]
                expected = expected_questions[question_id]
                _, receipt = evidence_intents[question_id]
                assert row["link_id"] == receipt["link_id"]
                assert (row["record_id"], row["version"]) == ("FICT-RECORD-CONTINUITY", "1")
                assert row["metadata_sha256"] == evidence_metadata["metadata_sha256"]
                for field in ("patient_id", "case_id", "source_snapshot_contract",
                              "source_snapshot_sha256", "preflight_sha256"):
                    assert row[field] == expected[field], "Stored citation anchor changed"
            citation_events = [row for row in state["events"] if row["event_type"] == "evidence.citation.linked"]
            assert len(citation_events) == len(evidence_intents), "Citation retries duplicated business history"
            assert {row["metadata_json"]["link_id"] for row in citation_events} == {
                receipt["link_id"] for _, receipt in evidence_intents.values()}
            assert evidence_metadata["title"] not in audit and evidence_metadata["link"] not in audit
            assert all(task["title"] not in audit and task["detail"] not in audit for task in expected_tasks.values())
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
            assert snapshot(database) == before, "Restore changed image/question/return/task/citation owner history"
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
            command(["exec", "-T", "api", "python", "-m", "oi_api.evidence_catalog"])
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
            read_review_queue()
            create_followthrough(question_one, 1)
            create_evidence(question_one, 1)
            before_image_activity = snapshot()
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
            # The queue fingerprint was captured before image import and reads.
            # Image receipts must not invalidate a deliberate verification return.
            read_review_queue()
            read_followthrough()
            read_citations()
            after_image_activity = snapshot()
            for owner in ("questions", "tasks", "task_events", "evidence_catalog", "evidence_rights", "evidence_links"):
                assert after_image_activity[owner] == before_image_activity[owner], "Image activity changed " + owner
            return_question(question_one, 1)
            retry_returns()
            retry_followthrough_and_evidence()
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
                    denied_reviews()
                    denied_question_requests(connected_requests())
                else:
                    read_questions()
                    read_review_queue()
                    retry_returns()
                    read_followthrough()
                    read_citations()
            for missing, body in (("question_read", None),
                                  ("question_create", question_intents[question_one])):
                credential["actions"] = [action for action in actions if action != missing]
                save_access()
                denied_question_requests([(case_path + "/questions", body)])
                if missing == "question_read":
                    denied_question_requests(connected_requests())
                read_images(source_one)
                read_originals(source_one)
            for missing in review_actions:
                credential["actions"] = [action for action in actions if action != missing]
                save_access()
                denied_reviews(queue=missing == "review_queue_read", returning=missing == "review_return")
                read_images(source_one)
                read_originals(source_one)
                if missing == "review_queue_read":
                    retry_returns()
                else:
                    read_review_queue()
            for missing in task_actions + evidence_actions:
                credential["actions"] = [action for action in actions if action != missing]
                save_access()
                denied_question_requests(connected_requests(missing))
                read_images(source_one)
                read_originals(source_one)
                read_review_queue()
                if missing in task_actions:
                    read_citations()
                else:
                    read_followthrough()
            # Image reads still succeed with no source disclosure, Composer or
            # question grant. Their grants cannot authorize the question path.
            credential["actions"] = list(image_actions)
            save_access()
            denied_questions()
            denied_reviews()
            denied_question_requests(connected_requests())
            read_images(source_one)
            read_originals(source_one)
            credential["actions"] = list(actions)
            credential["patient_ids"] = []
            save_access()
            denied(source_one, ingest=True)
            denied_questions()
            denied_reviews()
            denied_question_requests(connected_requests())
            credential["patient_ids"] = [patient]
            credential["purpose"] = "research"
            save_access()
            denied(source_one, ingest=True)
            denied_questions()
            denied_reviews()
            denied_question_requests(connected_requests())
            credential["purpose"] = "operations"
            save_access()
            denied(source_one, ingest=True, authenticated=False)
            denied_question_requests([(case_path + "/questions", None)], authenticated=False)
            denied_reviews(authenticated=False)
            denied_question_requests(connected_requests(), authenticated=False)

            for service in ("api", "db"):
                before = snapshot()
                command(["restart", service])
                ready()
                assert snapshot() == before, "Restart changed populated question/image custody or history"
                read_images(source_one)
                read_originals(source_one)
                read_questions()
                retry_questions()
                read_review_queue()
                retry_returns()
                read_followthrough()
                read_citations()
                retry_followthrough_and_evidence()
                check_history()
                check_question_history()
                verify_stored_originals()
                print("Populated v1 question/return/task/citation, exact image originals and receipts survived " + service + " restart")

            status, receipt, _ = request(source_path, {"synthetic": True, "original_text": AMENDED})
            assert (status, receipt["result"], receipt["version"]) == (201, "imported", 2)
            source_two = receipt["source_id"]
            assert re.fullmatch(r"SRC-[0-9A-F]{32}", source_two) and source_two != source_one
            original_question_row = snapshot()["questions"]
            expected_questions[question_one]["source_context_state"] = "source_reassessment_required"
            read_questions()
            historical_returns = read_review_queue()["receipts"]
            read_followthrough()
            read_citations()
            historical_owners = snapshot()
            old_intent, _ = return_intents[question_one]
            before_stale = snapshot()
            assert request(return_path(question_one), {
                **old_intent, "request_key": "COMPOSE-IMAGE-STALE-NEW-RETURN"})[0] == 409
            assert request(task_intents[0][0], {
                **task_intents[0][1], "request_key": "COMPOSE-IMAGE-STALE-NEW-TASK"})[0] == 409
            assert request(evidence_path(question_one), {
                **evidence_intents[question_one][0], "request_key": "COMPOSE-IMAGE-STALE-NEW-CITATION"})[0] == 409
            assert snapshot() == before_stale, "Rejected stale return changed durable history"
            retry_returns()
            retry_followthrough_and_evidence()
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
            assert read_review_queue()["receipts"] == historical_returns
            retry_returns()
            read_followthrough()
            read_citations()
            retry_followthrough_and_evidence()
            relinked_owners = snapshot()
            for owner in ("questions", "review_receipts", "tasks", "task_events", "evidence_catalog", "evidence_rights", "evidence_links"):
                assert relinked_owners[owner] == historical_owners[owner], "Relinking changed historical " + owner
            question_two = create_question(source_two, 2, AMENDED)
            assert question_two != question_one
            second_fingerprint = expected_questions[question_two]["source_snapshot_sha256"]
            assert second_fingerprint != first_fingerprint
            return_question(question_two, 2)
            create_followthrough(question_two, 2)
            create_evidence(question_two, 2)
            retry_questions()
            retry_returns()
            retry_followthrough_and_evidence()
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
            assert event_kinds.count("investigation.review.returned_for_verification") == 2
            assert event_kinds.count("coordination.followthrough.created") == 2
            assert event_kinds.count("coordination.followthrough.transitioned") == 4
            assert event_kinds.count("evidence.citation.linked") == 2

            # Both historical and current questions now exist. Restart the
            # actual services with this populated amended state before backup.
            for service in ("api", "db"):
                before = snapshot()
                command(["restart", service])
                ready()
                assert snapshot() == before, "Restart changed amended question/image history"
                read_questions()
                retry_questions()
                read_review_queue()
                retry_returns()
                read_followthrough()
                read_citations()
                retry_followthrough_and_evidence()
                read_images(source_two)
                read_originals(source_two)
                denied(source_one)
                check_history()
                check_question_history()
                print("Historical v1/current v2 questions/returns/tasks/citations and linked images survived " + service + " restart")

            # Withdraw rights before the active-case backup. Restored HTTP must
            # redact cached metadata while still exposing preserved task/image
            # history and returning exact historical identity receipts.
            revoke_metadata_rights()
            check_restricted_metadata(question_two)
            read_followthrough()
            retry_followthrough_and_evidence()

            # Restore an ACTIVE populated case and then recreate the same API
            # against that database, so reopened states and retries are served
            # from restored rows rather than from the still-running source DB.
            source_database = active_database
            restored_database = "oi_api_test_images_questions_restore"
            before = restore_database(restored_database)
            source_database_snapshot = before
            assert before["bindings"][0]["status"] == "active"
            assert len(before["questions"]) == 2
            assert len(before["review_receipts"]) == 2
            assert len(before["tasks"]) == len(before["evidence_links"]) == 2
            assert len(before["task_events"]) == 6 and len(before["evidence_rights"]) == 3
            # Both populated restart checkpoints above exercise local custody.
            # The restored API explicitly enables the original-read archive;
            # later checks prove invocation and no silent local fallback.
            use_archive_fixture()
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
            restored_review_receipt = read_review_queue()["access_receipt_id"]
            review_receipt_query = (
                "SELECT to_json(count(*)) FROM identity.identity_domain_events "
                "WHERE event_type='source.read_authorized' AND metadata_json->>'receipt_id'='"
                + restored_review_receipt + "'"
            )
            assert query(review_receipt_query) == 1, "Restored review HTTP did not write to the restored DB"
            assert query(review_receipt_query, source_database) == 0, "Review HTTP still used the source DB"
            restored_task_receipt = read_followthrough()["access_receipt_id"]
            restored_citations = read_citations()
            restored_evidence_receipt = restored_citations[question_two]["source_access_receipt_id"]
            for label, restored_access in (("task", restored_task_receipt), ("citation", restored_evidence_receipt)):
                query_receipt = (
                    "SELECT to_json(count(*)) FROM identity.identity_domain_events "
                    "WHERE event_type='source.read_authorized' AND metadata_json->>'receipt_id'='"
                    + restored_access + "'"
                )
                assert query(query_receipt) == 1, "Restored " + label + " HTTP lacks its receipt in the restored DB"
                assert query(query_receipt, source_database) == 0, "Restored " + label + " HTTP still used the source DB"
            check_restricted_metadata(question_two)
            retry_questions()
            retry_returns()
            retry_followthrough_and_evidence()
            read_images(source_two)
            restored_image_receipts = read_originals(source_two)
            for image_receipt in restored_image_receipts:
                image_receipt_query = (
                    "SELECT to_json(count(*)) FROM identity.identity_domain_events "
                    "WHERE event_type='image.original_read_authorized' AND metadata_json->>'receipt_id'='"
                    + image_receipt + "'"
                )
                assert query(image_receipt_query) == 1, "Archive HTTP lacks a restored image receipt"
                assert query(image_receipt_query, source_database) == 0, "Archive HTTP wrote to the source DB"
            denied(source_one, ingest=True)
            _, prepared = prepare_question(source_two, 2, AMENDED,
                                           expected_fingerprint=second_fingerprint)
            assert prepared["preflight_sha256"] == expected_questions[question_two]["preflight_sha256"]
            credential["actions"] = [action for action in actions if action != "question_read"]
            save_access()
            denied_question_requests([(case_path + "/questions", None)])
            denied_question_requests(connected_requests())
            read_originals(source_two)
            credential["actions"] = list(actions)
            save_access()
            for missing in review_actions:
                credential["actions"] = [action for action in actions if action != missing]
                save_access()
                denied_reviews(queue=missing == "review_queue_read", returning=missing == "review_return")
                read_originals(source_two)
            credential["actions"] = list(actions)
            save_access()
            for missing in task_actions + evidence_actions:
                credential["actions"] = [action for action in actions if action != missing]
                save_access()
                denied_question_requests(connected_requests(missing))
                read_originals(source_two)
            credential["actions"] = list(actions)
            save_access()
            read_questions()
            read_review_queue()
            retry_returns()
            read_followthrough()
            read_citations()
            retry_followthrough_and_evidence()
            check_history()
            check_question_history()
            assert snapshot(source_database) == before, "Restored HTTP mutated the pre-restore database"
            print("Active restored API reopened exact v1/v2 questions/returns/tasks/citations, archive originals and same-key retries; revoked title/URL stayed redacted")

            archive_state = snapshot()
            for missing in (False, True):
                archive_failure(source_two, missing=missing)
                read_originals(source_two)
                read_questions()
                read_review_queue()
                read_followthrough()
                read_citations()
                retry_questions()
                retry_returns()
                retry_followthrough_and_evidence()
                check_restricted_metadata(question_two)
            credential["actions"] = [action for action in actions if action != "image_original_read"]
            save_access()
            denied(source_two, index=False)
            read_questions()
            read_review_queue()
            read_followthrough()
            read_citations()
            retry_followthrough_and_evidence()
            credential["actions"] = list(actions)
            save_access()
            for service in ("api", "db"):
                state = snapshot()
                command(["restart", service])
                ready()
                assert snapshot() == state, "Restart changed archive-enabled restored history"
                read_images(source_two)
                read_originals(source_two)
                read_questions()
                read_review_queue()
                read_followthrough()
                read_citations()
                retry_questions()
                retry_returns()
                retry_followthrough_and_evidence()
                check_restricted_metadata(question_two)
                denied(source_one)
                check_history()
                check_question_history()
                verify_stored_originals()
            after_archive = snapshot()
            for owner in archive_state.keys() - {"events"}:
                assert after_archive[owner] == archive_state[owner], "Archive recovery changed durable " + owner
            assert after_archive["events"][:len(archive_state["events"])] == archive_state["events"]
            assert all(row["event_type"] in {
                "source.read_authorized", "image.read_authorized", "image.original_read_authorized",
            } for row in after_archive["events"][len(archive_state["events"]):]), \
                "Archive recovery added non-read business history"
            assert snapshot(source_database) == source_database_snapshot, "Archive checks mutated the source database"
            print("Restored archive HTTP preserved exact originals and immutable question/return/task/citation history; "
                  "changed/missing objects refused without fallback; grants, restricted metadata and API/DB restarts passed")

            calls_before_revocation = archive_history()
            status, revoked, _ = request(patient_path + "/case-bindings/" + CASE + "/revoke", {
                "synthetic": True, "reason": "Withdraw the independently fictional image Compose binding"})
            assert status == 200 and revoked["duplicate"] is False
            denied(source_one, ingest=True)
            denied(source_two, ingest=True)
            denied_questions()
            denied_reviews()
            denied_question_requests(connected_requests())
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
                denied_reviews()
                denied_question_requests(connected_requests())
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
            denied_reviews()
            denied_question_requests(connected_requests())
            assert snapshot() == before, "Restored revoked access changed durable history"
            assert snapshot(restored_database) == before, "Revoked-copy HTTP mutated its source database"
            assert snapshot(source_database) == source_database_snapshot, "Restored revocation/retries mutated the original database"
            assert archive_history() == calls_before_revocation, "Revoked restored access invoked the archive"
            assert archive_history(), "Archive-enabled recovery never invoked the archive"
            print("PASS: canonical v1/v2 questions, immutable verification returns, task events, citations and exact DICOM originals; "
                  "independent grants, immutable anchors, distinct receipts, API/DB restart, "
                  "amendment reassessment, explicit same-object relinking, active restored HTTP/retries, "
                  "archive-enabled restored HTTP without fallback, metadata rights redaction, original DB unchanged, "
                  "and revoked restored denial without archive invocation "
                  "through actual PostgreSQL dump/restore; no clinical approval or evidence appraisal")
        except Exception:
            command(["logs", "--no-color", "--tail", "80"], check=False)
            raise
        finally:
            command(["down", "--volumes"], check=False)


if __name__ == "__main__":
    main()
