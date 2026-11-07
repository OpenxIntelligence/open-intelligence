"""Actual isolated Compose acceptance, including restart and backup restore.

Uses generated synthetic credentials, fictional identity and EHR records, a unique
owned project and disposable volumes. Never accepts a deployment database URL.
"""

from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
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

from oi_api.contracts import SCHEMA_REVISION


ROOT = Path(__file__).resolve().parents[3]
BASE = "http://127.0.0.1:8000"
SOURCE_DB = "oi_api_synthetic"
RESTORE_DB = "oi_api_test_restore"
NOTE_KEY = "PROOF-NOTE"
CASE = "CASE-EHR-RESTORE"
REPORT = (
    f"OI-SYNTHETIC-REPORT/1\nPatient: {CASE}\nDocument: DOC-EHR-RESTORE\n"
    "Type: pathology\nEvent-Date: 2026-05-04\nIssued-At: 2026-05-05\n"
    "Finding: marker|pending|Independently fictional marker pending.\n"
)
AMENDMENT = (
    f"OI-SYNTHETIC-REPORT/1\nPatient: {CASE}\nDocument: DOC-EHR-RESTORE\n"
    "Type: pathology\nEvent-Date: 2026-05-04\nIssued-At: 2026-05-06\nAmends: DOC-EHR-RESTORE@1\n"
    "Finding: marker|negative|Independently fictional amended marker.\n"
)


def verify_chart(encounters, headers, history, *, patient, encounter_id, schedule, actor, drafts, receipts):
    """Check scoped HTTP results against the authored commands and their write receipts."""
    assert encounters["patient_id"] == headers["patient_id"] == history["patient_id"] == patient
    assert headers["encounter_id"] == history["encounter_id"] == encounter_id
    assert history["note_key"] == NOTE_KEY
    assert encounters["next_after_id"] is headers["next_after_id"] is history["next_after_version"] is None
    visit, = encounters["encounters"]
    assert (visit["id"], visit["patient_id"], visit["external_key"], visit["kind"], visit["service_date"],
            visit["status"], visit["revision"]) == (
        encounter_id, patient, schedule["external_key"], schedule["kind"], schedule["service_date"], "in_progress", 2)
    header, = headers["notes"]
    assert (header["note_key"], header["latest_version"]) == (NOTE_KEY, len(drafts))
    prior = None
    version_ids = set()
    for number, (row, draft, receipt) in enumerate(zip(history["versions"], drafts, receipts, strict=True), 1):
        assert type(row["id"]) is int and row["id"] > 0 and row["id"] not in version_ids
        version_ids.add(row["id"])
        digest = hashlib.sha256(draft["body"].encode("utf-8")).hexdigest()
        assert receipt == {"note_id": header["id"], "note_key": NOTE_KEY, "version": number,
                           "status": "draft", "sha256": digest}
        assert (row["version"], row["supersedes_id"], row["status"], row["amendment_reason"],
                row["body"], row["sha256"], row["authored_by"]) == (
            number, prior, "draft", None, draft["body"], digest, actor)
        assert all(row[key] == draft[key] for key in ("facility_id", "department_id", "note_kind"))
        prior = row["id"]
    # Capture all remaining fields, including original timestamp strings, for exact recovery comparison.
    return json.dumps([encounters, headers, history], sort_keys=True, ensure_ascii=False)


