"""Actual isolated Compose acceptance, including restart and backup restore.

Uses generated synthetic credentials, fictional identity-only records, a unique
owned project and disposable volumes. Never accepts a deployment database URL.
"""

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
            return subprocess.run(compose + args, cwd=ROOT, env=env, check=True, **kwargs)

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

        def snapshot(database="oi_api_synthetic"):
            tables = ("identity.identity_patients", "identity.identity_create_receipts",
                      "identity.identity_domain_events", "ehr.clinical_encounters",
                      "ehr.clinical_note_headers", "ehr.clinical_note_versions",
                      "ehr.clinical_encounter_commands", "public.alembic_version")
            result = {}
            for table in tables:
                sql = ("SELECT COALESCE(json_agg(row ORDER BY row::text),'[]'::json) "
                       "FROM (SELECT to_jsonb(t) AS row FROM " + table + " t) v")
                output = command(["exec", "-T", "db", "psql", "-X", "-U", "oi_api", "-d", database,
                                  "-v", "ON_ERROR_STOP=1", "-At", "-c", sql], capture_output=True, text=True)
                result[table] = json.loads(output.stdout)
            sql = """SELECT COALESCE(json_agg(s ORDER BY schemaname,sequencename),'[]'::json)
                     FROM (SELECT schemaname,sequencename,start_value,min_value,max_value,
                                  increment_by,cycle,cache_size,last_value FROM pg_sequences
                            WHERE schemaname IN ('identity','ehr')) s"""
            output = command(["exec", "-T", "db", "psql", "-X", "-U", "oi_api", "-d", database,
                              "-v", "ON_ERROR_STOP=1", "-At", "-c", sql], capture_output=True, text=True)
            result["sequence_state"] = json.loads(output.stdout)
            return result

        def serve_database(database):
            override = access / "restored-api.compose.json"
            override.write_text(json.dumps({"services": {"api": {"environment": {
                "OI_API_DATABASE_URL": "postgresql+pg8000://oi_api:oi_h1_synthetic_only@db:5432/" + database,
            }}}}), encoding="utf-8")
            compose.extend(["--file", str(override)])
            command(["up", "--no-deps", "--force-recreate", "--detach", "api"])
            ready()

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
            encounter_actions = ["encounter.schedule", "encounter.transition", "note.write", "note.read"]
            for credential in credentials:
                credential["actions"].extend(encounter_actions)
            save_access()
            visit_path = path + "/encounters"
            schedule = {"synthetic": True, "request_key": "SCHEDULE-PROOF", "external_key": "PROOF-VISIT",
                        "kind": "outpatient", "service_date": "2026-05-04"}
            status, visit = request(visit_path, tokens[0], schedule)
            assert status == 200 and visit["status"] == "scheduled"
            visit_path += "/" + str(visit["encounter_id"])
            assert request(visit_path + "/transitions", tokens[0], {"synthetic": True, "request_key": "START-VISIT",
                           "target": "in_progress", "expected_revision": 1})[0] == 200
            note_path = visit_path + "/notes/PROOF-NOTE/versions"
            drafts = ["Independently fictional draft.", "Revised independently fictional draft."]
            note_commands, note_receipts = [], []
            for i, body in enumerate(drafts):
                command_body = {"synthetic": True, "request_key": "PROOF-DRAFT-" + str(i),
                                "expected_version": i, "body": body, "note_kind": "consultation"}
                written = request(note_path, tokens[0], command_body)
                assert written[0] == 200 and written[1]["version"] == i + 1
                assert request(note_path, tokens[0], command_body) == written
                note_commands.append(command_body)
                note_receipts.append(written)
            versions = request(note_path, tokens[0])[1]["versions"]
            assert [v["body"] for v in versions] == drafts
            assert request(note_path, tokens[1])[0] == 404
            for service in ("api", "db"):
                command(["restart", service])
                ready()
                assert request("/v1/patients", tokens[0], payload) == (200, {"patient_id": patient, "duplicate": True})
                assert request(path, tokens[0])[1]["patient_id"] == patient
                assert request(note_path, tokens[0])[1]["versions"] == versions
                print("Canonical identity and idempotency persisted after " + service + " restart")

            # A real server dump/restore checks identity history, not only an
            # in-process serialization. Both databases belong to this project.
            original = snapshot()
            dump = command(["exec", "-T", "db", "pg_dump", "-U", "oi_api", "-d", "oi_api_synthetic", "--format=custom"], capture_output=True).stdout
            command(["exec", "-T", "db", "createdb", "-U", "oi_api", "oi_api_test_restore"])
            command(["exec", "-T", "db", "pg_restore", "-U", "oi_api", "-d", "oi_api_test_restore", "--exit-on-error", "--no-owner"], input=dump)
            query = (
                "SELECT (SELECT count(*) FROM identity.identity_patients),"
                "(SELECT count(*) FROM identity.identity_create_receipts),"
                "(SELECT count(*) FROM identity.identity_domain_events WHERE event_type='identity.patient.created'),"
                "(SELECT count(*) FROM identity.identity_domain_events),"
                "(SELECT version_num FROM public.alembic_version)"
            )
            restored = command(["exec", "-T", "db", "psql", "-U", "oi_api", "-d", "oi_api_test_restore", "-At", "-c", query], capture_output=True, text=True).stdout.strip()
            assert restored == "1|1|1|8|" + SCHEMA_REVISION, restored
            restored_id = command(["exec", "-T", "db", "psql", "-U", "oi_api", "-d", "oi_api_test_restore", "-At", "-c", "SELECT patient_id FROM identity.identity_patients"], capture_output=True, text=True).stdout.strip()
            assert restored_id == patient
            restored_notes = command(["exec", "-T", "db", "psql", "-U", "oi_api", "-d", "oi_api_test_restore",
                "-At", "-c", "SELECT sha256 FROM ehr.clinical_note_versions ORDER BY version"],
                capture_output=True, text=True).stdout.splitlines()
            assert restored_notes == [hashlib.sha256(b.encode()).hexdigest() for b in drafts]
            saved = command(["exec", "-T", "db", "psql", "-U", "oi_api", "-d", "oi_api_test_restore",
                "-At", "-c", "SELECT (SELECT count(*) FROM ehr.clinical_encounter_commands),"
                "(SELECT count(*) FROM identity.identity_domain_events WHERE event_type='clinical_note_draft_saved')"],
                capture_output=True, text=True).stdout.strip()
            assert saved == "4|2", saved
            assert snapshot("oi_api_test_restore") == original, "Restore changed EHR rows or sequence state"
            serve_database("oi_api_test_restore")
            assert snapshot("oi_api_test_restore") == original, "Restored API startup changed history"
            assert request(note_path, tokens[0])[1]["versions"] == versions
            for note_command, note_receipt in zip(note_commands, note_receipts):
                assert request(note_path, tokens[0], note_command) == note_receipt
            third_body = "A third independently fictional draft saved after database restore."
            third_command = {"synthetic": True, "request_key": "PROOF-DRAFT-RESTORED-3",
                             "expected_version": 2, "body": third_body, "note_kind": "consultation"}
            status, third = request(note_path, tokens[0], third_command)
            assert status == 200 and third["version"] == 3 and third["status"] == "draft"
            assert third["note_id"] == note_receipts[0][1]["note_id"]
            assert third["sha256"] == hashlib.sha256(third_body.encode()).hexdigest()
            assert request(note_path, tokens[0], third_command) == (200, third)
            restored_versions = request(note_path, tokens[0])[1]["versions"]
            assert restored_versions[:2] == versions
            assert [row["body"] for row in restored_versions] == drafts + [third_body]
            assert restored_versions[2]["id"] > max(row["id"] for row in versions)
            assert restored_versions[2]["supersedes_id"] == versions[-1]["id"]
            restored_state = snapshot("oi_api_test_restore")
            assert len(restored_state["ehr.clinical_encounter_commands"]) == 5
            assert len(restored_state["ehr.clinical_note_versions"]) == 3
            old_events = original["identity.identity_domain_events"]
            new_events = restored_state["identity.identity_domain_events"]
            assert all(event in new_events for event in old_events)
            third_event, = [event for event in new_events
                            if event["event_type"] == "clinical_note_draft_saved"
                            and event["metadata_json"]["version"] == 3]
            assert third_event["id"] > max(event["id"] for event in old_events)
            assert snapshot() == original, "Restored HTTP reads/writes changed the original database"
            credentials[0]["actions"].remove("note.read")
            save_access()
            assert request(note_path, tokens[0])[0] == 404
            assert snapshot("oi_api_test_restore") == restored_state, "Denied note read changed restored history"
            assert request(path, tokens[0])[0] == 200
            assert "note.write" in credentials[0]["actions"]
            assert snapshot() == original
            print("PASS EHR: exact restored rows/sequences, served prior notes and retries, third draft appended "
                  "through restored HTTP, independent note-read withdrawal and original database unchanged")
            # Exercise both restored ownership triggers against valid destination keys.
            # The other actor can read its own history even after the first loses note.read.
            status, second = request("/v1/patients", tokens[1],
                                     {"synthetic": True, "request_key": "RESTORE-SECOND-PATIENT"})
            assert status == 201
            second_patient = second["patient_id"]
            assert re.fullmatch(r"PAT-[0-9A-F]{32}", second_patient) and second_patient != patient
            credentials[1]["patient_ids"] = [second_patient]
            save_access()
            second_visits = "/v1/patients/" + second_patient + "/encounters"
            status, second_visit = request(second_visits, tokens[1],
                                          {**schedule, "external_key": "RESTORE-SECOND-VISIT"})
            assert status == 200
            second_id = int(second_visit["encounter_id"])
            first_id = int(visit["encounter_id"])
            note_id = int(note_receipts[0][1]["note_id"])
            assert first_id != second_id
            before_moves = snapshot("oi_api_test_restore")
            for change in (
                f"UPDATE ehr.clinical_encounters SET patient_id='{second_patient}' WHERE id={first_id}",
                f"UPDATE ehr.clinical_note_headers SET encounter_id={second_id} WHERE id={note_id}",
            ):
                try:
                    command(["exec", "-T", "db", "psql", "-X", "-U", "oi_api", "-d", "oi_api_test_restore",
                             "-v", "ON_ERROR_STOP=1", "-c", "BEGIN; " + change + "; ROLLBACK"],
                            capture_output=True, text=True)
                except subprocess.CalledProcessError as error:
                    assert "OI-IDENTITY-HISTORY-IMMUTABLE" in error.stderr, error.stderr
                else:
                    raise AssertionError("Restored EHR allowed owner reassignment")
            assert snapshot("oi_api_test_restore") == before_moves
            second_history = second_visits + "/" + str(second_id) + "/notes/" + note_path.split("/")[-2] + "/versions"
            status, history = request(second_history, tokens[1])
            assert status == 200 and history["versions"] == []
            assert snapshot() == original
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
