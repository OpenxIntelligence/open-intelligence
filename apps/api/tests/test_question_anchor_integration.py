"""Pure existing-owner compatibility and refusal tests, not PostgreSQL acceptance."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from open_intelligence.patient_registry import PatientRegistryError
from open_intelligence.postgres_registry import PostgresPatientRegistry
from oi_api import composer_preflight
from oi_api.question_followthrough import _project_task
from oi_api.source_questions import PostgresSourceQuestions
from oi_api.source_world_model import project_source_world_model
from question_anchor_fixtures import (
    compatibility_outputs, question_row, task_rows, text_context, text_preflight,
)


class QuestionAnchorIntegrationTests(unittest.TestCase):
    def test_existing_payloads_and_fingerprints_match_the_frozen_pr503_baseline(self):
        expected = json.loads((Path(__file__).parent / 'fixtures' /
                               'question_anchor_compatibility.json').read_text())
        actual = compatibility_outputs()
        self.assertEqual(set(actual), set(expected))
        for case in expected:
            with self.subTest(case=case):
                self.assertEqual(json.dumps(actual[case], sort_keys=True, ensure_ascii=False),
                                 json.dumps(expected[case], sort_keys=True, ensure_ascii=False))

    def test_question_history_rejects_boolean_or_coerced_line_identity(self):
        world = project_source_world_model(text_context())
        for value in (True, False, 8.0, '8', None, 0):
            row = list(question_row()); row[5] = value
            with self.subTest(line=value), self.assertRaises(PatientRegistryError):
                PostgresSourceQuestions._question_state(tuple(row), world)

    def test_question_history_rejects_coerced_source_version(self):
        world = project_source_world_model(text_context())
        for value in (True, 1.0, '1', None):
            row = list(question_row()); row[7] = value
            with self.subTest(version=value), self.assertRaises(PatientRegistryError):
                PostgresSourceQuestions._question_state(tuple(row), world)

    def test_saved_question_list_uses_the_same_validated_projection(self):
        registry = PostgresPatientRegistry(SimpleNamespace(autocommit=False))
        registry._transaction_active = True  # Pure projection, not database authority proof.
        owner = PostgresSourceQuestions(registry)
        index = text_context()
        expected = json.loads((Path(__file__).parent / 'fixtures' /
                               'question_anchor_compatibility.json').read_text())['question_current']
        with patch.object(registry, '_fetchall', return_value=[question_row()]):
            actual = owner.project_locked(index['patient_id'], index['case_id'],
                                          organization='ORG-ALPHA', source_index=index)
        self.assertEqual(json.dumps(actual, sort_keys=True), json.dumps([expected], sort_keys=True))
        for field_index, value in ((5, True), (5, 8.0), (7, True), (7, '1')):
            row = list(question_row()); row[field_index] = value
            with self.subTest(field_index=field_index, value=value), \
                 patch.object(registry, '_fetchall', return_value=[tuple(row)]), \
                 self.assertRaises(PatientRegistryError):
                owner.project_locked(index['patient_id'], index['case_id'],
                                     organization='ORG-ALPHA', source_index=index)

    def test_followthrough_rejects_malformed_anchors_even_when_both_sides_match(self):
        for field, value in (('source_line', True), ('source_line', 8.0),
                             ('source_version', True), ('source_version', '1'),
                             ('source_line', None)):
            task, history, question = task_rows()
            task[field] = question[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(PatientRegistryError):
                _project_task(task, history, question, '2026-11-05')

    def test_followthrough_refuses_silent_resource_to_text_downgrade(self):
        task, history, question = task_rows()
        task['resource_reference'] = question['resource_reference'] = 'Observation/OTHER'
        with self.assertRaises(PatientRegistryError):
            _project_task(task, history, question, '2026-11-05')

    def test_both_composer_paths_invoke_shared_validation_before_publication(self):
        validator = getattr(composer_preflight, 'anchor_from_preflight', None)
        self.assertTrue(callable(validator), 'Composer has no shared typed anchor validation')
        with patch.object(composer_preflight, 'anchor_from_preflight', wraps=validator) as check:
            compatibility_outputs()
        kinds = [call.args[0]['contract'] for call in check.call_args_list]
        self.assertIn('oi.synthetic-source-composer-preflight/2', kinds)
        self.assertIn('oi.synthetic-laboratory-question-preflight/1', kinds)

    def test_validation_failure_withholds_preparation(self):
        self.assertTrue(callable(getattr(composer_preflight, 'anchor_from_preflight', None)),
                        'Composer has no shared typed anchor validation')
        with patch.object(composer_preflight, 'anchor_from_preflight',
                          side_effect=PatientRegistryError('Fictional invalid anchor')):
            with self.assertRaises(PatientRegistryError):
                text_preflight()

    def test_historical_source_context_is_not_promoted_to_review_or_approval(self):
        row = question_row()
        world = project_source_world_model(text_context())
        current = PostgresSourceQuestions._question_state(row, world)
        changed = PostgresSourceQuestions._question_state(
            row, world | {'snapshot_fingerprint': '0' * 64})
        self.assertEqual(current['source_context_state'], 'current_unreviewed_question')
        self.assertEqual(changed['source_context_state'], 'source_reassessment_required')
        for result in (current, changed):
            self.assertFalse(result['clinical_approval'])
            self.assertFalse(result['model_executed'])
            self.assertEqual(result['source_line'], 8)
            self.assertEqual(result['source_sha256'], 'a' * 64)
        self.assertEqual(row, question_row())
