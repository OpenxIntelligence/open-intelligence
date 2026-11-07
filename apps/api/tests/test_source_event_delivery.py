"""Actual PG16 source-event delivery and owned Composer effects.

These independently fictional tests require the disposable database fixture.
Skipping them is not evidence for atomic delivery, lease recovery or persistence.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import uuid
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.engine import make_url

from oi_api.access import SyntheticFileAuthentication, authenticate_token
from oi_api.app import create_app
from oi_api.composer_runs import PostgresComposerRuns
from oi_api.config import Settings
from oi_api.database import Database, make_engine
from oi_api.registry_context import registry_for_principal
from open_intelligence.patient_registry import PatientRegistryConflict, PatientRegistryDenied
from open_intelligence.postgres_registry import PostgresPatientRegistry
from http_support import running_server
import test_composer_runs_postgres as run_fixture
import test_patients as patient_fixture
import test_source_versions as source_fixture


TOKEN = patient_fixture.TOKEN_A
OTHER_TOKEN = "synthetic-event-other-" + "b" * 32
CASE = "CASE-ALPHA"
ACTIONS = frozenset({"patient_read", "question_read", "source_read", "source_brief_export"})
OUTBOX = "coordination.source_event_outbox"
DELIVERIES = "coordination.source_event_deliveries"
HISTORY = "coordination.source_event_delivery_events"
RECEIPTS = "investigation.composer_source_event_receipts"


class SourceEventDeliveryPostgresTests(source_fixture.SourceVersionFixture):
    # Borrow fixture methods explicitly; do not rediscover Composer's acceptance tests.
    path = staticmethod(run_fixture.ComposerRunsPostgresTests.path)
    model_path = staticmethod(run_fixture.ComposerRunsPostgresTests.model_path)
    run_path = staticmethod(run_fixture.ComposerRunsPostgresTests.run_path)
    world = run_fixture.ComposerRunsPostgresTests.world
    preflight = run_fixture.ComposerRunsPostgresTests.preflight
    prepared = run_fixture.ComposerRunsPostgresTests.prepared
    save = run_fixture.ComposerRunsPostgresTests.save
    seed = run_fixture.ComposerRunsPostgresTests.seed
    events = run_fixture.ComposerRunsPostgresTests.events
    enqueue = run_fixture.ComposerRunsPostgresTests.enqueue
    seeded_run = run_fixture.ComposerRunsPostgresTests.seeded_run
    status = run_fixture.ComposerRunsPostgresTests.status
    cancel = run_fixture.ComposerRunsPostgresTests.cancel
    store = run_fixture.ComposerRunsPostgresTests.store
    fresh_authority = run_fixture.ComposerRunsPostgresTests.fresh_authority
    claim = run_fixture.ComposerRunsPostgresTests.claim
    complete = run_fixture.ComposerRunsPostgresTests.complete
    work = run_fixture.ComposerRunsPostgresTests.work
    stored = run_fixture.ComposerRunsPostgresTests.stored

    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend(("composer_context_read", "question_create",
                                         "question_read", "source_brief_export"))
        self.write()

    @contextmanager
    def delivery_store(self, patient, *, token=TOKEN, settings=None):
        settings = settings or self.settings
        database = Database(settings)
        provider = SyntheticFileAuthentication(str(self.access))
        initial = authenticate_token(token, provider)
        try:
            with database.registry_connection() as connection:
                registry = registry_for_principal(connection, initial)
                def recheck():
                    current = authenticate_token(token, provider)
                    if (current.actor, current.organization, current.purpose) != (
                            initial.actor, initial.organization, initial.purpose):
                        raise PatientRegistryDenied("Synthetic delivery identity changed")
                    live = registry_for_principal(connection, current)
                    for action in ACTIONS:
                        live._allow(current.actor, patient, action, current.purpose)
                yield PostgresComposerRuns(registry).source_events(), initial, recheck
        finally:
            database.close()

    def claim_event(self, patient, *, case=CASE, token=TOKEN, lease=30, settings=None):
        with self.delivery_store(patient, token=token, settings=settings) as (store, context, recheck):
            return store.claim_next(patient, case, organization=context.organization,
                                    actor=context.actor, purpose=context.purpose,
                                    recheck_authority=recheck, lease_seconds=lease)

    def deliver_event(self, claim, *, token=TOKEN, settings=None):
        with self.delivery_store(claim["patient_id"], token=token, settings=settings) as (store, _, recheck):
            return store.deliver(claim, recheck_authority=recheck)

    def fail_event(self, claim, reason="retryable_failure"):
        with self.delivery_store(claim["patient_id"]) as (store, _, _):
            return store.finish_failure(claim, reason_code=reason)

    def event_work(self, patient, *, case=CASE, token=TOKEN, settings=None, lease=30):
        from oi_api.event_worker import run_once
        result = run_once(settings or self.settings, lambda: token, patient, case, lease_seconds=lease)
        self.assertLessEqual(set(result), {"status", "attempt_count", "invalidated_count"})
        self.assertNotIn(token, json.dumps(result))
        return result

    def event_status(self, patient, *, case=CASE, token=TOKEN):
        from oi_api.event_worker import read_status
        return read_status(self.settings, lambda: token, patient, case)

    def test_status_observes_backlog_without_claiming_and_separates_actor_history(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            empty = self.event_status(patient)
            fields = ("unclaimed", "queued_ready", "queued_waiting", "running_active",
                      "running_expired", "delivered", "dead_letter")
            self.assertEqual(empty["status"], "observed")
            self.assertEqual([empty[key] for key in fields], [0] * len(fields))
            self.assertEqual(self.ingest(base, patient)[0], 201)
        self.add_other_actor(patient)
        before = self.snapshot()
        observed = self.event_status(patient)
        self.assertEqual(observed["unclaimed"], 1)
        after = self.snapshot()
        journal = "identity.identity_domain_events"
        self.assertEqual({k: v for k, v in before.items() if k != journal},
                         {k: v for k, v in after.items() if k != journal})
        self.assertEqual(after[journal][:-1], before[journal])
        self.assertEqual(after[journal][-1]["event_type"], "source.delivery.status_read_authorized")
        claim = self.claim_event(patient)
        self.assertEqual(self.event_status(patient)["running_active"], 1)
        self.assertEqual(self.event_status(patient, token=OTHER_TOKEN)["unclaimed"], 1)
        self.deliver_event(claim)
        self.assertEqual(self.event_status(patient)["delivered"], 1)
        self.assertEqual(self.event_status(patient, token=OTHER_TOKEN)["delivered"], 0)
        cli = subprocess.run([sys.executable, "-m", "oi_api.event_worker", "--status",
                              "--patient", patient, "--case", CASE], env=self.event_worker_env(),
                             capture_output=True, text=True, timeout=15)
        self.assertEqual(cli.returncode, 0, cli.stderr)
        self.assertEqual(json.loads(cli.stdout)["delivered"], 1)
        self.assertEqual(cli.stderr, "")
        self.assertEqual(self.event_status(patient, case="CASE-OTHER"), {"status": "blocked"})
        self.assertEqual(self.event_status("PATIENT-OTHER"), {"status": "blocked"})
        for private in (TOKEN, claim["lease_token"], claim["delivery_id"], patient):
            self.assertNotIn(private, json.dumps(observed))

    def test_status_reports_retry_delay_expired_lease_and_dead_letter_without_recovery(self):
        with running_server(create_app(self.settings)) as base:
            patient, _, _, run = self.seeded_run(base)
        claim = self.claim_event(patient, lease=1)
        time.sleep(1.1)
        before = self.delivery(claim["delivery_id"])
        self.assertEqual(self.event_status(patient)["running_expired"], 1)
        self.assertEqual(self.delivery(claim["delivery_id"]), before)
        retry = self.claim_event(patient)
        self.assertEqual(self.fail_event(retry), "queued")
        self.assertEqual(self.event_status(patient)["queued_waiting"], 1)
        # Database clock controls eligibility; observe rather than rewriting a lease.
        deadline = time.monotonic() + 10
        while self.event_status(patient)["queued_ready"] != 1 and time.monotonic() < deadline:
            time.sleep(0.1)
        self.assertEqual(self.event_status(patient)["queued_ready"], 1)
        final = self.claim_event(patient)
        self.assertEqual(self.fail_event(final, "invalid_event"), "dead_letter")
        self.assertEqual(self.event_work(patient), {"status": "idle"})
        self.assertEqual(self.event_status(patient)["dead_letter"], 1)
        self.assertEqual(self.stored(run)[0]["state"], "queued")

    def test_status_revocation_at_audit_tail_rolls_back_read_receipt(self):
        with running_server(create_app(self.settings)) as base:
            patient, _, _, _ = self.seeded_run(base)
        before = self.snapshot()
        original = PostgresPatientRegistry.append_event
        def revoke(registry, patient_id, event_type, **metadata):
            result = original(registry, patient_id, event_type, **metadata)
            if event_type == "source.delivery.status_read_authorized":
                self.creds[0]["actions"].remove("source_read")
                self.write()
            return result
        with patch.object(PostgresPatientRegistry, "append_event", revoke):
            self.assertEqual(self.event_status(patient), {"status": "blocked"})
        self.assertEqual(self.snapshot(), before)

    def event_dead_letters(self, patient, *, case=CASE, token=TOKEN, **page):
        from oi_api.event_worker import read_dead_letters
        return read_dead_letters(self.settings, lambda: token, patient, case, **page)

    def test_dead_letters_paginate_exact_failures_without_mutating_or_leaking_actor_scope(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            self.assertEqual(self.event_dead_letters(patient),
                             {"status": "observed", "items": [], "next_after_event_id": None})
            self.assertEqual(self.ingest(base, patient)[0], 201)
            self.assertEqual(self.ingest(base, patient, source_fixture.AMENDED)[0], 201)
        self.add_other_actor(patient)
        claims = []
        for reason in ("invalid_event", "authority_unavailable"):
            claim = self.claim_event(patient)
            self.assertEqual(self.fail_event(claim, reason), "dead_letter")
            claims.append(claim)
        before = self.snapshot()
        first = self.event_dead_letters(patient, limit=1)
        after = self.snapshot()
        journal = "identity.identity_domain_events"
        self.assertEqual({k: v for k, v in before.items() if k != journal},
                         {k: v for k, v in after.items() if k != journal})
        self.assertEqual(after[journal][:-1], before[journal])
        self.assertEqual(after[journal][-1]["event_type"], "source.delivery.dead_letters_read_authorized")
        self.assertEqual(first["next_after_event_id"], claims[0]["event_id"])
        second = self.event_dead_letters(patient, limit=1, after_event=first["next_after_event_id"])
        self.assertIsNone(second["next_after_event_id"])
        for page, claim, reason in zip((first, second), claims, ("invalid_event", "authority_unavailable")):
            self.assertEqual(len(page["items"]), 1)
            item = page["items"][0]
            self.assertEqual(set(item), {"delivery_id", "event_id", "revision", "attempt_count",
                                        "failure_count", "reason_code", "failed_at"})
            current = self.delivery(claim["delivery_id"])
            for key in ("delivery_id", "event_id", "revision", "attempt_count", "failure_count"):
                self.assertEqual(item[key], current[key])
            self.assertEqual(item["reason_code"], reason)
            self.assertEqual(item["failed_at"], current["updated_at"].isoformat())
            for secret in (TOKEN, claim["lease_token"], source_fixture.ORIGINAL, patient):
                self.assertNotIn(secret, json.dumps(page))
        self.assertEqual(self.event_dead_letters(patient, token=OTHER_TOKEN)["items"], [])
        self.assertEqual(self.event_dead_letters(patient, case="CASE-OTHER"), {"status": "blocked"})
        self.assertEqual(self.event_dead_letters("PATIENT-OTHER"), {"status": "blocked"})
        self.assertEqual(self.event_dead_letters(patient, after_event=claims[-1]["event_id"])["items"], [])
        cli = subprocess.run([sys.executable, "-m", "oi_api.event_worker", "--dead-letters",
                              "--patient", patient, "--case", CASE, "--limit", "1", "--after-event",
                              str(first["next_after_event_id"])], env=self.event_worker_env(),
                             capture_output=True, text=True, timeout=15)
        self.assertEqual(cli.returncode, 0, cli.stderr)
        self.assertEqual(json.loads(cli.stdout), second)
        self.assertEqual(cli.stderr, "")

    def test_dead_letter_read_revocation_rolls_back_audit_and_withholds_identifiers(self):
        with running_server(create_app(self.settings)) as base:
            patient, _, _, _ = self.seeded_run(base)
        self.assertEqual(self.fail_event(self.claim_event(patient), "invalid_event"), "dead_letter")
        before = self.snapshot()
        original = PostgresPatientRegistry.append_event
        def revoke(registry, patient_id, event_type, **metadata):
            result = original(registry, patient_id, event_type, **metadata)
            if event_type == "source.delivery.dead_letters_read_authorized":
                self.creds[0]["actions"].remove("source_read")
                self.write()
            return result
        with patch.object(PostgresPatientRegistry, "append_event", revoke):
            self.assertEqual(self.event_dead_letters(patient), {"status": "blocked"})
        self.assertEqual(self.snapshot(), before)

    def test_bounded_drain_budget_and_cli_resume_preserve_exact_delivery_receipts(self):
        from oi_api.event_worker import run_bounded
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            self.assertEqual(self.ingest(base, patient)[0], 201)
            self.assertEqual(self.ingest(base, patient, source_fixture.AMENDED)[0], 201)
        result = run_bounded(self.settings, lambda: TOKEN, patient, CASE, max_batches=1)
        self.assertEqual(result, {"status": "limit_reached", "batches_attempted": 1,
                                  "delivered_batches": 1, "continued_batches": 0})
        self.assertEqual(self.event_status(patient)["unclaimed"], 1)
        cli = subprocess.run([sys.executable, "-m", "oi_api.event_worker", "--drain",
                              "--patient", patient, "--case", CASE, "--max-batches", "10"],
                             env=self.event_worker_env(), capture_output=True, text=True, timeout=30)
        self.assertEqual(cli.returncode, 0, cli.stderr)
        self.assertEqual(json.loads(cli.stdout), {"status": "idle", "batches_attempted": 2,
                                                 "delivered_batches": 1, "continued_batches": 0})
        self.assertEqual(cli.stderr, "")
        self.assertEqual(self.event_status(patient)["delivered"], 2)
        rows = self.rows(DELIVERIES, "event_id")
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(row["attempt_count"], 1)
            self.assertEqual(len(self.receipts(row["delivery_id"])), 1)

    def test_elapsed_drain_stop_preserves_committed_receipt_and_resumes_unclaimed_work(self):
        import oi_api.event_worker as worker
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            self.assertEqual(self.ingest(base, patient)[0], 201)
            self.assertEqual(self.ingest(base, patient, source_fixture.AMENDED)[0], 201)
        clock = [0.0]
        original = worker.run_once
        def complete_then_expire(*args, **kwargs):
            result = original(*args, **kwargs)
            self.assertEqual(result["status"], "delivered")
            clock[0] = 2.0
            return result
        with patch.object(worker, "monotonic", side_effect=lambda: clock[0]), \
             patch.object(worker, "run_once", side_effect=complete_then_expire) as execute:
            result = worker.run_bounded(self.settings, lambda: TOKEN, patient, CASE,
                                        max_batches=10, max_seconds=1)
        self.assertEqual(result, {"status": "time_limit_reached", "batches_attempted": 1,
                                  "delivered_batches": 1, "continued_batches": 0})
        self.assertEqual(execute.call_count, 1)
        first, = self.rows(DELIVERIES, "event_id")
        first_receipts = self.receipts(first["delivery_id"])
        self.assertEqual(len(first_receipts), 1)
        self.assertEqual(self.event_status(patient)["unclaimed"], 1)
        cli = subprocess.run([sys.executable, "-m", "oi_api.event_worker", "--drain",
                              "--patient", patient, "--case", CASE,
                              "--max-batches", "10", "--max-seconds", "10"],
                             env=self.event_worker_env(), capture_output=True, text=True, timeout=30)
        self.assertEqual(cli.returncode, 0, cli.stderr)
        self.assertEqual(json.loads(cli.stdout), {"status": "idle", "batches_attempted": 2,
                                                 "delivered_batches": 1, "continued_batches": 0})
        self.assertEqual(cli.stderr, "")
        self.assertEqual(self.receipts(first["delivery_id"]), first_receipts)
        rows = self.rows(DELIVERIES, "event_id")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], first)
        for row in rows:
            self.assertEqual(row["state"], "delivered")
            self.assertEqual(row["attempt_count"], 1)
            self.assertEqual(len(self.receipts(row["delivery_id"])), 1)

    def assert_bounded_drain_authority_change(self, change):
        import oi_api.event_worker as worker
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base, key="CREATE-DRAIN-" + change.upper(),
                                      source_subject="SUBJECT-DRAIN-" + change.upper())
            self.assertEqual(self.ingest(base, patient)[0], 201)
            self.assertEqual(self.ingest(base, patient, source_fixture.AMENDED)[0], 201)
        original = worker.run_once
        original_actor = self.creds[0]["actor"]
        calls = []
        def revoke_after_batch(*args, **kwargs):
            result = original(*args, **kwargs)
            calls.append(result)
            if len(calls) == 1:
                self.assertEqual(result["status"], "delivered")
                if change == "grant":
                    self.creds[0]["actions"].remove("source_read")
                else:
                    self.creds[0]["actor"] = "ACTOR-ROTATED"
                self.write()
            return result
        try:
            with patch.object(worker, "run_once", revoke_after_batch):
                result = worker.run_bounded(self.settings, lambda: TOKEN, patient, CASE)
            self.assertEqual(result, {"status": "blocked", "batches_attempted": 2,
                                      "delivered_batches": 1, "continued_batches": 0})
            scoped = [row for row in self.rows(DELIVERIES, "event_id") if row["patient_id"] == patient]
            self.assertEqual(len(scoped), 1)
            self.assertEqual(scoped[0]["state"], "delivered")
        finally:
            self.creds[0]["actor"] = original_actor
            if "source_read" not in self.creds[0]["actions"]:
                self.creds[0]["actions"].append("source_read")
            self.write()

    def test_bounded_drain_rechecks_revocation_between_batches(self):
        self.assert_bounded_drain_authority_change("grant")

    def test_bounded_drain_pins_identity_between_batches(self):
        self.assert_bounded_drain_authority_change("actor")

    def drain(self, patient, *, case=CASE, token=TOKEN):
        outcomes = []
        for _ in range(20):
            claim = self.claim_event(patient, case=case, token=token)
            if claim is None:
                return outcomes
            self.assertEqual(claim["state"], "running")
            result = self.deliver_event(claim, token=token)
            self.assertIn(result["status"], ("delivered", "queued"))
            outcomes.append(result)
        self.fail("Finite fictional source events did not drain")

    def rows(self, table, order, *, settings=None):
        engine = make_engine(settings) if settings else self.engine
        try:
            with engine.connect() as connection:
                return [dict(row) for row in connection.execute(text(
                    "SELECT * FROM " + table + " ORDER BY " + order)).mappings().all()]
        finally:
            if settings:
                engine.dispose()

    def delivery(self, delivery_id, *, settings=None):
        return next(row for row in self.rows(DELIVERIES, "delivery_id", settings=settings)
                    if row["delivery_id"] == delivery_id)

    def receipts(self, delivery_id, *, settings=None):
        return [row for row in self.rows(RECEIPTS, "delivery_id,attempt_count", settings=settings)
                if row["delivery_id"] == delivery_id]

    def snapshot(self, *, settings=None):
        tables = {
            "identity.identity_patients": "patient_id",
            "identity.identity_domain_events": "id",
            "clinical_source.source_versions": "source_id",
            "clinical_source.assertions": "source_id,source_line",
            "investigation.source_questions": "question_id",
            "investigation.composer_tool_runs": "run_id",
            "investigation.composer_tool_run_events": "run_id,revision",
            "investigation.composer_tool_run_results": "run_id",
            OUTBOX: "event_id", DELIVERIES: "delivery_id",
            HISTORY: "delivery_id,revision", RECEIPTS: "delivery_id,attempt_count",
        }
        return {table: self.rows(table, order, settings=settings) for table, order in tables.items()}

    def assert_replay_only_adds_authorized_read(self, before, after, claim):
        journal = "identity.identity_domain_events"
        self.assertEqual({key: value for key, value in after.items() if key != journal},
                         {key: value for key, value in before.items() if key != journal})
        self.assertEqual(after[journal][:-1], before[journal])
        audit = after[journal][-1]
        self.assertEqual(audit["event_type"], "source.delivery.receipt_read_authorized")
        self.assertEqual(audit["patient_id"], claim["patient_id"])
        self.assertEqual(audit["metadata_json"]["delivery_id"], claim["delivery_id"])
        self.assertEqual(audit["metadata_json"]["source_event_id"], claim["event_id"])

    def add_other_actor(self, patient):
        self.creds.append(patient_fixture.credential(
            OTHER_TOKEN, actor="ACTOR-EVENT-OTHER", organization=self.creds[0]["organization"],
            patients=(patient,), actions=self.creds[0]["actions"]))
        self.write()

    def enqueue_as(self, base, patient, question, preflight, *, key, token=TOKEN, case=CASE):
        payload = {
            "synthetic": True, "request_key": key,
            "source_snapshot_contract": "oi.pg-source-world-model/1",
            "expected_source_snapshot_sha256": preflight["source_snapshot_sha256"],
            "expected_preflight_sha256": preflight["preflight_sha256"],
        }
        code, receipt, _ = patient_fixture.request(
            base, f"/v1/patients/{patient}/cases/{case}/questions/{question}/runs",
            token=token, body=payload)
        self.assertEqual(code, 201, receipt)
        return receipt["run"]["run_id"]

    def test_outbox_references_original_journal_and_duplicate_import_has_no_delivery(self):
        with running_server(create_app(self.settings)) as base:
            patient, _, _, run = self.seeded_run(base)
            outbox = self.rows(OUTBOX, "event_id")
            self.assertEqual(len(outbox), 1)
            row = outbox[0]
            self.assertEqual((row["patient_id"], row["case_id"], row["purpose"], row["source_version"]),
                             (patient, CASE, "operations", 1))
            self.assertEqual(row["source_id"], self.stored(run)[0]["source_id"])
            with self.engine.connect() as connection:
                event = connection.execute(text(
                    "SELECT patient_id,event_type,metadata_json FROM identity.identity_domain_events WHERE id=:id"),
                    {"id": row["event_id"]}).mappings().one()
            self.assertEqual((event["patient_id"], event["event_type"]),
                             (patient, "source.original.imported"))
            self.assertEqual(event["metadata_json"]["source_id"], row["source_id"])
            self.assertNotIn("raw", row)
            self.assertNotIn("question", row)
            self.assertEqual(self.ingest(base, patient)[0], 200)
            self.assertEqual(self.rows(OUTBOX, "event_id"), outbox)
            self.assertEqual(self.rows(DELIVERIES, "delivery_id"), [])

    def test_outbox_insert_failure_rolls_back_original_assertions_and_journal(self):
        with running_server(create_app(self.settings)) as base:
            patient = self.setup_case(base)
            before = self.snapshot()
            with self.engine.begin() as connection:
                connection.exec_driver_sql("""CREATE FUNCTION coordination.reject_test_publication()
                    RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
                    RAISE EXCEPTION 'SYNTHETIC-OUTBOX-FAILURE'; END; $$""")
                connection.exec_driver_sql("CREATE TRIGGER reject_test_publication BEFORE INSERT ON " + OUTBOX +
                                           " FOR EACH ROW EXECUTE FUNCTION coordination.reject_test_publication()")
            try:
                code, body, _ = self.ingest(base, patient)
                self.assertEqual(code, 503, body)
                self.assertEqual(set(body), {"detail"})
                self.assertEqual(self.snapshot(), before)
            finally:
                with self.engine.begin() as connection:
                    connection.exec_driver_sql("DROP TRIGGER reject_test_publication ON " + OUTBOX)
                    connection.exec_driver_sql("DROP FUNCTION coordination.reject_test_publication()")

    def test_current_snapshot_delivery_records_zero_effect_without_blinding_run(self):
        with running_server(create_app(self.settings)) as base:
            patient, _, _, run = self.seeded_run(base)
            before = self.stored(run)
            claim = self.claim_event(patient)
            self.assertEqual(self.deliver_event(claim),
                             {"status": "delivered", "invalidated_count": 0, "duplicate": False})
            self.assertEqual(self.stored(run), before)
            receipt = self.receipts(claim["delivery_id"])[0]
            self.assertEqual((receipt["event_id"], receipt["invalidated_count"], receipt["has_more"]),
                             (claim["event_id"], 0, False))
            self.assertEqual(receipt["source_snapshot_sha256"], before[0]["source_snapshot_sha256"])
            self.assertIsNone(self.claim_event(patient))

    def test_amendment_retires_queued_run_without_consuming_a_compute_attempt(self):
        with running_server(create_app(self.settings)) as base:
            patient, question, _, run = self.seeded_run(base)
            self.drain(patient)
            self.assertEqual(self.ingest(base, patient, source_fixture.AMENDED)[0], 201)
            self.assertEqual(self.stored(run)[0]["state"], "queued")
            claim = self.claim_event(patient)
            result = self.deliver_event(claim)
            self.assertEqual((result["status"], result["invalidated_count"]), ("delivered", 1))
            row, count, history = self.stored(run)
            self.assertEqual((row["state"], row["attempt_count"], count), ("stale", 0, 0))
            self.assertIsNone(row["lease_token"])
            self.assertEqual(history, [(1, "queued", "queued"), (2, "stale", "source_changed")])
            self.assertEqual(self.status(base, patient, question, run)[1]["state"], "stale")
            self.assertEqual(self.work(patient), {"status": "idle"})
            stale_audits = [metadata for kind, metadata in self.events()
                            if kind == "composer.run.stale" and metadata["run_id"] == run]
            self.assertEqual(len(stale_audits), 1)
            self.assertEqual({key: stale_audits[0][key] for key in
                              ("source_event_id", "delivery_id", "delivery_attempt")},
                             {"source_event_id": claim["event_id"], "delivery_id": claim["delivery_id"],
                              "delivery_attempt": claim["attempt_count"]})
            before = self.snapshot()
            self.assertEqual(self.deliver_event(claim),
                             {"status": "delivered", "invalidated_count": 1, "duplicate": True})
            self.assert_replay_only_adds_authorized_read(before, self.snapshot(), claim)
            self.assertEqual([metadata for kind, metadata in self.events()
                              if kind == "composer.run.stale" and metadata["run_id"] == run], stale_audits)

    def test_new_other_document_invalidates_whole_case_snapshot(self):
        with running_server(create_app(self.settings)) as base:
            patient, _, _, run = self.seeded_run(base)
            original_source = self.stored(run)[0]["source_id"]
            self.drain(patient)
            other = source_fixture.ORIGINAL.replace("DOC-ONE", "DOC-OTHER").replace("SPECIMEN-ONE", "SPECIMEN-OTHER")
            code, imported, _ = self.ingest(base, patient, other)
            self.assertEqual(code, 201, imported)
            self.assertNotEqual(imported["source_id"], original_source)
            self.assertEqual(self.event_work(patient)["invalidated_count"], 1)
            self.assertEqual(self.stored(run)[0]["state"], "stale")

    def test_manual_document_import_does_not_change_source_only_run_snapshot(self):
        with running_server(create_app(self.settings)) as base:
            patient, _, _, run = self.seeded_run(base)
            self.drain(patient)
            before = self.stored(run)
            raw = b"Independently fictional manual record\nMarker pending.\n"
            path = f"/v1/patients/{patient}/cases/{CASE}/documents"
            upload = {"synthetic": True, "filename": "fictional.txt",
                      "original_base64": base64.b64encode(raw).decode()}
            code, preview, _ = patient_fixture.request(base, path + "/preview", token=TOKEN, body=upload)
            self.assertEqual(code, 200, preview)
            payload = {**upload, "confirmed_case_id": CASE, "expected_sha256": preview["sha256"],
                       "metadata": {"document_id": "DOC-MANUAL", "kind": "pathology",
                                    "event_date": "2026-01-10", "issued_at": "2026-01-11",
                                    "manual_transcription_confirmed": True},
                       "findings": [{"key": "marker", "state": "pending", "quote": "Marker pending.", "line": 2}]}
            code, saved, _ = patient_fixture.request(base, path, token=TOKEN, body=payload)
            self.assertEqual(code, 201, saved)
            result = self.event_work(patient)
            self.assertEqual((result["status"], result["invalidated_count"]), ("delivered", 0))
            self.assertEqual(self.stored(run), before)

    def test_delayed_older_event_preserves_new_current_run_and_completed_history(self):
        with running_server(create_app(self.settings)) as base:
            patient, question, preflight, completed = self.seeded_run(base)
            self.assertEqual(self.work(patient)["status"], "completed")
            completed_before = self.stored(completed)
            stale = self.enqueue_as(base, patient, question, preflight, key="RUN-OLD-CONTEXT")
            code, amended, _ = self.ingest(base, patient, source_fixture.AMENDED)
            self.assertEqual(code, 201, amended)
            fresh = self.prepared(base, patient, amended["source_id"], line=9,
                                  question="What does the amended fictional statement report?")
            code, saved, _ = self.save(base, patient, fresh, request_key="QUESTION-AFTER-AMENDMENT")
            self.assertEqual(code, 201, saved)
            current = self.enqueue_as(base, patient, saved["question_id"], fresh, key="RUN-CURRENT-CONTEXT")
            current_before = self.stored(current)
            outcomes = self.drain(patient)
            self.assertEqual(sum(row["invalidated_count"] for row in outcomes), 1)
            self.assertEqual(self.stored(stale)[0]["state"], "stale")
            self.assertEqual(self.stored(current), current_before)
            self.assertEqual(self.stored(completed), completed_before)
            self.assertEqual(self.status(base, patient, question, completed, "/result")[0], 409)

    def test_running_compute_claim_is_fenced_by_source_event(self):
        with running_server(create_app(self.settings)) as base:
            patient, _, _, run = self.seeded_run(base)
            self.drain(patient)
            compute_claim = self.claim(patient)
            self.assertEqual(self.ingest(base, patient, source_fixture.AMENDED)[0], 201)
            self.assertEqual(self.event_work(patient)["invalidated_count"], 1)
            row, count, _ = self.stored(run)
            self.assertEqual((row["state"], row["attempt_count"], count), ("stale", 1, 0))
            self.assertIsNone(row["lease_token"])
            with self.assertRaises(PatientRegistryConflict):
                self.complete(compute_claim)

    def test_each_owner_actor_gets_delivery_without_importer_impersonation(self):
        with running_server(create_app(self.settings)) as base:
            patient, question, preflight, first = self.seeded_run(base)
            self.add_other_actor(patient)
            second = self.enqueue_as(base, patient, question, preflight, key="RUN-OTHER-ACTOR", token=OTHER_TOKEN)
            self.drain(patient)
            self.drain(patient, token=OTHER_TOKEN)
            self.assertEqual(self.ingest(base, patient, source_fixture.AMENDED, token=OTHER_TOKEN)[0], 201)
            first_claim = self.claim_event(patient)
            self.assertEqual(self.deliver_event(first_claim)["invalidated_count"], 1)
            self.assertEqual(self.stored(first)[0]["state"], "stale")
            self.assertEqual(self.stored(second)[0]["state"], "queued")
            second_claim = self.claim_event(patient, token=OTHER_TOKEN)
            self.assertEqual(second_claim["event_id"], first_claim["event_id"])
            self.assertNotEqual(second_claim["delivery_id"], first_claim["delivery_id"])
            self.assertEqual(self.deliver_event(second_claim, token=OTHER_TOKEN)["invalidated_count"], 1)
            self.assertEqual(self.stored(second)[0]["state"], "stale")

    def test_duplicate_delivery_recovers_receipt_after_restart_without_second_effect(self):
        with running_server(create_app(self.settings)) as base:
            patient, _, _, run = self.seeded_run(base)
            self.drain(patient)
            self.assertEqual(self.ingest(base, patient, source_fixture.AMENDED)[0], 201)
        claim = self.claim_event(patient)
        delivered = self.deliver_event(claim)
        before = self.snapshot()
        duplicate = self.deliver_event(claim)
        self.assertEqual(duplicate, {**delivered, "duplicate": True})
        self.assert_replay_only_adds_authorized_read(before, self.snapshot(), claim)
        self.assertEqual(len(self.receipts(claim["delivery_id"])), 1)
        self.assertEqual(self.stored(run)[0]["revision"], 2)
        before = self.snapshot()
        self.creds[0]["actions"].remove("source_read")
        self.write()
        with self.assertRaises((PatientRegistryDenied, HTTPException)):
            self.deliver_event(claim)
        self.assertEqual(self.snapshot(), before)

    def test_replaced_delivery_lease_fences_the_old_attempt(self):
        with running_server(create_app(self.settings)) as base:
            patient, _, _, run = self.seeded_run(base)
            self.drain(patient)
            self.assertEqual(self.ingest(base, patient, source_fixture.AMENDED)[0], 201)
        old = self.claim_event(patient, lease=1)
        time.sleep(1.1)
        current = self.claim_event(patient)
        self.assertEqual(current["delivery_id"], old["delivery_id"])
        self.assertNotEqual(current["lease_token"], old["lease_token"])
        self.assertEqual(current["attempt_count"], old["attempt_count"] + 1)
        before = self.snapshot()
        with self.assertRaises(PatientRegistryConflict):
            self.deliver_event(old)
        self.assertEqual(self.fail_event(old), "fenced")
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.deliver_event(current)["invalidated_count"], 1)
        self.assertEqual(self.stored(run)[0]["state"], "stale")

    def test_concurrent_delivery_claims_have_one_owner(self):
        with running_server(create_app(self.settings)) as base:
            patient, _, _, _ = self.seeded_run(base)
        barrier = threading.Barrier(2)
        def claim():
            barrier.wait(timeout=10)
            return self.claim_event(patient)
        with ThreadPoolExecutor(max_workers=2) as pool:
            claims = list(pool.map(lambda _: claim(), range(2)))
        self.assertEqual(sum(claim is not None for claim in claims), 1)
        claim = next(value for value in claims if value is not None)
        self.assertEqual(self.deliver_event(claim)["status"], "delivered")
        self.assertEqual(len(self.rows(DELIVERIES, "delivery_id")), 1)

    def test_partial_batches_preserve_receipts_and_reset_consecutive_failures(self):
        with running_server(create_app(self.settings)) as base:
            patient, question, preflight, first = self.seeded_run(base)
            self.drain(patient)
            runs = [first] + [self.enqueue_as(base, patient, question, preflight, key=f"RUN-BATCH-{index:03d}")
                              for index in range(100)]
            self.assertEqual(self.ingest(base, patient, source_fixture.AMENDED)[0], 201)
        failed = self.claim_event(patient)
        self.assertEqual(self.fail_event(failed), "queued")
        self.assertEqual(self.delivery(failed["delivery_id"])["failure_count"], 1)
        time.sleep(2.1)
        first_batch = self.claim_event(patient)
        self.assertEqual(self.deliver_event(first_batch),
                         {"status": "queued", "invalidated_count": 100, "duplicate": False})
        self.assertEqual(self.delivery(first_batch["delivery_id"])["failure_count"], 0)
        self.assertEqual(sum(self.stored(run)[0]["state"] == "stale" for run in runs), 100)
        second_batch = self.claim_event(patient)
        self.assertEqual(second_batch["delivery_id"], first_batch["delivery_id"])
        self.assertEqual(second_batch["attempt_count"], 3)
        self.assertEqual(self.deliver_event(second_batch),
                         {"status": "delivered", "invalidated_count": 1, "duplicate": False})
        self.assertTrue(all(self.stored(run)[0]["state"] == "stale" for run in runs))
        receipts = self.receipts(first_batch["delivery_id"])
        self.assertEqual([(row["attempt_count"], row["invalidated_count"], row["has_more"]) for row in receipts],
                         [(2, 100, True), (3, 1, False)])
        before = self.snapshot()
        self.assertEqual(self.deliver_event(first_batch),
                         {"status": "queued", "invalidated_count": 100, "duplicate": True})
        self.assert_replay_only_adds_authorized_read(before, self.snapshot(), first_batch)

    def test_third_consecutive_expired_lease_is_dead_lettered(self):
        with running_server(create_app(self.settings)) as base:
            patient, _, _, run = self.seeded_run(base)
        claims = []
        for expected_attempt in (1, 2, 3):
            claim = self.claim_event(patient, lease=1)
            self.assertEqual((claim["state"], claim["attempt_count"]), ("running", expected_attempt))
            claims.append(claim)
            time.sleep(1.1)
        exhausted = self.claim_event(patient)
        self.assertEqual((exhausted["state"], exhausted["attempt_count"], exhausted["failure_count"]),
                         ("dead_letter", 3, 3))
        self.assertEqual(self.receipts(exhausted["delivery_id"]), [])
        self.assertIsNone(self.claim_event(patient))
        self.assertEqual(self.stored(run)[0]["state"], "queued")
        for claim in claims:
            self.assertEqual(self.fail_event(claim), "fenced")

    def recover(self, patient, *, token=TOKEN, settings=None, **command):
        from oi_api.event_worker import retry_delivery
        return retry_delivery(settings or self.settings, lambda: token, patient, CASE, **command)

    def failed_amendment(self, reason):
        with running_server(create_app(self.settings)) as base:
            patient, _, _, run = self.seeded_run(base)
            self.drain(patient)
            self.assertEqual(self.ingest(base, patient, source_fixture.AMENDED)[0], 201)
        claim = self.claim_event(patient)
        self.assertEqual(self.fail_event(claim, reason), "dead_letter")
        revision = self.delivery(claim["delivery_id"])["revision"]
        return patient, run, claim, dict(delivery_id=claim["delivery_id"], expected_revision=revision)

    def test_authorized_exact_retry_survives_response_loss_and_only_fresh_worker_changes_run(self):
        patient, run, claim, command = self.failed_amendment("authority_unavailable")
        self.assertEqual(self.recover(patient, **command), {"status": "blocked"})
        self.creds[0]["actions"].append("source_delivery_retry")
        self.write()
        page = self.event_dead_letters(patient)
        self.assertEqual(page["status"], "observed")
        item, = page["items"]
        self.assertEqual((item["delivery_id"], item["revision"], item["reason_code"]),
                         (claim["delivery_id"], command["expected_revision"], "authority_unavailable"))
        self.assertEqual(self.event_dead_letters(patient, after_event=claim["event_id"])["items"], [])
        self.add_other_actor(patient)
        self.assertEqual(self.event_dead_letters(patient, token=OTHER_TOKEN)["items"], [])
        self.assertEqual(self.recover(patient, token=OTHER_TOKEN, **command), {"status": "blocked"})
        self.assertEqual(self.recover(patient, delivery_id=claim["delivery_id"],
                                      expected_revision=command["expected_revision"]-1), {"status": "conflict"})
        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = [f.result(timeout=10) for f in
                             [pool.submit(self.recover, patient, **command) for _ in range(2)]]
        self.assertEqual({first["duplicate"], second["duplicate"]}, {True, False})
        self.assertEqual(first["audit_id"], second["audit_id"])
        self.assertEqual(first["status"], "retry_authorized")
        self.assertEqual(self.receipts(claim["delivery_id"]), [])
        self.assertEqual(self.stored(run)[0]["state"], "queued")
        self.creds[0]["actions"].remove("source_read")
        self.write()
        self.assertEqual(self.event_work(patient), {"status": "blocked"})
        self.assertEqual(self.recover(patient, **command), {"status": "blocked"})
        self.creds[0]["actions"].append("source_read")
        self.write()
        restarted = subprocess.run([sys.executable, "-m", "oi_api.event_worker", "--drain", "--max-batches", "2",
                                    "--patient", patient, "--case", CASE], env=self.event_worker_env(),
                                   text=True, capture_output=True, timeout=15)
        self.assertEqual(restarted.returncode, 0, restarted.stderr)
        self.assertEqual(json.loads(restarted.stdout), {"status": "idle", "batches_attempted": 2,
                                                       "delivered_batches": 1, "continued_batches": 0})
        self.assertEqual(self.delivery(claim["delivery_id"])["attempt_count"], 2)
        again = self.recover(patient, **command)
        self.assertEqual(again, {**first, "duplicate": True})
        self.assertEqual(self.event_dead_letters(patient)["items"], [])
        self.assertEqual(self.stored(run)[0]["state"], "stale")
        self.assertEqual(len(self.receipts(claim["delivery_id"])), 1)
        history = [row for row in self.rows(HISTORY, "revision") if row["delivery_id"] == claim["delivery_id"]]
        self.assertEqual([row["reason_code"] for row in history],
                         ["queued", "claimed", "authority_unavailable", "operator_retry", "claimed", "delivered"])
        self.assertEqual(history[3]["retry_audit_id"], first["audit_id"])
        self.assertEqual(self.fail_event(claim), "fenced")

    def test_invalid_event_remains_visible_and_cannot_be_requeued(self):
        patient, run, claim, command = self.failed_amendment("invalid_event")
        self.creds[0]["actions"].append("source_delivery_retry")
        self.write()
        item, = self.event_dead_letters(patient)["items"]
        self.assertEqual(item["reason_code"], "invalid_event")
        before = self.snapshot()
        self.assertEqual(self.recover(patient, **command), {"status": "conflict"})
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.stored(run)[0]["state"], "queued")

    def test_recovery_grant_revocation_at_commit_rolls_back_audit_and_requeue(self):
        patient, _, _, command = self.failed_amendment("authority_unavailable")
        self.creds[0]["actions"].append("source_delivery_retry")
        self.write()
        before = self.snapshot()
        original = PostgresPatientRegistry.append_event_with_id
        def revoke(registry, pid, kind, **details):
            audit_id = original(registry, pid, kind, **details)
            if kind == "source.delivery.retry_authorized":
                self.creds[0]["actions"].remove("source_delivery_retry")
                self.write()
            return audit_id
        with patch.object(PostgresPatientRegistry, "append_event_with_id", revoke):
            self.assertEqual(self.recover(patient, **command), {"status": "blocked"})
        self.assertEqual(self.snapshot(), before)

    def test_three_retryable_failures_use_backoff_then_dead_letter(self):
        with running_server(create_app(self.settings)) as base:
            patient, _, _, run = self.seeded_run(base)
        for failures in (1, 2, 3):
            claim = self.claim_event(patient)
            self.assertEqual(claim["state"], "running")
            state = self.fail_event(claim)
            self.assertEqual(state, "dead_letter" if failures == 3 else "queued")
            row = self.delivery(claim["delivery_id"])
            self.assertEqual(row["failure_count"], failures)
            self.assertIsNone(self.claim_event(patient))
            if failures < 3:
                self.assertGreater((row["available_at"] - row["updated_at"]).total_seconds(), 1.5)
                time.sleep((2 ** failures) + 0.1)
        self.assertEqual(self.receipts(claim["delivery_id"]), [])
        self.assertEqual(self.stored(run)[0]["state"], "queued")

        self.creds[0]["actions"].append("source_delivery_retry")
        self.write()
        failed = self.delivery(claim["delivery_id"])
        authorized = self.recover(patient, delivery_id=claim["delivery_id"], expected_revision=failed["revision"])
        self.assertEqual(authorized["status"], "retry_authorized")
        resumed = self.claim_event(patient)
        self.assertEqual((resumed["attempt_count"], resumed["failure_count"]), (4, 0))
        self.assertEqual(self.deliver_event(resumed)["status"], "delivered")

    def test_scope_revocation_before_delivery_rolls_back_all_effects(self):
        with running_server(create_app(self.settings)) as base:
            patient, _, _, run = self.seeded_run(base)
            self.drain(patient)
            self.assertEqual(self.ingest(base, patient, source_fixture.AMENDED)[0], 201)
        claim = self.claim_event(patient)
        before = self.snapshot()
        self.creds[0]["actions"].remove("source_brief_export")
        self.write()
        with self.assertRaises((PatientRegistryDenied, HTTPException)):
            self.deliver_event(claim)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.stored(run)[0]["state"], "queued")

    def test_source_audit_tail_revocation_rolls_back_receipt_ack_and_run_changes(self):
        with running_server(create_app(self.settings)) as base:
            patient, _, _, run = self.seeded_run(base)
            self.drain(patient)
            self.assertEqual(self.ingest(base, patient, source_fixture.AMENDED)[0], 201)
        claim = self.claim_event(patient)
        before = self.snapshot()
        original = PostgresPatientRegistry.append_event
        reached = []
        def revoke_after_source_audit(registry, pid, kind, **details):
            result = original(registry, pid, kind, **details)
            if kind == "source.read_authorized":
                reached.append(kind)
                self.creds[0]["actions"].remove("source_read")
                self.write()
            return result
        with patch.object(PostgresPatientRegistry, "append_event", revoke_after_source_audit):
            with self.assertRaises((PatientRegistryDenied, HTTPException)):
                self.deliver_event(claim)
        self.assertEqual(reached, ["source.read_authorized"])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.stored(run)[0]["state"], "queued")

    def test_transport_audit_tail_revocation_rolls_back_accepted_receipt_and_effect(self):
        with running_server(create_app(self.settings)) as base:
            patient, _, _, run = self.seeded_run(base)
            self.drain(patient)
            self.assertEqual(self.ingest(base, patient, source_fixture.AMENDED)[0], 201)
        claim = self.claim_event(patient)
        before = self.snapshot()
        original = PostgresPatientRegistry.append_event
        reached = []
        def revoke_after_ack(registry, pid, kind, **details):
            result = original(registry, pid, kind, **details)
            if kind == "source.delivery.delivered":
                reached.append(kind)
                self.creds[0]["actions"].remove("question_read")
                self.write()
            return result
        with patch.object(PostgresPatientRegistry, "append_event", revoke_after_ack):
            with self.assertRaises((PatientRegistryDenied, HTTPException)):
                self.deliver_event(claim)
        self.assertEqual(reached, ["source.delivery.delivered"])
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.stored(run)[0]["state"], "queued")

    def test_transport_audit_failure_cannot_leave_a_consumer_effect_without_ack(self):
        with running_server(create_app(self.settings)) as base:
            patient, _, _, _ = self.seeded_run(base)
            self.drain(patient)
            self.assertEqual(self.ingest(base, patient, source_fixture.AMENDED)[0], 201)
        claim = self.claim_event(patient)
        before = self.snapshot()
        original = PostgresPatientRegistry.append_event
        def fail_after_ack(registry, pid, kind, **details):
            result = original(registry, pid, kind, **details)
            if kind == "source.delivery.delivered":
                raise RuntimeError("SYNTHETIC-TRANSPORT-AUDIT-FAILURE")
            return result
        with patch.object(PostgresPatientRegistry, "append_event", fail_after_ack):
            with self.assertRaisesRegex(RuntimeError, "SYNTHETIC-TRANSPORT-AUDIT-FAILURE"):
                self.deliver_event(claim)
        self.assertEqual(self.snapshot(), before)

    def test_expiry_during_consumer_or_ack_audit_rolls_back_tentative_work(self):
        from oi_api.source_event_delivery import EventLeaseLost
        with running_server(create_app(self.settings)) as base:
            patient, _, _, run = self.seeded_run(base)
            self.drain(patient)
            self.assertEqual(self.ingest(base, patient, source_fixture.AMENDED)[0], 201)
        original = PostgresPatientRegistry.append_event
        for stage in ("composer.source_event.reconciled", "source.delivery.delivered"):
            with self.subTest(stage=stage):
                claim = self.claim_event(patient, lease=1)
                before = self.snapshot()
                reached = []
                def hold_after_real_write(registry, pid, kind, **details):
                    result = original(registry, pid, kind, **details)
                    if kind == stage:
                        reached.append(kind)
                        time.sleep(1.1)
                    return result
                with patch.object(PostgresPatientRegistry, "append_event", hold_after_real_write):
                    with self.assertRaises(EventLeaseLost):
                        self.deliver_event(claim)
                self.assertEqual(reached, [stage])
                self.assertEqual(self.snapshot(), before)
                self.assertEqual(self.stored(run)[0]["state"], "queued")

    def test_changed_worker_identity_after_claim_only_dead_letters_its_held_attempt(self):
        from oi_api.source_event_delivery import PostgresSourceEventDelivery
        with running_server(create_app(self.settings)) as base:
            patient, _, _, run = self.seeded_run(base)
            self.drain(patient)
            self.assertEqual(self.ingest(base, patient, source_fixture.AMENDED)[0], 201)
        original = PostgresSourceEventDelivery.claim_next
        def switch_actor(store, *args, **kwargs):
            claim = original(store, *args, **kwargs)
            self.creds[0]["actor"] = "ACTOR-CHANGED-AFTER-CLAIM"
            self.write()
            return claim
        with patch.object(PostgresSourceEventDelivery, "claim_next", switch_actor):
            result = self.event_work(patient)
        self.assertEqual(result, {"status": "dead_letter", "attempt_count": 1})
        delivery = self.rows(DELIVERIES, "event_id")[-1]
        self.assertEqual((delivery["state"], delivery["actor"]), ("dead_letter", "ACTOR-ALPHA"))
        self.assertEqual(self.receipts(delivery["delivery_id"]), [])
        self.assertEqual(self.stored(run)[0]["state"], "queued")
        history = [row for row in self.rows(HISTORY, "delivery_id,revision")
                   if row["delivery_id"] == delivery["delivery_id"]]
        self.assertEqual(history[-1]["reason_code"], "authority_unavailable")

    def test_other_actor_or_authorized_other_patient_cannot_apply_a_stolen_claim(self):
        with running_server(create_app(self.settings)) as base:
            patient, _, _, run = self.seeded_run(base)
            other = self.setup_case(base, case="CASE-BETA", key="PATIENT-OTHER", source_subject="SUBJECT-BETA")
            self.add_other_actor(patient)
            claim = self.claim_event(patient)
            before = self.snapshot()
            with self.assertRaises((PatientRegistryDenied, HTTPException)):
                self.deliver_event(claim, token=OTHER_TOKEN)
            forged = {**claim, "patient_id": other, "case_id": "CASE-BETA"}
            with self.assertRaises((PatientRegistryDenied, HTTPException)):
                self.deliver_event(forged)
            self.assertEqual(self.snapshot(), before)
            self.assertEqual(self.stored(run)[0]["state"], "queued")

    def test_earlier_event_committed_late_is_not_hidden_by_another_patient_cursor(self):
        with running_server(create_app(self.settings)) as base:
            first = self.setup_case(base)
            second = self.setup_case(base, case="CASE-BETA", key="PATIENT-SECOND", source_subject="SUBJECT-BETA")
            inserted = threading.Event()
            release = threading.Event()
            original = PostgresPatientRegistry.append_event
            def hold_first_commit(registry, pid, kind, **details):
                result = original(registry, pid, kind, **details)
                if pid == first and kind == "source.original.imported":
                    inserted.set()
                    if not release.wait(timeout=8):
                        raise AssertionError("Fictional cross-patient commit was not released")
                return result
            with patch.object(PostgresPatientRegistry, "append_event", hold_first_commit):
                with ThreadPoolExecutor(max_workers=1) as pool:
                    pending = pool.submit(self.ingest, base, first)
                    try:
                        self.assertTrue(inserted.wait(timeout=3), "First import did not allocate its journal event")
                        code, imported, _ = self.ingest(base, second, source_fixture.DIFFERENT, case="CASE-BETA")
                        self.assertEqual(code, 201, imported)
                        visible = self.claim_event(second, case="CASE-BETA")
                        self.assertEqual(self.deliver_event(visible)["invalidated_count"], 0)
                    finally:
                        release.set()
                    self.assertEqual(pending.result(timeout=5)[0], 201)
            earlier = self.claim_event(first)
            self.assertIsNotNone(earlier)
            self.assertLess(earlier["event_id"], visible["event_id"])
            self.assertEqual(self.deliver_event(earlier)["status"], "delivered")
            self.assertIsNone(self.claim_event(first))
            self.assertIsNone(self.claim_event(second, case="CASE-BETA"))

    def event_worker_env(self, settings=None):
        token_path = Path(self.temp.name) / "event-worker-token.txt"
        token_path.write_text(TOKEN)
        settings = settings or self.settings
        return {**os.environ, "OI_API_DATABASE_URL": settings.database_url,
                "OI_API_ACCESS_FILE": str(self.access), "OI_API_EVENT_WORKER_TOKEN_FILE": str(token_path),
                "OI_API_ENVIRONMENT": "synthetic"}

    def test_killed_retry_transaction_leaves_failed_delivery_and_original_audit_intact(self):
        patient, _, claim, command = self.failed_amendment("authority_unavailable")
        self.creds[0]["actions"].append("source_delivery_retry")
        self.write()
        before = self.snapshot()
        marker = Path(self.temp.name) / "retry-before-commit"
        script = """
