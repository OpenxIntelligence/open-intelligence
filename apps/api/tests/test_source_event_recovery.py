"""Real PostgreSQL acceptance for explicit, revision-bound event recovery.

The fixtures are independently authored fiction. A skipped database fixture is
not evidence for transaction, restart, authorization, or restore correctness.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
from unittest.mock import patch

from sqlalchemy.engine import make_url

from oi_api.app import create_app
from oi_api.config import Settings
from open_intelligence.postgres_registry import PostgresPatientRegistry
from http_support import running_server
import test_source_event_delivery as delivery_fixture
import test_source_versions as source_fixture
import test_patient_permissions as permission_fixture


TOKEN = delivery_fixture.TOKEN
OTHER_TOKEN = delivery_fixture.OTHER_TOKEN
CASE = delivery_fixture.CASE
RECOVERIES = "coordination.source_event_recoveries"


class SourceEventRecoveryPostgresTests(source_fixture.SourceVersionFixture):
    # Explicitly borrow helpers, not the parent TestCase's tests.
    path = staticmethod(delivery_fixture.SourceEventDeliveryPostgresTests.path)
    model_path = staticmethod(delivery_fixture.SourceEventDeliveryPostgresTests.model_path)
    run_path = staticmethod(delivery_fixture.SourceEventDeliveryPostgresTests.run_path)
    world = delivery_fixture.SourceEventDeliveryPostgresTests.world
    preflight = delivery_fixture.SourceEventDeliveryPostgresTests.preflight
    prepared = delivery_fixture.SourceEventDeliveryPostgresTests.prepared
    save = delivery_fixture.SourceEventDeliveryPostgresTests.save
    seed = delivery_fixture.SourceEventDeliveryPostgresTests.seed
    events = delivery_fixture.SourceEventDeliveryPostgresTests.events
    enqueue = delivery_fixture.SourceEventDeliveryPostgresTests.enqueue
    seeded_run = delivery_fixture.SourceEventDeliveryPostgresTests.seeded_run
    status = delivery_fixture.SourceEventDeliveryPostgresTests.status
    stored = delivery_fixture.SourceEventDeliveryPostgresTests.stored
    delivery_store = delivery_fixture.SourceEventDeliveryPostgresTests.delivery_store
    claim_event = delivery_fixture.SourceEventDeliveryPostgresTests.claim_event
    deliver_event = delivery_fixture.SourceEventDeliveryPostgresTests.deliver_event
    fail_event = delivery_fixture.SourceEventDeliveryPostgresTests.fail_event
    event_work = delivery_fixture.SourceEventDeliveryPostgresTests.event_work
    event_worker_env = delivery_fixture.SourceEventDeliveryPostgresTests.event_worker_env
    rows = delivery_fixture.SourceEventDeliveryPostgresTests.rows
    delivery = delivery_fixture.SourceEventDeliveryPostgresTests.delivery
    receipts = delivery_fixture.SourceEventDeliveryPostgresTests.receipts
    drain = delivery_fixture.SourceEventDeliveryPostgresTests.drain
    add_other_actor = delivery_fixture.SourceEventDeliveryPostgresTests.add_other_actor
    url_permissions = permission_fixture.PermissionHTTPTests.url_permissions
    grant = permission_fixture.PermissionHTTPTests.grant
    revoke = permission_fixture.PermissionHTTPTests.revoke

    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend(("composer_context_read", "question_create",
                                         "question_read", "source_brief_export", "source_delivery_retry"))
        self.write()

    def snapshot(self, *, settings=None):
        return {
            **delivery_fixture.SourceEventDeliveryPostgresTests.snapshot(self, settings=settings),
            RECOVERIES: self.rows(RECOVERIES, "delivery_id,failed_revision", settings=settings),
        }

    def terminal_amendment(self, *, reason="authority_unavailable"):
        with running_server(create_app(self.settings)) as base:
            patient, _, _, run = self.seeded_run(base)
            self.drain(patient)
            self.assertEqual(self.ingest(base, patient, source_fixture.AMENDED)[0], 201)
        claim = self.claim_event(patient)
        self.assertEqual(self.fail_event(claim, reason), "dead_letter")
        failed = self.delivery(claim["delivery_id"])
        self.assertEqual(self.stored(run)[0]["state"], "queued")
        return patient, run, failed

    def recover(self, failed, *, patient=None, case=CASE, token=TOKEN, settings=None, **changes):
        from oi_api.event_worker import request_recovery
        intent = dict(delivery_id=failed["delivery_id"], event_id=failed["event_id"],
                      expected_revision=failed["revision"])
        return request_recovery(settings or self.settings, lambda: token,
            patient or failed["patient_id"], case, **(intent | changes))

    def recovery_cli(self, failed, *, settings=None):
        return [sys.executable, "-m", "oi_api.event_worker", "--recover", failed["delivery_id"],
                "--event-id", str(failed["event_id"]), "--expected-revision", str(failed["revision"]),
                "--patient", failed["patient_id"], "--case", CASE]

    def assert_only_read_audit_changed(self, before, after):
        journal = "identity.identity_domain_events"
        self.assertEqual({k: v for k, v in before.items() if k != journal},
                         {k: v for k, v in after.items() if k != journal})
        self.assertEqual(after[journal][:len(before[journal])], before[journal])

    def test_recovery_preserves_identity_and_history_then_reconciles_once_after_restart(self):
        patient, run, failed = self.terminal_amendment()
        before = self.snapshot()
        requested = self.recover(failed)
        self.assertEqual(requested, {
            "status": "recovery_requested", "delivery_id": failed["delivery_id"],
            "event_id": failed["event_id"], "failed_revision": failed["revision"],
            "recovery_revision": failed["revision"] + 1, "duplicate": False,
        })
        queued = self.delivery(failed["delivery_id"])
        for key in ("delivery_id", "event_id", "consumer", "patient_id", "case_id", "origin_org",
                    "actor", "purpose", "attempt_count", "created_at"):
            self.assertEqual(queued[key], failed[key])
        self.assertEqual((queued["state"], queued["revision"], queued["failure_count"]),
                         ("queued", failed["revision"] + 1, 0))
        self.assertIsNone(queued["lease_token"])
        self.assertIsNone(queued["lease_expires_at"])
        self.assertEqual(self.stored(run)[0]["state"], "queued")
        self.assertEqual(self.receipts(failed["delivery_id"]), [])
        history = self.rows(delivery_fixture.HISTORY, "delivery_id,revision")
        self.assertEqual([r for r in history if r["reason_code"] != "recovery_requested"],
                         before[delivery_fixture.HISTORY])

        # A fresh process performs the existing consumer command, not recover().
        resumed = subprocess.run(
            [sys.executable, "-m", "oi_api.event_worker", "--once", "--patient", patient, "--case", CASE],
            env=self.event_worker_env(), capture_output=True, text=True, timeout=20)
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual(json.loads(resumed.stdout), {
            "status": "delivered", "attempt_count": failed["attempt_count"] + 1,
            "invalidated_count": 1,
        })
        self.assertEqual(self.stored(run)[0]["state"], "stale")
        accepted = self.snapshot()
        self.assertEqual(self.recover(failed), requested | {"duplicate": True})
        self.assert_only_read_audit_changed(accepted, self.snapshot())
        self.assertEqual(self.event_work(patient), {"status": "idle"})
        self.assertEqual(len(self.rows(RECOVERIES, "delivery_id,failed_revision")), 1)
        self.assertEqual(len(self.receipts(failed["delivery_id"])), 1)
        stale = [metadata for kind, metadata in self.events()
                 if kind == "composer.run.stale" and metadata["run_id"] == run]
        self.assertEqual(len(stale), 1)
        self.assertEqual(stale[0]["source_event_id"], failed["event_id"])
        self.assertEqual(stale[0]["delivery_id"], failed["delivery_id"])

    def test_concurrent_exact_recovery_has_one_transition_and_receipt(self):
        _, run, failed = self.terminal_amendment()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.recover(failed), range(2)))
        self.assertEqual([r["status"] for r in results], ["recovery_requested"] * 2)
        self.assertEqual(sorted(r["duplicate"] for r in results), [False, True])
        self.assertEqual(len(self.rows(RECOVERIES, "delivery_id,failed_revision")), 1)
        self.assertEqual(self.delivery(failed["delivery_id"])["revision"], failed["revision"] + 1)
        self.assertEqual(self.stored(run)[0]["state"], "queued")

    def test_old_recovery_retry_cannot_reset_a_later_failure(self):
        _, run, failed = self.terminal_amendment()
        first = self.recover(failed)
        next_claim = self.claim_event(failed["patient_id"])
        self.assertEqual(self.fail_event(next_claim, "authority_unavailable"), "dead_letter")
        later = self.delivery(failed["delivery_id"])
        before = self.snapshot()
        self.assertEqual(self.recover(failed), first | {"duplicate": True})
        self.assert_only_read_audit_changed(before, self.snapshot())
        self.assertEqual(self.delivery(failed["delivery_id"]), later)
        self.assertEqual(self.recover(later)["duplicate"], False)
        self.assertEqual(len(self.rows(RECOVERIES, "delivery_id,failed_revision")), 2)
        self.assertEqual(self.stored(run)[0]["state"], "queued")

    def test_exhausted_failure_budgets_recover_without_reviving_abandoned_claims(self):
        from oi_api.source_event_delivery import EventLeaseLost
        patient, run, first_failure = self.terminal_amendment()
        self.assertEqual(self.recover(first_failure)["status"], "recovery_requested")
        abandoned = []
        for count in (1, 2, 3):
            claim = self.claim_event(patient)
            abandoned.append(claim)
            self.assertEqual(self.fail_event(claim), "dead_letter" if count == 3 else "queued")
            if count < 3:
                time.sleep(2 ** count + 0.1)
        retry_failed = self.delivery(first_failure["delivery_id"])
        self.assertEqual(retry_failed["failure_count"], 3)
        self.assertEqual(self.recover(retry_failed)["status"], "recovery_requested")
        for _ in range(3):
            claim = self.claim_event(patient, lease=1)
            self.assertEqual(claim["state"], "running")
            abandoned.append(claim)
            time.sleep(1.1)
        expired = self.claim_event(patient)
        self.assertEqual((expired["state"], expired["failure_count"]), ("dead_letter", 3))
        self.assertEqual(self.recover(expired)["status"], "recovery_requested")
        for obsolete in abandoned:
            with self.assertRaises(EventLeaseLost):
                self.deliver_event(obsolete)
        self.assertEqual(self.stored(run)[0]["state"], "queued")
        self.assertEqual(self.event_work(patient)["invalidated_count"], 1)
        self.assertEqual(len(self.receipts(first_failure["delivery_id"])), 1)

    def test_stale_revision_invalid_event_and_delivered_state_refuse_recovery(self):
        patient, _, failed = self.terminal_amendment()
        for revision in (failed["revision"] - 1, failed["revision"] + 1):
            before = self.snapshot()
            self.assertEqual(self.recover(failed, expected_revision=revision), {"status": "conflict"})
            self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.recover(failed)["status"], "recovery_requested")
        queued = self.delivery(failed["delivery_id"])
        before = self.snapshot()
        self.assertEqual(self.recover(queued), {"status": "conflict"})
        self.assertEqual(self.snapshot(), before)
        claim = self.claim_event(patient)
        self.assertEqual(self.fail_event(claim, "invalid_event"), "dead_letter")
        invalid = self.delivery(failed["delivery_id"])
        before = self.snapshot()
        self.assertEqual(self.recover(invalid), {"status": "conflict"})
        self.assertEqual(self.snapshot(), before)
        # The separately delivered initial event cannot be reset either.
        delivered = next(r for r in self.rows(delivery_fixture.DELIVERIES, "event_id")
                         if r["state"] == "delivered")
        self.assertEqual(self.recover(delivered), {"status": "conflict"})
        self.assertEqual(self.snapshot(), before)

    def test_recovery_rejects_other_actor_case_patient_purpose_and_organization(self):
        patient, _, failed = self.terminal_amendment()
        self.add_other_actor(patient)
        before = self.snapshot()
        for changes in ({"token": OTHER_TOKEN}, {"case": "CASE-OTHER"},
                        {"patient": "PAT-UNKNOWN"}, {"event_id": failed["event_id"] + 1}):
            with self.subTest(changes=changes):
                self.assertEqual(self.recover(failed, **changes), {"status": "blocked"})
                self.assertEqual(self.snapshot(), before)
        original = dict(self.creds[0])
        for changes in ({"purpose": "research"}, {"organization": "ORG-OTHER"}, {"patient_ids": []}):
            self.creds[0] = original | changes
            self.write()
            self.assertEqual(self.recover(failed), {"status": "blocked"})
            self.assertEqual(self.snapshot(), before)
        self.creds[0] = original
        self.write()

    def test_current_credentials_and_audit_tail_recheck_roll_back_recovery(self):
        _, _, failed = self.terminal_amendment()
        before = self.snapshot()
        self.creds[0]["actions"].remove("source_delivery_retry")
        self.write()
        self.assertEqual(self.recover(failed), {"status": "blocked"})
        self.assertEqual(self.snapshot(), before)
        self.creds[0]["actions"].append("source_delivery_retry")
        self.creds[0]["actions"].remove("source_read")
        self.write()
        self.assertEqual(self.recover(failed), {"status": "blocked"})
        self.assertEqual(self.snapshot(), before)
        self.creds[0]["actions"].append("source_read")
        self.write()
        original = PostgresPatientRegistry.append_event
        seen = []
        def revoke_at_tail(registry, patient_id, event_type, **metadata):
            result = original(registry, patient_id, event_type, **metadata)
            if event_type == "source.delivery.recovery_requested":
                seen.append(event_type)
                self.creds[0]["actions"].remove("source_read")
                self.write()
            return result
        with patch.object(PostgresPatientRegistry, "append_event", revoke_at_tail):
            self.assertEqual(self.recover(failed), {"status": "blocked"})
        self.assertEqual(len(seen), 1)
        self.assertEqual(self.snapshot(), before)

    def test_persisted_permission_is_required_for_recovery_and_receipt_retry(self):
        patient, _, failed = self.terminal_amendment()
        self.creds[0]["actions"].extend(("patient_permissions_read", "patient_permissions_manage"))
        self.write()
        governed = replace(self.settings, require_persisted_grants=True)
        before = self.snapshot()
        self.assertEqual(self.recover(failed, settings=governed), {"status": "blocked"})
        self.assertEqual(self.snapshot(), before)
        with running_server(create_app(governed)) as base:
            code, grant, _ = self.grant(base, patient, permission_fixture.grant_payload(
                request_key="GRANT-RECOVERY", actions=sorted(delivery_fixture.ACTIONS)))
            self.assertEqual(code, 200, grant)
            self.assertEqual(self.recover(failed, settings=governed), {"status": "blocked"})
            code, retry_grant, _ = self.grant(base, patient, permission_fixture.grant_payload(
                request_key="GRANT-EXPLICIT-RETRY", actions=["source_delivery_retry"]))
            self.assertEqual(code, 200, retry_grant)
            self.assertEqual(self.recover(failed, settings=governed)["status"], "recovery_requested")
            self.assertEqual(self.revoke(base, patient, retry_grant["grant_id"])[0], 200)
        before = self.snapshot()
        self.assertEqual(self.recover(failed, settings=governed), {"status": "blocked"})
        self.assertEqual(self.snapshot(), before)

    def test_killed_recovery_response_is_recoverable_without_repeating_effects(self):
        patient, run, failed = self.terminal_amendment()
        marker = Path(self.temp.name) / "recovery-committed.json"
        script = '''
import json, os, signal, sys
from pathlib import Path
from oi_api.source_event_delivery import PostgresSourceEventDelivery
from oi_api.event_worker import main
original = PostgresSourceEventDelivery.recover
def stop_after_commit(self, *args, **kwargs):
    result = original(self, *args, **kwargs)
    Path(sys.argv[1]).write_text(json.dumps(result))
    os.kill(os.getpid(), signal.SIGSTOP)
    return result
PostgresSourceEventDelivery.recover = stop_after_commit
raise SystemExit(main(sys.argv[2:]))
'''
        args = self.recovery_cli(failed)[3:]
        child = subprocess.Popen([sys.executable, "-c", script, str(marker), *args],
            env=self.event_worker_env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            until = time.monotonic() + 15
            while not marker.exists() and child.poll() is None and time.monotonic() < until:
                time.sleep(0.05)
            self.assertTrue(marker.exists(), "Recovery process did not reach committed state")
            committed = json.loads(marker.read_text())
            self.assertEqual(committed["status"], "recovery_requested")
            self.assertEqual(self.delivery(failed["delivery_id"])["state"], "queued")
            self.assertEqual(self.stored(run)[0]["state"], "queued")
        finally:
            child.kill()
            child.communicate(timeout=5)
        retried = subprocess.run(self.recovery_cli(failed), env=self.event_worker_env(),
            capture_output=True, text=True, timeout=20)
        self.assertEqual(retried.returncode, 0, retried.stderr)
        self.assertEqual(json.loads(retried.stdout), committed | {"duplicate": True})
        self.assertEqual(self.event_work(patient)["invalidated_count"], 1)
        self.assertEqual(len(self.receipts(failed["delivery_id"])), 1)

    def test_dump_restore_preserves_recovery_receipt_and_enforces_current_rights(self):
        for binary in ("pg_dump", "pg_restore", "psql"):
            self.assertIsNotNone(shutil.which(binary), f"PostgreSQL acceptance requires {binary}")
            version = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=5)
            self.assertEqual(version.returncode, 0, version.stderr)
            self.assertRegex(version.stdout, r"\(PostgreSQL\) 16\.")
        patient, run, failed = self.terminal_amendment()
        requested = self.recover(failed)
        before = self.snapshot()
        url = make_url(self.admin.database_url)
        name = "oi_api_test_event_recovery_" + uuid.uuid4().hex[:12]
        env = dict(os.environ, PGHOST=url.host, PGPORT=str(url.port or 5432),
                   PGUSER=url.username, PGPASSWORD=url.password or "")
        dump = str(Path(self.temp.name) / "event-recovery.backup")
        def command(args):
            result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
        command(["pg_dump", "--format=custom", "--no-owner", "--no-acl", "--dbname", url.database, "--file", dump])
        command(["psql", "--dbname", "postgres", "-v", "ON_ERROR_STOP=1", "--command", "CREATE DATABASE " + name])
        try:
            command(["pg_restore", "--no-owner", "--no-acl", "--dbname", name, dump])
            restored = Settings(database_url=url.set(database=name).render_as_string(hide_password=False),
                                access_file=str(self.access))
            self.assertEqual(self.snapshot(settings=restored), before)
            self.assertEqual(self.recover(failed, settings=restored), requested | {"duplicate": True})
            self.assertEqual(self.event_work(patient, settings=restored)["invalidated_count"], 1)
            restored_state = self.snapshot(settings=restored)
            saved = next(row for row in restored_state["investigation.composer_tool_runs"] if row["run_id"] == run)
            self.assertEqual(saved["state"], "stale")
            self.assertEqual(restored_state[RECOVERIES], before[RECOVERIES])
            self.assertEqual(len(self.receipts(failed["delivery_id"], settings=restored)), 1)
            self.assertEqual(self.snapshot(), before)
            self.creds[0]["actions"].remove("source_read")
            self.write()
            self.assertEqual(self.recover(failed, settings=restored), {"status": "blocked"})
            self.assertEqual(self.snapshot(settings=restored), restored_state)
        finally:
            command(["psql", "--dbname", "postgres", "-v", "ON_ERROR_STOP=1", "--command", "DROP DATABASE " + name])
