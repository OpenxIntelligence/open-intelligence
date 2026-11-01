"""Adversarial checks of existing OI-021 proposal/review boundaries.

Fictional engineering fixtures only. No clinical eligibility or treatment
claim. These tests distinguish current projections from historical evidence.
"""
import tempfile
import unittest
from pathlib import Path

from open_intelligence import CaseStore, InvalidInput

SAMPLES = Path(__file__).resolve().parents[1] / 'examples' / 'synthetic'


class OptionReviewRegressions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / 'regression.sqlite')
        self.store.add_case('CASE-ALPHA', 'Fictional Alpha')
        self.path = self.store.import_report(
            'CASE-ALPHA', (SAMPLES / 'alpha-pathology-original.txt').read_bytes())
        self.image = self.store.import_report(
            'CASE-ALPHA', (SAMPLES / 'alpha-imaging.txt').read_bytes())
        self.question = self.store.add_question(
            'CASE-ALPHA', 'Which fictional discussion records remain supported?')
        self.snapshot = self.store.create_snapshot(
            'CASE-ALPHA', self.question, 'An authored fictional discussion record.',
            [self.path['source_id']])
        self.image_snapshot = self.store.create_snapshot(
            'CASE-ALPHA', self.question, 'An independent fictional imaging record.',
            [self.image['source_id']])

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def option(self, label='Fictional discussion item', epistemic='unknown', snapshot=None):
        return self.store.create_option(
            'CASE-ALPHA', self.snapshot if snapshot is None else snapshot,
            label, 'Original fictional planning discussion, without a clinical action.', epistemic)

    def view(self, option_id):
        return next(o for o in self.store.option_view('CASE-ALPHA')['options']
                    if o['id'] == option_id)

    def review(self, option_id, action, snapshot=None):
        return self.store.review_option(
            'CASE-ALPHA', option_id, 'Fictional reviewer', action,
            'Review of an authored fictional discussion item only.', snapshot)

    def amend(self):
        return self.store.import_report(
            'CASE-ALPHA', (SAMPLES / 'alpha-pathology-amended.txt').read_bytes())

    def test_direct_contradiction_blocks_approval(self):
        option = self.option(epistemic='contradicted')
        self.assertEqual(self.view(option)['display_operational_status'], 'held')
        with self.assertRaises(InvalidInput):
            self.review(option, 'approve')
        self.assertEqual(self.view(option)['operational_status'], 'proposed')
        self.assertEqual(self.view(option)['review_events'], [])

    def test_superseded_source_cannot_be_new_active_dependency(self):
        self.amend()
        option = self.option(snapshot=self.image_snapshot)
        with self.assertRaises(InvalidInput):
            self.store.add_option_dependency(
                'CASE-ALPHA', option, 'source', source_version_id=self.path['source_id'])
        self.assertEqual(self.view(option)['dependencies'], [])

    def test_withdrawn_evidence_cannot_be_new_active_dependency(self):
        evidence = self.store.import_synthetic_evidence(
            (SAMPLES / 'demo-evidence.txt').read_bytes())
        assessment = self.store.assess_synthetic_evidence(
            'CASE-ALPHA', self.question, evidence['evidence_version_id'],
            'context', 'limited', 'An original fictional applicability note.')
        self.store.withdraw_synthetic_evidence(
            evidence['evidence_version_id'], 'Fictional source withdrawn for the test.')
        option = self.option()
        with self.assertRaises(InvalidInput):
            self.store.add_option_dependency(
                'CASE-ALPHA', option, 'evidence_assessment',
                evidence_assessment_id=assessment)
        self.assertEqual(self.view(option)['dependencies'], [])

    def test_dependency_added_after_review_reopens_review(self):
        option = self.option()
        self.review(option, 'approve')
        self.store.add_option_dependency(
            'CASE-ALPHA', option, 'source', source_version_id=self.image['source_id'])
        self.assertEqual(self.view(option)['review_state'], 'needs_review')
        self.assertEqual(len(self.view(option)['review_events']), 1)
        with self.assertRaises(InvalidInput):
            self.review(option, 'approve')

    def test_withdrawing_prerequisite_reopens_only_dependents(self):
        prerequisite = self.option(label='Fictional prerequisite')
        dependent = self.option(label='Fictional dependent')
        unrelated = self.option(label='Fictional independent item')
        self.store.add_option_dependency(
            'CASE-ALPHA', dependent, 'option', depends_on_option_id=prerequisite)
        self.review(dependent, 'approve')
        self.review(unrelated, 'approve')
        self.review(prerequisite, 'withdraw')
        self.assertEqual(self.view(dependent)['review_state'], 'needs_review')
        self.assertEqual(self.view(unrelated)['review_state'], 'current')
        with self.assertRaises(InvalidInput):
            self.review(dependent, 'reconfirm', self.snapshot)

    def test_rejected_option_does_not_reopen_as_proposed_after_amendment(self):
        option = self.option()
        self.review(option, 'reject')
        amendment = self.amend()
        replacement = self.store.create_snapshot(
            'CASE-ALPHA', self.question, 'An authored replacement fictional draft.',
            [amendment['source_id']])
        with self.assertRaises(InvalidInput):
            self.review(option, 'reconfirm', replacement)
        self.assertEqual(self.view(option)['operational_status'], 'rejected')
        self.assertEqual(self.view(option)['review_events'][0]['action'], 'reject')

    def test_original_snapshot_association_survives_reconfirmation(self):
        option = self.option()
        amendment = self.amend()
        replacement = self.store.create_snapshot(
            'CASE-ALPHA', self.question, 'An authored replacement fictional draft.',
            [amendment['source_id']])
        self.review(option, 'reconfirm', replacement)
        old_view = self.store.option_view('CASE-ALPHA', self.snapshot)
        self.assertIn(option, [o['id'] for o in old_view['options']])
        # Association filtering is not a reconstruction of past mutable state.
        self.assertFalse(old_view['historical_replay_supported'])
        self.assertEqual(old_view['snapshot_filter_id'], self.snapshot)
        self.assertIsNone(old_view['as_known_at_snapshot_id'])

    def test_deadline_traverses_longer_shared_dependency_path(self):
        root = self.option(label='Fictional root item')
        middle = self.option(label='Fictional intermediate item')
        shared = self.option(label='Fictional shared dependency')
        # Visit the shorter path first to expose global-visited pruning.
        self.store.add_option_dependency(
            'CASE-ALPHA', root, 'option', depends_on_option_id=shared, lead_time_days=1)
        self.store.add_option_dependency(
            'CASE-ALPHA', root, 'option', depends_on_option_id=middle, lead_time_days=0)
        self.store.add_option_dependency(
            'CASE-ALPHA', middle, 'option', depends_on_option_id=shared, lead_time_days=20)
        self.store.add_option_dependency(
            'CASE-ALPHA', shared, 'source', source_version_id=self.path['source_id'],
            deadline_date='2026-08-01', deadline_basis='sourced',
            anchor='An authored fictional discussion window for testing only.')
        self.assertEqual(self.view(root)['potential_discussion_deadline']['date'], '2026-07-12')

    def test_unknown_preparation_duration_does_not_become_zero(self):
        option = self.option()
        task = self.store.add_preparation_task(
            'CASE-ALPHA', option, 'Fictional preparation step', 'Fictional owner')
        self.store.add_option_dependency(
            'CASE-ALPHA', option, 'preparation_task', preparation_task_id=task)
        self.store.add_option_dependency(
            'CASE-ALPHA', option, 'source', source_version_id=self.path['source_id'],
            deadline_date='2026-08-01', deadline_basis='sourced',
            anchor='An authored fictional discussion window for testing only.')
        deadline = self.view(option)['potential_discussion_deadline']
        self.assertIsNone(deadline['date'])
        self.assertEqual(deadline['basis'], 'unknown')


if __name__ == '__main__':
    unittest.main()
