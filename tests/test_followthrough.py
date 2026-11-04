"""Follow-through tasks: agreed human work with accountability history.

All cases, owners, and notes are fictional and independently authored.
Nothing here performs an action or asserts one was taken: completion is
only a recorded acknowledgment path, and every status change keeps
who/when/why in append-only history.
"""
import tempfile
import unittest
from pathlib import Path

from open_intelligence import CaseStore, InvalidInput
from open_intelligence.followthrough import followthrough_view

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / 'examples' / 'synthetic'


def report(name):
    return (SAMPLE / name).read_bytes()


def task_in(view, task_id):
    for task in view['tasks']:
        if task['id'] == task_id:
            return task
    raise AssertionError(f'task {task_id} not in view')


class FollowthroughTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / 'test.sqlite'
        self.store = CaseStore(self.db_path)
        self.store.add_case('CASE-ALPHA', 'Fictional Alpha')
        self.store.add_case('CASE-BETA', 'Fictional Beta')
        self.alpha_source = self.store.import_report(
            'CASE-ALPHA', report('alpha-pathology-original.txt'))
        self.beta_source = self.store.import_report(
            'CASE-BETA', report('beta-pathology.txt'))
        self.question = self.store.add_question(
            'CASE-ALPHA', 'What follow-up did the fictional team agree on?')

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _create(self, title='Prepare the fictional review notes', **kwargs):
        params = {'actor_label': 'Fictional Recorder', **kwargs}
        return self.store.create_followthrough_task('CASE-ALPHA', title, **params)

    def test_full_lifecycle_preserves_who_when_why(self):
        task_id = self._create(
            detail='Collect the fictional source pages for the next review.',
            due_date='2026-06-10', review_trigger='Revisit at the next fictional review.',
            question_id=self.question, source_version_id=self.alpha_source['source_id'],
            reason='The fictional team agreed to prepare review notes.')
        self.store.update_followthrough_task(
            'CASE-ALPHA', task_id, 'assigned', actor_label='Fictional Coordinator',
            reason='The fictional coordinator takes ownership of the notes.',
            owner_label='Fictional Coordinator')
        self.store.update_followthrough_task(
            'CASE-ALPHA', task_id, 'acknowledged', actor_label='Fictional Coordinator',
            reason='The fictional coordinator confirms they saw this task.')
        outcome = self.store.update_followthrough_task(
            'CASE-ALPHA', task_id, 'completed', actor_label='Fictional Coordinator',
            reason='The fictional review notes were prepared by a human.')
        self.assertEqual(outcome['result'], 'completed')
        self.assertEqual(outcome['previous_status'], 'acknowledged')
        task = task_in(followthrough_view(self.store, 'CASE-ALPHA'), task_id)
        self.assertEqual(task['status'], 'completed')
        self.assertEqual(task['owner_label'], 'Fictional Coordinator')
        self.assertTrue(task['human_action_recorded'])
        path = [(e['previous_status'], e['new_status']) for e in task['history']]
        self.assertEqual(path, [(None, 'created'), ('created', 'assigned'),
                                ('assigned', 'acknowledged'), ('acknowledged', 'completed')])
        for event in task['history']:
            self.assertTrue(event['actor_label'])
            self.assertTrue(event['noted_at'])
        reasons = [e['reason'] for e in task['history']]
        self.assertTrue(all(isinstance(r, str) for r in reasons))
        self.assertIn('coordinator takes ownership', reasons[1])

    def test_completion_requires_a_recorded_acknowledgment(self):
        task_id = self._create()
        with self.assertRaisesRegex(InvalidInput, 'acknowledgment'):
            self.store.update_followthrough_task(
                'CASE-ALPHA', task_id, 'completed', actor_label='Fictional Recorder',
                reason='Attempting to complete a task nobody acknowledged.')
        self.store.update_followthrough_task(
            'CASE-ALPHA', task_id, 'assigned', actor_label='Fictional Recorder',
            reason='Assigning the fictional task to its human owner now.',
            owner_label='Fictional Owner')
        with self.assertRaisesRegex(InvalidInput, 'acknowledgment'):
            self.store.update_followthrough_task(
                'CASE-ALPHA', task_id, 'completed', actor_label='Fictional Owner',
                reason='Attempting to complete before any acknowledgment.')
        task = task_in(followthrough_view(self.store, 'CASE-ALPHA'), task_id)
        self.assertFalse(task['human_action_recorded'])

    def test_deferral_needs_a_reason_and_reopens_only_through_assignment(self):
        task_id = self._create()
        with self.assertRaisesRegex(InvalidInput, '10'):
            self.store.update_followthrough_task(
                'CASE-ALPHA', task_id, 'deferred', actor_label='Fictional Recorder',
                reason='Too soon')
        self.store.update_followthrough_task(
            'CASE-ALPHA', task_id, 'deferred', actor_label='Fictional Recorder',
            reason='Waiting on the next fictional report before proceeding.')
        with self.assertRaisesRegex(InvalidInput, 'Cannot move'):
            self.store.update_followthrough_task(
                'CASE-ALPHA', task_id, 'acknowledged', actor_label='Fictional Owner',
                reason='A deferred task cannot skip straight to acknowledgment.')
        with self.assertRaisesRegex(InvalidInput, 'Owner label'):
            self.store.update_followthrough_task(
                'CASE-ALPHA', task_id, 'assigned', actor_label='Fictional Recorder',
                reason='Reopening the deferred fictional task with an owner.')
        outcome = self.store.update_followthrough_task(
            'CASE-ALPHA', task_id, 'assigned', actor_label='Fictional Recorder',
            reason='Reopening the deferred fictional task with an owner.',
            owner_label='Fictional Owner')
        self.assertEqual(outcome['previous_status'], 'deferred')
        task = task_in(followthrough_view(self.store, 'CASE-ALPHA'), task_id)
        self.assertEqual(task['status'], 'assigned')
        self.assertEqual(len(task['history']), 3)

    def test_completed_tasks_are_terminal_history(self):
        task_id = self._create()
        self.store.update_followthrough_task(
            'CASE-ALPHA', task_id, 'assigned', actor_label='Fictional Recorder',
            reason='Assigning the fictional task to its human owner now.',
            owner_label='Fictional Owner')
        self.store.update_followthrough_task(
            'CASE-ALPHA', task_id, 'acknowledged', actor_label='Fictional Owner',
            reason='The fictional owner confirms they saw this task here.')
        self.store.update_followthrough_task(
            'CASE-ALPHA', task_id, 'completed', actor_label='Fictional Owner',
            reason='The fictional owner finished the agreed human work.')
        for status in ('assigned', 'acknowledged', 'deferred', 'completed'):
            with self.subTest(status=status):
                with self.assertRaisesRegex(InvalidInput, 'history'):
                    self.store.update_followthrough_task(
                        'CASE-ALPHA', task_id, status, actor_label='Fictional Recorder',
                        reason='Attempting to move a completed task somewhere else.',
                        owner_label='Fictional Owner' if status == 'assigned' else None)
        task = task_in(followthrough_view(self.store, 'CASE-ALPHA'), task_id)
        self.assertEqual(task['status'], 'completed')
        self.assertEqual(len(task['history']), 4)

    def test_no_status_change_erases_history(self):
        task_id = self._create(reason='First fictional note on why this exists.')
        before = [dict(e) for e in
                  task_in(followthrough_view(self.store, 'CASE-ALPHA'), task_id)['history']]
        self.store.update_followthrough_task(
            'CASE-ALPHA', task_id, 'assigned', actor_label='Fictional Recorder',
            reason='Assigning the fictional task to its human owner now.',
            owner_label='Fictional Owner')
        self.store.update_followthrough_task(
            'CASE-ALPHA', task_id, 'deferred', actor_label='Fictional Owner',
            reason='The fictional owner defers until the next report arrives.')
        after = task_in(followthrough_view(self.store, 'CASE-ALPHA'), task_id)['history']
        self.assertEqual(len(after), 3)
        self.assertEqual([dict(e) for e in after[:1]], before)
        # History survives a restart: it is durable ledger state, not memory.
        self.store.close()
        self.store = CaseStore(self.db_path)
        reopened = task_in(followthrough_view(self.store, 'CASE-ALPHA'), task_id)['history']
        self.assertEqual([dict(e) for e in reopened], [dict(e) for e in after])

    def test_overdue_and_due_soon_are_derived_and_exclude_finished_work(self):
        overdue = self._create(title='Overdue fictional check', due_date='2026-06-01')
        due_soon = self._create(title='Due-soon fictional check', due_date='2026-06-08')
        boundary = self._create(title='Boundary fictional check', due_date='2026-06-09')
        later = self._create(title='Later fictional check', due_date='2026-06-10')
        undated = self._create(title='Undated fictional check')
        finished = self._create(title='Finished fictional check', due_date='2026-05-01')
        for status, owner in (('assigned', 'Fictional Owner'), ('acknowledged', None),
                              ('completed', None)):
            self.store.update_followthrough_task(
                'CASE-ALPHA', finished, status, actor_label='Fictional Owner',
                reason='Moving the finished fictional task along its path.',
                owner_label=owner)
        deferred = self._create(title='Deferred fictional check', due_date='2026-05-01')
        self.store.update_followthrough_task(
            'CASE-ALPHA', deferred, 'deferred', actor_label='Fictional Recorder',
            reason='Deferring the fictional task with a recorded reason.')
        view = followthrough_view(self.store, 'CASE-ALPHA', today='2026-06-02')
        self.assertEqual(view['today'], '2026-06-02')
        self.assertEqual(view['overdue_task_ids'], [overdue])
        self.assertEqual(view['due_soon_task_ids'], [due_soon, boundary])
        self.assertNotIn(finished, view['overdue_task_ids'])
        self.assertNotIn(deferred, view['overdue_task_ids'])
        self.assertFalse(task_in(view, later)['is_overdue'])
        self.assertFalse(task_in(view, later)['is_due_soon'])
        self.assertFalse(task_in(view, undated)['is_overdue'])
        self.assertFalse(task_in(view, undated)['is_due_soon'])
        self.assertEqual(view['counts']['overdue'], 1)
        self.assertEqual(view['counts']['due_soon'], 2)
        self.assertEqual(view['counts']['completed'], 1)
        self.assertEqual(view['counts']['deferred'], 1)
        # The boundary is inclusive: today + 7 days is due soon, +8 is not.
        self.assertTrue(task_in(view, boundary)['is_due_soon'])
        self.assertFalse(task_in(view, later)['is_due_soon'])

    def test_amendment_flags_the_anchored_task_and_nothing_else(self):
        anchored = self._create(
            title='Anchored fictional check',
            source_version_id=self.alpha_source['source_id'])
        plain = self._create(title='Unanchored fictional check')
        beta_task = self.store.create_followthrough_task(
            'CASE-BETA', 'Beta fictional check', actor_label='Fictional Recorder',
            source_version_id=self.beta_source['source_id'])
        before = len(task_in(
            followthrough_view(self.store, 'CASE-ALPHA'), anchored)['history'])
        update = self.store.import_report(
            'CASE-ALPHA', report('alpha-pathology-amended.txt'))
        self.assertEqual(update['version'], 2)
        view = followthrough_view(self.store, 'CASE-ALPHA')
        flagged = task_in(view, anchored)
        self.assertTrue(flagged['needs_recheck'])
        self.assertEqual(flagged['source_state'], 'superseded')
        self.assertEqual(flagged['status'], 'created')
        # The flag is derived: the amendment appends no task history itself.
        self.assertEqual(len(flagged['history']), before)
        self.assertFalse(task_in(view, plain)['needs_recheck'])
        beta_view = followthrough_view(self.store, 'CASE-BETA')
        self.assertFalse(task_in(beta_view, beta_task)['needs_recheck'])
        self.assertNotIn(beta_task, [t['id'] for t in view['tasks']])

    def test_status_changes_perform_no_action_and_touch_no_other_ledger(self):
        before = self.store.state('CASE-ALPHA')
        task_id = self._create(due_date='2026-06-10')
        self.store.update_followthrough_task(
            'CASE-ALPHA', task_id, 'assigned', actor_label='Fictional Recorder',
            reason='Assigning the fictional task to its human owner now.',
            owner_label='Fictional Owner')
        self.store.update_followthrough_task(
            'CASE-ALPHA', task_id, 'acknowledged', actor_label='Fictional Owner',
            reason='The fictional owner confirms they saw this task here.')
        self.store.update_followthrough_task(
            'CASE-ALPHA', task_id, 'completed', actor_label='Fictional Owner',
            reason='The fictional owner finished the agreed human work.')
        after = self.store.state('CASE-ALPHA')
        for key in ('sources', 'assertions', 'questions', 'snapshots', 'options',
                    'evidence', 'evidence_assessments', 'quarantines'):
            self.assertEqual(after[key], before[key],
                             f'follow-through must not change {key}')
        kinds = [e['kind'] for e in after['events']]
        before_kinds = [e['kind'] for e in before['events']]
        self.assertIn('followthrough_task_created', kinds)
        self.assertIn('followthrough_task_status_changed', kinds)
        self.assertEqual(kinds.count('source_imported'),
                         before_kinds.count('source_imported'),
                         'follow-through must not import or amend sources')

    def test_clinical_language_is_rejected_in_task_text(self):
        with self.assertRaisesRegex(InvalidInput, 'must not state'):
            self._create(title='Recommend the best treatment for this case')
        with self.assertRaisesRegex(InvalidInput, 'must not state'):
            self._create(detail='Prescribe the usual starting dose now.')
        with self.assertRaisesRegex(InvalidInput, 'must not state'):
            self._create(review_trigger='Diagnose the underlying condition first')
        task_id = self._create()
        with self.assertRaisesRegex(InvalidInput, 'must not state'):
            self.store.update_followthrough_task(
                'CASE-ALPHA', task_id, 'assigned', actor_label='Fictional Recorder',
                reason='The owner should receive the new therapy right away.',
                owner_label='Fictional Owner')

    def test_tasks_are_case_scoped(self):
        task_id = self._create()
        beta_view = followthrough_view(self.store, 'CASE-BETA')
        self.assertEqual(beta_view['tasks'], [])
        self.assertEqual(beta_view['counts']['open'], 0)
        with self.assertRaisesRegex(InvalidInput, 'not in this case'):
            self.store.update_followthrough_task(
                'CASE-BETA', task_id, 'assigned', actor_label='Fictional Recorder',
                reason='Attempting to change an Alpha task through Beta.',
                owner_label='Fictional Owner')
        beta_question = self.store.add_question(
            'CASE-BETA', 'What follow-up did the fictional beta team agree on?')
        with self.assertRaisesRegex(InvalidInput, 'not in this case'):
            self.store.create_followthrough_task(
                'CASE-ALPHA', 'Cross-case fictional check',
                actor_label='Fictional Recorder', question_id=beta_question)
        with self.assertRaisesRegex(InvalidInput, 'another case'):
            self.store.create_followthrough_task(
                'CASE-ALPHA', 'Cross-case fictional check',
                actor_label='Fictional Recorder',
                source_version_id=self.beta_source['source_id'])

    def test_case_state_carries_the_followthrough_projection(self):
        task_id = self._create(due_date='2026-05-01')
        state = self.store.state('CASE-ALPHA')
        self.assertIn('followthrough', state)
        projection = state['followthrough']
        self.assertTrue(projection['synthetic'])
        self.assertIn('takes no action', projection['disclaimer'])
        self.assertEqual([t['id'] for t in projection['tasks']], [task_id])
        self.assertIn('overdue_task_ids', projection)
        self.assertIn('due_soon_task_ids', projection)

    def test_assignment_and_date_validation(self):
        task_id = self._create()
        with self.assertRaisesRegex(InvalidInput, 'Owner label'):
            self.store.update_followthrough_task(
                'CASE-ALPHA', task_id, 'assigned', actor_label='Fictional Recorder',
                reason='Assigning without naming a human owner must fail here.')
        with self.assertRaisesRegex(InvalidInput, 'recorded only when'):
            self.store.update_followthrough_task(
                'CASE-ALPHA', task_id, 'deferred', actor_label='Fictional Recorder',
                reason='Deferring while passing an owner must fail as well.',
                owner_label='Fictional Owner')
        with self.assertRaisesRegex(InvalidInput, 'YYYY-MM-DD'):
            self._create(title='Bad-date fictional check', due_date='June 10th')
        with self.assertRaisesRegex(InvalidInput, 'Actor label'):
            self.store.create_followthrough_task('CASE-ALPHA', 'No-actor check', actor_label='x')
        outcome = self.store.update_followthrough_task(
            'CASE-ALPHA', task_id, 'deferred', actor_label='Fictional Recorder',
            reason='Deferring with a new due date for the fictional work.',
            due_date='2026-07-01')
        self.assertEqual(outcome['result'], 'deferred')
        task = task_in(followthrough_view(self.store, 'CASE-ALPHA'), task_id)
        self.assertEqual(task['due_date'], '2026-07-01')
        reopened = self.store.update_followthrough_task(
            'CASE-ALPHA', task_id, 'assigned', actor_label='Fictional Recorder',
            reason='Reopening the deferred task and clearing its due date.',
            owner_label='Fictional Owner', due_date=None)
        self.assertEqual(reopened['result'], 'assigned')
        cleared = task_in(followthrough_view(self.store, 'CASE-ALPHA'), task_id)
        self.assertIsNone(cleared['due_date'])


if __name__ == '__main__':
    unittest.main()
