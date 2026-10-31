"""OI-021: reviewed option/dependency view over the existing ledger.

All cases are fictional and independently authored. Nothing here asserts
clinical eligibility, safety, or a next step.
"""
import tempfile
import unittest
from pathlib import Path

from open_intelligence import CaseStore, InvalidInput

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / 'examples' / 'synthetic'


def report(name):
    return (SAMPLE / name).read_bytes()


def evidence(name='demo-evidence.txt'):
    return (SAMPLE / name).read_bytes()


class OptionViewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / 'test.sqlite')
        self.store.add_case('CASE-ALPHA', 'Fictional Alpha')
        self.store.add_case('CASE-BETA', 'Fictional Beta')
        self.path = self.store.import_report('CASE-ALPHA', report('alpha-pathology-original.txt'))
        self.img = self.store.import_report('CASE-ALPHA', report('alpha-imaging.txt'))
        self.beta = self.store.import_report('CASE-BETA', report('beta-pathology.txt'))
        self.q = self.store.add_question('CASE-ALPHA', 'What options are discussed in this fictional case?')
        self.q_img = self.store.add_question('CASE-ALPHA', 'What does the imaging report discuss?')
        self.q_beta = self.store.add_question('CASE-BETA', 'What options are discussed in the beta case?')
        self.snap = self.store.create_snapshot(
            'CASE-ALPHA', self.q, 'A human-authored synthetic discussion draft.',
            [self.path['source_id']])
        self.snap_img = self.store.create_snapshot(
            'CASE-ALPHA', self.q_img, 'A human-authored synthetic imaging draft.',
            [self.img['source_id']])
        self.snap_beta = self.store.create_snapshot(
            'CASE-BETA', self.q_beta, 'A human-authored synthetic beta draft.',
            [self.beta['source_id']])

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _option(self, snapshot=None, label='Fictional discussion item A'):
        return self.store.create_option(
            'CASE-ALPHA', snapshot or self.snap, label,
            'A fictional item discussed for planning purposes only.', 'unknown')

    def _view_option(self, option_id, snapshot_id=None):
        view = self.store.option_view('CASE-ALPHA', snapshot_id)
        for option in view['options']:
            if option['id'] == option_id:
                return option
        self.fail(f'option {option_id} not in view')

    def test_as_known_at_replay_without_hindsight(self):
        opt_t0 = self._option()
        self.store.add_option_dependency('CASE-ALPHA', opt_t0, 'source',
                                         source_version_id=self.path['source_id'])
        # Amendment: T0 proposal reopens, a new proposal is made on the new draft.
        amended = self.store.import_report('CASE-ALPHA', report('alpha-pathology-amended.txt'))
        self.assertIn(opt_t0, amended['invalidated_options'])
        q2 = self.store.add_question('CASE-ALPHA', 'What is discussed after the amendment?')
        snap_t1 = self.store.create_snapshot(
            'CASE-ALPHA', q2, 'A human-authored post-amendment discussion draft.',
            [amended['source_id']])
        opt_t1 = self.store.create_option(
            'CASE-ALPHA', snap_t1, 'Fictional discussion item B',
            'A fictional item discussed after the amendment.', 'unknown')
        t0_view = self.store.option_view('CASE-ALPHA', self.snap)
        t1_view = self.store.option_view('CASE-ALPHA', snap_t1)
        self.assertEqual([o['id'] for o in t0_view['options']], [opt_t0])
        self.assertEqual([o['id'] for o in t1_view['options']], [opt_t1])
        # The T0 dependency still points at the original source version.
        self.assertIn('PATH-ALPHA@1', t0_view['options'][0]['dependencies'][0]['target'])
        # Current view keeps both, with T0 awaiting re-review.
        current = {o['id']: o for o in self.store.option_view('CASE-ALPHA')['options']}
        self.assertEqual(current[opt_t0]['review_state'], 'needs_review')
        self.assertEqual(current[opt_t1]['review_state'], 'current')
        self.assertEqual(current[opt_t0]['snapshot_state'], 'stale')

    def test_amendment_invalidates_only_dependent_options(self):
        dependent = self._option()
        self.store.add_option_dependency('CASE-ALPHA', dependent, 'source',
                                         source_version_id=self.path['source_id'])
        independent = self.store.create_option(
            'CASE-ALPHA', self.snap_img, 'Fictional imaging discussion item',
            'A fictional item tied only to the imaging report.', 'unknown')
        self.store.add_option_dependency('CASE-ALPHA', independent, 'source',
                                         source_version_id=self.img['source_id'])
        beta_option = self.store.create_option(
            'CASE-BETA', self.snap_beta, 'Fictional beta discussion item',
            'A fictional item in the independent beta case.', 'unknown')
        self.store.add_option_dependency('CASE-BETA', beta_option, 'source',
                                         source_version_id=self.beta['source_id'])
        result = self.store.import_report('CASE-ALPHA', report('alpha-pathology-amended.txt'))
        self.assertEqual(result['invalidated_options'], [dependent])
        self.assertEqual(self._view_option(dependent)['review_state'], 'needs_review')
        self.assertEqual(self._view_option(independent)['review_state'], 'current')
        beta_view = self.store.option_view('CASE-BETA')
        self.assertEqual(beta_view['options'][0]['review_state'], 'current')

    def test_evidence_withdrawal_invalidates_only_dependent_option(self):
        ev = self.store.import_synthetic_evidence(evidence())
        assessment = self.store.assess_synthetic_evidence(
            'CASE-ALPHA', self.q, ev['evidence_version_id'], 'context', 'limited',
            'A human-authored rationale for this fictional note.')
        dependent = self._option()
        self.store.add_option_dependency('CASE-ALPHA', dependent, 'evidence_assessment',
                                         evidence_assessment_id=assessment)
        independent = self._option(label='Fictional discussion item C')
        result = self.store.withdraw_synthetic_evidence(
            ev['evidence_version_id'], 'Fictional example withdrawn for test purposes.')
        self.assertEqual(result['invalidated_options'], [dependent])
        self.assertEqual(self._view_option(dependent)['review_state'], 'needs_review')
        self.assertEqual(self._view_option(independent)['review_state'], 'current')

    def test_contradicted_option_is_visibly_held_and_cannot_be_approved(self):
        ev = self.store.import_synthetic_evidence(evidence())
        assessment = self.store.assess_synthetic_evidence(
            'CASE-ALPHA', self.q, ev['evidence_version_id'], 'contradicts', 'limited',
            'A human-authored rationale noting a contradiction.')
        option = self._option()
        self.store.add_option_dependency('CASE-ALPHA', option, 'evidence_assessment',
                                         evidence_assessment_id=assessment)
        view = self._view_option(option)
        self.assertEqual(view['derived_epistemic_status'], 'contradicted')
        self.assertEqual(view['display_operational_status'], 'held')
        with self.assertRaisesRegex(InvalidInput, 'cannot be approved'):
            self.store.review_option('CASE-ALPHA', option, 'Synthetic reviewer', 'approve',
                                     'Discussion-only review scope for this item.')
        result = self.store.review_option('CASE-ALPHA', option, 'Synthetic reviewer', 'reject',
                                          'Rejected because the linked note contradicts it.')
        self.assertEqual(result['result'], 'reject')
        self.assertEqual(self._view_option(option)['operational_status'], 'rejected')
        self.assertEqual(len(self._view_option(option)['review_events']), 1)

    def test_unreviewed_approval_after_amendment_then_reconfirm(self):
        option = self._option()
        self.store.add_option_dependency('CASE-ALPHA', option, 'source',
                                         source_version_id=self.path['source_id'])
        self.store.import_report('CASE-ALPHA', report('alpha-pathology-amended.txt'))
        with self.assertRaisesRegex(InvalidInput, 'not current'):
            self.store.review_option('CASE-ALPHA', option, 'Synthetic reviewer', 'approve',
                                     'Discussion-only review scope for this item.')
        q2 = self.store.add_question('CASE-ALPHA', 'What is discussed after the amendment?')
        new_source = self.store.state('CASE-ALPHA')['sources']
        current_path = [s for s in new_source if s['document_id'] == 'PATH-ALPHA' and s['state'] == 'current'][0]
        snap_t1 = self.store.create_snapshot(
            'CASE-ALPHA', q2, 'A human-authored post-amendment discussion draft.',
            [current_path['id']])
        self.store.review_option('CASE-ALPHA', option, 'Synthetic reviewer', 'reconfirm',
                                 'Re-review against the post-amendment draft.', snap_t1)
        view = self._view_option(option)
        self.assertEqual(view['review_state'], 'current')
        self.assertEqual(view['operational_status'], 'proposed')
        self.store.review_option('CASE-ALPHA', option, 'Synthetic reviewer', 'approve',
                                 'Discussion-only review scope for this item.')
        self.assertEqual(self._view_option(option)['operational_status'], 'reviewed')

    def test_potential_discussion_deadline_is_deterministic_and_labelled(self):
        option = self._option()
        task = self.store.add_preparation_task('CASE-ALPHA', option, 'Fictional preparation step',
                                               'Synthetic owner', lead_time_days=14)
        self.store.add_option_dependency('CASE-ALPHA', option, 'preparation_task',
                                         preparation_task_id=task)
        self.store.add_option_dependency(
            'CASE-ALPHA', option, 'source', source_version_id=self.path['source_id'],
            deadline_date='2026-08-01', deadline_basis='sourced',
            anchor='Fictional source window closing note, authored for tests.')
        deadline = self._view_option(option)['potential_discussion_deadline']
        self.assertEqual(deadline['date'], '2026-07-18')
        self.assertEqual(deadline['basis'], 'sourced')
        self.assertIn('not a clinical deadline', deadline['label'])
        # A finished task stops costing lead time.
        self.store.set_preparation_task_status('CASE-ALPHA', task, 'done')
        self.assertEqual(self._view_option(option)['potential_discussion_deadline']['date'], '2026-08-01')

    def test_unknown_deadline_and_unknown_threat_date(self):
        option = self._option()
        self.store.add_option_dependency('CASE-ALPHA', option, 'source',
                                         source_version_id=self.path['source_id'])
        deadline = self._view_option(option)['potential_discussion_deadline']
        self.assertIsNone(deadline['date'])
        self.assertEqual(deadline['basis'], 'unknown')
        threat = self.store.add_optionality_threat(
            'CASE-ALPHA', option, 'expiring_window',
            'A fictional window may close at an unknown date.')
        view = self._view_option(option)
        self.assertEqual(view['threats'][0]['threat_basis'], 'unknown')
        self.assertIsNone(view['threats'][0]['threat_date'])
        # A date without a sourced basis is refused, not silently stored.
        with self.assertRaisesRegex(InvalidInput, 'sourced'):
            self.store.add_option_dependency(
                'CASE-ALPHA', option, 'source', source_version_id=self.path['source_id'],
                deadline_date='2026-08-01', deadline_basis='unknown', anchor='')
        with self.assertRaisesRegex(InvalidInput, 'sourced'):
            self.store.add_optionality_threat(
                'CASE-ALPHA', option, 'other', 'A fictional dated threat.',
                threat_date='2026-08-01', threat_basis='unknown', anchor='')

    def test_no_recommendation_or_order_language_in_outputs(self):
        with self.assertRaisesRegex(InvalidInput, 'recommendation'):
            self.store.create_option('CASE-ALPHA', self.snap, 'Bad item',
                                     'We recommend this fictional item.', 'unknown')
        with self.assertRaisesRegex(InvalidInput, 'eligibility'):
            self.store.create_option('CASE-ALPHA', self.snap, 'Bad item',
                                     'The subject is eligible for this item.', 'unknown')
        option = self._option()
        view = self.store.option_view('CASE-ALPHA')
        self.assertNotIn('recommend', view['disclaimer'].lower())
        self.assertNotIn('prescribe', view['disclaimer'].lower())
        self.assertNotIn('eligible', view['disclaimer'].lower())
        option_view = self._view_option(option)
        self.assertIn('not a clinical deadline', option_view['potential_discussion_deadline']['label'])
        self.assertIn('no clinical eligibility', view['disclaimer'])

    def test_wrong_case_refs_and_stale_snapshot_are_refused(self):
        with self.assertRaisesRegex(InvalidInput, 'not in this case'):
            self.store.create_option('CASE-ALPHA', self.snap_beta, 'Cross-case item',
                                     'A fictional item on the wrong snapshot.', 'unknown')
        option = self._option()
        with self.assertRaisesRegex(InvalidInput, 'not in this case'):
            self.store.add_option_dependency('CASE-ALPHA', option, 'source',
                                             source_version_id=self.beta['source_id'])
        with self.assertRaisesRegex(InvalidInput, 'not in this case'):
            self.store.review_option('CASE-BETA', option, 'Synthetic reviewer', 'approve',
                                     'Discussion-only review scope for this item.')
        self.store.import_report('CASE-ALPHA', report('alpha-pathology-amended.txt'))
        with self.assertRaisesRegex(InvalidInput, 'stale'):
            self.store.create_option('CASE-ALPHA', self.snap, 'Late item',
                                     'A fictional item on a stale snapshot.', 'unknown')

    def test_dependency_cycle_and_terminal_states(self):
        first = self._option()
        second = self._option(label='Fictional discussion item B')
        self.store.add_option_dependency('CASE-ALPHA', first, 'option', depends_on_option_id=second)
        with self.assertRaisesRegex(InvalidInput, 'cycle'):
            self.store.add_option_dependency('CASE-ALPHA', second, 'option', depends_on_option_id=first)
        self.store.review_option('CASE-ALPHA', first, 'Synthetic reviewer', 'withdraw',
                                 'Withdrawn for fictional test purposes.')
        view = self._view_option(first)
        self.assertEqual(view['operational_status'], 'withdrawn')
        self.assertEqual(len(view['review_events']), 1)
        # Withdrawn history stays inspectable; it cannot be approved later.
        with self.assertRaisesRegex(InvalidInput, 'withdrawn'):
            self.store.review_option('CASE-ALPHA', first, 'Synthetic reviewer', 'approve',
                                     'Discussion-only review scope for this item.')
        self.assertEqual(self._view_option(first)['operational_status'], 'withdrawn')
        self.store.review_option('CASE-ALPHA', second, 'Synthetic reviewer', 'expire',
                                 'Fictional window closed in this test.')
        self.assertEqual(self._view_option(second)['operational_status'], 'expired')

    def test_transitive_invalidation_through_option_chain(self):
        base = self._option()
        self.store.add_option_dependency('CASE-ALPHA', base, 'source',
                                         source_version_id=self.path['source_id'])
        follower = self._option(label='Fictional discussion item B')
        self.store.add_option_dependency('CASE-ALPHA', follower, 'option', depends_on_option_id=base)
        result = self.store.import_report('CASE-ALPHA', report('alpha-pathology-amended.txt'))
        self.assertEqual(sorted(result['invalidated_options']), sorted([base, follower]))

    def test_reviewer_actions_record_actor_scope_and_snapshot(self):
        option = self._option()
        self.store.review_option('CASE-ALPHA', option, 'Synthetic reviewer', 'abstain',
                                 'Abstaining on this discussion item for now.')
        event = self._view_option(option)['review_events'][0]
        self.assertEqual(event['reviewer_label'], 'Synthetic reviewer')
        self.assertEqual(event['action'], 'abstain')
        self.assertEqual(event['snapshot_id'], self.snap)
        self.assertIn('Abstaining', event['scope'])
        # Double approval is refused, not silently recorded twice.
        self.store.review_option('CASE-ALPHA', option, 'Synthetic reviewer', 'approve',
                                 'Discussion-only review scope for this item.')
        with self.assertRaisesRegex(InvalidInput, 'already reviewed'):
            self.store.review_option('CASE-ALPHA', option, 'Synthetic reviewer', 'approve',
                                     'Discussion-only review scope for this item.')


if __name__ == '__main__':
    unittest.main()
