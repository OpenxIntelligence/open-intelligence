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
import sys
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


def assert_restored_selection_response(actual, expected):
    """Require type-exact JSON provenance; only the access receipt may change.

    Expected values are recorded and field-checked on the first authorized HTTP
    read. The anchor digest is recomputed independently at the restored read.
    """
    receipt = actual.get("access_receipt_id")
    assert type(receipt) is str and re.fullmatch(r"ACCESS-[A-F0-9]{32}", receipt), \
        "Restored selection lacks a canonical access receipt"
    received = {key: value for key, value in actual.items() if key != "access_receipt_id"}
    assert json.dumps(received, sort_keys=True, ensure_ascii=False, allow_nan=False) == \
        json.dumps(expected, sort_keys=True, ensure_ascii=False, allow_nan=False), \
        "Restored selection changed exact JSON provenance or freshness"
    anchor = actual["anchor"]
    canonical = json.dumps(anchor, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":"), allow_nan=False)
    assert hashlib.sha256(canonical.encode("utf-8")).hexdigest() == actual["anchor_sha256"], \
        "Restored selection anchor digest differs"


def assert_read_only_recovery(before, after, expected_events):
    """Check complete recovery snapshots against the actual returned receipts."""
    events_table = "identity.identity_domain_events"
    event_sequence = "identity.identity_domain_events_id_seq"
    assert before.keys() == after.keys(), "Snapshot coverage changed"
    assert before["tables"].keys() == after["tables"].keys(), "Table coverage changed"
    for table in before["tables"].keys() - {events_table}:
        assert before["tables"][table] == after["tables"][table], "Read/retry changed " + table
    for key in before.keys() - {"tables", "sequences"}:
        assert before[key] == after[key], "Read/retry changed " + key
    old_rows, new_rows = before["tables"][events_table], after["tables"][events_table]
    old = {row["id"]: row for row in old_rows}
    current = {row["id"]: row for row in new_rows}
    assert len(old) == len(old_rows) and len(current) == len(new_rows), "Duplicate event identifier"
    assert all(current.get(key) == row for key, row in old.items()), "Historical event changed"
    fresh = sorted((row for key, row in current.items() if key not in old), key=lambda row: row["id"])
    assert expected_events and len(fresh) == len(expected_events), "Missing or unexpected restored access event"
    receipts = [event["metadata_json"]["receipt_id"] for event in expected_events]
    assert len(receipts) == len(set(receipts)), "Reused returned receipt"
    old_receipts = {row["metadata_json"].get("receipt_id") for row in old_rows}
    assert not old_receipts.intersection(receipts), "Returned an old access receipt"
    for actual, expected in zip(fresh, expected_events):
        assert actual["id"] > max(old, default=0), "Access event is not appended"
        assert {key: actual[key] for key in ("patient_id", "event_type", "metadata_json")} == expected, \
            "Restored receipt differs from returned scope or action"
        assert actual["event_type"] in {"source.document_read_authorized", "source.original_read_authorized",
                                        "source.document_selection_read_authorized"}, \
            "Read/retry emitted a business event"
    assert before["sequences"].keys() == after["sequences"].keys(), "Sequence coverage changed"
    assert event_sequence in before["sequences"], "Access sequence absent"
    for sequence in before["sequences"].keys() - {event_sequence}:
        assert before["sequences"][sequence] == after["sequences"][sequence], "Business sequence changed"
    prior_sequence = before["sequences"][event_sequence]
    first_id = prior_sequence["last_value"] + int(prior_sequence["is_called"])
    assert [row["id"] for row in fresh] == list(range(first_id, first_id + len(expected_events))), \
        "Unaccounted access sequence allocation"
    assert after["sequences"][event_sequence] == {"last_value": max(current), "is_called": True}, \
        "Unexpected access sequence consumption"


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
            # All application tables, including empty owners, exact bytea values,
            # immutable receipts and events. No selected-column/count-only proof.
            schemas = "('identity','clinical_source','investigation','coordination')"
            tables = query("SELECT COALESCE(json_agg(schemaname || '.' || tablename "
                           "ORDER BY schemaname,tablename),'[]'::json) FROM pg_tables WHERE "
                           "schemaname IN " + schemas + " OR (schemaname='public' AND tablename='alembic_version')", database)
            sequences = query("SELECT COALESCE(json_agg(schemaname || '.' || sequencename "
                              "ORDER BY schemaname,sequencename),'[]'::json) FROM pg_sequences WHERE "
                              "schemaname IN " + schemas, database)
            assert tables and sequences
            assert all(re.fullmatch(r"[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*", name) for name in tables + sequences)
            table_sql = ",".join("'" + table + "',(SELECT COALESCE(json_agg(row ORDER BY row::text),'[]'::json) "
                                 "FROM (SELECT to_jsonb(t) AS row FROM " + table + " t) v)" for table in tables)
            sequence_sql = ",".join("'" + name + "',(SELECT json_build_object('last_value',last_value,"
                                    "'is_called',is_called) FROM " + name + ")" for name in sequences)
            return {
                "tables": query("SELECT json_build_object(" + table_sql + ")", database),
                "sequences": query("SELECT json_build_object(" + sequence_sql + ")", database),
                "sequence_properties": query("SELECT COALESCE(json_agg(row ORDER BY row::text),'[]'::json) "
                    "FROM (SELECT to_jsonb(s) - 'last_value' AS row FROM pg_sequences s WHERE schemaname IN "
                    + schemas + ") v", database),
            }

        def serve_database(database):
            # Same image/credentials/security/network; no migration or seed.
            override = access / "restore.compose.json"
            override.write_text(json.dumps({"services": {"api": {"environment": {
                "OI_API_DATABASE_URL": "postgresql+pg8000://oi_api:oi_h1_synthetic_only@db:5432/" + database,
            }}}}))
            if str(override) not in compose:
                compose.extend(["--file", str(override)])
            command(["up", "--no-deps", "--force-recreate", "--detach", "api"])
            ready()
            result = command(["exec", "-T", "api", "python", "-c",
                "from oi_api.config import Settings\n"
                "from oi_api.database import make_engine\n"
                "from sqlalchemy import text\n"
                "engine = make_engine(Settings.from_env())\n"
                "try:\n"
                "    with engine.connect() as connection:\n"
                "        print(connection.execute(text('SELECT current_database()')).scalar_one())\n"
                "finally:\n"
                "    engine.dispose()\n"], capture_output=True, text=True)
            assert result.stdout.strip() == database, "Recreated API connected to wrong database"

        def restore(source_database, target):
            before = snapshot(source_database)
            dump = command(["exec", "-T", "db", "pg_dump", "-U", "oi_api", "-d",
                            source_database, "--format=custom"], capture_output=True).stdout
            command(["exec", "-T", "db", "createdb", "-U", "oi_api", target])
            command(["exec", "-T", "db", "pg_restore", "-U", "oi_api", "-d", target,
                     "--exit-on-error", "--no-owner"], input=dump)
            assert snapshot(target) == before, "Restore changed complete rows or sequence state"
            serve_database(target)
            assert snapshot(target) == before, "API startup changed restored history"
            assert snapshot(source_database) == before, "Restore changed source database"
            return before

        def original_bytes(path):
            req = Request(BASE + path, headers={"Authorization": "Bearer " + token})
            with build_opener(ProxyHandler({})).open(req, timeout=5) as response:
                assert response.status == 200
                assert response.headers.get("Cache-Control") == "no-store"
                assert response.headers.get("X-Content-Type-Options") == "nosniff"
                return response.read(), response.headers

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
            document_raw = "Independently fictional café record\r\nMarker pending.\r\nCorrected passage.\r\n".encode("utf-8")
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

            # Reuse the repository's independently authored, deterministic PDF generator.
            sys.path.insert(0, str(ROOT / "tests"))
            from pdf_fixtures import text_pdf
            pdf_raw = text_pdf([["Independently fictional recovery page one"],
                                ["Marker pending.", "Corrected passage."]])
            pdf_upload = {"synthetic": True, "filename": "fictional-recovery.pdf",
                          "original_base64": base64.b64encode(pdf_raw).decode()}
            status, pdf_preview = request(document_path + "/preview", pdf_upload)
            assert status == 200 and pdf_preview["page_count"] == 2
            pdf_intake = {**pdf_upload, "confirmed_case_id": CASE, "expected_sha256": pdf_preview["sha256"],
                          "expected_extraction_sha256": pdf_preview["extraction_sha256"],
                          "metadata": {**intake["metadata"], "document_id": "DOC-REVIEWED-PDF"},
                          "findings": [{"key": "marker", "state": "pending", "quote": "Marker pending.", "line": 2}]}
            status, pdf_saved = request(document_path, pdf_intake)
            assert status == 201
            pdf_path = document_path + "/" + pdf_saved["source_id"]
            pdf_correction = {**correction, "expected_sha256": pdf_preview["sha256"],
                              "expected_extraction_sha256": pdf_preview["extraction_sha256"],
                              "expected_revision_id": pdf_saved["annotation_revision_id"],
                              "findings": [{"key": "passage", "state": "reported", "quote": "Corrected passage.", "line": 3}]}
            status, pdf_corrected = request(pdf_path + "/annotations", pdf_correction)
            assert status == 201
            status, pdf_document = request(pdf_path)
            assert status == 200 and [r["revision"] for r in pdf_document["revisions"]] == [1, 2]
            assert pdf_document["preview"]["lines"][1]["page"] == 2
            assert pdf_document["preview"]["lines"][2]["page"] == 2
            assert pdf_document["revisions"][1]["findings"][0]["line"] == 3
            documents = [
                dict(path=saved_path, raw=document_raw, saved=document_saved, intake=intake,
                     correction=correction, corrected=correction_saved, document=document),
                dict(path=pdf_path, raw=pdf_raw, saved=pdf_saved, intake=pdf_intake,
                     correction=pdf_correction, corrected=pdf_corrected, document=pdf_document),
            ]
            status, document_index = request(document_path)
            assert status == 200 and len(document_index["documents"]) == 2
            for item in documents:
                item["selections"] = []
                for revision in item["document"]["revisions"]:
                    finding, = revision["findings"]
                    path = item["path"] + "/selections/" + revision["revision_id"] + "/" + finding["key"]
                    status, value = request(path)
                    assert status == 200
                    anchor = value["anchor"]
                    assert value["contract"] == "oi.reviewed-document-selection/1"
                    assert anchor["source_id"] == item["saved"]["source_id"]
                    assert anchor["original_sha256"] == hashlib.sha256(item["raw"]).hexdigest()
                    assert anchor["extraction_sha256"] == item["document"]["preview"].get("extraction_sha256")
                    assert anchor["annotation_revision_id"] == revision["revision_id"]
                    assert anchor["review_sha256"] == revision["review_sha256"]
                    assert (anchor["selection_key"], anchor["quote"], anchor["line"]) == \
                           (finding["key"], finding["quote"], finding["line"])
                    assert (anchor["selected_state"], anchor["selected_by"], anchor["selected_at"]) == \
                           (finding["state"], revision["actor"], revision["created_at"])
                    assert anchor["page"] == item["document"]["preview"]["lines"][finding["line"] - 1].get("page")
                    assert value["anchor_sha256"] == hashlib.sha256(json.dumps(
                        anchor, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
                    assert value["selection_state"] == (
                        "current_unreviewed_selection" if revision == item["document"]["revisions"][-1]
                        else "selection_reassessment_required")
                    item["selections"].append({"path": path, "reference": {
                        key: field for key, field in value.items() if key != "access_receipt_id"}})

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

            # Back up while readable. Denial-only restore cannot establish that
            # an allowed original/history can actually be served after recovery.
            original_database = "oi_api_synthetic"
            restored_database = "oi_api_test_documents_restore"
            readable_before = restore(original_database, restored_database)
            rows = readable_before["tables"]
            assert len(rows["clinical_source.source_versions"]) == 4
            assert len(rows["clinical_source.assertions"]) == 2
            assert len(rows["clinical_source.document_intakes"]) == 2
            assert len(rows["clinical_source.annotation_revisions"]) == 4
            assert rows["public.alembic_version"] == [{"version_num": "0016_manual_task_dependency"}]
            for item in documents:
                stored = next(row for row in rows["clinical_source.source_versions"]
                              if row["source_id"] == item["saved"]["source_id"])
                assert bytes.fromhex(stored["raw"][2:]) == item["raw"]
                assert stored["sha256"] == hashlib.sha256(item["raw"]).hexdigest()

            restored_events = []

            def document_receipt(receipt_id, event_type, item=None):
                assert re.fullmatch(r"ACCESS-[A-F0-9]{32}", receipt_id)
                restored_events.append({"patient_id": patient, "event_type": event_type,
                    "metadata_json": {"receipt_id": receipt_id, "case_id": CASE,
                        "actor": credential["actor"], "purpose": "operations", "binding_revision": 1,
                        "source_id": item["saved"]["source_id"] if item else None,
                        "sha256": hashlib.sha256(item["raw"]).hexdigest() if item else None}})

            def restored_index():
                status, value = request(document_path)
                assert status == 200 and value["documents"] == document_index["documents"]
                assert (value["patient_id"], value["case_id"], value["synthetic"]) == (patient, CASE, True)
                document_receipt(value["access_receipt_id"], "source.document_read_authorized")

            def restored_document(item):
                status, value = request(item["path"])
                assert status == 200
                assert {k: v for k, v in value.items() if k != "access_receipt_id"} == \
                       {k: v for k, v in item["document"].items() if k != "access_receipt_id"}, \
                       "Restored rendition, anchor or immutable correction history changed"
                document_receipt(value["access_receipt_id"], "source.document_read_authorized", item)

            def restored_original(item):
                raw, headers = original_bytes(item["path"] + "/original")
                assert raw == item["raw"], "Restored original bytes changed"
                assert headers["X-Content-SHA256"] == hashlib.sha256(raw).hexdigest()
                assert headers["Content-Disposition"] == 'attachment; filename="' + item["intake"]["filename"] + '"'
                assert headers["Content-Type"].split(";")[0] == item["document"]["preview"]["media_type"].split(";")[0]
                document_receipt(headers["X-Access-Receipt-ID"], "source.original_read_authorized", item)

            def restored_selection(item, selected):
                status, value = request(selected["path"])
                assert status == 200
                assert_restored_selection_response(value, selected["reference"])
                receipt_id = value["access_receipt_id"]
                anchor = value["anchor"]
                restored_events.append({"patient_id": patient,
                    "event_type": "source.document_selection_read_authorized",
                    "metadata_json": {"receipt_id": receipt_id, "case_id": CASE,
                        "actor": credential["actor"], "purpose": "operations", "binding_revision": 1,
                        "source_id": item["saved"]["source_id"],
                        "annotation_revision_id": anchor["annotation_revision_id"],
                        "selection_key": anchor["selection_key"], "anchor_sha256": value["anchor_sha256"]}})

            def exact_retries(item):
                for path, body, prior in ((document_path, item["intake"], item["saved"]),
                                         (item["path"] + "/annotations", item["correction"], item["corrected"])):
                    status, value = request(path, body)
                    assert status == 200 and value == {**prior, "duplicate": True}, "Restored retry identity changed"

            def readable_cycle():
                restored_index()
                for item in documents:
                    restored_document(item)
                    restored_original(item)
                    for selected in item["selections"]:
                        restored_selection(item, selected)
                    exact_retries(item)

            def no_effect_denial(path, body=None, *, authenticated=True, database=restored_database):
                before = snapshot(database)
                status, value = request(path, body, authenticated=authenticated)
                assert status == (404 if authenticated else 401), "Restored authority did not fail closed"
                assert set(value) == {"detail"} and isinstance(value["detail"], str), "Denial exposed document fields"
                assert snapshot(database) == before, "Denied document request caused effects"

            readable_cycle()
            for service in ("api", "db"):
                before = snapshot(restored_database)
                command(["restart", service])
                ready()
                assert snapshot(restored_database) == before, "Restored restart changed durable state"
                readable_cycle()

            for missing in ("source_read", "source_original_read", "source_import", "patient_read"):
                credential["actions"] = [action for action in actions if action != missing]
                save_access()
                if missing in ("source_read", "patient_read"):
                    no_effect_denial(document_path)
                else:
                    restored_index()
                for item in documents:
                    if missing in ("source_read", "source_original_read", "patient_read"):
                        no_effect_denial(item["path"])
                    else:
                        restored_document(item)
                    if missing in ("source_original_read", "patient_read"):
                        no_effect_denial(item["path"] + "/original")
                    else:
                        restored_original(item)
                    for selected in item["selections"]:
                        if missing in ("source_read", "source_original_read", "patient_read"):
                            no_effect_denial(selected["path"])
                        else:
                            restored_selection(item, selected)
                    if missing in ("source_import", "patient_read"):
                        no_effect_denial(document_path, item["intake"])
                    else:
                        status, value = request(document_path, item["intake"])
                        assert status == 200 and value == {**item["saved"], "duplicate": True}
                    if missing in ("source_import", "source_original_read", "patient_read"):
                        no_effect_denial(item["path"] + "/annotations", item["correction"])
                    else:
                        status, value = request(item["path"] + "/annotations", item["correction"])
                        assert status == 200 and value == {**item["corrected"], "duplicate": True}

            credential["actions"] = list(actions)
            save_access()
            for field, unavailable in (("patient_ids", []), ("purpose", "research")):
                previous = credential[field]
                credential[field] = unavailable
                save_access()
                no_effect_denial(document_path)
                for item in documents:
                    no_effect_denial(item["path"])
                    no_effect_denial(item["path"] + "/original")
                    no_effect_denial(item["path"] + "/annotations", item["correction"])
                    for selected in item["selections"]:
                        no_effect_denial(selected["path"])
                credential[field] = previous
                save_access()
            no_effect_denial(document_path, authenticated=False)
            for item in documents:
                no_effect_denial(item["path"].replace(CASE, "CASE-NOT-BOUND"))
                no_effect_denial(item["path"].replace(CASE, "CASE-NOT-BOUND") + "/original")
                for selected in item["selections"]:
                    no_effect_denial(selected["path"], authenticated=False)
                    no_effect_denial(selected["path"].replace(CASE, "CASE-NOT-BOUND"))
            readable_cycle()
            assert_read_only_recovery(readable_before, snapshot(restored_database), restored_events)
            assert snapshot(original_database) == readable_before, "Restored HTTP changed original database"
            print("PASS RESTORED DOCUMENT HTTP: text/PDF exact bytes, page anchors, immutable history, "
                  "exact current/historical selection references and hashes, exact retries, independent "
                  "grants and restarts; restored-only access receipts")

            # Revoke on the restored copy and back it up again. Keep every grant
            # enabled so only the restored binding state can explain denial.
            assert credential["actions"] == actions and credential["patient_ids"] == [patient]
            assert credential["purpose"] == "operations"
            status, revoked = request(patient_path + "/case-bindings/" + CASE + "/revoke", {
                "synthetic": True, "reason": "Withdraw the independently fictional Compose binding"})
            assert status == 200 and revoked["duplicate"] is False
            revoked_database = "oi_api_test_documents_revoked"
            revoked_before = restore(restored_database, revoked_database)
            assert revoked_before["tables"]["coordination.patient_case_bindings"][0]["status"] == "revoked"
            no_effect_denial(document_path, database=revoked_database)
            for item in documents:
                for path, body in ((item["path"], None), (item["path"] + "/original", None),
                                   (document_path, item["intake"]),
                                   (document_path + "/preview", {k: item["intake"][k] for k in ("synthetic", "filename", "original_base64")}),
                                   (item["path"] + "/annotations", item["correction"])):
                    no_effect_denial(path, body, database=revoked_database)
                for selected in item["selections"]:
                    no_effect_denial(selected["path"], database=revoked_database)
            for path in (source_path, original_path, source_path + "/" + source_ids[1]):
                status, value = request(path)
                assert status == 404 and "access_receipt_id" not in value and "original_text" not in value
            assert snapshot(revoked_database) == revoked_before, "Restored revoked requests changed state"
            assert snapshot(restored_database) == revoked_before, "Revoked restore changed its source copy"
            assert snapshot(original_database) == readable_before, "Recovery changed original database"
            receipt = {"contract": "oi.source-document-recovery/1", "synthetic": True,
                "schema_revision": "0016_manual_task_dependency", "table_count": len(rows),
                "sequence_count": len(readable_before["sequences"]),
                "documents": [{"source_id": item["saved"]["source_id"],
                    "sha256": hashlib.sha256(item["raw"]).hexdigest(), "byte_length": len(item["raw"]),
                    "revision_ids": [r["revision_id"] for r in item["document"]["revisions"]],
                    "selection_anchor_sha256": [selected["reference"]["anchor_sha256"]
                                               for selected in item["selections"]]}
                    for item in documents],
                "restored_access_receipts": len(restored_events), "restored_readable_http": True,
                "restored_binary_originals": True, "restored_exact_retries": True,
                "restored_exact_selection_references": sum(len(item["selections"]) for item in documents),
                "restored_independent_grants": True, "restored_api_database_restart": True,
                "restored_revoked_binding_denial": True, "original_database_unchanged": True}
            output = os.environ.get("OI_SOURCE_ACCEPTANCE_FILE")
            if output:
                Path(output).parent.mkdir(parents=True, exist_ok=True)
                Path(output).write_text(json.dumps(receipt, indent=2) + "\n")
            print("PASS: scoped source HTTP, exact UTF-8 originals, amendment history, denial, "
                  "API/DB restart, durable access receipts and complete dump/restore; actual restored "
                  "text/PDF/history/selection/retry HTTP, independent permissions and restored revoked binding")

        except Exception:
            command(["logs", "--no-color", "--tail", "80"], check=False)
            raise
        finally:
            command(["down", "--volumes"])


if __name__ == "__main__":
    main()
