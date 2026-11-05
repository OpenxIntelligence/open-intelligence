"""First-party task lifecycle checks and actual PostgreSQL persistence acceptance.

The local pure checks do not emulate PostgreSQL. Database tests inherit the
existing explicit disposable-PG16 gate and are never counted as local passes.
"""
from concurrent.futures import ThreadPoolExecutor
import base64
from contextlib import contextmanager
from copy import deepcopy
from datetime import date, datetime, timezone
import importlib
import importlib.util
from pathlib import Path
import unittest

from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from pydantic import ValidationError

from open_intelligence.patient_registry import (
    PatientRegistryConflict, PatientRegistryDenied, PatientRegistryError,
)
from open_intelligence.postgres_registry import PostgresPatientRegistry
from oi_api.app import create_app
from oi_api.contracts import SCHEMA_REVISION
from oi_api.reviewed_documents import fingerprint
from test_reviewed_documents import RAW
from oi_api.followthrough_contracts import ManualTaskDependency
from oi_api.composer_preflight import SOURCE_SNAPSHOT_CONTRACT
from oi_api.migrate import migrate
from http_support import running_server
from test_canonical_review_flow import create_question
from test_patients import TOKEN_A, request
from test_source_versions import SourceVersionFixture, AMENDED


TASK = "TASK-" + "A" * 32
QUESTION = "QUESTION-" + "B" * 32
SOURCE = "SRC-" + "C" * 32
PATIENT = "PATIENT-FICTIONAL"
CASE = "CASE-ALPHA"
WHEN = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)


def owner_module(test):
    test.assertIsNotNone(importlib.util.find_spec("oi_api.question_followthrough"),
                         "H1 has no persisted question follow-through owner")
    return importlib.import_module("oi_api.question_followthrough")


def authored_rows():
    task = {
        "task_id": TASK, "question_id": QUESTION, "patient_id": PATIENT,
        "case_id": CASE, "origin_org": "ORG-ALPHA", "actor": "ACTOR-ALPHA",
        "purpose": "operations", "title": "Prepare the fictional review packet",
        "detail": "Collect the existing source references.", "initial_owner_label": "",
        "due_date": date(2026, 11, 4), "review_trigger": "When another source arrives",
        "created_at": WHEN, "source_id": SOURCE, "source_line": 8,
        "source_sha256": "1" * 64, "source_version": 1,
        "source_snapshot_contract": SOURCE_SNAPSHOT_CONTRACT,
        "source_snapshot_sha256": "2" * 64, "preflight_sha256": "3" * 64,
    }
    question = {name: task[name] for name in (
        "question_id", "patient_id", "case_id", "source_id", "source_line",
        "source_sha256", "source_version", "source_snapshot_contract",
        "source_snapshot_sha256", "preflight_sha256",
    )}
    question["source_context_state"] = "current_unreviewed_question"
    events = [{
        "event_id": "TASK-EVENT-" + "D" * 32, "task_id": TASK,
        "patient_id": PATIENT, "case_id": CASE, "origin_org": "ORG-ALPHA",
        "revision": 1, "previous_status": None, "status": "created",
        "owner_label": "", "actor_label": "ACTOR-ALPHA", "purpose": "operations",
        "reason": "Created for the fictional discussion.", "recorded_at": WHEN,
    }]
    return task, events, question


