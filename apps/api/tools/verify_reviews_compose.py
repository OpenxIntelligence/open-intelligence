"""Actual disposable HTTP/restart/dump-restore proof for canonical review returns.

Only independently authored synthetic source bytes and generated fixture grants
are used. The same PostgreSQL question/receipt owners are exercised via HTTP;
no clinical approval, external notification or evidence investigation is implied.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener
import uuid


ROOT = Path(__file__).resolve().parents[3]
BASE = "http://127.0.0.1:8000"
CASE = "CASE-COMPOSE-REVIEW"
ORIGINAL = (
    "OI-SYNTHETIC-REPORT/1\nPatient: CASE-COMPOSE-REVIEW\nDocument: DOC-REVIEW\n"
    "Type: pathology\nEvent-Date: 2026-01-10\nIssued-At: 2026-01-11\n"
    "Specimen: SPECIMEN-REVIEW\n"
    "Finding: marker|pending|Independently fictional café marker — pending.\n"
)
AMENDED = (
    "OI-SYNTHETIC-REPORT/1\nPatient: CASE-COMPOSE-REVIEW\nDocument: DOC-REVIEW\n"
    "Type: pathology\nEvent-Date: 2026-01-10\nIssued-At: 2026-01-12\n"
    "Specimen: SPECIMEN-REVIEW\nAmends: DOC-REVIEW@1\n"
    "Finding: marker|negative|Independently fictional café marker — negative.\n"
)
SOURCE_CONTRACT = "oi.pg-source-world-model/1"
QUEUE_CONTRACT = "oi.synthetic-question-review-return-queue/2"
FINGERPRINT_CONTRACT = "oi.synthetic-source-review-return/2"


def main():
    project = "oi-h1-review-proof-" + uuid.uuid4().hex[:12]
    compose = ["docker", "compose", "--project-name", project,
               "--file", str(ROOT / "apps/api/compose.yaml"),
               "--file", str(ROOT / "apps/api/compose.synthetic-access.yaml")]
    with tempfile.TemporaryDirectory(prefix="oi-synthetic-review-access-") as directory:
        access = Path(directory)
        access.chmod(0o755)
        env = dict(os.environ, OI_API_ACCESS_DIRECTORY=directory)
        token = secrets.token_urlsafe(32)
        actions = ["patient_create", "patient_read", "case_binding_create",
                   "case_binding_read", "case_binding_revoke", "source_import",
                   "source_read", "source_original_read", "composer_context_read",
                   "question_create", "question_read", "review_queue_read", "review_return"]
        credential = {
            "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
            "actor": "ACTOR-REVIEW-PROOF", "organization": "ORG-REVIEW-PROOF",
            "purpose": "operations", "actions": list(actions), "patient_ids": [],
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        }

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
                    raise RuntimeError("Synthetic review API did not become ready")
                time.sleep(0.25)

        def snapshot(database="oi_api_synthetic"):
            return query("""
                SELECT json_build_object(
                  'questions', (SELECT COALESCE(json_agg(q ORDER BY q.question_id),'[]'::json)
                    FROM investigation.source_questions q),
                  'receipts', (SELECT COALESCE(json_agg(r ORDER BY r.receipt_id),'[]'::json)
                    FROM investigation.question_review_receipts r),
                  'sources', (SELECT json_agg(s ORDER BY s.document_id,s.version)
                    FROM (SELECT source_id,case_id,document_id,version,sha256,
                      encode(sha256(raw),'hex') AS raw_sha256,octet_length(raw) AS byte_length,
                      state,supersedes_id FROM clinical_source.source_versions) s),
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

        def read_queue():
            status, value = request(prefix + "/review-queue")
            assert status == 200, "Review queue unavailable"
            assert value["contract"] == QUEUE_CONTRACT
            assert (value["patient_id"], value["case_id"]) == (patient, CASE)
            uuid.UUID(value["access_receipt_id"].removeprefix("ACCESS-"))
            assert value["access_receipt_id"].startswith("ACCESS-")
            for flag in ("clinical_approval", "reviewer_identity_verified",
                         "external_notification_sent", "review_completion_supported"):
                assert value[flag] is False
            for row in value["items"] + value["receipts"]:
                assert row["source_snapshot_contract"] == SOURCE_CONTRACT
                assert row["queue_fingerprint_contract"] == FINGERPRINT_CONTRACT
            return value

        def question(source_id, line, version):
            status, world = request(prefix + "/world-model")
            assert status == 200 and world["contract"] == SOURCE_CONTRACT
            proposal = {"synthetic": True, "source_id": source_id, "source_line": line,
                        "question": "Which fictional source details still require verification?",
                        "expected_source_snapshot_sha256": world["snapshot_fingerprint"]}
            status, preflight = request(prefix + "/composer/source-preflight", proposal)
            assert status == 200 and preflight["source_snapshot_contract"] == SOURCE_CONTRACT
            status, saved = request(prefix + "/questions", {
                **proposal, "request_key": "COMPOSE-QUESTION-V" + str(version),
                "expected_preflight_sha256": preflight["preflight_sha256"],
            })
            assert status == 201 and saved["duplicate"] is False
            return saved["question_id"]

        def return_question(question_id, version):
            queue = read_queue()
            item = next(row for row in queue["items"] if row["question_id"] == question_id)
            assert item["review_state"] == "awaiting_independent_verification"
            assert item["current_return_receipt_id"] is None
            assert (item["return_count"], item["prior_return_count"]) == (0, 0)
            intent = {"synthetic": True, "request_key": "COMPOSE-RETURN-V" + str(version),
                      "expected_queue_fingerprint": item["queue_fingerprint"],
                      "reason": "Please independently verify the fictional source and its uncertainty."}
            url = prefix + "/questions/" + question_id + "/return-for-verification"
            status, saved = request(url, intent)
            assert status == 201 and saved["duplicate"] is False
            duplicate = {**saved, "duplicate": True}
            assert request(url, intent) == (200, duplicate)
            return url, intent, duplicate

        def assert_history():
            value = read_queue()
            items = {row["question_id"]: row for row in value["items"]}
            old, current = items[questions[0]], items[questions[1]]
            assert len(items) == 2 and len(value["receipts"]) == 2
            assert (old["source_id"], old["source_line"], old["source_version"]) == (sources[0], 8, 1)
            assert old["review_state"] == "source_reassessment_required"
            assert old["queue_fingerprint"] is None and old["current_return_receipt_id"] is None
            assert (old["return_count"], old["prior_return_count"]) == (0, 1)
            assert (current["source_id"], current["source_line"], current["source_version"]) == (sources[1], 9, 2)
            assert current["review_state"] == "returned_for_independent_verification"
            assert current["current_return_receipt_id"] == returns[1][2]["receipt_id"]
            assert (current["return_count"], current["prior_return_count"]) == (1, 0)
            assert current["queue_fingerprint"] == returns[1][1]["expected_queue_fingerprint"]
            receipts = {row["receipt_id"]: row for row in value["receipts"]}
            for url, intent, saved in returns:
                assert request(url, intent) == (200, saved)
                receipt = receipts[saved["receipt_id"]]
                assert receipt["action"] == "returned" and receipt["reason"] == intent["reason"]
                assert receipt["clinical_approval"] is False
                assert receipt["reviewer_identity_verified"] is False
                assert receipt["external_notification_sent"] is False
            state = snapshot()
            events = [event for event in state["events"]
                      if event["event_type"] == "investigation.review.returned_for_verification"]
            assert len(events) == len(state["receipts"]) == 2, "Retry duplicated a return effect"
            assert state["revision"] == "0010_question_evidence"
            encoded = json.dumps(state["events"], ensure_ascii=False)
            assert token not in encoded and "Independently fictional café marker" not in encoded
            return state

        save_access()
        try:
            command(["config", "--quiet"])
            command(["up", "--build", "--detach", "api"])
            ready()
            status, created = request("/v1/patients", {
                "synthetic": True, "request_key": "CREATE-REVIEW-COMPOSE-PROOF"})
            assert status == 201 and created["duplicate"] is False
            patient = created["patient_id"]
            credential["patient_ids"] = [patient]
            save_access()
            patient_path = "/v1/patients/" + patient
            status, bound = request(patient_path + "/case-bindings", {
                "synthetic": True, "case_id": CASE, "source_organization": "ORG-SYNTHETIC-REVIEW",
                "source_system": "SYS-SYNTHETIC-REVIEW", "source_subject_ref": "SUBJECT-REVIEW",
                "review_ref": "REVIEW-SYNTHETIC-COMPOSE"})
            assert status == 201 and bound["patient_id"] == patient
            prefix = patient_path + "/cases/" + CASE
            sources, questions, returns = [], [], []
            for version, original in enumerate((ORIGINAL, AMENDED), start=1):
                status, imported = request(prefix + "/sources", {
                    "synthetic": True, "original_text": original})
                assert (status, imported["result"], imported["version"]) == (201, "imported", version)
                sources.append(imported["source_id"])
                if version == 2:
                    # An old operation remains recoverable, but a new operation
                    # against that stale snapshot must fail without an event.
                    old_url, old_intent, old_receipt = returns[0]
                    before = snapshot()
                    assert request(old_url, {**old_intent, "request_key": "STALE-NEW-RETURN"})[0] == 409
                    assert snapshot() == before, "Rejected stale return changed durable history"
                    assert request(old_url, old_intent) == (200, old_receipt)
                questions.append(question(imported["source_id"], 8 if version == 1 else 9, version))
                returns.append(return_question(questions[-1], version))
            first, second = read_queue(), read_queue()
            assert first["access_receipt_id"] != second["access_receipt_id"]
            assert first["items"] == second["items"] and first["receipts"] == second["receipts"]
            assert_history()

            # Queue reads and writes have independent grants. A denial cannot
            # expose a queue or mint an access/business receipt.
            for missing in ("review_queue_read", "review_return"):
                credential["actions"] = [action for action in actions if action != missing]
                save_access()
                before = snapshot()
                if missing == "review_queue_read":
                    status, denied = request(prefix + "/review-queue")
                    assert status == 404 and "items" not in denied and "access_receipt_id" not in denied
                    assert snapshot() == before
                    assert request(returns[1][0], returns[1][1]) == (200, returns[1][2])
                else:
                    assert request(returns[1][0], returns[1][1])[0] == 404
                    assert snapshot() == before
                    read_queue()
            credential["actions"] = list(actions)
            save_access()

            for service in ("api", "db"):
                before = assert_history()
                command(["restart", service])
                ready()
                assert snapshot() == before, "Restart changed question/receipt/source history"
                assert_history()
                print("Canonical questions, historical returns and retry identity survived " + service + " restart")

            status, revoked = request(patient_path + "/case-bindings/" + CASE + "/revoke", {
                "synthetic": True, "reason": "Withdraw the independently fictional review binding"})
            assert status == 200 and revoked["duplicate"] is False
            before = snapshot()
            assert request(prefix + "/review-queue")[0] == 404
            assert request(returns[1][0], returns[1][1])[0] == 404
            assert snapshot() == before
            assert before["bindings"][0]["status"] == "revoked"
            for row, original in zip(before["sources"], (ORIGINAL, AMENDED)):
                assert row["sha256"] == row["raw_sha256"] == hashlib.sha256(original.encode("utf-8")).hexdigest()
            dump = command(["exec", "-T", "db", "pg_dump", "-U", "oi_api", "-d",
                            "oi_api_synthetic", "--format=custom"], capture_output=True).stdout
            restored = "oi_api_test_reviews_restore"
            command(["exec", "-T", "db", "createdb", "-U", "oi_api", restored])
            command(["exec", "-T", "db", "pg_restore", "-U", "oi_api", "-d", restored,
                     "--exit-on-error", "--no-owner"], input=dump)
            assert snapshot(restored) == before, "Restore changed source/question/receipt/event history"
            print("PASS: actual canonical review HTTP, stable queue provenance, same-key recovery, "
                  "amendment history, independent grants, API/DB restart, binding revocation and dump/restore")
        except Exception:
            command(["logs", "--no-color", "--tail", "80"], check=False)
            raise
        finally:
            command(["down", "--volumes"])


if __name__ == "__main__":
    main()