import os, signal, sys
from pathlib import Path
from open_intelligence.postgres_registry import PostgresPatientRegistry
from oi_api.event_worker import main
original = PostgresPatientRegistry._execute
def pause_after_history(registry, sql, params=()):
    result = original(registry, sql, params)
    if "INSERT INTO coordination.source_event_delivery_events" in sql and "operator_retry" in sql:
        Path(sys.argv[1]).write_text("uncommitted")
        os.kill(os.getpid(), signal.SIGSTOP)
    return result
PostgresPatientRegistry._execute = pause_after_history
raise SystemExit(main(["--retry-delivery", sys.argv[2], "--expected-revision", sys.argv[3],
                       "--patient", sys.argv[4], "--case", "CASE-ALPHA"]))
"""
        child = subprocess.Popen(
            [sys.executable, "-c", script, str(marker), claim["delivery_id"],
             str(command["expected_revision"]), patient], env=self.event_worker_env(),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            until = time.monotonic() + 10
            while not marker.exists() and child.poll() is None and time.monotonic() < until:
                time.sleep(0.05)
            self.assertTrue(marker.exists(), "Retry did not reach its uncommitted history")
        finally:
            child.kill()
            child.communicate(timeout=5)
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.recover(patient, **command)["status"], "retry_authorized")
        self.assertEqual(self.event_work(patient)["status"], "delivered")

    def test_killed_delivery_process_recovers_and_fences_its_original_claim(self):
        from oi_api.source_event_delivery import EventLeaseLost
        with running_server(create_app(self.settings)) as base:
            patient, _, _, run = self.seeded_run(base)
            self.drain(patient)
            self.assertEqual(self.ingest(base, patient, source_fixture.AMENDED)[0], 201)
        marker = Path(self.temp.name) / "delivery-claim.json"
        script = '''
import json, os, signal, sys
from pathlib import Path
from oi_api.source_event_delivery import PostgresSourceEventDelivery
from oi_api.event_worker import main
original = PostgresSourceEventDelivery.claim_next
def stop_after_durable_claim(self, *args, **kwargs):
    claim = original(self, *args, **kwargs)
    if claim is not None:
        Path(sys.argv[1]).write_text(json.dumps(claim, default=str))
        os.kill(os.getpid(), signal.SIGSTOP)
    return claim
PostgresSourceEventDelivery.claim_next = stop_after_durable_claim
raise SystemExit(main(["--once", "--patient", sys.argv[2], "--case", "CASE-ALPHA", "--lease-seconds", "1"]))
'''
        child = subprocess.Popen([sys.executable, "-c", script, str(marker), patient],
                                 env=self.event_worker_env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            until = time.monotonic() + 10
            while not marker.exists() and child.poll() is None and time.monotonic() < until:
                time.sleep(0.05)
            self.assertTrue(marker.exists(), "Delivery process did not reach its durable claim")
            claim = json.loads(marker.read_text())
            self.assertEqual(self.delivery(claim["delivery_id"])["state"], "running")
            self.assertEqual(self.stored(run)[0]["state"], "queued")
        finally:
            child.kill()
            child.communicate(timeout=5)
        time.sleep(1.1)
        restarted = subprocess.run([sys.executable, "-m", "oi_api.event_worker", "--once", "--patient", patient,
                                    "--case", CASE], env=self.event_worker_env(), capture_output=True, text=True, timeout=15)
        self.assertEqual(restarted.returncode, 0, restarted.stderr)
        self.assertEqual(json.loads(restarted.stdout),
                         {"status": "delivered", "attempt_count": 2, "invalidated_count": 1})
        self.assertEqual(self.stored(run)[0]["state"], "stale")
        self.assertEqual(len(self.receipts(claim["delivery_id"])), 1)
        with self.assertRaises(EventLeaseLost):
            self.deliver_event(claim)

    def test_populated_restore_retains_pending_running_completed_and_delivery_replay(self):
        self.check_populated_restore()

    def test_populated_restore_retains_authorized_retry_and_lost_response_receipt(self):
        self.check_populated_restore(recovery=True)

    def check_populated_restore(self, *, recovery=False):
        for binary in ("pg_dump", "pg_restore", "psql"):
            self.assertIsNotNone(shutil.which(binary), f"PostgreSQL acceptance needs {binary}")
            version = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=5)
            self.assertEqual(version.returncode, 0, version.stderr)
            self.assertRegex(version.stdout, r"\(PostgreSQL\) 16\.")
        with running_server(create_app(self.settings)) as base:
            patient, question, preflight, completed = self.seeded_run(base)
            self.assertEqual(self.work(patient)["status"], "completed")
            self.drain(patient)
            running = self.enqueue_as(base, patient, question, preflight, key="RUN-RESTORE-RUNNING")
            self.assertEqual(self.claim(patient)["run_id"], running)
            queued = self.enqueue_as(base, patient, question, preflight, key="RUN-RESTORE-QUEUED")
            self.assertEqual(self.ingest(base, patient, source_fixture.AMENDED)[0], 201)
        claim = self.claim_event(patient, lease=30 if recovery else 1)
        if recovery:
            self.assertEqual(self.fail_event(claim, "authority_unavailable"), "dead_letter")
            self.creds[0]["actions"].append("source_delivery_retry")
            self.write()
            retry_intent = dict(delivery_id=claim["delivery_id"],
                                expected_revision=self.delivery(claim["delivery_id"])["revision"])
            authorization = self.recover(patient, **retry_intent)
            self.assertEqual(authorization["status"], "retry_authorized")
        before = self.snapshot()
        original_runs = {run: self.stored(run) for run in (completed, running, queued)}
        url = make_url(self.admin.database_url)
        name = "oi_api_test_source_event_restore_" + uuid.uuid4().hex[:12]
        env = {**os.environ, "PGHOST": url.host, "PGPORT": str(url.port or 5432),
               "PGUSER": url.username, "PGPASSWORD": url.password or ""}
        dump = str(Path(self.temp.name) / "source-event.backup")
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
            if recovery:
                retry = subprocess.run(
                    [sys.executable, "-m", "oi_api.event_worker", "--retry-delivery", claim["delivery_id"],
                     "--expected-revision", str(retry_intent["expected_revision"]), "--patient", patient,
                     "--case", CASE], env=self.event_worker_env(restored),
                    capture_output=True, text=True, timeout=15)
                self.assertEqual(retry.returncode, 0, retry.stderr)
                self.assertEqual(json.loads(retry.stdout), {**authorization, "duplicate": True})
            time.sleep(1.1)
            resumed = subprocess.run([sys.executable, "-m", "oi_api.event_worker", "--once", "--patient", patient,
                                      "--case", CASE], env=self.event_worker_env(restored),
                                     capture_output=True, text=True, timeout=15)
            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            self.assertEqual(json.loads(resumed.stdout),
                             {"status": "delivered", "attempt_count": 2, "invalidated_count": 2})
            after = self.snapshot(settings=restored)
            saved_runs = {row["run_id"]: row for row in after["investigation.composer_tool_runs"]}
            self.assertEqual(saved_runs[completed], original_runs[completed][0])
            self.assertEqual((saved_runs[running]["state"], saved_runs[queued]["state"]), ("stale", "stale"))
            self.assertEqual(after["investigation.composer_tool_run_results"],
                             before["investigation.composer_tool_run_results"])
            receipt = self.receipts(claim["delivery_id"], settings=restored)[0]
            replay_claim = {**claim, "attempt_count": 2, "lease_token": receipt["claim_token"]}
            self.assertEqual(self.deliver_event(replay_claim, settings=restored),
                             {"status": "delivered", "invalidated_count": 2, "duplicate": True})
            self.assert_replay_only_adds_authorized_read(after, self.snapshot(settings=restored), replay_claim)
            self.assertEqual(self.snapshot(), before)
            self.creds[0]["actions"].remove("source_read")
            self.write()
            with self.assertRaises((PatientRegistryDenied, HTTPException)):
                self.deliver_event(replay_claim, settings=restored)
        finally:
            command(["psql", "--dbname", "postgres", "-v", "ON_ERROR_STOP=1", "--command", "DROP DATABASE " + name])