class ManualTaskDependencyContractTests(unittest.TestCase):
    """Contract-only: no task/Review persistence or action grant is implied."""

    def test_explicit_dependency_has_exact_scoped_versioned_identity(self):
        fields=dict(patient_id=PATIENT,case_id=CASE,question_id=QUESTION,
                    revision_id="PASSAGES-"+"E"*32,references_sha256="a"*64)
        value=ManualTaskDependency(**fields)
        self.assertEqual(value.model_dump(mode="json"),fields)
        self.assertNotIn("quote",value.model_dump())
        with self.assertRaises((TypeError,ValueError)):
            value.revision_id="PASSAGES-"+"F"*32

    def test_missing_forged_or_unstructured_dependency_is_rejected(self):
        fields=dict(patient_id=PATIENT,case_id=CASE,question_id=QUESTION,
                    revision_id="PASSAGES-"+"E"*32,references_sha256="a"*64)
        for change in (
            dict(patient_id=""),dict(case_id=""),dict(question_id="QUESTION-WRONG"),
            dict(revision_id="PASSAGES-INVALID"),
            dict(references_sha256="a"*63),
            dict(references_sha256=True),
            dict(quote="A fictional private passage"),
            dict(clinical_approval=True),
        ):
            with self.subTest(change=change),self.assertRaises(ValidationError):
                ManualTaskDependency(**(fields|change))
        for name in fields:
            with self.subTest(missing=name),self.assertRaises(ValidationError):
                ManualTaskDependency(**{k:v for k,v in fields.items() if k!=name})


class FollowthroughLogicTests(unittest.TestCase):
    def test_creation_requires_visible_bounded_text_and_a_revisit_basis(self):
        owner = owner_module(self)
        fields = dict(title="Prepare notes", detail="", owner_label="", due_date="2026-11-04",
                      review_trigger="", reason="Recorded for review.")
        self.assertEqual(owner._creation_fields(**fields), fields)
        for change in (
            {"title": "ab"}, {"title": "x" * 161}, {"title": " Prepare notes"},
            {"title": "Record\nFORGED"}, {"detail": "x" * 2001},
            {"detail": "Line\u2028break"}, {"owner_label": "Owner\u202e"},
            {"review_trigger": "When\x00changed"}, {"reason": "ab"},
            {"reason": "Prescribe tablets"}, {"due_date": "2026-02-30"},
            {"due_date": None, "review_trigger": ""}, {"due_date": True},
        ):
            with self.subTest(change=change), self.assertRaises(PatientRegistryError):
                owner._creation_fields(**{**fields, **change})

    def test_transition_input_cannot_hide_owner_changes_or_boolean_revisions(self):
        owner = owner_module(self)
        fields = dict(expected_revision=1, status="assigned", owner_label="Fictional Owner",
                      reason="Recorded assignment.")
        self.assertEqual(owner._transition_fields(**fields), fields)
        for change in (
            {"expected_revision": True}, {"expected_revision": 0},
            {"status": "approved"}, {"owner_label": ""},
            {"status": "acknowledged", "owner_label": "Changed Owner"},
            {"reason": "reason\rforged"},
        ):
            with self.subTest(change=change), self.assertRaises(PatientRegistryError):
                owner._transition_fields(**{**fields, **change})

    def test_projection_uses_canonical_freshness_and_preserves_original_anchor(self):
        owner = owner_module(self)
        task, events, question = authored_rows()
        before = deepcopy((task, events, question))
        current = owner._project_task(task, events, question, "2026-11-03")
        self.assertTrue(current["is_due_soon"])
        self.assertFalse(current["is_overdue"])
        self.assertFalse(current["needs_recheck"])
        self.assertFalse(current["clinical_approval"])
        question["source_context_state"] = "source_reassessment_required"
        stale = owner._project_task(task, events, question, "2026-11-05")
        self.assertTrue(stale["is_overdue"])
        self.assertTrue(stale["needs_recheck"])
        self.assertEqual(stale["source_id"], SOURCE)
        self.assertEqual(stale["source_version"], 1)
        self.assertEqual(stale["source_sha256"], "1" * 64)
        self.assertEqual(stale["revision"], 1)
        self.assertEqual((task, events), before[:2])

    def test_completed_and_deferred_work_stays_history_after_source_change(self):
        owner = owner_module(self)
        for terminal, path in (
            ("deferred", ("deferred",)),
            ("completed", ("assigned", "acknowledged", "completed")),
        ):
            with self.subTest(status=terminal):
                task, events, question = authored_rows()
                for number, status in enumerate(path, 2):
                    events.append({**events[-1], "event_id": "TASK-EVENT-" + f"{number:032X}",
                                   "revision": number, "previous_status": events[-1]["status"],
                                   "status": status,
                                   "owner_label": "Fictional Owner" if terminal == "completed" else ""})
                question["source_context_state"] = "source_reassessment_required"
                item = owner._project_task(task, events, question, "2026-11-05")
                self.assertEqual(item["status"], terminal)
                self.assertFalse(item["needs_recheck"])
                self.assertFalse(item["is_overdue"])
                self.assertFalse(item["is_due_soon"])
                self.assertEqual(len(item["history"]), len(events))
                self.assertEqual(item["source_context_state"], "source_reassessment_required")

    def test_projection_rejects_scope_retargeting_and_invalid_history(self):
        owner = owner_module(self)
        task, events, question = authored_rows()
        for field, changed in (("source_id", "SRC-" + "F" * 32),
                               ("source_sha256", "0" * 64), ("case_id", "CASE-BETA")):
            with self.subTest(field=field), self.assertRaises(PatientRegistryError):
                owner._project_task(task, events, {**question, field: changed}, "2026-11-03")
        for change in ({"revision": 2}, {"status": "completed"},
                       {"actor_label": "ACTOR\nFORGED"}, {"patient_id": "OTHER-PATIENT"}):
            with self.subTest(change=change), self.assertRaises(PatientRegistryError):
                owner._project_task(task, [{**events[0], **change}], question, "2026-11-03")

    def test_missing_independent_grants_fail_before_any_database_access(self):
        owner = owner_module(self)

        class UnreachableDatabase:
            autocommit = False

            def cursor(self):
                raise AssertionError("Denied service call touched the database")

        actions = {"patient_read", "question_read", "source_read", "followthrough_read"}
        for missing in actions:
            with self.subTest(missing=missing):
                registry = PostgresPatientRegistry(
                    UnreachableDatabase(), authorizer=lambda a, p, action, purpose: action != missing)
                with self.assertRaises(PatientRegistryDenied):
                    owner.PostgresQuestionFollowthrough(registry).list(
                        PATIENT, CASE, organization="ORG-ALPHA", actor="ACTOR-ALPHA",
                        purpose="operations", recheck_authority=lambda: None)


