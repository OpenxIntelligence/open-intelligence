"""Actual disposable Compose proof for the canonical PostgreSQL source owner.

Only independently authored synthetic UTF-8 text and generated fixture grants
are used. All imports, bindings and reads go through the existing HTTP API.
The owned PostgreSQL container supplies restart and dump/restore evidence.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import base64
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener
import uuid


ROOT = Path(__file__).resolve().parents[3]
BASE = "http://127.0.0.1:8000"
CASE = "CASE-COMPOSE-SOURCE"
ORIGINAL = (
    "OI-SYNTHETIC-REPORT/1\nPatient: CASE-COMPOSE-SOURCE\nDocument: DOC-COMPOSE\n"
    "Type: pathology\nEvent-Date: 2026-01-10\nIssued-At: 2026-01-11\n"
    "Specimen: SPECIMEN-COMPOSE\n"
    "Finding: marker|pending|Independently fictional café marker — pending.\n"
)
AMENDED = (
    "OI-SYNTHETIC-REPORT/1\nPatient: CASE-COMPOSE-SOURCE\nDocument: DOC-COMPOSE\n"
    "Type: pathology\nEvent-Date: 2026-01-10\nIssued-At: 2026-01-12\n"
    "Specimen: SPECIMEN-COMPOSE\nAmends: DOC-COMPOSE@1\n"
    "Finding: marker|negative|Independently fictional café marker — negative.\n"
)
ACCESS_EVENTS = "'source.read_authorized','source.original_read_authorized'"


def main():
    project = "oi-h1-source-proof-" + uuid.uuid4().hex[:12]
    compose = ["docker", "compose", "--project-name", project,
               "--file", str(ROOT / "apps/api/compose.yaml"),
               "--file", str(ROOT / "apps/api/compose.synthetic-access.yaml")]
    with tempfile.TemporaryDirectory(prefix="oi-synthetic-source-access-") as directory:
        access = Path(directory)
        access.chmod(0o755)
        env = dict(os.environ, OI_API_ACCESS_DIRECTORY=directory)
        # The raw token never enters the fixture file, command line or logs.
        token = secrets.token_urlsafe(32)
        actions = ["patient_create", "patient_read", "case_binding_create",
                   "case_binding_read", "case_binding_revoke", "source_import",
                   "source_read", "source_original_read"]
        credential = {
            "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
            "actor": "ACTOR-SOURCE-PROOF", "organization": "ORG-SOURCE-PROOF",
            "purpose": "operations", "actions": list(actions), "patient_ids": [],
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        }
        expected_access = []

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

        def request(path, body=None, *, authenticated=True):
            headers = {"Authorization": "Bearer " + token} if authenticated else {}
            if body is not None:
                headers["Content-Type"] = "application/json"
            req = Request(BASE + path, headers=headers,
                          data=None if body is None else json.dumps(body).encode("utf-8"))
            try:
                response = build_opener(ProxyHandler({})).open(req, timeout=3)
            except HTTPError as exc:
                response = exc
            with response:
                assert response.headers.get("Cache-Control") == "no-store"
                return response.status, json.load(response)

        def ready():
            deadline = time.monotonic() + 45
            while True:
                try:
                    status, value = request("/health/ready", authenticated=False)
                    if status == 200 and value["status"] == "ready":
                        return
                except (OSError, URLError, TimeoutError):
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError("Synthetic source API did not become ready")
                time.sleep(0.25)

        def history(database="oi_api_synthetic"):
            return query(
                "SELECT COALESCE(json_agg(e ORDER BY e.id),'[]'::json) FROM "
                "(SELECT id,patient_id,event_type,metadata_json,occurred_at "
                "FROM identity.identity_domain_events WHERE event_type IN ("
                + ACCESS_EVENTS + ")) e", database)

        def check_history():
            rows = history()
            assert [(row["metadata_json"]["receipt_id"], row["event_type"])
                    for row in rows] == expected_access, "Access receipt history differs from returned receipts"
            assert all(row["patient_id"] == patient for row in rows)
            assert len({receipt for receipt, _ in expected_access}) == len(expected_access)
            encoded = json.dumps(rows, ensure_ascii=False)
            assert token not in encoded and "Independently fictional café marker" not in encoded
            return rows

        def remember(value, event_type):
            receipt = value["access_receipt_id"]
            assert isinstance(receipt, str) and receipt.startswith("ACCESS-"), "Invalid access receipt identifier"
            uuid.UUID(receipt.removeprefix("ACCESS-"))
            expected_access.append((receipt, event_type))

        def read_index(ids):
            status, value = request(source_path)
            assert status == 200, "Source index unavailable"
            remember(value, "source.read_authorized")
            assert (value["patient_id"], value["case_id"]) == (patient, CASE)
            assert value["synthetic"] is True and value["clinical_interpretation"] is False
            assert value["research_review_invalidation_integrated"] is False
            assert [item["source_id"] for item in value["sources"]] == ids
            for index, item in enumerate(value["sources"]):
                original = (ORIGINAL, AMENDED)[index]
                assert (item["document_id"], item["version"], item["specimen_id"]) == (
                    "DOC-COMPOSE", index + 1, "SPECIMEN-COMPOSE")
                assert item["sha256"] == hashlib.sha256(original.encode("utf-8")).hexdigest()
                assert item["state"] == ("superseded" if index + 1 < len(ids) else "current")
                assert item["supersedes_id"] == (None if index == 0 else ids[0])
            assertion, = value["source_reported_assertions"]
            assert assertion["source_id"] == ids[-1]
            assert assertion["finding_key"] == "marker"
            assert assertion["reported_state"] == ("pending" if len(ids) == 1 else "negative")
            assert assertion["source_line"] == (8 if len(ids) == 1 else 9)
            assert assertion["clinical_review_state"] == "not_established"
            expected = "Independently fictional café marker — " + (
                "pending." if len(ids) == 1 else "negative.")
            assert assertion["source_statement"] == expected

        def read_original(source_id, original, version, state):
            status, value = request(source_path + "/" + source_id)
            assert status == 200, "Exact original unavailable"
            remember(value, "source.original_read_authorized")
            raw = value["original_text"].encode("utf-8")
            assert raw == original.encode("utf-8"), "Original UTF-8 bytes changed"
            assert value["sha256"] == hashlib.sha256(raw).hexdigest()
            assert (value["source_id"], value["case_id"], value["version"], value["state"]) == (
                source_id, CASE, version, state)
            assert value["clinical_review_state"] == "not_established"

        def denied(paths, *, authenticated=True):
            before = check_history()
            for path in paths:
                status, value = request(path, authenticated=authenticated)
                assert status == (404 if authenticated else 401), "Source denial did not fail closed"
                assert "access_receipt_id" not in value and "original_text" not in value
            assert history() == before, "Denied read created an authorization receipt"

        def snapshot(database="oi_api_synthetic"):
            # sha256(bytea) is built into PG16; no extension or new dependency.
            return query("""
                SELECT json_build_object(
                  'sources', (SELECT json_agg(s ORDER BY s.document_id,s.version)
                    FROM (SELECT source_id,case_id,document_id,version,sha256,
                      encode(sha256(raw),'hex') AS raw_sha256,octet_length(raw) AS byte_length,
                      state,supersedes_id FROM clinical_source.source_versions) s),
                  'document_intakes', (SELECT json_agg(d ORDER BY d.source_id) FROM clinical_source.document_intakes d),
                  'annotation_revisions', (SELECT json_agg(r ORDER BY r.source_id,r.revision) FROM clinical_source.annotation_revisions r),
                  'assertions', (SELECT json_agg(a ORDER BY a.assertion_id)
                    FROM clinical_source.assertions a),
                  'bindings', (SELECT json_agg(b ORDER BY b.case_id)
                    FROM coordination.patient_case_bindings b),
                  'patients', (SELECT json_agg(p ORDER BY p.patient_id)
                    FROM identity.identity_patients p),
                  'events', (SELECT json_agg(e ORDER BY e.id)
                    FROM identity.identity_domain_events e),
                  'revision', (SELECT version_num FROM public.alembic_version))
            """, database)

        save_access()
        try:
            command(["config", "--quiet"])
            command(["up", "--build", "--detach", "api"])
            ready()
            status, created = request("/v1/patients", {
                "synthetic": True, "request_key": "CREATE-SOURCE-COMPOSE-PROOF"})
            assert status == 201 and created["duplicate"] is False
            patient = created["patient_id"]
            assert re.fullmatch(r"PAT-[0-9A-F]{32}", patient)
            credential["patient_ids"] = [patient]
            save_access()
            patient_path = "/v1/patients/" + patient
            status, binding = request(patient_path + "/case-bindings", {
                "synthetic": True, "case_id": CASE, "source_organization": "ORG-SYNTHETIC-SOURCE",
                "source_system": "SYS-SYNTHETIC-SOURCE", "source_subject_ref": "SUBJECT-COMPOSE",
                "review_ref": "REVIEW-SYNTHETIC-COMPOSE"})
            assert status == 201 and binding["patient_id"] == patient
            source_path = patient_path + "/cases/" + CASE + "/sources"
            source_ids = []
            for version, original in enumerate((ORIGINAL, AMENDED), start=1):
                status, receipt = request(source_path, {"synthetic": True, "original_text": original})
                assert (status, receipt["result"], receipt["version"]) == (201, "imported", version)
                assert re.fullmatch(r"SRC-[0-9A-F]{32}", receipt["source_id"])
                source_ids.append(receipt["source_id"])
                read_index(source_ids)
                read_original(source_ids[-1], original, version, "current")
            read_original(source_ids[0], ORIGINAL, 1, "superseded")
            original_path = source_path + "/" + source_ids[0]
            check_history()

            document_path = patient_path + "/cases/" + CASE + "/documents"
            document_raw = b"Independently fictional reviewed record\r\nMarker pending.\r\nCorrected passage.\r\n"
            upload = {"synthetic": True, "filename": "fictional-review.txt", "original_base64": base64.b64encode(document_raw).decode()}
            status, preview = request(document_path + "/preview", upload)
            assert status == 200
            intake = {**upload, "confirmed_case_id": CASE, "expected_sha256": preview["sha256"],
                      "metadata": {"document_id": "DOC-REVIEWED", "kind": "pathology", "event_date": "2026-01-10",
                                   "issued_at": "2026-01-11", "manual_transcription_confirmed": True},
                      "findings": [{"key": "marker", "state": "pending", "quote": "Marker pending.", "line": 2}]}
            status, document_saved = request(document_path, intake)
            assert status == 201
            saved_path = document_path + "/" + document_saved["source_id"]
            correction = {"synthetic": True, "request_key": "CORRECTION-RECOVERY", "confirmed_case_id": CASE,
                          "expected_sha256": preview["sha256"], "expected_revision_id": document_saved["annotation_revision_id"],
                          "reason": "Correct fictional passage", "findings": [{"key": "passage", "state": "reported", "quote": "Corrected passage.", "line": 3}]}
            status, correction_saved = request(saved_path + "/annotations", correction)
            assert status == 201
            status, document = request(saved_path)
            assert status == 200 and document["preview"]["text"].encode() == document_raw
            assert [r["revision"] for r in document["revisions"]] == [1, 2]

            # Each grant is independent. Changing the mounted fixture takes
            # effect without restarting; denied requests cannot mint receipts.
            for missing, paths in (
                ("source_read", [source_path]),
                ("source_original_read", [original_path]),
                ("patient_read", [source_path, original_path]),
            ):
                credential["actions"] = [action for action in actions if action != missing]
                save_access()
                denied(paths)
            credential["actions"] = list(actions)
            credential["patient_ids"] = []
            save_access()
            denied([source_path, original_path])
            credential["patient_ids"] = [patient]
            credential["purpose"] = "research"
            save_access()
            denied([source_path, original_path])
            credential["purpose"] = "operations"
            save_access()
            denied([source_path, original_path], authenticated=False)

            for service in ("api", "db"):
                before = snapshot()
                command(["restart", service])
                ready()
                assert snapshot() == before, "Restart changed durable sources or history"
                check_history()
                read_index(source_ids)
                read_original(source_ids[0], ORIGINAL, 1, "superseded")
                read_original(source_ids[1], AMENDED, 2, "current")
                check_history()
                status, recovered_document = request(saved_path)
                assert status == 200 and recovered_document["preview"] == document["preview"]
                assert recovered_document["revisions"] == document["revisions"]
                status, recovered_correction = request(saved_path + "/annotations", correction)
                assert status == 200 and recovered_correction["annotation_revision_id"] == correction_saved["annotation_revision_id"]
                print("Source originals, amendments, reviewed selections and access receipts survived " + service + " restart")

            status, revoked = request(patient_path + "/case-bindings/" + CASE + "/revoke", {
                "synthetic": True, "reason": "Withdraw the independently fictional Compose binding"})
            assert status == 200 and revoked["duplicate"] is False
            denied([source_path, original_path, source_path + "/" + source_ids[1]])
            before = snapshot()
            assert len(before["sources"]) == 3 and len(before["assertions"]) == 2
            assert len(before["document_intakes"]) == 1 and len(before["annotation_revisions"]) == 2
            assert before["bindings"][0]["status"] == "revoked"
            for source, original in zip([s for s in before["sources"] if s["document_id"] == "DOC-COMPOSE"], (ORIGINAL, AMENDED)):
                assert source["sha256"] == source["raw_sha256"] == hashlib.sha256(original.encode("utf-8")).hexdigest()
                assert source["byte_length"] == len(original.encode("utf-8"))
            dump = command(["exec", "-T", "db", "pg_dump", "-U", "oi_api", "-d",
                            "oi_api_synthetic", "--format=custom"], capture_output=True).stdout
            restored_database = "oi_api_test_sources_restore"
            command(["exec", "-T", "db", "createdb", "-U", "oi_api", restored_database])
            command(["exec", "-T", "db", "pg_restore", "-U", "oi_api", "-d", restored_database,
                     "--exit-on-error", "--no-owner"], input=dump)
            assert snapshot(restored_database) == before, "Restore changed original hashes, anchors or history"
            assert history(restored_database) == check_history()
            assert next(s for s in before["sources"] if s["document_id"] == "DOC-REVIEWED")["raw_sha256"] == hashlib.sha256(document_raw).hexdigest()
            print("PASS: scoped source HTTP, exact UTF-8 originals, amendment history, denial, "
                  "API/DB restart, durable access receipts, binding revocation and dump/restore")
        except Exception:
            command(["logs", "--no-color", "--tail", "80"], check=False)
            raise
        finally:
            command(["down", "--volumes"])


if __name__ == "__main__":
    main()
