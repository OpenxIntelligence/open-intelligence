"""Direct PostgreSQL verification of append-only, source-pinned amendment checks."""
from concurrent.futures import ThreadPoolExecutor
import json
from threading import Barrier
import uuid

from alembic.util.exc import CommandError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from oi_api.contracts import SCHEMA_REVISION
from oi_api.laboratory_fhir_r4 import prepare_laboratory_bundle
from oi_api.laboratory_fhir_store import PostgresLaboratoryFHIR
from oi_api.migrate import migrate
import test_laboratory_followthrough_migration as tasks
from test_durable_laboratory_questions import CASE, OBS, two_observations
from test_evidence_convergence_migrations import OPTIONS
from test_source_versions import SourceVersionFixture

TABLE = 'investigation.laboratory_amendment_reviews'
PREVIOUS = '0029_patient_access'


def identifier():
    return 'VERIFY-' + uuid.uuid4().hex.upper()


class LaboratoryAmendmentReviewMigrationTests(SourceVersionFixture):
    services = tasks.LaboratoryFollowthroughMigrationTests.services
    start_at = tasks.LaboratoryFollowthroughMigrationTests.start_at
    snapshot = tasks.LaboratoryFollowthroughMigrationTests.snapshot
    schema_definition = tasks.LaboratoryFollowthroughMigrationTests.schema_definition
    insert_task = tasks.LaboratoryFollowthroughMigrationTests.insert_task
    event = tasks.LaboratoryFollowthroughMigrationTests.event

    def lab_source(self, patient, value, previous=None, *, document=None, remove_original=False):
        raw = two_observations(value).replace('FICTIONAL-PATIENT-A', 'UPGRADE-SUBJECT')
        if document:
            raw = raw.replace('FICTIONAL-REPORT-A', document)
        if remove_original:
            bundle = json.loads(raw)
            bundle['entry'] = [e for e in bundle['entry'] if e['resource'].get('id') != OBS.split('/')[1]]
            report = next(e['resource'] for e in bundle['entry'] if e['resource']['resourceType']=='DiagnosticReport')
            report['result'] = [r for r in report['result'] if r['reference'] != OBS]
            raw = json.dumps(bundle)
        prepared = prepare_laboratory_bundle(raw.encode(), expected_subject_reference='Patient/UPGRADE-SUBJECT')
        with self.services() as registry:
            return PostgresLaboratoryFHIR(registry).import_bundle(patient, CASE, prepared,
                request_key=identifier(), expected_previous_source_id=previous, **OPTIONS)

    def seed(self):
        patient, text_question, question = tasks.LaboratoryFollowthroughMigrationTests.seed(self)
        migrate(self.admin, 'upgrade', PREVIOUS)
        with self.engine.begin() as db:
            task = self.insert_task(db, question)
            self.event(db, task, 1, None, 'created')
            other_task = self.insert_task(db, question)
            self.event(db, other_task, 1, None, 'created')
            original = db.execute(text(f'SELECT source_id FROM {tasks.TASKS} WHERE task_id=:task'), {'task': task}).scalar_one()
            text_task = db.execute(text(f'SELECT task_id FROM {tasks.TASKS} WHERE question_id=:q'),
                                   {'q': text_question}).scalar_one()
        latest = self.lab_source(patient, 2, original)
        key = identifier()
        request = dict(entry_id=key, request_id=key, task_id=task, question_id=question, patient_id=patient,
            case_id=CASE, origin_org='ORG-ALPHA', actor='ACTOR-REQUESTER', purpose='operations', action='request',
            reason='Please check the fictional transcription.', disposition=None, original_source_id=original,
            latest_source_id=latest['source_id'], latest_sha256=latest['original_sha256'], request_key=key, intent_sha256='a'*64)
        return request, text_task, other_task

    @staticmethod
    def write(db, row):
        db.execute(text(f"INSERT INTO {TABLE} ({','.join(row)}) VALUES ({','.join(':'+k for k in row)})"), row)

    def response(self, request, **changes):
        key = identifier()
        return request | dict(entry_id=key, request_key=key, actor='ACTOR-REVIEWER', action='respond',
            disposition='transcription_checked', reason='Checked against the fictional original.', intent_sha256='b'*64) | changes

    def refused(self, row, marker):
        with self.assertRaisesRegex(DBAPIError, marker), self.engine.begin() as db:
            self.write(db, row)

    def test_populated_upgrade_empty_downgrade_and_forged_history_controls(self):
        request, text_task, other_task = self.seed()
        history, schema = self.snapshot(), self.schema_definition()
        migrate(self.admin, 'upgrade', SCHEMA_REVISION)
        self.assertEqual(self.snapshot(history[0]), history)
        self.assertEqual(self.snapshot()[0][TABLE], [])
        migrate(self.admin, 'downgrade', PREVIOUS)
        self.assertEqual(self.snapshot(), history)
        self.assertEqual(self.schema_definition(), schema)
        migrate(self.admin, 'upgrade', SCHEMA_REVISION)
        other = self.lab_source(request['patient_id'], 3, document='FICTIONAL-OTHER')
        for change, marker in (
            ({'task_id': text_task}, 'TASK-ORIGIN'), ({'question_id': 'QUESTION-'+'D'*32}, 'TASK-ORIGIN'),
            ({'original_source_id': other['source_id']}, 'TASK-ORIGIN'),
            ({'patient_id': 'PAT-'+'D'*32}, 'PATIENT-SCOPE'), ({'case_id': 'CASE-BETA'}, 'CASE-SCOPE'),
            ({'origin_org': 'ORG-BETA'}, 'PATIENT-SCOPE'), ({'purpose': 'research'}, 'CASE-SCOPE'),
            ({'latest_source_id': other['source_id'], 'latest_sha256': other['original_sha256']}, 'SOURCE-LINEAGE'),
            ({'latest_sha256': 'd'*64}, 'SOURCE-LINEAGE'), ({'disposition': 'transcription_checked'}, 'check constraint'),
            ({'request_id': identifier()}, 'check constraint'), ({'actor':' ACTOR-REQUESTER'}, 'check constraint'),
        ):
            with self.subTest(change=change):
                self.refused(request | change, marker)
        with self.engine.connect().execution_options(isolation_level='REPEATABLE READ') as db:
            with self.assertRaisesRegex(DBAPIError, 'READ-COMMITTED-REQUIRED'):
                self.write(db, request)
        with self.engine.begin() as db:
            self.write(db, request)
        new_id = identifier()
        self.refused(request | dict(entry_id=new_id, request_id=new_id, request_key=new_id), 'oi_lab_amendment_one_request')
        self.refused(request | dict(task_id=other_task, entry_id=new_id, request_id=new_id), 'unique constraint')
        for change in (dict(actor=request['actor']), dict(task_id=other_task), dict(request_id=new_id)):
            with self.subTest(change=change):
                self.refused(self.response(request, **change), 'RESPONSE-SCOPE')
        self.refused(self.response(request, disposition=None), 'check constraint')
        self.refused(self.response(request, disposition='clinically_approved'), 'check constraint')
        # Unique indexes and the binding lock give competing independent responses one winner.
        ready = Barrier(2)
        def compete(actor):
            try:
                with self.engine.begin() as db:
                    ready.wait(timeout=5)
                    self.write(db, self.response(request, actor=actor))
                return True
            except DBAPIError as exc:
                self.assertIn('oi_lab_amendment_one_response', str(exc))
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(compete, ('ACTOR-TWO','ACTOR-THREE'))), [False, True])
        preserved = self.snapshot()
        for sql in (f"UPDATE {TABLE} SET reason='Rewrite the record'", f'DELETE FROM {TABLE}', f'TRUNCATE {TABLE}'):
            with self.subTest(sql=sql), self.assertRaisesRegex(DBAPIError, 'HISTORY-IMMUTABLE'), self.engine.begin() as db:
                db.execute(text(sql))
        with self.assertRaisesRegex(CommandError, 'Stored laboratory amendment review history'):
            migrate(self.admin, 'downgrade', PREVIOUS)
        self.assertEqual(self.snapshot(), preserved)
        with self.engine.connect() as db:
            self.assertEqual(db.execute(text('SELECT version_num FROM public.alembic_version')).scalar_one(), SCHEMA_REVISION)

    def test_superseded_request_remains_readable_and_only_new_multi_step_basis_accepts_a_response(self):
        request, _, _ = self.seed()
        migrate(self.admin, 'upgrade', SCHEMA_REVISION)
        with self.engine.begin() as db:
            self.write(db, request)
        new = self.lab_source(request['patient_id'], 3, request['latest_source_id'], remove_original=True)
        key = identifier()
        updated = request | dict(entry_id=key, request_id=key, request_key=key, latest_source_id=new['source_id'],
                                 latest_sha256=new['original_sha256'])
        self.refused(self.response(request), 'SOURCE-LINEAGE')
        self.refused(self.response(updated, request_id=request['entry_id']), 'RESPONSE-SCOPE')
        with self.engine.begin() as db:
            self.write(db, updated)
            self.write(db, self.response(updated))
            self.assertEqual(db.execute(text(f'SELECT latest_source_id FROM {TABLE} WHERE entry_id=:id'),
                {'id':request['entry_id']}).scalar_one(), request['latest_source_id'])
            self.assertEqual(db.execute(text('SELECT count(*) FROM clinical_source.fhir_laboratory_observations '
                'WHERE source_id=:s AND observation_reference=:ref'), {'s':new['source_id'],'ref':OBS}).scalar_one(), 0)