class FollowthroughMigrationGraphTests(unittest.TestCase):
    def test_task_migration_extends_the_published_single_head(self):
        config = Config()
        config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
        script = ScriptDirectory.from_config(config)
        self.assertEqual(script.get_heads(), [SCHEMA_REVISION])
        self.assertEqual(script.get_revision("0010_question_evidence").down_revision,
                         "0009_question_followthrough")
        self.assertEqual(script.get_revision("0009_question_followthrough").down_revision,
                         "0008_review_convergence")


class FollowthroughPostgresTests(SourceVersionFixture):
    """Actual SQL constraints, transactions and concurrency; no database double."""

    def setUp(self):
        super().setUp()
        self.creds[0]["actions"].extend(("composer_context_read", "question_create", "question_read"))
        self.write()
        self.allowed = {"patient_read", "question_read", "source_read",
                        "followthrough_read", "followthrough_create", "followthrough_update"}
        with running_server(create_app(self.settings)) as base:
            self.patient = self.setup_case(base)
            code, source, _ = self.ingest(base, self.patient)
            self.assertEqual(code, 201, source)
            self.source_id = source["source_id"]
            self.question, snapshot = create_question(self, base, self.patient, self.source_id)
            code, questions, _ = request(
                base, f"/v1/patients/{self.patient}/cases/{CASE}/questions", token=TOKEN_A)
            self.assertEqual(code, 200, questions)
            saved = [row for row in questions["questions"] if row["question_id"] == self.question]
            self.assertEqual(len(saved), 1, questions)
            self.preflight = saved[0]
            self.assertEqual(self.preflight["source_snapshot_sha256"], snapshot)

    @contextmanager
    def service(self):
        connection = self.engine.raw_connection()
        try:
            registry = PostgresPatientRegistry(connection,
                authorizer=lambda actor, patient, action, purpose: (
                    actor == "ACTOR-ALPHA" and patient == self.patient
                    and action in self.allowed and purpose == "operations"))
            yield owner_module(self).PostgresQuestionFollowthrough(registry)
        finally:
            connection.close()

    def create_task(self, *, key="TASK-CREATE-ONE", **overrides):
        values = dict(organization="ORG-ALPHA", actor="ACTOR-ALPHA", purpose="operations",
                      request_key=key, title="Prepare the fictional source packet", detail="",
                      owner_label="", due_date="2026-11-04", review_trigger="",
                      reason="Recorded for the next fictional discussion.",
                      source_snapshot_contract=SOURCE_SNAPSHOT_CONTRACT,
                      expected_source_snapshot_sha256=self.preflight["source_snapshot_sha256"],
                      expected_preflight_sha256=self.preflight["preflight_sha256"],
                      recheck_authority=lambda: None)
        values.update(overrides)
        with self.service() as service:
            return service.create(self.patient, CASE, self.question, **values)

    def transition(self, task, revision, status, *, key=None, **overrides):
        values = dict(organization="ORG-ALPHA", actor="ACTOR-ALPHA", purpose="operations",
                      request_key=key or f"TASK-TRANSITION-{revision}", expected_revision=revision,
                      status=status, owner_label="Fictional Owner" if status == "assigned" else "",
                      reason=f"Recorded the {status} state for fictional work.",
                      recheck_authority=lambda: None)
        values.update(overrides)
        with self.service() as service:
            return service.transition(self.patient, CASE, task, **values)

    def listing(self, **overrides):
        values = dict(organization="ORG-ALPHA", actor="ACTOR-ALPHA", purpose="operations",
                      recheck_authority=lambda: None, evaluated_on="2026-11-05")
        values.update(overrides)
        with self.service() as service:
            return service.list(self.patient, CASE, **values)

    def rows(self):
        with self.engine.connect() as connection:
            return tuple(connection.execute(text(f"SELECT * FROM {table} ORDER BY 1")).all()
                         for table in ("coordination.question_followthrough_tasks",
                                       "coordination.question_followthrough_events",
                                       "investigation.source_questions", "identity.identity_domain_events"))

    def test_lifecycle_exact_retries_and_restart_keep_immutable_receipts(self):
        created = self.create_task()
        self.assertEqual(created["revision"], 1)
        self.assertFalse(created["duplicate"])
        self.assertEqual(self.create_task(), {**created, "duplicate": True})
        for revision, status in ((1, "assigned"), (2, "acknowledged"), (3, "completed")):
            receipt = self.transition(created["task_id"], revision, status)
            self.assertEqual(receipt["revision"], revision + 1)
            self.assertEqual(self.transition(created["task_id"], revision, status),
                             {**receipt, "duplicate": True})
        reopened = self.listing()["tasks"][0]
        self.assertEqual(reopened["status"], "completed")
        self.assertEqual(reopened["revision"], 4)
        self.assertEqual([row["status"] for row in reopened["history"]],
                         ["created", "assigned", "acknowledged", "completed"])
        self.assertEqual(reopened["source_id"], self.source_id)
        self.assertEqual(reopened["source_line"], 8)
        self.assertEqual(reopened["owner_label"], "Fictional Owner")
        before = self.rows()
        with self.assertRaises(PatientRegistryConflict):
            self.transition(created["task_id"], 4, "assigned", key="REOPEN-COMPLETED")
        self.assertEqual(self.rows(), before)

    def test_optional_manual_dependency_storage_is_scoped_and_immutable(self):
        # No dependency row is implicitly created for a source-only task.
        task = self.create_task(key="SOURCE-ONLY-TASK")
        table = "coordination.question_followthrough_manual_dependencies"
        with self.engine.connect() as db:
            self.assertEqual(db.execute(text("SELECT count(*) FROM " + table)).scalar_one(), 0)
        with running_server(create_app(self.settings)) as base:
            docs = self.url(self.patient).removesuffix("/sources") + "/documents"
            payload = dict(synthetic=True,filename="fictional.txt",
                           original_base64=base64.b64encode(RAW).decode())
            status,preview,_ = request(base,docs+"/preview",token=TOKEN_A,body=payload)
            self.assertEqual(status,200,preview)
            payload.update(confirmed_case_id=CASE,expected_sha256=preview["sha256"],
                metadata=dict(document_id="DOC-DEPENDENCY",kind="pathology",
                              event_date="2026-01-10",issued_at="2026-01-11",
                              manual_transcription_confirmed=True),
                findings=[dict(key="marker",state="pending",quote="Marker pending.",line=2)])
            status,doc,_=request(base,docs,token=TOKEN_A,body=payload)
            self.assertEqual(status,201,doc)
            select=docs+"/"+doc["source_id"]+"/selections/"+doc["annotation_revision_id"]+"/marker"
            status,selection,_=request(base,select,token=TOKEN_A)
            self.assertEqual(status,200,selection)
            ref=dict(source_id=doc["source_id"],annotation_revision_id=doc["annotation_revision_id"],
                     selection_key="marker",anchor_sha256=selection["anchor_sha256"])
            manual=f"/v1/patients/{self.patient}/cases/{CASE}/questions/{self.question}/manual-passages"
            status,current,_=request(base,manual,token=TOKEN_A)
            self.assertEqual(status,200,current)
            status,saved,_=request(base,manual,token=TOKEN_A,body=dict(
                synthetic=True,request_key="TASK-MANUAL-DEPENDENCY",
                expected_context_sha256=current["context_sha256"],references=[ref]))
            self.assertEqual(status,201,saved)
            second_question,_=create_question(self,base,self.patient,self.source_id,
                request_key="TASK-MANUAL-DEPENDENCY-QUESTION-2")
        values=dict(task_id=task["task_id"],question_id=self.question,
                    revision_id=saved["revision_id"],patient_id=self.patient,
                    case_id=CASE,origin_org="ORG-ALPHA",
                    references_sha256=fingerprint([ref]))
        statement=text("INSERT INTO "+table+" ("+",".join(values)+") VALUES ("+
                       ",".join(":"+key for key in values)+")")
        with self.engine.begin() as db:
            db.execute(statement,values)
        with self.engine.connect() as db:
            row=db.execute(text("SELECT revision_id,references_sha256 FROM "+table),
                           {}).one()
            self.assertEqual(row[0],saved["revision_id"])
            self.assertEqual(row[1],fingerprint([ref]))
        # Scope fixtures: a revision with no references, and a revision owned
        # by a second question, each copied from the saved revision so every
        # other scope conjunct still holds; only the probed conjunct fails.
        # (UPDATE on revisions is immutable, so new rows are inserted.)
        empty_revision="PASSAGES-"+"E"*32
        other_revision="PASSAGES-"+"F"*32
        revision_columns=("revision_id,revision,patient_id,case_id,origin_org,"
            "question_id,request_key,intent_sha256,references_json,command_json,"
            "actor,purpose")
        with self.engine.begin() as db:
            db.execute(text(
                "INSERT INTO investigation.question_passage_revisions ("
                +revision_columns+") SELECT :empty_id,(SELECT coalesce(max(revision),0)+1 FROM "
                "investigation.question_passage_revisions WHERE question_id=:question),"
                "patient_id,case_id,origin_org,question_id,'TASK-MANUAL-DEPENDENCY-EMPTY',"
                "intent_sha256,'[]'::jsonb,command_json,actor,purpose FROM "
                "investigation.question_passage_revisions WHERE revision_id=:saved"),
                {"empty_id":empty_revision,"question":self.question,
                 "saved":saved["revision_id"]})
            db.execute(text(
                "INSERT INTO investigation.question_passage_revisions ("
                +revision_columns+") SELECT :other_id,(SELECT coalesce(max(revision),0)+1 FROM "
                "investigation.question_passage_revisions WHERE question_id=:other),"
                "patient_id,case_id,origin_org,:other,'TASK-MANUAL-DEPENDENCY-OTHER',"
                "intent_sha256,references_json,command_json,actor,purpose FROM "
                "investigation.question_passage_revisions WHERE revision_id=:saved"),
                {"other_id":other_revision,"other":second_question,
                 "saved":saved["revision_id"]})
        for label,change in (
            ("wrong case",dict(case_id="CASE-WRONG")),
            ("wrong patient",dict(patient_id="PATIENT-WRONG")),
            ("wrong origin",dict(origin_org="ORG-BETA")),
            ("empty references",dict(revision_id=empty_revision)),
            ("other question revision",dict(revision_id=other_revision)),
        ):
            with self.subTest(label=label),self.assertRaises(DBAPIError) as caught:
                with self.engine.begin() as db:
                    db.execute(statement,{**values,**change})
            self.assertIn("OI-MANUAL-TASK-DEPENDENCY-SCOPE",str(caught.exception))
        for statement in (
            "UPDATE "+table+" SET references_sha256='"+("f"*64)+"'",
            "DELETE FROM "+table,
        ):
            with self.assertRaises(DBAPIError):
                with self.engine.begin() as db:
                    db.execute(text(statement))
        with self.assertRaises(CommandError):
            migrate(self.admin,"downgrade","0015_manual_report_context")
        with self.engine.connect() as db:
            self.assertEqual(db.execute(text("SELECT count(*) FROM "+table)).scalar_one(),1)

    def test_stale_revision_and_changed_request_intent_cannot_write(self):
        created = self.create_task()
        self.transition(created["task_id"], 1, "assigned")
        before = self.rows()
        for operation in (
            lambda: self.create_task(title="Changed task title"),
            lambda: self.transition(created["task_id"], 1, "deferred", key="STALE-REVISION"),
            lambda: self.transition(created["task_id"], 1, "deferred", key="TASK-TRANSITION-1"),
            lambda: self.transition(created["task_id"], 2, "completed", key="SKIP-ACKNOWLEDGMENT"),
        ):
            with self.assertRaises(PatientRegistryConflict):
                operation()
            self.assertEqual(self.rows(), before)

    def test_amendment_preserves_anchor_and_allows_operational_history_only(self):
        created = self.create_task()
        with running_server(create_app(self.settings)) as base:
            self.assertEqual(self.ingest(base, self.patient, AMENDED)[0], 201)
        self.assertTrue(self.listing()["tasks"][0]["needs_recheck"])
        self.assertEqual(self.create_task(), {**created, "duplicate": True})
        with self.assertRaises(PatientRegistryConflict):
            self.create_task(key="NEW-TASK-STALE-QUESTION")
        self.transition(created["task_id"], 1, "deferred")
        item = self.listing()["tasks"][0]
        self.assertEqual(item["source_id"], self.source_id)
        self.assertEqual(item["source_version"], 1)
        self.assertEqual(item["source_context_state"], "source_reassessment_required")
        self.assertFalse(item["needs_recheck"])
        self.assertFalse(item["is_overdue"])

    def test_prepare_or_final_authority_failure_rolls_back_origin_history_and_journal(self):
        before = self.rows()

        def denied():
            raise PatientRegistryDenied("Withdrawn synthetic grant")

        def broken(_payload):
            raise ValueError("Synthetic encoder failure")

        for override, error in (({"recheck_authority": denied}, PatientRegistryDenied),
                                ({"prepare_response": broken}, ValueError)):
            with self.subTest(kind=list(override)), self.assertRaises(error):
                self.create_task(**override)
            self.assertEqual(self.rows(), before)
        created = self.create_task()
        before = self.rows()
        with self.assertRaises(PatientRegistryDenied):
            self.transition(created["task_id"], 1, "assigned", recheck_authority=denied)
        self.assertEqual(self.rows(), before)

    def test_independent_grant_is_rechecked_after_preparation(self):
        before = self.rows()

        def withdraw(payload):
            self.allowed.remove("followthrough_create")
            return payload

        with self.assertRaises(PatientRegistryDenied):
            self.create_task(prepare_response=withdraw)
        self.assertEqual(self.rows(), before)

    def test_concurrent_retries_and_competing_revisions_have_one_winner(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            receipts = list(pool.map(lambda _: self.create_task(), range(2)))
        self.assertEqual(len({row["task_id"] for row in receipts}), 1)
        self.assertEqual(sorted(row["duplicate"] for row in receipts), [False, True])
        task = receipts[0]["task_id"]

        def compete(status):
            try:
                return self.transition(task, 1, status, key=f"CONCURRENT-{status}")
            except PatientRegistryConflict:
                return "conflict"

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(compete, ("assigned", "deferred")))
        self.assertEqual(outcomes.count("conflict"), 1)
        self.assertEqual(self.listing()["tasks"][0]["revision"], 2)

    def test_database_guards_reject_history_rewrite_delete_and_illegal_insert(self):
        created = self.create_task()
        with self.engine.connect() as connection:
            original = dict(connection.execute(text(
                "SELECT * FROM coordination.question_followthrough_events"
            )).mappings().one())
        before = self.rows()
        statements = (
            "UPDATE coordination.question_followthrough_tasks SET title='Changed title'",
            "DELETE FROM coordination.question_followthrough_tasks",
            "UPDATE coordination.question_followthrough_events SET reason='Changed reason'",
            "DELETE FROM coordination.question_followthrough_events",
            "TRUNCATE coordination.question_followthrough_events",
        )
        for statement in statements:
            with self.subTest(statement=statement), self.assertRaises(DBAPIError):
                with self.engine.begin() as connection:
                    connection.execute(text(statement))
            self.assertEqual(self.rows(), before)
        for change in (
            {"revision": 3, "previous_status": "created", "status": "assigned", "owner_label": "Owner"},
            {"revision": 2, "previous_status": "created", "status": "completed"},
            {"revision": 2, "previous_status": "created", "status": "deferred", "case_id": "CASE-OTHER"},
        ):
            candidate = {**original, **change, "event_id": "TASK-EVENT-" + "F" * 32,
                         "request_key": "DIRECT-SQL-ILLEGAL"}
            columns = list(candidate)
            with self.subTest(change=change), self.assertRaises(DBAPIError):
                with self.engine.begin() as connection:
                    connection.execute(text(
                        "INSERT INTO coordination.question_followthrough_events (" + ",".join(columns) +
                        ") VALUES (" + ",".join(":" + name for name in columns) + ")"
                    ), candidate)
            self.assertEqual(self.rows(), before)

    def test_populated_downgrade_cannot_erase_task_history(self):
        self.create_task()
        before = self.rows()
        with self.assertRaises(CommandError):
            migrate(self.admin, "downgrade", "0008_review_convergence")
        self.assertEqual(self.rows(), before)

    def test_migration_refuses_competing_table_owner_and_preserves_existing_questions(self):
        before_question_rows = self.rows()[2]
        migrate(self.admin, "downgrade", "0008_review_convergence")
        with self.engine.begin() as connection:
            connection.execute(text("CREATE TABLE coordination.question_followthrough_tasks (foreign_owner text)"))
        with self.assertRaises(CommandError):
            migrate(self.admin, "upgrade", "head")
        with self.engine.begin() as connection:
            self.assertIsNone(connection.execute(text(
                "SELECT to_regclass('coordination.question_followthrough_events')"
            )).scalar_one())
            connection.execute(text("DROP TABLE coordination.question_followthrough_tasks"))
        migrate(self.admin, "upgrade", "head")
        self.assertEqual(self.rows()[2], before_question_rows)


if __name__ == "__main__":
    unittest.main()
