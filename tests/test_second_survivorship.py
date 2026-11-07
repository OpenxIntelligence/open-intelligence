"""Second-opinion and survivorship care records.

Fictional synthetic data only. A second-opinion response is a separate
record that never overwrites the original case conclusion; survivorship
items are plain recorded plans that never direct care. These tests verify
software contracts only, not clinical correctness.
"""
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence import CaseStore, InvalidInput
from open_intelligence.__main__ import Handler, seed
from session_auth import signin_demo
from open_intelligence.care_records import find_directed_language

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / 'examples' / 'synthetic'


def report(name):
    return (SAMPLE / name).read_bytes()


QUESTION = 'What does the fictional record state about marker A?'
REQUEST_TEXT = 'How is the recorded marker A wording best described in plain words?'
RESPONSE_TEXT = ('The recorded wording states that marker A testing was not reported in the '
                 'original source version; the quoted lines are listed with the request materials.')
PLAN_TITLE = 'Recorded follow-up notes (fictional)'
FOLLOWUP = 'A follow-up visit is recorded for 2026-09-01 in the fictional file.'
WATCH = 'Tiredness noted in the source is recorded here for comparison with later reports.'
TRIGGER = ('A later imaging source with a newer event date is recorded as a reason '
           'to look at this plan again.')
SCOPE = 'Demo-only acknowledgment of this fictional record.'
REVIEWER = 'Synthetic reviewer (unverified)'

# Each sample carries directive or clinical-claim wording aimed at care.
DIRECTIVE_SAMPLES = (
    'The subject should return in six weeks for another visit.',
    'The subject must attend the clinic without delay.',
    'The subject needs to rest for several days.',
    'The subject need to rest for several days.',
    'The subject will have to attend the next visit.',
    'We recommend further testing of the fictional sample.',
    'The clinic prescribed rest for the fictional subject.',
    'The subject is eligible for further review.',
    'Order the treatment without waiting for review.',
    'Start treatment as soon as possible.',
    'Watch for fever in the coming days.',
    'Look out for new pain in the coming days.',
    'Seek care if tiredness continues.',
    'Go to the clinic if anything changes.',
    'Call your doctor if anything changes.',
    'Contact the clinic if anything changes.',
    'This approach is effective for the fictional case.',
    'Proven benefit was noted in the fictional file.',
)


def walk_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from walk_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from walk_strings(item)


class SecondOpinionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / 'test.sqlite')
        self.store.add_case('CASE-ALPHA', 'Fictional Alpha')
        self.store.add_case('CASE-BETA', 'Fictional Beta')
        self.path = self.store.import_report('CASE-ALPHA', report('alpha-pathology-original.txt'))
        self.img = self.store.import_report('CASE-ALPHA', report('alpha-imaging.txt'))
        self.beta = self.store.import_report('CASE-BETA', report('beta-pathology.txt'))
        self.q = self.store.add_question('CASE-ALPHA', QUESTION)
        self.q_beta = self.store.add_question('CASE-BETA', QUESTION)
        self.snap = self.store.create_snapshot(
            'CASE-ALPHA', self.q, 'A human-authored synthetic discussion draft.',
            [self.path['source_id']])

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _request(self, materials=None, snapshot='default', question=None):
        if snapshot == 'default':
            snapshot = self.snap
        return self.store.create_second_opinion_request(
            'CASE-ALPHA', question or self.q, REQUEST_TEXT,
            materials or [self.path['source_id']], snapshot)

    def _view_request(self, request_id):
        for entry in self.store.second_opinion_view('CASE-ALPHA')['requests']:
            if entry['id'] == request_id:
                return entry
        self.fail(f'request {request_id} not in view')

    def test_request_and_response_leave_original_untouched(self):
        before_snapshots = self.store.state('CASE-ALPHA')['snapshots']
        before_questions = self.store.state('CASE-ALPHA')['questions']
        request_id = self._request()
        self.store.record_second_opinion_response(
            'CASE-ALPHA', request_id, 'Fictional second reviewer', RESPONSE_TEXT,
            self.path['source_id'])
        after = self.store.state('CASE-ALPHA')
        # The original conclusion rows are byte-identical: nothing was merged.
        self.assertEqual(after['snapshots'], before_snapshots)
        self.assertEqual(after['questions'], before_questions)
        # Both stay visible side by side as separate records.
        entry = self._view_request(request_id)
        self.assertEqual(entry['original_snapshot']['id'], self.snap)
        self.assertEqual(entry['original_snapshot']['summary'],
                         'A human-authored synthetic discussion draft.')
        self.assertEqual(entry['response']['response_text'], RESPONSE_TEXT)
        self.assertIsNotNone(entry['original_snapshot'])
        self.assertIsNotNone(entry['response'])
        self.assertEqual(entry['status'], 'response_recorded')
        self.assertEqual(entry['materials'][0]['document_id'], 'PATH-ALPHA')
        self.assertEqual(entry['response']['anchor']['document_id'], 'PATH-ALPHA')
        self.assertIn('separate from the original', self.store.state('CASE-ALPHA')['second_opinion_disclaimer'])

    def test_response_recorded_once_then_reviewed(self):
        request_id = self._request()
        response_id = self.store.record_second_opinion_response(
            'CASE-ALPHA', request_id, 'Fictional second reviewer', RESPONSE_TEXT,
            self.path['source_id'])
        self.assertGreater(response_id, 0)
        with self.assertRaisesRegex(InvalidInput, 'already recorded'):
            self.store.record_second_opinion_response(
                'CASE-ALPHA', request_id, 'Fictional second reviewer', RESPONSE_TEXT,
                self.path['source_id'])
        outcome = self.store.review_second_opinion('CASE-ALPHA', request_id, REVIEWER, SCOPE)
        self.assertEqual(outcome['result'], 'acknowledged_in_demo')
        self.assertEqual(self._view_request(request_id)['review_state'], 'reviewed_in_demo')
        events = self._view_request(request_id)['review_events']
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['reviewer_label'], REVIEWER)
        self.assertEqual(events[0]['action'], 'acknowledge')
        with self.assertRaisesRegex(InvalidInput, 'already reviewed'):
            self.store.review_second_opinion('CASE-ALPHA', request_id, REVIEWER, SCOPE)

    def test_amendment_reopens_only_dependent_requests(self):
        on_path = self._request(materials=[self.path['source_id']], snapshot=None)
        on_img = self._request(materials=[self.img['source_id']], snapshot=None)
        anchored = self._request(materials=[self.img['source_id']], snapshot=None)
        self.store.record_second_opinion_response(
            'CASE-ALPHA', anchored, 'Fictional second reviewer', RESPONSE_TEXT,
            self.path['source_id'])
        beta_request = self.store.create_second_opinion_request(
            'CASE-BETA', self.q_beta, REQUEST_TEXT, [self.beta['source_id']])
        result = self.store.import_report('CASE-ALPHA', report('alpha-pathology-amended.txt'))
        self.assertEqual(sorted(result['invalidated_second_opinions']), sorted([on_path, anchored]))
        self.assertEqual(self._view_request(on_path)['review_state'], 'needs_review')
        self.assertEqual(self._view_request(anchored)['review_state'], 'needs_review')
        self.assertEqual(self._view_request(on_img)['review_state'], 'pending')
        beta_view = self.store.second_opinion_view('CASE-BETA')['requests']
        self.assertEqual(beta_view[0]['id'], beta_request)
        self.assertEqual(beta_view[0]['review_state'], 'pending')
        # History stays inspectable; review of the reopened record is refused.
        self.assertEqual(self._view_request(on_path)['materials'][0]['version'], 1)
        self.assertEqual(self._view_request(on_path)['materials'][0]['state'], 'superseded')
        with self.assertRaisesRegex(InvalidInput, 'create a new request'):
            self.store.review_second_opinion('CASE-ALPHA', on_path, REVIEWER, SCOPE)
        current = [s for s in self.store.state('CASE-ALPHA')['sources']
                   if s['document_id'] == 'PATH-ALPHA' and s['state'] == 'current'][0]
        fresh = self.store.create_second_opinion_request(
            'CASE-ALPHA', self.q, REQUEST_TEXT, [current['id']])
        self.assertEqual(self._view_request(fresh)['review_state'], 'pending')

    def test_linked_original_going_stale_reopens_request(self):
        request_id = self._request(materials=[self.img['source_id']], snapshot=self.snap)
        self.store.import_report('CASE-ALPHA', report('alpha-pathology-amended.txt'))
        entry = self._view_request(request_id)
        self.assertEqual(entry['review_state'], 'needs_review')
        self.assertEqual(entry['original_snapshot']['state'], 'stale')
        self.assertEqual(entry['materials'][0]['state'], 'current')

    def test_case_scoped_refs_rejected(self):
        with self.assertRaisesRegex(InvalidInput, 'not in this case'):
            self.store.create_second_opinion_request(
                'CASE-ALPHA', self.q_beta, REQUEST_TEXT, [self.path['source_id']])
        with self.assertRaisesRegex(InvalidInput, 'another case'):
            self.store.create_second_opinion_request(
                'CASE-ALPHA', self.q, REQUEST_TEXT, [self.beta['source_id']])
        beta_snap = self.store.create_snapshot(
            'CASE-BETA', self.q_beta, 'A human-authored synthetic beta draft.',
            [self.beta['source_id']])
        with self.assertRaisesRegex(InvalidInput, 'not in this case'):
            self.store.create_second_opinion_request(
                'CASE-ALPHA', self.q, REQUEST_TEXT, [self.path['source_id']], beta_snap)
        request_id = self._request()
        with self.assertRaisesRegex(InvalidInput, 'another case'):
            self.store.record_second_opinion_response(
                'CASE-ALPHA', request_id, 'Fictional second reviewer', RESPONSE_TEXT,
                self.beta['source_id'])
        with self.assertRaisesRegex(InvalidInput, 'not in this case'):
            self.store.record_second_opinion_response(
                'CASE-BETA', request_id, 'Fictional second reviewer', RESPONSE_TEXT,
                self.beta['source_id'])
        with self.assertRaisesRegex(InvalidInput, 'not in this case'):
            self.store.review_second_opinion('CASE-BETA', request_id, REVIEWER, SCOPE)

    def test_superseded_materials_refused_for_new_requests(self):
        self.store.import_report('CASE-ALPHA', report('alpha-pathology-amended.txt'))
        with self.assertRaisesRegex(InvalidInput, 'superseded'):
            self.store.create_second_opinion_request(
                'CASE-ALPHA', self.q, REQUEST_TEXT, [self.path['source_id']])
        with self.assertRaisesRegex(InvalidInput, 'unique'):
            self.store.create_second_opinion_request(
                'CASE-ALPHA', self.q, REQUEST_TEXT,
                [self.img['source_id'], self.img['source_id']])
        with self.assertRaisesRegex(InvalidInput, 'Shared materials'):
            self.store.create_second_opinion_request('CASE-ALPHA', self.q, REQUEST_TEXT, [])


class SurvivorshipTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / 'test.sqlite')
        self.store.add_case('CASE-ALPHA', 'Fictional Alpha')
        self.store.add_case('CASE-BETA', 'Fictional Beta')
        self.path = self.store.import_report('CASE-ALPHA', report('alpha-pathology-original.txt'))
        self.img = self.store.import_report('CASE-ALPHA', report('alpha-imaging.txt'))
        self.beta = self.store.import_report('CASE-BETA', report('beta-pathology.txt'))
        self.plan = self.store.create_survivorship_plan('CASE-ALPHA', PLAN_TITLE)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _view_item(self, item_id, case_id='CASE-ALPHA'):
        for plan in self.store.survivorship_view(case_id)['plans']:
            for item in plan['items']:
                if item['id'] == item_id:
                    return item
        self.fail(f'item {item_id} not in view')

    def test_plan_and_items_are_plain_records_with_anchors(self):
        followup = self.store.add_survivorship_item(
            'CASE-ALPHA', self.plan, 'followup', FOLLOWUP, self.path['source_id'],
            recorded_date='2026-09-01')
        watch = self.store.add_survivorship_item(
            'CASE-ALPHA', self.plan, 'watch', WATCH, self.img['source_id'])
        trigger = self.store.add_survivorship_item(
            'CASE-ALPHA', self.plan, 'trigger', TRIGGER, self.path['source_id'])
        state = self.store.state('CASE-ALPHA')
        self.assertIn('never direct care', state['survivorship_disclaimer'])
        plans = state['survivorship_plans']
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]['title'], PLAN_TITLE)
        by_id = {item['id']: item for item in plans[0]['items']}
        self.assertEqual(by_id[followup]['kind'], 'followup')
        self.assertEqual(by_id[followup]['recorded_date'], '2026-09-01')
        self.assertIn('not a clinical due date', by_id[followup]['recorded_date_label'])
        self.assertEqual(by_id[watch]['recorded_date'], None)
        for item_id in (followup, watch, trigger):
            item = by_id[item_id]
            self.assertEqual(item['state'], 'recorded')
            self.assertEqual(item['review_state'], 'pending')
            self.assertIn(item['anchor']['document_id'], ('PATH-ALPHA', 'IMG-ALPHA'))
            self.assertEqual(item['anchor']['state'], 'current')
        # Trigger items transition exactly once; other kinds never do.
        outcome = self.store.mark_survivorship_trigger(
            'CASE-ALPHA', trigger, 'A newer imaging source arrived in the fictional file.')
        self.assertEqual(outcome['result'], 'triggered')
        self.assertEqual(self._view_item(trigger)['state'], 'triggered')
        with self.assertRaisesRegex(InvalidInput, 'already marked'):
            self.store.mark_survivorship_trigger(
                'CASE-ALPHA', trigger, 'A newer imaging source arrived in the fictional file.')
        with self.assertRaisesRegex(InvalidInput, 'Only a review-trigger'):
            self.store.mark_survivorship_trigger(
                'CASE-ALPHA', followup, 'A newer imaging source arrived in the fictional file.')
        with self.assertRaisesRegex(InvalidInput, 'Only a review-trigger'):
            self.store.mark_survivorship_trigger(
                'CASE-ALPHA', watch, 'A newer imaging source arrived in the fictional file.')
        # Review is a demo acknowledgment with a recorded actor and scope.
        reviewed = self.store.review_survivorship_item('CASE-ALPHA', followup, REVIEWER, SCOPE)
        self.assertEqual(reviewed['result'], 'acknowledged_in_demo')
        item = self._view_item(followup)
        self.assertEqual(item['review_state'], 'reviewed_in_demo')
        self.assertEqual(len(item['review_events']), 1)
        self.assertEqual(item['review_events'][0]['reviewer_label'], REVIEWER)
        with self.assertRaisesRegex(InvalidInput, 'already reviewed'):
            self.store.review_survivorship_item('CASE-ALPHA', followup, REVIEWER, SCOPE)

    def test_amendment_reopens_only_dependent_items(self):
        on_path = self.store.add_survivorship_item(
            'CASE-ALPHA', self.plan, 'watch', WATCH, self.path['source_id'])
        on_img = self.store.add_survivorship_item(
            'CASE-ALPHA', self.plan, 'watch', WATCH, self.img['source_id'])
        beta_plan = self.store.create_survivorship_plan('CASE-BETA', PLAN_TITLE)
        beta_item = self.store.add_survivorship_item(
            'CASE-BETA', beta_plan, 'watch', WATCH, self.beta['source_id'])
        result = self.store.import_report('CASE-ALPHA', report('alpha-pathology-amended.txt'))
        self.assertEqual(result['invalidated_survivorship_items'], [on_path])
        self.assertEqual(self._view_item(on_path)['review_state'], 'needs_review')
        self.assertEqual(self._view_item(on_img)['review_state'], 'pending')
        self.assertEqual(self._view_item(beta_item, 'CASE-BETA')['review_state'], 'pending')
        # The reopened item stays inspectable; a new item replaces its role.
        self.assertEqual(self._view_item(on_path)['anchor']['state'], 'superseded')
        with self.assertRaisesRegex(InvalidInput, 'record a new item'):
            self.store.review_survivorship_item('CASE-ALPHA', on_path, REVIEWER, SCOPE)
        current = [s for s in self.store.state('CASE-ALPHA')['sources']
                   if s['document_id'] == 'PATH-ALPHA' and s['state'] == 'current'][0]
        fresh = self.store.add_survivorship_item(
            'CASE-ALPHA', self.plan, 'watch', WATCH, current['id'])
        self.assertEqual(self._view_item(fresh)['review_state'], 'pending')
        with self.assertRaisesRegex(InvalidInput, 'superseded'):
            self.store.add_survivorship_item(
                'CASE-ALPHA', self.plan, 'watch', WATCH, self.path['source_id'])

    def test_case_scoped_refs_and_kinds_rejected(self):
        with self.assertRaisesRegex(InvalidInput, 'not in this case'):
            self.store.add_survivorship_item(
                'CASE-BETA', self.plan, 'watch', WATCH, self.beta['source_id'])
        with self.assertRaisesRegex(InvalidInput, 'another case'):
            self.store.add_survivorship_item(
                'CASE-ALPHA', self.plan, 'watch', WATCH, self.beta['source_id'])
        with self.assertRaisesRegex(InvalidInput, 'must be followup, watch, or trigger'):
            self.store.add_survivorship_item(
                'CASE-ALPHA', self.plan, 'prescription', WATCH, self.path['source_id'])
        beta_plan = self.store.create_survivorship_plan('CASE-BETA', PLAN_TITLE)
        beta_item = self.store.add_survivorship_item(
            'CASE-BETA', beta_plan, 'watch', WATCH, self.beta['source_id'])
        with self.assertRaisesRegex(InvalidInput, 'not in this case'):
            self.store.review_survivorship_item('CASE-ALPHA', beta_item, REVIEWER, SCOPE)
        with self.assertRaisesRegex(InvalidInput, 'not in this case'):
            self.store.mark_survivorship_trigger('CASE-ALPHA', beta_item, 'An observation for tests.')

    def test_recorded_date_validation(self):
        with self.assertRaises(InvalidInput):
            self.store.add_survivorship_item(
                'CASE-ALPHA', self.plan, 'followup', FOLLOWUP, self.path['source_id'],
                recorded_date='next Friday')
        with self.assertRaises(InvalidInput):
            self.store.add_survivorship_item(
                'CASE-ALPHA', self.plan, 'followup', FOLLOWUP, self.path['source_id'],
                recorded_date=20260901)
        item = self.store.add_survivorship_item(
            'CASE-ALPHA', self.plan, 'followup', FOLLOWUP, self.path['source_id'],
            recorded_date='2026-09-01')
        self.assertEqual(self._view_item(item)['recorded_date'], '2026-09-01')


class DescriptiveLanguageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = CaseStore(Path(self.tmp.name) / 'test.sqlite')
        self.store.add_case('CASE-ALPHA', 'Fictional Alpha')
        self.source = self.store.import_report(
            'CASE-ALPHA', report('alpha-pathology-original.txt'))['source_id']
        self.q = self.store.add_question('CASE-ALPHA', QUESTION)
        self.plan = self.store.create_survivorship_plan('CASE-ALPHA', PLAN_TITLE)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_directed_wording_rejected_in_every_record_field(self):
        for sample in DIRECTIVE_SAMPLES:
            with self.subTest(sample=sample):
                with self.assertRaisesRegex(InvalidInput, 'must not direct care'):
                    self.store.create_second_opinion_request(
                        'CASE-ALPHA', self.q, sample, [self.source])
                request_id = self.store.create_second_opinion_request(
                    'CASE-ALPHA', self.q, REQUEST_TEXT, [self.source])
                with self.assertRaisesRegex(InvalidInput, 'must not direct care'):
                    self.store.record_second_opinion_response(
                        'CASE-ALPHA', request_id, 'Fictional second reviewer', sample, self.source)
                with self.assertRaisesRegex(InvalidInput, 'must not direct care'):
                    self.store.create_survivorship_plan('CASE-ALPHA', sample)
                with self.assertRaisesRegex(InvalidInput, 'must not direct care'):
                    self.store.add_survivorship_item(
                        'CASE-ALPHA', self.plan, 'watch', sample, self.source)
                with self.assertRaisesRegex(InvalidInput, 'must not direct care'):
                    self.store.review_second_opinion(
                        'CASE-ALPHA', request_id, REVIEWER, sample)
                item_id = self.store.add_survivorship_item(
                    'CASE-ALPHA', self.plan, 'trigger', TRIGGER, self.source)
                with self.assertRaisesRegex(InvalidInput, 'must not direct care'):
                    self.store.mark_survivorship_trigger('CASE-ALPHA', item_id, sample)
        # Rejected writes left no partial rows behind.
        self.assertEqual(self.store.second_opinion_view('CASE-ALPHA')['requests'][-1]['status'],
                         'requested')
        self.assertEqual(
            [i for p in self.store.survivorship_view('CASE-ALPHA')['plans'] for i in p['items']
             if i['kind'] == 'watch'], [])

    def test_slice_views_carry_no_directed_wording(self):
        request_id = self.store.create_second_opinion_request(
            'CASE-ALPHA', self.q, REQUEST_TEXT, [self.source])
        self.store.record_second_opinion_response(
            'CASE-ALPHA', request_id, 'Fictional second reviewer', RESPONSE_TEXT, self.source)
        self.store.review_second_opinion('CASE-ALPHA', request_id, REVIEWER, SCOPE)
        self.store.add_survivorship_item(
            'CASE-ALPHA', self.plan, 'followup', FOLLOWUP, self.source,
            recorded_date='2026-09-01')
        watch = self.store.add_survivorship_item(
            'CASE-ALPHA', self.plan, 'watch', WATCH, self.source)
        trigger = self.store.add_survivorship_item(
            'CASE-ALPHA', self.plan, 'trigger', TRIGGER, self.source)
        self.store.review_survivorship_item('CASE-ALPHA', watch, REVIEWER, SCOPE)
        self.store.mark_survivorship_trigger(
            'CASE-ALPHA', trigger, 'A newer imaging source arrived in the fictional file.')
        for name, view in (('second-opinion', self.store.second_opinion_view('CASE-ALPHA')),
                           ('survivorship', self.store.survivorship_view('CASE-ALPHA'))):
            for text in walk_strings(view):
                self.assertIsNone(find_directed_language(text),
                                  f'{name} view carries directed wording: {text!r}')


class CareRecordHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / 'server.sqlite')
        seed(cls.path)
        bound = type('BoundHandlerForCareRecords', (Handler,), {'db_path': cls.path})
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), bound)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls._cookie = signin_demo(cls.port, cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def request(self, path, data=None):
        headers = {"Cookie": self._cookie}
        if data is not None:
            headers['Content-Type'] = 'application/json'
        req = Request(f'http://127.0.0.1:{self.port}{path}',
                      data=None if data is None else json.dumps(data).encode(),
                      headers=headers)
        try:
            with urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read())
        except HTTPError as err:
            return err.code, json.loads(err.read())

    def test_http_second_opinion_and_survivorship_flow(self):
        status, state = self.request('/api/cases/CASE-ALPHA/state')
        self.assertEqual(status, 200)
        source_id = [s['id'] for s in state['sources']
                     if s['document_id'] == 'PATH-ALPHA' and s['state'] == 'current'][0]
        status, data = self.request('/api/cases/CASE-ALPHA/questions', {'question': QUESTION})
        self.assertEqual(status, 201)
        question_id = data['question_id']
        status, data = self.request('/api/cases/CASE-ALPHA/second-opinion-requests', {
            'question_id': question_id, 'question_text': REQUEST_TEXT,
            'source_version_ids': [source_id]})
        self.assertEqual(status, 201)
        request_id = data['request_id']
        status, data = self.request(
            f'/api/cases/CASE-ALPHA/second-opinion-requests/{request_id}/response', {
                'responder_label': 'Fictional second reviewer', 'response_text': RESPONSE_TEXT,
                'anchor_source_version_id': source_id})
        self.assertEqual(status, 201)
        status, data = self.request(
            f'/api/cases/CASE-ALPHA/second-opinion-requests/{request_id}/review',
            {'reviewer_label': REVIEWER, 'scope': SCOPE})
        self.assertEqual(status, 200)
        self.assertEqual(data['result'], 'acknowledged_in_demo')
        status, data = self.request('/api/cases/CASE-ALPHA/survivorship-plans',
                                    {'title': PLAN_TITLE})
        self.assertEqual(status, 201)
        plan_id = data['plan_id']
        status, data = self.request(
            f'/api/cases/CASE-ALPHA/survivorship-plans/{plan_id}/items', {
                'kind': 'followup', 'description': FOLLOWUP,
                'anchor_source_version_id': source_id, 'recorded_date': '2026-09-01'})
        self.assertEqual(status, 201)
        followup_id = data['item_id']
        status, data = self.request(
            f'/api/cases/CASE-ALPHA/survivorship-plans/{plan_id}/items', {
                'kind': 'trigger', 'description': TRIGGER,
                'anchor_source_version_id': source_id})
        self.assertEqual(status, 201)
        trigger_id = data['item_id']
        status, data = self.request(
            f'/api/cases/CASE-ALPHA/survivorship-items/{followup_id}/review',
            {'reviewer_label': REVIEWER, 'scope': SCOPE})
        self.assertEqual(status, 200)
        status, data = self.request(
            f'/api/cases/CASE-ALPHA/survivorship-items/{trigger_id}/trigger',
            {'reason': 'A newer imaging source arrived in the fictional file.'})
        self.assertEqual(status, 200)
        self.assertEqual(data['result'], 'triggered')
        status, state = self.request('/api/cases/CASE-ALPHA/state')
        self.assertEqual(status, 200)
        requests = [r for r in state['second_opinions'] if r['id'] == request_id]
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]['review_state'], 'reviewed_in_demo')
        self.assertEqual(requests[0]['response']['response_text'], RESPONSE_TEXT)
        plans = [p for p in state['survivorship_plans'] if p['id'] == plan_id]
        self.assertEqual(len(plans), 1)
        self.assertEqual({i['state'] for i in plans[0]['items']}, {'recorded', 'triggered'})

    def test_http_directed_wording_rejected(self):
        status, state = self.request('/api/cases/CASE-ALPHA/state')
        source_id = [s['id'] for s in state['sources'] if s['state'] == 'current'][0]
        status, data = self.request('/api/cases/CASE-ALPHA/questions', {'question': QUESTION})
        question_id = data['question_id']
        status, error = self.request('/api/cases/CASE-ALPHA/second-opinion-requests', {
            'question_id': question_id,
            'question_text': 'The subject should return in six weeks for another visit.',
            'source_version_ids': [source_id]})
        self.assertEqual(status, 422)
        self.assertIn('must not direct care', error['error'])
        status, data = self.request('/api/cases/CASE-ALPHA/survivorship-plans',
                                    {'title': PLAN_TITLE})
        plan_id = data['plan_id']
        status, error = self.request(
            f'/api/cases/CASE-ALPHA/survivorship-plans/{plan_id}/items', {
                'kind': 'watch', 'description': 'Watch for fever in the coming days.',
                'anchor_source_version_id': source_id})
        self.assertEqual(status, 422)
        self.assertIn('must not direct care', error['error'])


if __name__ == '__main__':
    unittest.main()
