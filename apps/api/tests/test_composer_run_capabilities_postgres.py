"""Real PostgreSQL capability/retirement checks; missing DB is not acceptance."""
from dataclasses import replace
from unittest.mock import patch

from sqlalchemy import text
from oi_api.app import create_app
from open_intelligence.patient_registry import PatientRegistryError
from http_support import running_server
import test_source_versions as source_fixture
import test_question_source_brief_postgres as brief_fixture
import test_composer_runs_postgres as run_fixture

CASE = run_fixture.CASE


class ComposerCapabilityPostgresTests(source_fixture.SourceVersionFixture):
    # Reuse the existing independently fictional fixture and its commands, not
    # its test methods or a second source/run owner.
    path = staticmethod(run_fixture.ComposerRunsPostgresTests.path)
    model_path = staticmethod(run_fixture.ComposerRunsPostgresTests.model_path)
    run_path = staticmethod(run_fixture.ComposerRunsPostgresTests.run_path)
    world = run_fixture.ComposerRunsPostgresTests.world
    preflight = run_fixture.ComposerRunsPostgresTests.preflight
    prepared = run_fixture.ComposerRunsPostgresTests.prepared
    save = run_fixture.ComposerRunsPostgresTests.save
    seed = run_fixture.ComposerRunsPostgresTests.seed
    enqueue = run_fixture.ComposerRunsPostgresTests.enqueue
    status = run_fixture.ComposerRunsPostgresTests.status
    seeded_run = run_fixture.ComposerRunsPostgresTests.seeded_run
    store = run_fixture.ComposerRunsPostgresTests.store
    fresh_authority = run_fixture.ComposerRunsPostgresTests.fresh_authority
    claim = run_fixture.ComposerRunsPostgresTests.claim
    complete = run_fixture.ComposerRunsPostgresTests.complete
    work = run_fixture.ComposerRunsPostgresTests.work
    stored = run_fixture.ComposerRunsPostgresTests.stored

    def setUp(self):
        super().setUp()
        self.creds[0]['actions'].extend(('composer_context_read', 'question_create',
                                       'question_read', 'source_brief_export'))
        self.write()

    def test_registered_capability_matches_persisted_run_and_actual_result(self):
        from oi_api.composer_capabilities import COMPOSER_CAPABILITIES
        with running_server(create_app(self.settings)) as base:
            patient, question, _, run = self.seeded_run(base)
            row = self.stored(run)[0]
            capability = COMPOSER_CAPABILITIES.require(row['kind'])
            self.assertEqual(row['source_snapshot_contract'], capability.input_contract)
            self.assertEqual(self.work(patient)['status'], 'completed')
            code, result, _ = self.status(base, patient, question, run, '/result')
            self.assertEqual(code, 200, result)
            self.assertEqual(result['brief']['contract'], capability.output_contract)
            self.assertEqual(result['run']['kind'], 'source-question-brief/1')
            self.assertEqual(self.stored(run)[1], 1)

    def test_disabled_capability_preserves_retry_receipt_and_rejects_new_work(self):
        from oi_api.composer_capabilities import SOURCE_BRIEF_CAPABILITY
        from oi_api.execution_capabilities import CapabilityCatalog
        disabled = CapabilityCatalog([replace(SOURCE_BRIEF_CAPABILITY, enabled=False)])
        with running_server(create_app(self.settings)) as base:
            patient, question, preflight, run = self.seeded_run(base)
            claim = self.claim(patient)
            before = self.stored(run)
            with patch('oi_api.composer_runs.COMPOSER_CAPABILITIES', disabled):
                code, replay, _ = self.enqueue(base, patient, question, preflight)
                self.assertEqual(code, 200, replay)
                self.assertTrue(replay['duplicate'])
                self.assertEqual(replay['run']['run_id'], run)
                with self.assertRaises(PatientRegistryError):
                    self.complete(claim)
                with self.store() as (store, context):
                    intent = brief_fixture.QuestionSourceBriefPostgresTests.brief_intent(preflight)
                    intent.pop('synthetic')
                    with self.assertRaises(PatientRegistryError):
                        store.enqueue(patient, CASE, question, organization=context.organization,
                                      actor=context.actor, purpose=context.purpose,
                                      request_key='DISABLED-NEW-INTENT', **intent,
                                      recheck_authority=self.fresh_authority)
                self.assertEqual(self.stored(run), before)
                with self.engine.connect() as connection:
                    self.assertEqual(connection.execute(text(
                        'SELECT count(*) FROM investigation.composer_tool_runs '
                        "WHERE request_key='DISABLED-NEW-INTENT'")).scalar_one(), 0)

    def test_disabled_capability_retains_history_but_not_revoked_authority(self):
        from oi_api.composer_capabilities import SOURCE_BRIEF_CAPABILITY
        from oi_api.execution_capabilities import CapabilityCatalog
        disabled = CapabilityCatalog([replace(SOURCE_BRIEF_CAPABILITY, enabled=False)])
        with running_server(create_app(self.settings)) as base:
            patient, question, _, run = self.seeded_run(base)
            self.assertEqual(self.work(patient)['status'], 'completed')
            code, original, _ = self.status(base, patient, question, run, '/result')
            self.assertEqual(code, 200, original)
            before = self.stored(run)
            with patch('oi_api.composer_runs.COMPOSER_CAPABILITIES', disabled):
                code, historical, _ = self.status(base, patient, question, run, '/result')
                self.assertEqual(code, 200, historical)
                self.assertEqual(historical['result_sha256'], original['result_sha256'])
                self.assertEqual(historical['brief'], original['brief'])
                self.creds[0]['actions'].remove('source_brief_export'); self.write()
                code, denied, _ = self.status(base, patient, question, run, '/result')
                self.assertIn(code, (403, 404))
                self.assertEqual(set(denied), {'detail'})
                self.assertEqual(self.stored(run), before)
