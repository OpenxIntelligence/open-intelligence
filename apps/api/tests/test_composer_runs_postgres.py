"""Real PG16 and HTTP execution acceptance using independently fictional sources.

Skipped without the disposable PostgreSQL fixture; skips are not acceptance.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import time
import threading
from unittest.mock import patch

from pydantic import ValidationError
from sqlalchemy import text
from oi_api.app import create_app
from oi_api.access import SyntheticFileAuthentication, authenticate_token
from oi_api.database import Database
from oi_api.registry_context import registry_for_principal
from open_intelligence.patient_registry import PatientRegistryConflict, PatientRegistryDenied
from http_support import running_server
import test_patients as patient_fixture
import test_source_versions as source_fixture
import test_question_source_brief_postgres as brief_fixture

TOKEN = patient_fixture.TOKEN_A
CASE = 'CASE-ALPHA'


class ComposerRunsPostgresTests(source_fixture.SourceVersionFixture):
    # Borrow helpers only, avoiding discovery of inherited acceptance methods.
    path = staticmethod(brief_fixture.QuestionSourceBriefPostgresTests.path)
    model_path = staticmethod(brief_fixture.QuestionSourceBriefPostgresTests.model_path)
    world = brief_fixture.QuestionSourceBriefPostgresTests.world
    preflight = brief_fixture.QuestionSourceBriefPostgresTests.preflight
    prepared = brief_fixture.QuestionSourceBriefPostgresTests.prepared
    save = brief_fixture.QuestionSourceBriefPostgresTests.save
    seed = brief_fixture.QuestionSourceBriefPostgresTests.seed
    events = brief_fixture.QuestionSourceBriefPostgresTests.events

    def setUp(self):
        super().setUp()
        self.creds[0]['actions'].extend(('composer_context_read', 'question_create',
                                       'question_read', 'source_brief_export'))
        self.write()

    @staticmethod
    def run_path(patient, question, run=None, suffix=''):
        return (f'/v1/patients/{patient}/cases/{CASE}/questions/{question}/runs'
                + (f'/{run}' if run else '') + suffix)

    def enqueue(self, base, patient, question, preflight, key='RUN-INTENT-ONE', **extra):
        payload = {**brief_fixture.QuestionSourceBriefPostgresTests.brief_intent(preflight),
                   'request_key': key, **extra}
        return patient_fixture.request(base, self.run_path(patient, question), token=TOKEN, body=payload)

    def status(self, base, patient, question, run, suffix='', token=TOKEN):
        return patient_fixture.request(base, self.run_path(patient, question, run, suffix), token=token)

    def cancel(self, base, patient, question, run):
        return patient_fixture.request(base, self.run_path(patient, question, run, '/cancel'),
                                       token=TOKEN, body={'synthetic': True})

    def seeded_run(self, base):
        patient, question, preflight = self.seed(base)
        code, receipt, _ = self.enqueue(base, patient, question, preflight)
        self.assertEqual(code, 201, receipt)
        return patient, question, preflight, receipt['run']['run_id']

    @contextmanager
    def store(self):
        from oi_api.composer_runs import PostgresComposerRuns
        db = Database(self.settings)
        authentication = SyntheticFileAuthentication(str(self.access))
        context = authenticate_token(TOKEN, authentication)
        try:
            with db.registry_connection() as connection:
                yield PostgresComposerRuns(registry_for_principal(connection, context)), context
        finally:
            db.close()

    def fresh_authority(self):
        current = authenticate_token(TOKEN, SyntheticFileAuthentication(str(self.access)))
        if not {'patient_read', 'question_read', 'source_read', 'source_brief_export'} <= current.actions:
            raise PatientRegistryDenied('Synthetic test grant revoked')

    def claim(self, patient, lease=30):
        with self.store() as (store, context):
            return store.claim_next(patient, CASE, organization=context.organization,
                                    actor=context.actor, purpose=context.purpose,
                                    recheck_authority=self.fresh_authority, lease_seconds=lease)

    def complete(self, claim, recheck=None):
        with self.store() as (store, _):
            return store.complete(claim, recheck_authority=recheck or self.fresh_authority)

    def work(self, patient):
        from oi_api.worker import run_once
        result = run_once(self.settings, lambda: TOKEN, patient, CASE)
        self.assertLessEqual(set(result), {'status', 'attempt_count'})
        return result

    def stored(self, run):
        with self.engine.connect() as connection:
            row = connection.execute(text('SELECT * FROM investigation.composer_tool_runs WHERE run_id=:run'),
                                     {'run': run}).mappings().one()
            results = connection.execute(text('SELECT count(*) FROM investigation.composer_tool_run_results WHERE run_id=:run'),
                                         {'run': run}).scalar_one()
            history = connection.execute(text('SELECT revision,state,reason_code FROM investigation.composer_tool_run_events WHERE run_id=:run ORDER BY revision'),
                                         {'run': run}).all()
            return dict(row), results, [tuple(item) for item in history]

    def test_idempotency_changed_intent_unknown_kind_and_restart(self):
        with running_server(create_app(self.settings)) as base:
            patient, question, preflight, run = self.seeded_run(base)
            code, replay, _ = self.enqueue(base, patient, question, preflight)
            self.assertEqual(code, 200, replay)
            self.assertTrue(replay['duplicate'])
            self.assertEqual(replay['run']['run_id'], run)
            before = self.stored(run)
            self.assertEqual(self.enqueue(base, patient, question, preflight,
                                         expected_preflight_sha256='0' * 64)[0], 409)
            self.assertEqual(self.enqueue(base, patient, question, preflight, kind='arbitrary-plugin')[0], 422)
            self.assertEqual(self.stored(run), before)
        with running_server(create_app(self.settings)) as base:
            code, resumed, _ = self.status(base, patient, question, run)
            self.assertEqual((code, resumed['state']), (200, 'queued'))

    def test_concurrent_duplicate_enqueue_has_one_intent(self):
        with running_server(create_app(self.settings)) as base:
            patient, question, preflight = self.seed(base)
            barrier = threading.Barrier(2)
            def enqueue():
                barrier.wait(timeout=10)
                return self.enqueue(base, patient, question, preflight)
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: enqueue(), range(2)))
            self.assertEqual(sorted(r[0] for r in results), [200, 201])
            self.assertEqual(len({r[1]['run']['run_id'] for r in results}), 1)

    def test_lost_enqueue_response_recovers_same_intent_after_source_amendment(self):
        with running_server(create_app(self.settings)) as base:
            patient, question, preflight, run = self.seeded_run(base)
            self.assertEqual(self.ingest(base, patient, source_fixture.AMENDED)[0], 201)
            before = self.stored(run)
            code, recovered, _ = self.enqueue(base, patient, question, preflight)
            self.assertEqual(code, 200, recovered)
            self.assertTrue(recovered['duplicate'])
            self.assertEqual(recovered['run']['run_id'], run)
            self.assertEqual(self.stored(run), before)
            self.assertEqual(self.enqueue(base, patient, question, preflight,
                                         expected_preflight_sha256='0' * 64)[0], 409)

    def test_real_worker_result_digest_restart_and_current_read_grants(self):
        with running_server(create_app(self.settings)) as base:
            patient, question, _, run = self.seeded_run(base)
            self.assertEqual(self.work(patient)['status'], 'completed')
            code, result, headers = self.status(base, patient, question, run, '/result')
            self.assertEqual(code, 200, result)
            self.assertEqual(headers['Cache-Control'], 'no-store')
            brief = result['brief']
            digest = hashlib.sha256(json.dumps(brief, sort_keys=True, ensure_ascii=False,
                                               separators=(',', ':'), allow_nan=False).encode()).hexdigest()
            self.assertEqual(result['result_sha256'], digest)
            self.assertEqual(brief['question']['question_id'], question)
            self.assertFalse(brief['model_executed'])
            self.assertFalse(brief['clinical_approval'])
            self.assertEqual(self.work(patient)['status'], 'idle')
        with running_server(create_app(self.settings)) as base:
            reopened = self.status(base, patient, question, run, '/result')
            self.assertEqual(reopened[0], 200, reopened[1])
            self.assertEqual(reopened[1]['brief'], brief)
            self.creds[0]['actions'].remove('source_brief_export'); self.write()
            denied = self.status(base, patient, question, run, '/result')
            self.assertIn(denied[0], (403, 404))
            self.assertEqual(set(denied[1]), {'detail'})
            self.assertEqual(self.stored(run)[1], 1)

    def test_actor_patient_and_organization_changes_cannot_read_job(self):
        with running_server(create_app(self.settings)) as base:
            patient, question, _, run = self.seeded_run(base)
            original = deepcopy(self.creds[0])
            for field, value in (('actor', 'ACTOR-OTHER'), ('patient_ids', []), ('organization', 'ORG-OTHER')):
                with self.subTest(field=field):
                    self.creds[0] = {**original, field: value}; self.write()
                    code, result, _ = self.status(base, patient, question, run)
                    self.assertIn(code, (403, 404)); self.assertEqual(set(result), {'detail'})
            self.creds[0] = original; self.write()
            self.assertEqual(self.status(base, patient, question, run)[0], 200)

    def test_amendment_before_work_marks_stale_without_result(self):
        with running_server(create_app(self.settings)) as base:
            patient, question, _, run = self.seeded_run(base)
            self.assertEqual(self.ingest(base, patient, source_fixture.AMENDED)[0], 201)
            self.assertEqual(self.work(patient)['status'], 'stale')
            row, count, _ = self.stored(run)
            self.assertEqual((row['state'], count), ('stale', 0))

    def test_amendment_after_claim_withholds_completion(self):
        with running_server(create_app(self.settings)) as base:
            patient, _, _, run = self.seeded_run(base)
            claim = self.claim(patient)
            self.assertIsNotNone(claim)
            self.assertEqual(self.ingest(base, patient, source_fixture.AMENDED)[0], 201)
            with self.assertRaises(PatientRegistryConflict):
                self.complete(claim)
            self.assertEqual(self.stored(run)[1], 0)

    def test_completed_result_is_withheld_after_source_amendment(self):
        with running_server(create_app(self.settings)) as base:
            patient, question, _, run = self.seeded_run(base)
            self.assertEqual(self.work(patient)['status'], 'completed')
            self.assertEqual(self.ingest(base, patient, source_fixture.AMENDED)[0], 201)
            code, body, _ = self.status(base, patient, question, run, '/result')
            self.assertEqual(code, 409); self.assertEqual(set(body), {'detail'})
            self.assertEqual(self.stored(run)[1], 1)

    def test_concurrent_claim_and_expired_lease_fence_old_worker(self):
        with running_server(create_app(self.settings)) as base:
            patient, _, _, run = self.seeded_run(base)
            barrier = threading.Barrier(2)
            def claim():
                barrier.wait(timeout=10)
                return self.claim(patient, 1)
            with ThreadPoolExecutor(max_workers=2) as pool:
                claims = list(pool.map(lambda _: claim(), range(2)))
            self.assertEqual(sum(c is not None for c in claims), 1)
            old = next(c for c in claims if c is not None)
            time.sleep(1.1)
            new = self.claim(patient)
            self.assertIsNotNone(new)
            self.assertNotEqual(new['lease_token'], old['lease_token'])
            self.assertEqual(new['attempt_count'], 2)
            with self.assertRaises(PatientRegistryConflict):
                self.complete(old)
            self.assertEqual(self.stored(run)[1], 0)
            self.complete(new)
            self.assertEqual(self.stored(run)[1], 1)

    def test_cancellation_survives_restart_and_fences_claimed_completion(self):
        with running_server(create_app(self.settings)) as base:
            patient, question, _, run = self.seeded_run(base)
            claim = self.claim(patient)
            code, cancelled, _ = self.cancel(base, patient, question, run)
            self.assertEqual((code, cancelled['state']), (200, 'cancelled'))
            with self.assertRaises(PatientRegistryConflict):
                self.complete(claim)
            self.assertEqual(self.stored(run)[1], 0)
        with running_server(create_app(self.settings)) as base:
            self.assertEqual(self.status(base, patient, question, run)[1]['state'], 'cancelled')
            self.assertEqual(self.work(patient)['status'], 'idle')

    def test_expired_attempts_are_bounded(self):
        with running_server(create_app(self.settings)) as base:
            patient, _, _, run = self.seeded_run(base)
            for attempt in range(1, 4):
                claim = self.claim(patient, 1)
                self.assertIsNotNone(claim)
                self.assertEqual(claim['attempt_count'], attempt)
                time.sleep(1.1)
            self.assertIsNone(self.claim(patient))
            row, count, history = self.stored(run)
            self.assertEqual((row['state'], row['attempt_count'], count), ('failed', 3, 0))
            self.assertEqual(history[-1][2], 'attempts_exhausted')

    def test_final_authority_denial_rolls_back_result_and_events(self):
        with running_server(create_app(self.settings)) as base:
            patient, _, _, run = self.seeded_run(base)
            claim = self.claim(patient)
            before, events = self.stored(run), self.events()
            calls = []
            def revoke_after_preparation():
                calls.append(1)
                self.creds[0]['actions'] = []; self.write()
                self.fresh_authority()
            with self.assertRaises(PatientRegistryDenied):
                self.complete(claim, revoke_after_preparation)
            self.assertTrue(calls)
            self.assertEqual(self.stored(run), before)
            self.assertEqual(self.events(), events)

    def test_audit_failure_rolls_back_completion(self):
        from open_intelligence.postgres_registry import PostgresPatientRegistry
        with running_server(create_app(self.settings)) as base:
            patient, _, _, run = self.seeded_run(base)
            claim = self.claim(patient)
            before, events = self.stored(run), self.events()
            with patch.object(PostgresPatientRegistry, 'append_event', side_effect=RuntimeError('PRIVATE-TEST-ERROR')):
                with self.assertRaises(RuntimeError):
                    self.complete(claim)
            self.assertEqual(self.stored(run), before)
            self.assertEqual(self.events(), events)

    def test_invalid_serialized_brief_rolls_back_result_and_audit(self):
        from oi_api import source_questions
        with running_server(create_app(self.settings)) as base:
            patient, _, _, run = self.seeded_run(base)
            claim = self.claim(patient)
            before, events = self.stored(run), self.events()
            render = source_questions.render_source_brief
            def invalid(*args, **kwargs):
                result = render(*args, **kwargs)
                result['body_sha256'] = '0' * 64
                return result
            with patch.object(source_questions, 'render_source_brief', side_effect=invalid):
                with self.assertRaises(ValidationError):
                    self.complete(claim)
            self.assertEqual(self.stored(run), before)
            self.assertEqual(self.events(), events)

    def test_cancel_completion_race_has_one_durable_winner(self):
        with running_server(create_app(self.settings)) as base:
            patient, question, _, run = self.seeded_run(base)
            claim = self.claim(patient)
            barrier = threading.Barrier(2)
            def complete():
                barrier.wait(timeout=10)
                try:
                    self.complete(claim)
                    return 'completed'
                except PatientRegistryConflict:
                    return 'fenced'
            def cancel():
                barrier.wait(timeout=10)
                return self.cancel(base, patient, question, run)
            with ThreadPoolExecutor(max_workers=2) as pool:
                completed, cancelled = pool.submit(complete), pool.submit(cancel)
                outcome, cancellation = completed.result(timeout=15), cancelled.result(timeout=15)
            self.assertEqual(cancellation[0], 200, cancellation[1])
            row, count, history = self.stored(run)
            self.assertIn(row['state'], ('completed', 'cancelled'))
            self.assertEqual(cancellation[1]['state'], row['state'])
            self.assertEqual(count, int(row['state'] == 'completed'))
            self.assertEqual(outcome, 'completed' if row['state'] == 'completed' else 'fenced')
            self.assertEqual(sum(state in ('completed', 'cancelled') for _, state, _ in history), 1)

    def test_retryable_failure_requeues_without_result(self):
        with running_server(create_app(self.settings)) as base:
            patient, _, _, run = self.seeded_run(base)
            claim = self.claim(patient)
            with self.store() as (store, _):
                self.assertEqual(store.finish_failure(claim, reason_code='retryable_failure'), 'queued')
            row, count, history = self.stored(run)
            self.assertEqual((row['state'], row['attempt_count'], count), ('queued', 1, 0))
            self.assertIsNone(row['lease_token'])
            self.assertEqual(history[-1][2], 'retryable_failure')

    def test_revocation_after_audit_write_rolls_back_prepared_result(self):
        from open_intelligence.postgres_registry import PostgresPatientRegistry
        with running_server(create_app(self.settings)) as base:
            patient, _, _, run = self.seeded_run(base)
            claim = self.claim(patient)
            before, events = self.stored(run), self.events()
            append = PostgresPatientRegistry.append_event
            written = []
            def append_then_revoke(registry, *args, **kwargs):
                append(registry, *args, **kwargs)
                if args[1] == 'source.read_authorized':
                    written.append(True)
                    self.creds[0]['actions'] = []; self.write()
            with patch.object(PostgresPatientRegistry, 'append_event', append_then_revoke):
                with self.assertRaises(PatientRegistryDenied):
                    self.complete(claim)
            self.assertTrue(written)
            self.assertEqual(self.stored(run), before)
            self.assertEqual(self.events(), events)