def main():
    project = "oi-h1-registry-proof-" + uuid.uuid4().hex[:12]
    compose = ["docker", "compose", "--project-name", project,
               "--file", str(ROOT / "apps/api/compose.yaml"),
               "--file", str(ROOT / "apps/api/compose.synthetic-access.yaml")]
    with tempfile.TemporaryDirectory(prefix="oi-synthetic-access-") as directory:
        access = Path(directory)
        # Only synthetic grants and token hashes are mounted; raw keys stay in
        # this process. The unprivileged API container needs read/traverse access.
        access.chmod(0o755)
        env = dict(os.environ, OI_API_ACCESS_DIRECTORY=directory)
        tokens = [secrets.token_urlsafe(32), secrets.token_urlsafe(32)]
        credentials = [
            {"token_sha256": hashlib.sha256(token.encode()).hexdigest(),
             "actor": "ACTOR-PROOF-" + suffix, "organization": "ORG-PROOF-" + suffix,
             "purpose": "operations", "actions": ["patient_create", "patient_read"],
             "patient_ids": [], "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}
            for token, suffix in zip(tokens, ("ALPHA", "BETA"))
        ]

        def save_access():
            pending = access / "access.new"
            pending.write_text(json.dumps({"version": "oi.synthetic-access/1", "credentials": credentials}))
            pending.chmod(0o644)
            pending.replace(access / "access.json")

        def command(args, **kwargs):
            return subprocess.run(compose + args, cwd=ROOT, env=env, check=True, timeout=180, **kwargs)

        def inspect(service):
            container_id = command(["ps", "--all", "--quiet", service], capture_output=True, text=True).stdout.strip()
            assert container_id, service + " container missing"
            return json.loads(subprocess.check_output(["docker", "inspect", container_id], text=True))[0]

        def request(path, token=None, body=None):
            headers = {} if token is None else {"Authorization": "Bearer " + token}
            if body is not None:
                headers["Content-Type"] = "application/json"
            req = Request(BASE + path, data=None if body is None else json.dumps(body).encode(), headers=headers)
            try:
                response = build_opener(ProxyHandler({})).open(req, timeout=2)
            except HTTPError as exc:
                response = exc
            with response:
                assert response.headers.get("Cache-Control") == "no-store"
                return response.status, json.load(response)

        def ready():
            deadline = time.monotonic() + 45
            while True:
                try:
                    status, body = request("/health/ready")
                    if status == 200 and body["status"] == "ready":
                        return
                except (OSError, URLError, TimeoutError):
                    pass
                if time.monotonic() >= deadline:
                    raise RuntimeError("Synthetic API did not become ready")
                time.sleep(0.25)

        save_access()
        try:
            command(["config", "--quiet"])
            command(["up", "--build", "--detach", "api"])
            migration, api, db = (inspect(service) for service in ("migrate", "api", "db"))
            assert migration["State"]["Status"] == "exited" and migration["State"]["ExitCode"] == 0
            assert api["NetworkSettings"]["Ports"].get("8000/tcp") == [{"HostIp": "127.0.0.1", "HostPort": "8000"}]
            assert not any(db["NetworkSettings"]["Ports"].values())
            networks = json.loads(subprocess.check_output(
                ["docker", "network", "inspect", *api["NetworkSettings"]["Networks"]], text=True))
            internal = {item["Name"] for item in networks if item["Internal"]}
            assert len(internal) == 1 and len(networks) == 2
            assert set(db["NetworkSettings"]["Networks"]) == internal
            assert set(migration["NetworkSettings"]["Networks"]) == internal
            ready()
            assert request("/health") == (200, {"status": "ok"})
            manifest = request("/v1")[1]
            assert manifest["stage"] == "synthetic_patient_registry"
            assert manifest["authentication"] == "synthetic_fixture" and manifest["patient_data_enabled"] is False
            assert request("/v1/openapi.json")[1]["paths"]["/v1/patients"]["post"]["security"] == [{"SyntheticFixture": []}]
            payload = {"synthetic": True, "request_key": "REQUEST-COMPOSE-PROOF"}
            assert request("/v1/patients", body=payload)[0] == 401
            status, receipt = request("/v1/patients", tokens[0], payload)
            assert status == 201 and not receipt["duplicate"], (status, receipt)
            patient = receipt["patient_id"]
            assert re.fullmatch(r"PAT-[0-9A-F]{32}", patient)
            path = "/v1/patients/" + patient
            assert request(path, tokens[0])[0] == 404  # Creation is not a read grant.
            for credential in credentials:
                credential["patient_ids"] = [patient]
            save_access()
            assert request(path, tokens[0])[0] == 200
            assert request(path, tokens[1]) == (404, {"detail": "Patient unavailable"})
            encounter_actions = ["encounter.schedule", "encounter.transition", "encounter.read", "note.write", "note.read",
                                 "case_binding_create", "source_read", "source_import", "encounter.source.link"]
            for credential in credentials:
                credential["actions"].extend(encounter_actions)
            save_access()
            encounters_path = path + "/encounters"
            schedule = {"synthetic": True, "request_key": "SCHEDULE-PROOF", "external_key": "PROOF-VISIT",
                        "kind": "outpatient", "service_date": "2026-05-04"}
            status, visit = request(encounters_path, tokens[0], schedule)
            assert status == 200 and visit["status"] == "scheduled"
            encounter_id = visit["encounter_id"]
            visit_path = encounters_path + "/" + str(encounter_id)
            transition = {"synthetic": True, "request_key": "START-VISIT", "target": "in_progress", "expected_revision": 1}
            started = request(visit_path + "/transitions", tokens[0], transition)
            assert started == (200, {"encounter_id": encounter_id, "revision": 2, "status": "in_progress"})
            headers_path = visit_path + "/notes"
            note_path = headers_path + "/" + NOTE_KEY + "/versions"
            drafts = [
                {"synthetic": True, "request_key": "PROOF-DRAFT-1", "expected_version": 0,
                 "body": "Independently fictional draft.", "note_kind": "consultation",
                 "facility_id": "FACILITY-PROOF-A", "department_id": "DEPARTMENT-PROOF-A"},
                {"synthetic": True, "request_key": "PROOF-DRAFT-2", "expected_version": 1,
                 "body": "Revised independently fictional draft — café.", "note_kind": "progress",
                 "facility_id": "FACILITY-PROOF-B", "department_id": "DEPARTMENT-PROOF-B"},
            ]
            receipts = []
            for draft in drafts:
                written = request(note_path, tokens[0], draft)
                assert written[0] == 200
                assert request(note_path, tokens[0], draft) == written
                receipts.append(written[1])

            status, binding = request(path + "/case-bindings", tokens[0], {
                "synthetic": True, "case_id": CASE, "source_organization": "ORG-PROOF-SOURCE",
                "source_system": "SYS-PROOF", "source_subject_ref": "SUBJECT-PROOF", "review_ref": "REVIEW-PROOF"})
            assert (status, binding["patient_id"], binding["case_id"]) == (201, patient, CASE)
            source_path = path + "/cases/" + CASE + "/sources"
            status, source = request(source_path, tokens[0], {"synthetic": True, "original_text": REPORT})
            assert (status, source["result"], source["version"]) == (201, "imported", 1)
            links_path = visit_path + "/cases/" + CASE + "/source-links"
            link_command = {"synthetic": True, "request_key": "LINK-REPORT-PROOF", "source_id": source["source_id"],
                            "expected_version": 1, "expected_sha256": hashlib.sha256(REPORT.encode()).hexdigest()}
            status, linked = request(links_path, tokens[0], link_command)
            assert status == 201 and linked["duplicate"] is False
            status, amended = request(source_path, tokens[0], {"synthetic": True, "original_text": AMENDMENT})
            assert (status, amended["result"], amended["version"]) == (201, "imported", 2)
            assert amended["source_id"] != source["source_id"]
            scope = {"patient_id": patient, "encounter_id": encounter_id, "case_id": CASE}
            expected_link = {**scope, "id": linked["id"], "source_id": source["source_id"], "version": 1,
                             "sha256": link_command["expected_sha256"], "source_state": "superseded"}
            read_ids = []

            def page(url):
                status, value = request(url, tokens[0])
                assert status == 200, "Chart read unavailable"
                receipt_id = value.pop("access_receipt_id")
                assert re.fullmatch(r"ACCESS-[A-F0-9]{32}", receipt_id) and receipt_id not in read_ids
                read_ids.append(receipt_id)
                return value

            def chart():
                pages = [page(url) for url in (encounters_path, headers_path, note_path)]
                assert page(links_path) == {**scope, "links": [expected_link], "next_after_id": None}
                return verify_chart(*pages, patient=patient, encounter_id=encounter_id, schedule=schedule,
                                    actor=credentials[0]["actor"], drafts=drafts, receipts=receipts)

            expected_chart = chart()
            unavailable = (404, {"detail": "Encounter unavailable"})
            assert request(note_path, tokens[1]) == unavailable
            for service in ("api", "db"):
                command(["restart", service])
                ready()
                assert request("/v1/patients", tokens[0], payload) == (200, {"patient_id": patient, "duplicate": True})
                assert request(path, tokens[0])[1]["patient_id"] == patient
                assert chart() == expected_chart, "Chart changed across restart"
                print("Canonical identity, chart and idempotency persisted after " + service + " restart")

            # The only targets are disposable databases in this unique Compose project.
            def snapshot(database):
                # Complete rows for the owners exercised here, including immutable commands and audit events.
                def query(sql):
                    result = command(["exec", "-T", "db", "psql", "-X", "-U", "oi_api", "-d", database,
                                      "-v", "ON_ERROR_STOP=1", "-At", "-c", sql], capture_output=True, text=True)
                    return json.loads(result.stdout)

                ehr = query("SELECT json_agg(tablename ORDER BY tablename) FROM pg_tables WHERE schemaname='ehr'")
                assert all(re.fullmatch(r"[a-z_][a-z0-9_]*", name) for name in ehr)
                tables = (["ehr." + name for name in ehr] + ["public.alembic_version", "identity.identity_patients",
                          "identity.identity_create_receipts", "identity.identity_domain_events",
                          "coordination.patient_case_bindings", "clinical_source.source_versions", "clinical_source.assertions"])
                fields = ",".join("'" + table + "',(SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY "
                                  + ("t.id" if table == "identity.identity_domain_events" else "to_jsonb(t)")
                                  + "),'[]'::jsonb) FROM " + table + " t)" for table in tables)
                return query("SELECT jsonb_build_object(" + fields + ", 'sequences', (SELECT jsonb_object_agg("
                             "s.schemaname || '.' || s.sequencename,s.last_value) FROM pg_sequences s "
                             "WHERE s.schemaname IN ('identity','ehr','clinical_source','coordination')))")

            events = "identity.identity_domain_events"
            before = snapshot(SOURCE_DB)
            assert before["public.alembic_version"] == [{"version_num": SCHEMA_REVISION}]
            assert [row["patient_id"] for row in before["identity.identity_patients"]] == [patient]
            assert len(before["identity.identity_create_receipts"]) == 1
            assert len(before["ehr.clinical_encounter_commands"]) == 4
            assert len(before["ehr.encounter_source_links"]) == 1
            event_counts = Counter(row["event_type"] for row in before[events])
            for kind, count in (("identity.patient.created", 1), ("clinical_encounter_scheduled", 1),
                                ("clinical_encounter_state_changed", 1), ("clinical_note_draft_saved", 2),
                                ("clinical_encounter_source_linked", 1), ("source.original.imported", 2)):
                assert event_counts[kind] == count, (kind, event_counts[kind])
            read_kinds = ("clinical_encounter_read_authorized", "clinical_encounter_sources_read_authorized")
            assert [row["metadata_json"]["receipt_id"] for row in before[events] if row["event_type"] in read_kinds] == read_ids

            dump = command(["exec", "-T", "db", "pg_dump", "-U", "oi_api", "-d", SOURCE_DB, "--format=custom"],
                           capture_output=True).stdout
            command(["exec", "-T", "db", "createdb", "-U", "oi_api", RESTORE_DB])
            command(["exec", "-T", "db", "pg_restore", "-U", "oi_api", "-d", RESTORE_DB,
                     "--exit-on-error", "--no-owner"], input=dump)
            assert snapshot(RESTORE_DB) == before, "Restored rows or sequence state differ from source"

            # Start the same API against the restore, without migrations or reseeding. Returned
            # receipt IDs must appear on this database, and the source snapshot must stay unchanged.
            override = access / "restore.compose.json"
            override.write_text(json.dumps({"services": {"api": {"environment": {
                "OI_API_DATABASE_URL": "postgresql+pg8000://oi_api:oi_h1_synthetic_only@db:5432/" + RESTORE_DB,
            }}}}))
            compose.extend(["--file", str(override)])
            command(["up", "--no-deps", "--force-recreate", "--detach", "api"])
            ready()
            configured = command(["exec", "-T", "api", "python", "-c",
                "from oi_api.config import Settings\nfrom oi_api.database import make_engine\n"
                "with make_engine(Settings.from_env()).connect() as c:\n"
                "    print(c.exec_driver_sql('SELECT current_database()').scalar_one())"],
                capture_output=True, text=True)
            assert configured.stdout.strip() == RESTORE_DB, "Recreated API is connected to the source database"
            assert chart() == expected_chart, "Restored HTTP chart differs from original"
            target = snapshot(RESTORE_DB)
            assert target[events][:len(before[events])] == before[events], "Restored journal history changed"
            new_events = target[events][len(before[events]):]
            assert [row["metadata_json"]["receipt_id"] for row in new_events] == read_ids[-4:], \
                "Returned HTTP receipts are absent from the restored database"
            reads = [
                (read_kinds[0], {"action": "encounter.read", "after_id": 0}),
                (read_kinds[0], {"action": "note.read", "encounter_id": encounter_id, "after_id": 0}),
                (read_kinds[0], {"action": "note.read", "encounter_id": encounter_id, "note_key": NOTE_KEY, "after_version": 0}),
                (read_kinds[1], {"encounter_id": encounter_id, "case_id": CASE, "after_id": 0}),
            ]
            for event, receipt_id, (kind, refs) in zip(new_events, read_ids[-4:], reads, strict=True):
                assert (event["patient_id"], event["event_type"]) == (patient, kind)
                assert event["metadata_json"] == dict(refs, receipt_id=receipt_id, actor=credentials[0]["actor"],
                                                      purpose="operations", page_size=25)
            assert all(target[k] == before[k] for k in before if k not in (events, "sequences"))
            event_sequence = "identity.identity_domain_events_id_seq"
            assert before["sequences"][event_sequence] + len(new_events) == new_events[-1]["id"]
            assert target["sequences"] == {**before["sequences"], event_sequence: new_events[-1]["id"]}

            assert request(encounters_path, tokens[0], schedule) == (200, visit)
            assert request(visit_path + "/transitions", tokens[0], transition) == started
            for draft, original in zip(drafts, receipts, strict=True):
                assert request(note_path, tokens[0], draft) == (200, original)
            assert request(note_path, tokens[0], dict(drafts[0], facility_id="FACILITY-OTHER")) == (
                409, {"detail": "Encounter command, state or version conflict"})
            assert request(links_path, tokens[0], link_command) == (200, {"id": linked["id"], "duplicate": True})
            for url in (encounters_path, headers_path, note_path, links_path):
                assert request(url, tokens[1]) == unavailable
            credentials[0]["actions"].remove("source_read")
            save_access()
            assert request(links_path, tokens[0]) == unavailable
            assert request(links_path, tokens[0], link_command) == unavailable
            credentials[0]["actions"].remove("note.read")
            save_access()
            for url in (headers_path, note_path):
                assert request(url, tokens[0]) == unavailable
            credentials[0]["actions"].remove("encounter.read")
            save_access()
            assert request(encounters_path, tokens[0]) == unavailable
            assert snapshot(RESTORE_DB) == target, "Retry, conflict or denial changed restored data or audit history"
            assert snapshot(SOURCE_DB) == before, "Restored API traffic changed the source database"
            print("PASS EHR: restored HTTP chart, attributed draft history, superseded source link, exact command retries, "
                  "intent conflict, tenant and withdrawn-grant denial; unchanged original")
            credentials[0]["patient_ids"] = []
            save_access()
            assert request(path, tokens[0])[0] == 404
            credentials.clear()
            save_access()
            assert request("/v1/patients", tokens[0], payload)[0] == 401
            print("PASS: actual scoped HTTP, tenant denial, API/DB restart, dump/restore, and next-request revocation")
        except Exception:
            command(["logs", "--no-color", "--tail", "80"])
            raise
        finally:
            command(["down", "--volumes"])


if __name__ == "__main__":
    main()
