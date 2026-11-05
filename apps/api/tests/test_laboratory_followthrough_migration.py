"""Exercise real published schemas and direct PostgreSQL task/event writes."""
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
import time
import uuid

from alembic.util.exc import CommandError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from oi_api.composer_preflight import PostgresSourceComposerPreflight
from oi_api.contracts import SCHEMA_REVISION
from oi_api.laboratory_fhir_r4 import prepare_laboratory_bundle
from oi_api.laboratory_fhir_store import PostgresLaboratoryFHIR
from oi_api.laboratory_questions import PostgresLaboratoryQuestions
from oi_api.migrate import migrate
from oi_api.source_world_model import project_source_world_model
from oi_api.sources import PostgresSourceVersions
import test_document_image_convergence as documents
import test_evidence_convergence_migrations as existing
import test_image_report_convergence_migrations as migrations
from test_durable_laboratory_questions import ABSENT, CASE, QUESTION, two_observations
from test_laboratory_fhir_r4 import OBS
from test_source_versions import ORIGINAL, SourceVersionFixture


PREVIOUS = "0022_lab_citation_source_scope"
TASKS = "coordination.question_followthrough_tasks"
EVENTS = "coordination.question_followthrough_events"


class LaboratoryFollowthroughMigrationTests(SourceVersionFixture):
    services = existing.EvidenceConvergenceMigrationTests.services
    start_at = existing.EvidenceConvergenceMigrationTests.start_at
    snapshot = existing.EvidenceConvergenceMigrationTests.snapshot
    schema_definition = migrations.ImageReportConvergenceMigrationTests.schema_definition

    def seed(self):
        patient, text_question, _ = self.start_at(PREVIOUS)
        with self.engine.begin() as db:
            task = self.insert_task(db, text_question, legacy=True)
            self.event(db, task, 1, None, 'created')
        raw = two_observations(0).replace('FICTIONAL-PATIENT-A', 'UPGRADE-SUBJECT').encode()
        prepared = prepare_laboratory_bundle(raw, expected_subject_reference='Patient/UPGRADE-SUBJECT')
        with self.services() as registry:
            source = PostgresLaboratoryFHIR(registry).import_bundle(patient, CASE, prepared,
                request_key='TASK-LAB-SOURCE', expected_previous_source_id=None, **existing.OPTIONS)
            index = PostgresSourceVersions(registry).list(patient, CASE, **existing.OPTIONS)
            fields = dict(source_id=source['source_id'], observation_reference=OBS, question=QUESTION,
                          expected_source_snapshot_sha256=project_source_world_model(index)['snapshot_fingerprint'])
            preview = PostgresSourceComposerPreflight(registry).preview_laboratory(patient, CASE, **fields, **existing.OPTIONS)
            lab = PostgresLaboratoryQuestions(registry).save(patient, CASE, **fields, **existing.OPTIONS,
                expected_preflight_sha256=preview['preflight_sha256'], request_key='TASK-LAB-QUESTION')
        return patient, text_question, lab['question_id']

    def insert_task(self, db, question, *, legacy=False, **changes):
        origin = db.execute(text("""
            SELECT q.question_id,q.patient_id,q.case_id,q.origin_org,q.actor,q.purpose,q.source_id,q.source_line,
                q.source_sha256,q.source_version,q.source_snapshot_contract,q.source_snapshot_sha256,q.preflight_sha256,
                a.observation_reference
            FROM investigation.source_questions q LEFT JOIN investigation.laboratory_question_anchors a USING(question_id)
            WHERE q.question_id=:q
        """), {'q': question}).mappings().one()
        row = dict(origin, task_id='TASK-' + uuid.uuid4().hex.upper(), title='Record fictional follow-up',
                   review_trigger='At the next discussion', initial_owner_label='Fictional Coordinator') | changes
        if legacy:
            del row['observation_reference']
        db.execute(text(f"INSERT INTO {TASKS} ({','.join(row)}) VALUES ({','.join(':'+k for k in row)})"), row)
        return row['task_id']

    def event(self, db, task, revision, prior, status):
        db.execute(text(f"""INSERT INTO {EVENTS}
            (event_id,task_id,patient_id,case_id,origin_org,request_key,intent_sha256,revision,previous_status,
             status,owner_label,actor_label,purpose,reason)
            SELECT :event,task_id,patient_id,case_id,origin_org,:key,:intent,:revision,:prior,:status,
                   initial_owner_label,actor,purpose,'Record fictional work history.' FROM {TASKS} WHERE task_id=:task"""),
            dict(event='TASK-EVENT-' + uuid.uuid4().hex.upper(), key='TASK-REQUEST-' + uuid.uuid4().hex.upper(),
                 intent='c'*64, task=task, revision=revision, prior=prior, status=status))

    def test_round_trip_preserves_text_history_and_populated_lab_refuses_downgrade(self):
        patient, text_q, lab = self.seed()
        previous_schema, history = self.schema_definition(), self.snapshot()
        migrate(self.admin, 'upgrade', SCHEMA_REVISION)
        self.assertEqual(self.snapshot(), history)
        with self.engine.connect() as db:
            self.assertEqual(db.execute(text(f'SELECT source_line,observation_reference FROM {TASKS}')).one(), (8, None))
        migrate(self.admin, 'downgrade', PREVIOUS)
        self.assertEqual(self.schema_definition(), previous_schema)
        self.assertEqual(self.snapshot(), history)
        migrate(self.admin, 'upgrade', SCHEMA_REVISION)
        # The other observation actually exists in this same immutable source.
        for q, change in ((lab, dict(observation_reference=ABSENT)), (lab, dict(observation_reference=None)),
                (lab, dict(source_line=8)), (text_q, dict(observation_reference=OBS)),
                (lab, dict(question_id=text_q)), (lab, dict(source_version=7)),
                (lab, dict(source_sha256='b'*64)), (lab, dict(preflight_sha256='b'*64)),
                (lab, dict(source_id='SRC-'+'F'*32)), (lab, dict(source_snapshot_sha256='b'*64)),
                (lab, dict(patient_id='PAT-'+'F'*32)), (lab, dict(case_id='CASE-OTHER')),
                (lab, dict(origin_org='ORG-OTHER')), (lab, dict(purpose='research'))):
            with self.subTest(change=change), self.assertRaises(DBAPIError), self.engine.begin() as db:
                self.insert_task(db, q, **change)
        self.assertEqual(self.snapshot(), history)
        with self.engine.connect().execution_options(isolation_level='REPEATABLE READ') as db:
            with self.assertRaisesRegex(DBAPIError, 'OI-LAB-FOLLOWTHROUGH-READ-COMMITTED-REQUIRED'):
                self.insert_task(db, lab)
        # A reviewed document and its annotations are outside the structured snapshot.
        documents.DocumentImageConvergenceMigrationTests.seed_document(self, {'patient': patient})
        with self.engine.begin() as db:
            task = self.insert_task(db, lab)
            self.event(db, task, 1, None, 'created')
            self.event(db, task, 2, 'created', 'assigned')
            self.event(db, task, 3, 'assigned', 'acknowledged')
            self.event(db, task, 4, 'acknowledged', 'completed')
        preserved = self.snapshot()
        with self.assertRaisesRegex(CommandError, 'Stored laboratory task history'):
            migrate(self.admin, 'downgrade', PREVIOUS)
        self.assertEqual(self.snapshot(), preserved)
        with self.engine.connect() as db:
            self.assertEqual(db.execute(text('SELECT version_num FROM public.alembic_version')).scalar_one(), SCHEMA_REVISION)

    def test_completion_waits_for_import_and_old_whole_case_snapshot_cannot_create_or_complete(self):
        patient, _, lab = self.seed()
        migrate(self.admin, 'upgrade', SCHEMA_REVISION)
        with self.engine.begin() as db:
            task = self.insert_task(db, lab)
            self.event(db, task, 1, None, 'created')
            self.event(db, task, 2, 'created', 'assigned')
            self.event(db, task, 3, 'assigned', 'acknowledged')
        pid = Queue()
        def complete():
            with self.assertRaisesRegex(DBAPIError, 'OI-LAB-FOLLOWTHROUGH-CASE-SOURCES-CHANGED'), self.engine.begin() as db:
                pid.put(db.execute(text('SELECT pg_backend_pid()')).scalar_one())
                self.event(db, task, 4, 'acknowledged', 'completed')
        with ThreadPoolExecutor(max_workers=1) as pool, self.services() as registry:
            pending = []
            def while_import_holds_binding(result):
                pending.append(pool.submit(complete))
                worker_pid = pid.get(timeout=5)
                with self.engine.connect() as observer:
                    deadline = time.monotonic() + 5
                    while not observer.execute(text('SELECT cardinality(pg_blocking_pids(:pid)) > 0'),
                                               {'pid': worker_pid}).scalar_one():
                        if time.monotonic() >= deadline:
                            self.fail('Task completion did not wait for the case binding lock')
                        time.sleep(0.01)
                return result
            # Independent structured source; the selected lab version is still current.
            raw = ORIGINAL.replace('Document: DOC-ONE', 'Document: DOC-TWO').encode()
            PostgresSourceVersions(registry).import_original(patient, CASE, raw,
                **(existing.OPTIONS | {'prepare_response': while_import_holds_binding}))
            pending[0].result(timeout=5)
        with self.assertRaisesRegex(DBAPIError, 'OI-LAB-FOLLOWTHROUGH-CASE-SOURCES-CHANGED'), self.engine.begin() as db:
            self.insert_task(db, lab)
        with self.engine.begin() as db:
            self.event(db, task, 4, 'acknowledged', 'deferred')
            self.assertEqual(db.execute(text(f'SELECT status FROM {EVENTS} WHERE task_id=:task ORDER BY revision'),
                                        {'task': task}).scalars().all(), ['created', 'assigned', 'acknowledged', 'deferred'])
