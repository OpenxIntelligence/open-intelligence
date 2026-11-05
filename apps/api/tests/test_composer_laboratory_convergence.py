"""Exercise both published histories against one migrated PostgreSQL application."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from unittest.mock import patch
import uuid

from sqlalchemy import text
from sqlalchemy.engine import make_url

from http_support import running_server
from oi_api.app import create_app
from oi_api.composer_runs import PostgresComposerRuns
from oi_api.config import Settings
from oi_api.database import make_engine
from oi_api.evidence_catalog import append_rights_decision
from oi_api.migrate import migrate
import test_composer_runs_postgres as composer
import test_ehr_laboratory_convergence as clinical
import test_evidence_convergence_migrations as history
from test_laboratory_fhir_r4 import OBS
from test_patients import TOKEN_A, request
from test_source_versions import SourceVersionFixture


COMPOSER = "0019_composer_runs"
EVENT = "0020_source_event_delivery"
CLINICAL = "0022_lab_citation_source_scope"
JOIN = "0023_composer_clinical_join"
CASE = "CASE-ALPHA"


class PopulatedComposerClinicalUpgradeTests(SourceVersionFixture):
    services = clinical.EHRLaboratoryUpgradeTests.services
    start_at = clinical.EHRLaboratoryUpgradeTests.start_at
    snapshot = clinical.EHRLaboratoryUpgradeTests.snapshot
    heads = clinical.EHRLaboratoryUpgradeTests.heads
    readiness = clinical.EHRLaboratoryUpgradeTests.readiness
    seed_lab = clinical.EHRLaboratoryUpgradeTests.seed_lab
    seed_citation = clinical.EHRLaboratoryUpgradeTests.seed_citation
    seed_encounter = clinical.EHRLaboratoryUpgradeTests.seed_encounter
    check_note = clinical.EHRLaboratoryUpgradeTests.check_note
    check_citation = clinical.EHRLaboratoryUpgradeTests.check_citation
    model_path = staticmethod(composer.ComposerRunsPostgresTests.model_path)
    path = staticmethod(composer.ComposerRunsPostgresTests.path)
    world = composer.ComposerRunsPostgresTests.world
    prepared = composer.ComposerRunsPostgresTests.prepared
    preflight = composer.ComposerRunsPostgresTests.preflight
    save = composer.ComposerRunsPostgresTests.save
    run_path = staticmethod(composer.ComposerRunsPostgresTests.run_path)
    enqueue = composer.ComposerRunsPostgresTests.enqueue
    status = composer.ComposerRunsPostgresTests.status
    work = composer.ComposerRunsPostgresTests.work
    stored = composer.ComposerRunsPostgresTests.stored
    fresh_authority = composer.ComposerRunsPostgresTests.fresh_authority

    def join(self, *parents):
        self.assertEqual(self.heads(), set(parents))
        self.readiness(False)
        tables, _ = self.snapshot()
        names = list(tables) + (clinical.EHR_TABLES if CLINICAL in parents else [])
        before, sequences = self.snapshot(names)
        migrate(self.admin, "upgrade", "head")
        migrate(self.admin, "upgrade", "head")
        self.assertEqual(self.heads(), {JOIN})
        self.readiness(True)
        after, current_sequences = self.snapshot(names)
        self.assertEqual(before, after)
        self.assertEqual(sequences, {key: current_sequences[key] for key in sequences})

    def assert_result(self, base, patient, question, run, prepared):
        code, result, headers = self.status(base, patient, question, run, "/result")
        self.assertEqual(code, 200, result)
        self.assertEqual(headers["Cache-Control"], "no-store")
        brief = result["brief"]
        calculated = hashlib.sha256(json.dumps(
            brief, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode()).hexdigest()
        self.assertEqual(result["result_sha256"], calculated)
        self.assertEqual(brief["question"]["question_id"], question)
        self.assertEqual(brief["selected_source"], prepared["selected_source"])
        self.assertFalse(brief["clinical_approval"])
        return calculated

    @contextmanager
    def restored_database(self):
        """Switch both runtime and trusted test reads to a freshly restored DB."""
        for executable in ("pg_dump", "pg_restore", "psql"):
            self.assertIsNotNone(shutil.which(executable), f"Joined restore needs {executable}")
            version = subprocess.run([executable, "--version"], check=True, capture_output=True,
                                     text=True, timeout=10).stdout
            self.assertRegex(version, r"\(PostgreSQL\) 16\.")
        url = make_url(self.admin.database_url)
        env = {**os.environ, "PGHOST": url.host, "PGPORT": str(url.port or 5432),
               "PGUSER": url.username, "PGPASSWORD": url.password or ""}
        name = "oi_api_test_join_restore_" + uuid.uuid4().hex[:16]
        dump = str(Path(self.temp.name) / "joined.backup")

        def command(*args):
            result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)

        # Snapshot complete original rows, including the acknowledgement and
        # consumer receipts. No client or worker is running during the dump.
        tables, _ = self.snapshot()
        names = [*tables, *clinical.EHR_TABLES, "public.alembic_version"]
        original = self.snapshot(names)
        command("pg_dump", "--format=custom", "--no-owner", "--no-acl", "--dbname", url.database, "--file", dump)
        command("psql", "--dbname", "postgres", "-v", "ON_ERROR_STOP=1", "-c", "CREATE DATABASE " + name)
        try:
            command("pg_restore", "--exit-on-error", "--no-owner", "--no-acl", "--dbname", name, dump)
            restored = Settings(database_url=url.set(database=name).render_as_string(hide_password=False),
                                access_file=str(self.access))
            engine = make_engine(restored)
            try:
                with patch.object(self, "engine", engine), patch.object(self, "settings", restored):
                    self.assertEqual(self.snapshot(names), original)
                    self.readiness(True)
                    yield
            finally:
                engine.dispose()
        finally:
            command("psql", "--dbname", "postgres", "-v", "ON_ERROR_STOP=1", "-c",
                    "DROP DATABASE " + name + " WITH (FORCE)")

    def seed_completed(self):
        patient, question, prepared = self.start_at(COMPOSER)
        self.creds[0]["actions"].append("source_brief_export")
        self.write()
        # Seed through the released storage owner; the current HTTP app must
        # refuse either incomplete schema. No version stamping or repair SQL.
        key = "COMPOSER-PRE-JOIN"
        with self.services() as registry:
            owner = PostgresComposerRuns(registry)
            run = self.queue_at_parent(owner, patient, question, prepared, key)
            claim = owner.claim_next(patient, CASE, **history.COMMON, recheck_authority=self.fresh_authority)
            self.assertEqual(claim["run_id"], run)
            completed = owner.complete(claim, recheck_authority=self.fresh_authority)
        stored = self.stored(run)
        self.assertEqual((stored[0]["state"], stored[1]), ("completed", 1))
        return patient, question, prepared, key, run, completed["result_sha256"], stored

    def queue_at_parent(self, owner, patient, question, prepared, key):
        return owner.enqueue(
            patient, CASE, question, **history.COMMON, request_key=key,
            source_snapshot_contract=prepared["source_snapshot_contract"],
            expected_source_snapshot_sha256=prepared["source_snapshot_sha256"],
            expected_preflight_sha256=prepared["preflight_sha256"],
            recheck_authority=self.fresh_authority,
        )["run"]["run_id"]

    def test_populated_composer_parent_retains_completed_result_retry_and_new_clinical_write(self):
        patient, question, prepared, key, run, digest, stored = self.seed_completed()
        self.join(COMPOSER)
        note = self.seed_encounter(patient)
        with running_server(create_app(self.settings)) as base:
            self.check_note(base, *note)
            self.assertEqual(self.assert_result(base, patient, question, run, prepared), digest)
            code, retry, _ = self.enqueue(base, patient, question, prepared, key)
            self.assertEqual((code, retry["duplicate"], retry["run"]["run_id"]), (200, True, run))
            self.creds[0]["actions"].remove("source_brief_export")
            self.write()
            code, denied, _ = self.status(base, patient, question, run, "/result")
            self.assertIn(code, (403, 404))
            self.assertEqual(set(denied), {"detail"})
            self.assertEqual(request(base, note[0], token=TOKEN_A)[0], 200)
        self.assertEqual(self.stored(run), stored)

    def test_populated_delivery_and_clinical_heads_resume_events_after_laboratory_import(self):
        from oi_api.event_worker import run_once

        patient, question, prepared, key, run, _, stored = self.seed_completed()
        migrate(self.admin, "upgrade", EVENT)
        self.assertEqual(self.heads(), {EVENT})
        with self.services() as registry:
            owner = PostgresComposerRuns(registry)
            pending = self.queue_at_parent(owner, patient, question, prepared, "JOIN-PENDING")
            delivery = owner.source_events()
            claimed = delivery.claim_next(patient, CASE, **history.COMMON,
                                          recheck_authority=self.fresh_authority)
            self.assertIsNotNone(claimed)
            # The backfilled source is current. Commit a real consumer receipt
            # on the published delivery schema before introducing the sibling.
            initial = delivery.deliver(claimed, recheck_authority=self.fresh_authority)
            self.assertEqual((initial["status"], initial["invalidated_count"]), ("delivered", 0))
        migrate(self.admin, "upgrade", CLINICAL)
        self.seed_lab(patient)
        note = self.seed_encounter(patient)
        self.join(EVENT, CLINICAL)
        outcome = run_once(self.settings, lambda: TOKEN_A, patient, CASE)
        self.assertEqual((outcome["status"], outcome["invalidated_count"]), ("delivered", 1))
        self.assertEqual(run_once(self.settings, lambda: TOKEN_A, patient, CASE)["status"], "idle")
        self.assertEqual(self.stored(pending)[0]["state"], "stale")
        with running_server(create_app(self.settings)) as base:
            self.check_note(base, *note)
            code, retry, _ = self.enqueue(base, patient, question, prepared, key)
            self.assertEqual((code, retry["duplicate"], retry["run"]["run_id"]), (200, True, run))
            code, withheld, _ = self.status(base, patient, question, run, "/result")
            self.assertEqual((code, set(withheld)), (409, {"detail"}))
            self.assertEqual(self.work(patient)["status"], "idle")
        self.assertEqual(self.stored(run), stored)

    def test_populated_clinical_parent_restores_exact_citation_source_run_and_event_receipts(self):
        from oi_api.event_worker import run_once

        patient, url, command, receipt = self.seed_citation()
        migrate(self.admin, "upgrade", CLINICAL)
        note = self.seed_encounter(patient)
        self.join(CLINICAL)
        self.creds[0]["actions"].append("source_brief_export")
        self.write()
        # The lab observation cannot be passed off as a text anchor for the
        # source-only worker. Use the independently saved text source and take
        # a fresh preflight against this same patient's now populated case.
        with self.engine.connect() as conn:
            source = conn.execute(text(
                "SELECT source_id FROM investigation.source_questions "
                "WHERE patient_id=:patient AND case_id=:case AND source_line IS NOT NULL"
            ), {"patient": patient, "case": CASE}).scalar_one()
        with running_server(create_app(self.settings)) as base:
            self.check_note(base, *note)
            self.check_citation(base, url, command, receipt)
            _, page, _ = request(base, url, token=TOKEN_A)
            self.assertEqual(page["question_anchor"]["observation_reference"], OBS)
            self.assertEqual(page["question_anchor"]["preflight_sha256"], command["expected_preflight_sha256"])
            row, = page["links"]
            record = row["record"]
            self.assertEqual((record["citation"], record["metadata_sha256"]),
                             (command["citation"], command["expected_metadata_sha256"]))
            prepared = self.prepared(base, patient, source)
            code, saved, _ = self.save(base, patient, prepared, request_key="JOIN-TEXT-QUESTION")
            self.assertEqual(code, 201, saved)
            question = saved["question_id"]
            code, queued, _ = self.enqueue(base, patient, question, prepared)
            self.assertEqual(code, 201, queued)
            run = queued["run"]["run_id"]
            self.assertEqual(self.work(patient)["status"], "completed")
            digest = self.assert_result(base, patient, question, run, prepared)
        # The source-text and laboratory imports have two independent journal
        # identities. A worker must acknowledge both before the joint backup.
        for _ in range(2):
            result = run_once(self.settings, lambda: TOKEN_A, patient, CASE)
            self.assertEqual((result["status"], result["invalidated_count"]), ("delivered", 0))
        self.assertEqual(run_once(self.settings, lambda: TOKEN_A, patient, CASE)["status"], "idle")
        with self.restored_database():
            with running_server(create_app(self.settings)) as base:
                self.check_citation(base, url, command, receipt)
                self.check_note(base, *note)
                code, retry, _ = self.enqueue(base, patient, question, prepared)
                self.assertEqual((code, retry["duplicate"], retry["run"]["run_id"]), (200, True, run))
                self.assertEqual(self.assert_result(base, patient, question, run, prepared), digest)
                self.assertEqual(run_once(self.settings, lambda: TOKEN_A, patient, CASE)["status"], "idle")
                # Revoke only the restored catalog record; its exact replay
                # must withhold the record while the source-only result survives.
                with self.services() as registry:
                    append_rights_decision(registry, record["id"], record["version"], permissions={},
                                           revoked=True, superseded=False, recorded_by="JOIN-REVIEWER",
                                           reason="Synthetic catalog permission withdrawn after restore.")
                code, masked, _ = request(base, url, token=TOKEN_A)
                self.assertEqual(code, 200, masked)
                self.assertEqual(masked["links"], [{**row, "record": None, "status": "rights_restricted"}])
                code, denied, _ = request(base, url, token=TOKEN_A, body={"synthetic": True, **command})
                self.assertEqual((code, set(denied)), (404, {"detail"}))
                self.assertEqual(self.assert_result(base, patient, question, run, prepared), digest)
                self.assertEqual(self.work(patient)["status"], "idle")
