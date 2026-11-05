"""Clinician review queue + sign-off receipts.

All cases are fictional and independently authored. A sign-off records
that a person looked at the listed item; it never approves, authorizes,
or recommends any treatment, test, or procedure.
"""
import json
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence import CaseStore, InvalidInput
from open_intelligence.__main__ import FICTIONAL_ACTOR_HEADER, Handler, seed
from open_intelligence.agent_writes import build_investigation_contract
from open_intelligence.investigation import validate_output

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / 'examples' / 'synthetic'


def report(name):
    return (SAMPLE / name).read_bytes()


def evidence(name='demo-evidence.txt'):
    return (SAMPLE / name).read_bytes()


class ReviewQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / 'test.sqlite')
        self.store.add_case('CASE-ALPHA', 'Fictional Alpha')
        self.store.add_case('CASE-BETA', 'Fictional Beta')
        self.path = self.store.import_report('CASE-ALPHA', report('alpha-pathology-original.txt'))
        self.img = self.store.import_report('CASE-ALPHA', report('alpha-imaging.txt'))
        self.beta = self.store.import_report('CASE-BETA', report('beta-pathology.txt'))

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _snapshot(self, case='CASE-ALPHA', source_id=None, question=None):
        q = self.store.add_question(case, question or 'What does this fictional report state?')
        return self.store.create_snapshot(
            case, q, 'A human-authored synthetic discussion draft.',
            [source_id or self.path['source_id']])

    def _held_option(self, snapshot=None):
        ev = self.store.import_synthetic_evidence(evidence())
        q = self.store.add_question('CASE-ALPHA', 'What does the fictional note discuss?')
        assessment = self.store.assess_synthetic_evidence(
            'CASE-ALPHA', q, ev['evidence_version_id'], 'contradicts', 'limited',
            'A human-authored rationale noting a contradiction.')
        snap = snapshot or self._snapshot()
        option = self.store.create_option(
            'CASE-ALPHA', snap, 'Fictional discussion item',
            'A fictional item discussed for planning purposes only.', 'unknown')
        self.store.add_option_dependency('CASE-ALPHA', option, 'evidence_assessment',
                                         evidence_assessment_id=assessment)
        return option

    def _keys(self, queue, section='awaiting'):
        return {x['queue_key'] for x in queue[section]}

    def test_queue_lists_all_kinds_with_age_and_status(self):
        snap = self._snapshot()
        option = self._held_option()
        amended = self.store.import_report('CASE-ALPHA', report('alpha-pathology-amended.txt'))
        ev = self.store.import_synthetic_evidence(evidence('oi019-evidence-discussion.txt'))
        q = self.store.add_question('CASE-ALPHA', 'What does the second fictional note discuss?')
        assessment = self.store.assess_synthetic_evidence(
            'CASE-ALPHA', q, ev['evidence_version_id'], 'context', 'limited',
            'A human-authored rationale for this fictional note.')
        queue = self.store.review_queue('CASE-ALPHA')
        self.assertTrue(queue['synthetic'])
        self.assertIn('does not approve, authorize, or recommend', queue['disclaimer'])
        kinds = {x['queue_key']: x['kind'] for x in queue['awaiting']}
        self.assertEqual(kinds[f'snapshot:{snap}'], 'investigation')
        self.assertEqual(kinds[f"amendment:{amended['source_id']}"], 'amendment')
        self.assertEqual(kinds[f'option:{option}'], 'held-option')
        self.assertEqual(kinds[f'evidence-assessment:{assessment}'], 'new-evidence')
        for item in queue['awaiting']:
            self.assertIn(item['status'], ('awaiting_review', 'returned'))
            self.assertIsInstance(item['age_days'], int)
            self.assertGreaterEqual(item['age_days'], 0)
            self.assertTrue(item['created_at'])
            self.assertTrue(item['title'].startswith('Fictional'))
            self.assertIn('Fictional', item['title'])
        created = [x['created_at'] for x in queue['awaiting']]
        self.assertEqual(created, sorted(created))

    def test_terminal_receipt_resolves_and_is_append_only(self):
        snap = self._snapshot()
        before = len(self.store.review_queue('CASE-ALPHA')['receipts'])
        result = self.store.add_review_receipt(
            'CASE-ALPHA', f'snapshot:{snap}', 'reviewed', 'Synthetic reviewer')
        self.assertEqual(result['result'], 'reviewed')
        queue = self.store.review_queue('CASE-ALPHA')
        self.assertNotIn(f'snapshot:{snap}', self._keys(queue))
        self.assertIn(f'snapshot:{snap}', self._keys(queue, 'resolved'))
        resolved = {x['queue_key']: x for x in queue['resolved']}[f'snapshot:{snap}']
        self.assertEqual(resolved['resolved_by']['reviewer_label'], 'Synthetic reviewer')
        self.assertEqual(len(queue['receipts']), before + 1)
        # A second terminal decision for the same version is rejected; the
        # first record stands and history only grows.
        with self.assertRaisesRegex(InvalidInput, 'already resolved'):
            self.store.add_review_receipt(
                'CASE-ALPHA', f'snapshot:{snap}', 'acknowledged', 'Another reviewer label')
        again = self.store.review_queue('CASE-ALPHA')
        self.assertEqual(len(again['receipts']), before + 1)
        self.assertFalse(hasattr(self.store, 'update_review_receipt'))
        self.assertFalse(hasattr(self.store, 'delete_review_receipt'))

    def test_returned_item_stays_queued_with_reason(self):
        snap = self._snapshot()
        with self.assertRaisesRegex(InvalidInput, 'requires a 10'):
            self.store.add_review_receipt(
                'CASE-ALPHA', f'snapshot:{snap}', 'returned', 'Synthetic reviewer')
        with self.assertRaisesRegex(InvalidInput, 'requires a 10'):
            self.store.add_review_receipt(
                'CASE-ALPHA', f'snapshot:{snap}', 'returned', 'Synthetic reviewer',
                'too short')
        self.store.add_review_receipt(
            'CASE-ALPHA', f'snapshot:{snap}', 'returned', 'Synthetic reviewer',
            'Please recheck the fictional source lines before review.')
        queue = self.store.review_queue('CASE-ALPHA')
        item = {x['queue_key']: x for x in queue['awaiting']}[f'snapshot:{snap}']
        self.assertEqual(item['status'], 'returned')
        self.assertEqual(item['return_reason'], 'Please recheck the fictional source lines before review.')
        self.assertEqual(item['returned_by'], 'Synthetic reviewer')
        self.store.add_review_receipt(
            'CASE-ALPHA', f'snapshot:{snap}', 'reviewed', 'Synthetic reviewer')
        queue = self.store.review_queue('CASE-ALPHA')
        self.assertIn(f'snapshot:{snap}', self._keys(queue, 'resolved'))
        history = [r for r in queue['receipts'] if r['queue_key'] == f'snapshot:{snap}']
        self.assertEqual([r['action'] for r in history], ['returned', 'reviewed'])

    def test_amendment_reopens_resolved_snapshot_with_history(self):
        snap = self._snapshot()
        self.store.add_review_receipt(
            'CASE-ALPHA', f'snapshot:{snap}', 'reviewed', 'Synthetic reviewer')
        self.assertIn(f'snapshot:{snap}', self._keys(self.store.review_queue('CASE-ALPHA'), 'resolved'))
        amended = self.store.import_report('CASE-ALPHA', report('alpha-pathology-amended.txt'))
        queue = self.store.review_queue('CASE-ALPHA')
        # The snapshot item never vanishes: it reopens as stale with its
        # earlier decision preserved as history for an older version.
        item = {x['queue_key']: x for x in queue['awaiting']}[f'snapshot:{snap}']
        self.assertEqual(item['status'], 'awaiting_review')
        self.assertTrue(item['reopened_after_change'])
        self.assertEqual(len(item['prior_receipts']), 1)
        self.assertEqual(item['prior_receipts'][0]['action'], 'reviewed')
        self.assertIn(f"amendment:{amended['source_id']}", self._keys(queue))
        self.store.add_review_receipt(
            'CASE-ALPHA', f'snapshot:{snap}', 'acknowledged', 'Synthetic reviewer')
        queue = self.store.review_queue('CASE-ALPHA')
        self.assertIn(f'snapshot:{snap}', self._keys(queue, 'resolved'))
        history = [r for r in queue['receipts'] if r['queue_key'] == f'snapshot:{snap}']
        self.assertEqual(len(history), 2)
        self.assertNotEqual(history[0]['fingerprint'], history[1]['fingerprint'])

    def test_existing_demo_acknowledgment_leaves_no_silent_gap(self):
        snap = self._snapshot()
        self.store.acknowledge_demo_review('CASE-ALPHA', snap, 'Unverified synthetic reviewer')
        queue = self.store.review_queue('CASE-ALPHA')
        self.assertNotIn(f'snapshot:{snap}', self._keys(queue))
        resolved = {x['queue_key']: x for x in queue['resolved']}[f'snapshot:{snap}']
        self.assertEqual(resolved['resolved_by']['action'], 'acknowledged')
        self.assertIn('not a clinical authorization', resolved['resolved_by']['reason'])

    def test_held_option_review_records_decision_without_silent_leave(self):
        option = self._held_option()
        queue = self.store.review_queue('CASE-ALPHA')
        self.assertIn(f'option:{option}', self._keys(queue))
        self.store.review_option('CASE-ALPHA', option, 'Synthetic reviewer', 'reject',
                                 'Rejected because the linked note contradicts it.')
        queue = self.store.review_queue('CASE-ALPHA')
        # A terminal option is historical, not queued — but its queue receipt
        # proves the decision, so it did not vanish silently.
        self.assertNotIn(f'option:{option}', self._keys(queue))
        self.assertNotIn(f'option:{option}', self._keys(queue, 'resolved'))
        history = [r for r in queue['receipts'] if r['queue_key'] == f'option:{option}']
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['action'], 'reviewed')
        self.assertIn('option review (reject)', history[0]['reason'])

    def test_reconfirm_moves_needs_review_option_out_with_receipt(self):
        snap = self._snapshot()
        option = self.store.create_option(
            'CASE-ALPHA', snap, 'Fictional discussion item',
            'A fictional item discussed for planning purposes only.', 'unknown')
        # No source dependency: the amendment reopens this option through its
        # stale snapshot, and reconfirmation stays possible. (An option pinned
        # to a superseded source version needs a new proposal instead.)
        amended = self.store.import_report('CASE-ALPHA', report('alpha-pathology-amended.txt'))
        queue = self.store.review_queue('CASE-ALPHA')
        self.assertIn(f'option:{option}', self._keys(queue))
        q2 = self.store.add_question('CASE-ALPHA', 'What is discussed after the amendment?')
        replacement = self.store.create_snapshot(
            'CASE-ALPHA', q2, 'A human-authored post-amendment discussion draft.',
            [amended['source_id']])
        self.store.review_option('CASE-ALPHA', option, 'Synthetic reviewer', 'reconfirm',
                                 'Reconsidered against the replacement draft.', replacement)
        queue = self.store.review_queue('CASE-ALPHA')
        self.assertNotIn(f'option:{option}', self._keys(queue))
        history = [r for r in queue['receipts'] if r['queue_key'] == f'option:{option}']
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['action'], 'reviewed')

    def test_evidence_withdrawal_reopens_assessment_item(self):
        ev = self.store.import_synthetic_evidence(evidence())
        q = self.store.add_question('CASE-ALPHA', 'What does the fictional note discuss?')
        assessment = self.store.assess_synthetic_evidence(
            'CASE-ALPHA', q, ev['evidence_version_id'], 'context', 'limited',
            'A human-authored rationale for this fictional note.')
        self.store.add_review_receipt(
            'CASE-ALPHA', f'evidence-assessment:{assessment}', 'reviewed', 'Synthetic reviewer')
        self.assertIn(f'evidence-assessment:{assessment}',
                      self._keys(self.store.review_queue('CASE-ALPHA'), 'resolved'))
        self.store.withdraw_synthetic_evidence(
            ev['evidence_version_id'], 'Fictional example withdrawn for test purposes.')
        queue = self.store.review_queue('CASE-ALPHA')
        item = {x['queue_key']: x for x in queue['awaiting']}[f'evidence-assessment:{assessment}']
        self.assertTrue(item['reopened_after_change'])
        self.assertEqual(len(item['prior_receipts']), 1)

    def test_nothing_vanishes_without_receipt_across_operations(self):
        snap = self._snapshot()
        option = self._held_option()
        seen = set(self._keys(self.store.review_queue('CASE-ALPHA')))

        def assert_no_silent_vanish():
            queue = self.store.review_queue('CASE-ALPHA')
            present = self._keys(queue) | self._keys(queue, 'resolved')
            receipted = {r['queue_key'] for r in queue['receipts']}
            for key in seen:
                self.assertIn(key, present | receipted, f'{key} vanished without a receipt')
            seen.update(present)

        self.store.add_question('CASE-ALPHA', 'Another fictional question for the case?')
        assert_no_silent_vanish()
        amended = self.store.import_report('CASE-ALPHA', report('alpha-pathology-amended.txt'))
        assert_no_silent_vanish()
        # The amended snapshot is still present, reopened as stale.
        self.assertIn(f'snapshot:{snap}', self._keys(self.store.review_queue('CASE-ALPHA')))
        q_new = self.store.add_question('CASE-ALPHA', 'What does the amended fictional report state?')
        replacement = self.store.create_snapshot(
            'CASE-ALPHA', q_new, 'A human-authored draft on the amended fictional source.',
            [amended['source_id']])
        seen.add(f'snapshot:{replacement}')
        self.store.acknowledge_demo_review('CASE-ALPHA', replacement, 'Unverified synthetic reviewer')
        assert_no_silent_vanish()
        self.store.review_option('CASE-ALPHA', option, 'Synthetic reviewer', 'reject',
                                 'Rejected because the linked note contradicts it.')
        assert_no_silent_vanish()

    def test_queue_never_ages_out_or_auto_resolves(self):
        snap = self._snapshot()
        old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat(timespec='seconds')
        with self.store.db:
            self.store.db.execute('UPDATE snapshots SET created_at=? WHERE id=?', (old, snap))
        first = self.store.review_queue('CASE-ALPHA')
        item = {x['queue_key']: x for x in first['awaiting']}[f'snapshot:{snap}']
        self.assertGreaterEqual(item['age_days'], 60)
        # Repeated reads and unrelated work never resolve or remove it.
        for _ in range(3):
            again = self.store.review_queue('CASE-ALPHA')
            self.assertIn(f'snapshot:{snap}', self._keys(again))
            self.assertEqual(again['receipts'], first['receipts'])
        self.store.add_question('CASE-BETA', 'An unrelated fictional beta question?')
        self.store.add_question('CASE-ALPHA', 'Another fictional question for the case?')
        self.assertIn(f'snapshot:{snap}', self._keys(self.store.review_queue('CASE-ALPHA')))
        self.assertEqual(self.store.review_queue('CASE-ALPHA')['receipts'], first['receipts'])

    def test_signoff_is_acknowledgment_never_authorization(self):
        snap = self._snapshot()
        for action in ('approve', 'authorize', 'prescribe', 'order'):
            with self.assertRaisesRegex(InvalidInput, 'must be reviewed, acknowledged, or returned'):
                self.store.add_review_receipt(
                    'CASE-ALPHA', f'snapshot:{snap}', action, 'Synthetic reviewer')
        with self.assertRaisesRegex(InvalidInput, 'must not state a clinical recommendation'):
            self.store.add_review_receipt(
                'CASE-ALPHA', f'snapshot:{snap}', 'reviewed', 'Synthetic reviewer',
                'I recommend starting treatment immediately for this case.')
        with self.assertRaisesRegex(InvalidInput, 'must not state a clinical recommendation'):
            self.store.add_review_receipt(
                'CASE-ALPHA', f'snapshot:{snap}', 'reviewed', 'We prescribe therapy X')
        queue = self.store.review_queue('CASE-ALPHA')
        self.assertIn('records that a person looked', queue['disclaimer'])
        self.assertIn('does not approve, authorize, or recommend', queue['disclaimer'])
        self.assertIn('nothing is auto-approved', queue['disclaimer'])

    def test_cross_case_isolation(self):
        alpha_snap = self._snapshot(case='CASE-ALPHA')
        q_beta = self.store.add_question('CASE-BETA', 'What does the fictional beta report state?')
        beta_snap = self.store.create_snapshot(
            'CASE-BETA', q_beta, 'A human-authored synthetic beta discussion draft.',
            [self.beta['source_id']])
        self.store.add_review_receipt(
            'CASE-ALPHA', f'snapshot:{alpha_snap}', 'reviewed', 'Synthetic reviewer')
        beta_queue = self.store.review_queue('CASE-BETA')
        self.assertIn(f'snapshot:{beta_snap}', self._keys(beta_queue))
        self.assertEqual(beta_queue['receipts'], [])
        with self.assertRaisesRegex(InvalidInput, 'not found in this case'):
            self.store.add_review_receipt(
                'CASE-BETA', f'snapshot:{alpha_snap}', 'reviewed', 'Synthetic reviewer')

    def test_model_investigation_queued_and_reopened_by_amendment(self):
        q = self.store.add_question('CASE-ALPHA', 'What does this fictional report state?')
        facts = self.store.investigation_facts('CASE-ALPHA', q)
        source_id = next(iter(facts['valid_sources']))
        validated = validate_output(
            {'claims': [{'text': 'The sources report a finding.',
                         'support': 'context',
                         'citations': [{'type': 'source', 'id': source_id}],
                         'uncertainty': 'moderate', 'limits': 'Synthetic only.'}],
             'abstentions': []},
            facts['valid_sources'], facts['valid_assessments'])
        inv_id = self.store.save_investigation(
            'CASE-ALPHA', q, 'evidence-summary', validated, 'replay',
            write_contract=build_investigation_contract(
                self.store, 'CASE-ALPHA', q, 'evidence-summary',
                validated.model, facts=facts))
        # A bound draft ensures the amendment below invalidates dependent work,
        # which is what marks the case's investigations stale.
        self._snapshot()
        queue = self.store.review_queue('CASE-ALPHA')
        self.assertIn(f'model-investigation:{inv_id}', self._keys(queue))
        self.store.add_review_receipt(
            'CASE-ALPHA', f'model-investigation:{inv_id}', 'acknowledged', 'Synthetic reviewer')
        self.assertIn(f'model-investigation:{inv_id}',
                      self._keys(self.store.review_queue('CASE-ALPHA'), 'resolved'))
        self.store.import_report('CASE-ALPHA', report('alpha-pathology-amended.txt'))
        queue = self.store.review_queue('CASE-ALPHA')
        item = {x['queue_key']: x for x in queue['awaiting']}[f'model-investigation:{inv_id}']
        self.assertTrue(item['reopened_after_change'])


class ReviewQueueHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / 'server.sqlite')
        seed(cls.path)
        bound_handler = type('BoundHandlerForTest', (Handler,), {'db_path': cls.path})
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), bound_handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def request(self, path, data=None):
        values = {FICTIONAL_ACTOR_HEADER: 'FICTIONAL-NAVIGATOR-A'}
        if data is not None:
            values['Content-Type'] = 'application/json'
        request = Request(f'http://127.0.0.1:{self.port}{path}',
                          data=None if data is None else json.dumps(data).encode(),
                          headers=values)
        try:
            with urlopen(request, timeout=5) as response:
                content = response.read()
                return response.status, json.loads(content) if 'json' in response.headers.get('Content-Type') else content
        except HTTPError as err:
            return err.code, json.loads(err.read())

    def test_get_queue_and_unknown_case(self):
        status, data = self.request('/api/cases/CASE-ALPHA/review-queue')
        self.assertEqual(status, 200)
        self.assertTrue(data['synthetic'])
        self.assertIn('does not approve, authorize, or recommend', data['disclaimer'])
        self.assertIn('awaiting', data)
        self.assertIn('resolved', data)
        self.assertIn('receipts', data)
        status, error = self.request('/api/cases/CASE-NOPE/review-queue')
        self.assertEqual(status, 422)
        self.assertEqual(error['error'], 'Unknown case')

    def test_post_receipt_through_api(self):
        status, result = self.request('/api/cases/CASE-ALPHA/questions',
                                      {'question': 'Which fictional findings need a queue sign-off?'})
        self.assertEqual(status, 201)
        status, state = self.request('/api/cases/CASE-ALPHA/state')
        source_id = [s['id'] for s in state['sources']
                     if s['document_id'] == 'PATH-ALPHA' and s['state'] == 'current'][0]
        status, draft = self.request('/api/cases/CASE-ALPHA/snapshots',
                                     {'question_id': result['question_id'],
                                      'summary': 'A human-authored draft awaiting queue sign-off.',
                                      'source_ids': [source_id]})
        self.assertEqual(status, 201)
        key = f"snapshot:{draft['snapshot_id']}"
        status, error = self.request('/api/cases/CASE-ALPHA/review-queue/receipts',
                                     {'queue_key': key, 'action': 'returned',
                                      'reviewer_label': 'Synthetic reviewer'})
        self.assertEqual(status, 422)
        status, created = self.request('/api/cases/CASE-ALPHA/review-queue/receipts',
                                       {'queue_key': key, 'action': 'returned',
                                        'reviewer_label': 'Synthetic reviewer',
                                        'reason': 'Please recheck the fictional source lines first.'})
        self.assertEqual(status, 201)
        self.assertEqual(created['result'], 'returned')
        status, queue = self.request('/api/cases/CASE-ALPHA/review-queue')
        item = {x['queue_key']: x for x in queue['awaiting']}[key]
        self.assertEqual(item['status'], 'returned')
        status, created = self.request('/api/cases/CASE-ALPHA/review-queue/receipts',
                                       {'queue_key': key, 'action': 'reviewed',
                                        'reviewer_label': 'Synthetic reviewer'})
        self.assertEqual(status, 201)
        status, error = self.request('/api/cases/CASE-ALPHA/review-queue/receipts',
                                     {'queue_key': key, 'action': 'reviewed',
                                      'reviewer_label': 'Synthetic reviewer'})
        self.assertEqual(status, 422)
        status, queue = self.request('/api/cases/CASE-ALPHA/review-queue')
        self.assertIn(key, {x['queue_key'] for x in queue['resolved']})

    def test_static_review_queue_surface(self):
        with urlopen(f'http://127.0.0.1:{self.port}/') as response:
            body = response.read().decode()
            self.assertIn('href="#review-queue"', body)
            self.assertIn('id="review-queue"', body)
            self.assertIn('id="review-awaiting"', body)
            self.assertIn('FICTIONAL DEMO DATA', body)
            self.assertIn('never approves or authorizes', body)


class ReviewQueueUiContractTests(unittest.TestCase):
    def test_markup_is_plain_language_and_fictional(self):
        html = (ROOT / 'web' / 'index.html').read_text()
        self.assertIn('href="#review-queue"', html)
        self.assertIn('id="review-queue"', html)
        self.assertIn('id="review-queue-disclaimer"', html)
        self.assertIn('id="review-awaiting"', html)
        self.assertIn('id="review-resolved"', html)
        self.assertIn('id="review-receipts"', html)
        self.assertIn('only records that someone looked', html)
        self.assertIn('every item ends in a recorded decision or stays visible', html)

    def test_renderer_is_case_scoped_and_source_safe(self):
        javascript = (ROOT / 'web' / 'app.js').read_text()
        self.assertIn("'/api/cases/' + requested + '/review-queue'", javascript)
        self.assertIn('renderReviewQueue', javascript)
        self.assertIn('loadReviewQueue', javascript)
        self.assertIn('review-queue/receipts', javascript)
        self.assertIn('textContent', javascript)
        self.assertNotIn('innerHTML', javascript)


if __name__ == '__main__':
    unittest.main()
