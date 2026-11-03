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
            for service in ("api", "db"):
                command(["restart", service])
                ready()
                assert request("/v1/patients", tokens[0], payload) == (200, {"patient_id": patient, "duplicate": True})
                assert request(path, tokens[0])[1]["patient_id"] == patient
                print("Canonical identity and idempotency persisted after " + service + " restart")

            # A real server dump/restore checks identity history, not only an
            # in-process serialization. Both databases belong to this project.
            dump = command(["exec", "-T", "db", "pg_dump", "-U", "oi_api", "-d", "oi_api_synthetic", "--format=custom"], capture_output=True).stdout
            command(["exec", "-T", "db", "createdb", "-U", "oi_api", "oi_api_test_restore"])
            command(["exec", "-T", "db", "pg_restore", "-U", "oi_api", "-d", "oi_api_test_restore", "--exit-on-error", "--no-owner"], input=dump)
            query = (
                "SELECT (SELECT count(*) FROM identity.identity_patients),"
                "(SELECT count(*) FROM identity.identity_create_receipts),"
                "(SELECT count(*) FROM identity.identity_domain_events),"
                "(SELECT version_num FROM public.alembic_version)"
            )
            restored = command(["exec", "-T", "db", "psql", "-U", "oi_api", "-d", "oi_api_test_restore", "-At", "-c", query], capture_output=True, text=True).stdout.strip()
            assert restored == "1|1|1|0005_source_versions", restored
            restored_id = command(["exec", "-T", "db", "psql", "-U", "oi_api", "-d", "oi_api_test_restore", "-At", "-c", "SELECT patient_id FROM identity.identity_patients"], capture_output=True, text=True).stdout.strip()
            assert restored_id == patient
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
