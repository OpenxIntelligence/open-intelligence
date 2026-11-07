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

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / 'examples' / 'synthetic'


def report(name):
    return (SAMPLE / name).read_bytes()


QUESTION = 'What did the first fictional pathology report conclude?'
REASON = 'A human reviewer recorded this status change.'
ANSWER = 'The fictional report describes a pending classification awaiting review.'


class WorkspaceStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / 'test.sqlite'
        self.store = CaseStore(self.db_path)
        self.store.add_case('CASE-ALPHA', 'Fictional Alpha')
        self.store.add_case('CASE-BETA', 'Fictional Beta')

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_create_link_answer_amend_reopens_with_history(self):
        original = self.store.import_report('CASE-ALPHA', report('alpha-pathology-original.txt'))
        qid = self.store.create_workspace_question('CASE-ALPHA', QUESTION)
        created = self.store.list_workspace_questions('CASE-ALPHA')
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0]['status'], 'open')
        self.assertIsNone(created[0]['answer'])
        self.assertEqual(created[0]['created_date'], created[0]['created_at'][:10])
        self.assertEqual(len(created[0]['history']), 1)
        self.assertIsNone(created[0]['history'][0]['previous_status'])
        self.assertEqual(created[0]['history'][0]['new_status'], 'open')
        link_id = self.store.link_workspace_source('CASE-ALPHA', qid, original['source_id'])
        self.assertIsInstance(link_id, int)
        linked = self.store.list_workspace_questions('CASE-ALPHA')[0]
        self.assertEqual(len(linked['links']), 1)
        self.assertEqual(linked['links'][0]['source_anchor'], 'PATH-ALPHA@1')
        self.assertEqual(linked['links'][0]['state'], 'active')
        self.assertEqual(linked['links'][0]['source_state'], 'current')
        outcome = self.store.set_workspace_question_status('CASE-ALPHA', qid, 'answered', REASON, ANSWER)
        self.assertEqual(outcome['status'], 'answered')
        self.assertEqual(outcome['previous_status'], 'open')
        answered = self.store.list_workspace_questions('CASE-ALPHA')[0]
        self.assertEqual(answered['answer'], ANSWER)
        update = self.store.import_report('CASE-ALPHA', report('alpha-pathology-amended.txt'))
        self.assertEqual(update['invalidated_workspace_questions'], [qid])
        reopened = self.store.list_workspace_questions('CASE-ALPHA')[0]
        self.assertEqual(reopened['status'], 'needs_review')
        self.assertIsNone(reopened['answer'])
        answered_entries = [h for h in reopened['history'] if h['new_status'] == 'answered']
        self.assertEqual([h['answer'] for h in answered_entries], [ANSWER])
        self.assertEqual(reopened['history'][-1]['new_status'], 'needs_review')
        self.assertEqual([h['new_status'] for h in reopened['history']],
                         ['open', 'answered', 'needs_review'])
        self.assertEqual([h['previous_status'] for h in reopened['history']],
                         [None, 'open', 'answered'])
        self.assertIn('amended', reopened['history'][-1]['reason'])
        self.assertEqual(reopened['history'][-1]['answer'], ANSWER)
        self.assertEqual(len(reopened['links']), 1)
        self.assertEqual(reopened['links'][0]['source_anchor'], 'PATH-ALPHA@1')
        self.assertEqual(reopened['links'][0]['source_state'], 'superseded')
        self.assertEqual(reopened['links'][0]['state'], 'active')
        # The user can link the replacement version and record a fresh answer.
        replacement = self.store.link_workspace_source('CASE-ALPHA', qid, update['source_id'])
        self.assertNotEqual(replacement, link_id)
        self.store.set_workspace_question_status('CASE-ALPHA', qid, 'answered', REASON,
                                                 'The amended fictional report was reviewed again.')
        final = self.store.list_workspace_questions('CASE-ALPHA')[0]
        self.assertEqual(final['status'], 'answered')
        self.assertEqual(len(final['links']), 2)
        self.assertEqual(len(final['history']), 4)

    def test_status_change_requires_a_reason(self):
        self.store.import_report('CASE-ALPHA', report('alpha-pathology-original.txt'))
        qid = self.store.create_workspace_question('CASE-ALPHA', QUESTION)
        for bad in (None, '', '   ', 'no'):
            with self.subTest(reason=bad):
                with self.assertRaisesRegex(InvalidInput, 'reason'):
                    self.store.set_workspace_question_status('CASE-ALPHA', qid, 'in_progress', bad)
        self.assertEqual(self.store.list_workspace_questions('CASE-ALPHA')[0]['status'], 'open')
        self.store.set_workspace_question_status('CASE-ALPHA', qid, 'in_progress', REASON)
        self.assertEqual(self.store.list_workspace_questions('CASE-ALPHA')[0]['status'], 'in_progress')

    def test_answer_rules(self):
        self.store.import_report('CASE-ALPHA', report('alpha-pathology-original.txt'))
        qid = self.store.create_workspace_question('CASE-ALPHA', QUESTION)
        with self.assertRaisesRegex(InvalidInput, 'Unknown investigation question status'):
            self.store.set_workspace_question_status('CASE-ALPHA', qid, 'closed', REASON)
        for bad_status in (None, 7, ['answered'], {'status': 'open'}):
            with self.subTest(status=bad_status):
                with self.assertRaisesRegex(InvalidInput, 'Unknown investigation question status'):
                    self.store.set_workspace_question_status('CASE-ALPHA', qid, bad_status, REASON)
        with self.assertRaisesRegex(InvalidInput, 'recorded answer'):
            self.store.set_workspace_question_status('CASE-ALPHA', qid, 'answered', REASON)
        with self.assertRaisesRegex(InvalidInput, 'recorded answer'):
            self.store.set_workspace_question_status('CASE-ALPHA', qid, 'answered', REASON, 'too short')
        with self.assertRaisesRegex(InvalidInput, 'only accepted when marking'):
            self.store.set_workspace_question_status('CASE-ALPHA', qid, 'in_progress', REASON, ANSWER)
        with self.assertRaisesRegex(InvalidInput, 'already has this status'):
            self.store.set_workspace_question_status('CASE-ALPHA', qid, 'open', REASON)
        self.store.set_workspace_question_status('CASE-ALPHA', qid, 'answered', REASON, ANSWER)
        with self.assertRaisesRegex(InvalidInput, 'already has this status and answer'):
            self.store.set_workspace_question_status('CASE-ALPHA', qid, 'answered', REASON, ANSWER)
        self.store.set_workspace_question_status('CASE-ALPHA', qid, 'answered', REASON,
                                                 'A revised fictional answer after review.')
        revised = self.store.list_workspace_questions('CASE-ALPHA')[0]
        self.assertEqual(revised['answer'], 'A revised fictional answer after review.')
        self.assertEqual([h['answer'] for h in revised['history'] if h['new_status'] == 'answered'],
                         [ANSWER, 'A revised fictional answer after review.'])

    def test_unanswered_questions_never_expose_an_answer(self):
        self.store.import_report('CASE-ALPHA', report('alpha-pathology-original.txt'))
        qid = self.store.create_workspace_question('CASE-ALPHA', QUESTION)
        self.store.set_workspace_question_status('CASE-ALPHA', qid, 'in_progress', REASON)
        listed = self.store.list_workspace_questions('CASE-ALPHA')[0]
        self.assertIsNone(listed['answer'])
        self.assertTrue(all(h['answer'] is None for h in listed['history']))
        self.store.set_workspace_question_status('CASE-ALPHA', qid, 'answered', REASON, ANSWER)
        self.store.set_workspace_question_status('CASE-ALPHA', qid, 'in_progress', REASON)
        moved_back = self.store.list_workspace_questions('CASE-ALPHA')[0]
        self.assertEqual(moved_back['status'], 'in_progress')
        self.assertIsNone(moved_back['answer'])
        self.assertEqual([h['answer'] for h in moved_back['history'] if h['new_status'] == 'answered'],
                         [ANSWER])

    def test_amendment_never_auto_answers_and_ignores_unlinked(self):
        original = self.store.import_report('CASE-ALPHA', report('alpha-pathology-original.txt'))
        linked_answered = self.store.create_workspace_question('CASE-ALPHA', QUESTION)
        linked_open = self.store.create_workspace_question('CASE-ALPHA', 'Which fictional finding is still open?')
        linked_progress = self.store.create_workspace_question('CASE-ALPHA', 'Which fictional finding is in progress?')
        unlinked_answered = self.store.create_workspace_question('CASE-ALPHA', 'Which fictional finding was unlinked?')
        for target in (linked_answered, linked_open, linked_progress, unlinked_answered):
            self.store.link_workspace_source('CASE-ALPHA', target, original['source_id'])
        self.store.set_workspace_question_status('CASE-ALPHA', linked_answered, 'answered', REASON, ANSWER)
        self.store.set_workspace_question_status('CASE-ALPHA', linked_progress, 'in_progress', REASON)
        self.store.set_workspace_question_status('CASE-ALPHA', unlinked_answered, 'answered', REASON, ANSWER)
        listed = self.store.list_workspace_questions('CASE-ALPHA')
        stale_link = [q for q in listed if q['id'] == unlinked_answered][0]['links'][0]['id']
        self.store.unlink_workspace_source('CASE-ALPHA', unlinked_answered, stale_link)
        update = self.store.import_report('CASE-ALPHA', report('alpha-pathology-amended.txt'))
        self.assertEqual(update['invalidated_workspace_questions'], [linked_answered])
        by_id = {q['id']: q for q in self.store.list_workspace_questions('CASE-ALPHA')}
        self.assertEqual(by_id[linked_answered]['status'], 'needs_review')
        self.assertEqual(by_id[linked_open]['status'], 'open')
        self.assertEqual(by_id[linked_progress]['status'], 'in_progress')
        self.assertEqual(by_id[unlinked_answered]['status'], 'answered')
        self.assertEqual(by_id[unlinked_answered]['answer'], ANSWER)

    def test_links_are_append_only_and_version_pinned(self):
        original = self.store.import_report('CASE-ALPHA', report('alpha-pathology-original.txt'))
        qid = self.store.create_workspace_question('CASE-ALPHA', QUESTION)
        first = self.store.link_workspace_source('CASE-ALPHA', qid, original['source_id'])
        with self.assertRaisesRegex(InvalidInput, 'already linked'):
            self.store.link_workspace_source('CASE-ALPHA', qid, original['source_id'])
        outcome = self.store.unlink_workspace_source('CASE-ALPHA', qid, first)
        self.assertEqual(outcome, {'result': 'unlinked', 'link_id': first})
        with self.assertRaisesRegex(InvalidInput, 'already superseded'):
            self.store.unlink_workspace_source('CASE-ALPHA', qid, first)
        superseded = self.store.list_workspace_questions('CASE-ALPHA')[0]['links']
        self.assertEqual(len(superseded), 1)
        self.assertEqual(superseded[0]['state'], 'superseded')
        self.assertIsNotNone(superseded[0]['superseded_at'])
        second = self.store.link_workspace_source('CASE-ALPHA', qid, original['source_id'])
        self.assertNotEqual(second, first)
        self.assertEqual(len(self.store.list_workspace_questions('CASE-ALPHA')[0]['links']), 2)
        update = self.store.import_report('CASE-ALPHA', report('alpha-pathology-amended.txt'))
        fresh = self.store.create_workspace_question('CASE-ALPHA', 'Can a superseded version be linked?')
        with self.assertRaisesRegex(InvalidInput, 'Only a current source version'):
            self.store.link_workspace_source('CASE-ALPHA', fresh, original['source_id'])
        self.store.link_workspace_source('CASE-ALPHA', fresh, update['source_id'])
        with self.assertRaisesRegex(InvalidInput, 'Source version not in this case'):
            self.store.link_workspace_source('CASE-ALPHA', fresh, 999)
        with self.assertRaisesRegex(InvalidInput, 'positive integer'):
            self.store.link_workspace_source('CASE-ALPHA', fresh, '1')

    def test_case_isolation(self):
        alpha = self.store.import_report('CASE-ALPHA', report('alpha-pathology-original.txt'))
        beta = self.store.import_report('CASE-BETA', report('beta-pathology.txt'))
        alpha_q = self.store.create_workspace_question('CASE-ALPHA', QUESTION)
        beta_q = self.store.create_workspace_question('CASE-BETA', 'What is uncertain in the fictional beta case?')
        self.store.link_workspace_source('CASE-ALPHA', alpha_q, alpha['source_id'])
        self.store.link_workspace_source('CASE-BETA', beta_q, beta['source_id'])
        self.store.set_workspace_question_status('CASE-ALPHA', alpha_q, 'answered', REASON, ANSWER)
        self.store.set_workspace_question_status('CASE-BETA', beta_q, 'answered', REASON, ANSWER)
        self.assertEqual([q['id'] for q in self.store.list_workspace_questions('CASE-BETA')], [beta_q])
        with self.assertRaisesRegex(InvalidInput, 'Source version not in this case'):
            self.store.link_workspace_source('CASE-ALPHA', alpha_q, beta['source_id'])
        with self.assertRaisesRegex(InvalidInput, 'not in this case'):
            self.store.set_workspace_question_status('CASE-BETA', alpha_q, 'open', REASON)
        with self.assertRaisesRegex(InvalidInput, 'Link not found'):
            self.store.unlink_workspace_source('CASE-BETA', beta_q, 1)
        update = self.store.import_report('CASE-ALPHA', report('alpha-pathology-amended.txt'))
        self.assertEqual(update['invalidated_workspace_questions'], [alpha_q])
        beta_state = self.store.list_workspace_questions('CASE-BETA')[0]
        self.assertEqual(beta_state['status'], 'answered')
        self.assertEqual(beta_state['answer'], ANSWER)

    def test_unknown_case_rejected(self):
        with self.assertRaisesRegex(InvalidInput, 'Unknown case'):
            self.store.create_workspace_question('CASE-NOPE', QUESTION)
        with self.assertRaisesRegex(InvalidInput, 'Unknown case'):
            self.store.list_workspace_questions('CASE-NOPE')
        with self.assertRaisesRegex(InvalidInput, 'Unknown case'):
            self.store.link_workspace_source('CASE-NOPE', 1, 1)
        with self.assertRaisesRegex(InvalidInput, 'Unknown case'):
            self.store.unlink_workspace_source('CASE-NOPE', 1, 1)
        with self.assertRaisesRegex(InvalidInput, 'Unknown case'):
            self.store.set_workspace_question_status('CASE-NOPE', 1, 'open', REASON)


class WorkspaceHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / 'server.sqlite')
        seed(cls.path)
        bound_handler = type('BoundHandlerForWorkspaceTest', (Handler,), {'db_path': cls.path})
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), bound_handler)
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
        values = {"Cookie": self._cookie}
        if data is not None:
            values['Content-Type'] = 'application/json'
        if data is not None:
            values['Origin'] = f'http://127.0.0.1:{self.port}'
        request = Request(f'http://127.0.0.1:{self.port}{path}',
                          data=None if data is None else json.dumps(data).encode(), headers=values)
        try:
            with urlopen(request, timeout=5) as response:
                content = response.read()
                return response.status, json.loads(content) if 'json' in response.headers.get('Content-Type') else content
        except HTTPError as err:
            return err.code, json.loads(err.read())

    def current_source(self, case_id, document_id=None):
        status, state = self.request(f'/api/cases/{case_id}/state')
        self.assertEqual(status, 200)
        current = [s for s in state['sources'] if s['state'] == 'current']
        if document_id is not None:
            current = [s for s in current if s['document_id'] == document_id]
        self.assertTrue(current)
        return current[0]

    def test_amendment_reopens_over_http(self):
        status, example = self.request('/api/examples/amendment')
        self.assertEqual(status, 200)
        status, created = self.request('/api/cases/CASE-ALPHA/workspace-questions', {'question': QUESTION})
        self.assertEqual(status, 201)
        qid = created['workspace_question_id']
        pathology = self.current_source('CASE-ALPHA', 'PATH-ALPHA')
        status, linked = self.request(f'/api/cases/CASE-ALPHA/workspace-questions/{qid}/links',
                                      {'source_version_id': pathology['id']})
        self.assertEqual(status, 201)
        self.assertIsInstance(linked['link_id'], int)
        status, answered = self.request(f'/api/cases/CASE-ALPHA/workspace-questions/{qid}/status',
                                        {'status': 'answered', 'reason': REASON, 'answer': ANSWER})
        self.assertEqual(status, 200)
        self.assertEqual(answered['status'], 'answered')
        status, update = self.request('/api/cases/CASE-ALPHA/imports', {'text': example['text']})
        self.assertEqual(status, 200)
        self.assertEqual(update['result'], 'imported')
        status, listed = self.request('/api/cases/CASE-ALPHA/workspace-questions')
        self.assertEqual(status, 200)
        mine = [q for q in listed['workspace_questions'] if q['id'] == qid][0]
        self.assertEqual(mine['status'], 'needs_review')
        self.assertIsNone(mine['answer'])
        self.assertEqual([h['answer'] for h in mine['history'] if h['new_status'] == 'answered'], [ANSWER])
        self.assertEqual(mine['links'][0]['source_anchor'], 'PATH-ALPHA@1')

    def test_create_and_list_roundtrip(self):
        status, created = self.request('/api/cases/CASE-ALPHA/workspace-questions', {'question': QUESTION})
        self.assertEqual(status, 201)
        self.assertIsInstance(created['workspace_question_id'], int)
        status, listed = self.request('/api/cases/CASE-ALPHA/workspace-questions')
        self.assertEqual(status, 200)
        mine = [q for q in listed['workspace_questions'] if q['id'] == created['workspace_question_id']][0]
        self.assertEqual(mine['status'], 'open')
        self.assertIsNone(mine['answer'])
        self.assertEqual(mine['created_date'], mine['created_at'][:10])
        self.assertEqual(mine['history'][0]['new_status'], 'open')
        self.assertEqual(mine['links'], [])

    def test_cross_case_link_rejected(self):
        beta_source = self.current_source('CASE-BETA')
        status, created = self.request('/api/cases/CASE-ALPHA/workspace-questions', {'question': QUESTION})
        self.assertEqual(status, 201)
        status, error = self.request(
            f'/api/cases/CASE-ALPHA/workspace-questions/{created["workspace_question_id"]}/links',
            {'source_version_id': beta_source['id']})
        self.assertEqual(status, 422)
        self.assertEqual(error['error'], 'Source version not in this case')

    def test_link_and_unlink_roundtrip(self):
        status, created = self.request('/api/cases/CASE-ALPHA/workspace-questions', {'question': QUESTION})
        qid = created['workspace_question_id']
        source = self.current_source('CASE-ALPHA')
        status, linked = self.request(f'/api/cases/CASE-ALPHA/workspace-questions/{qid}/links',
                                      {'source_version_id': source['id']})
        self.assertEqual(status, 201)
        status, duplicate = self.request(f'/api/cases/CASE-ALPHA/workspace-questions/{qid}/links',
                                         {'source_version_id': source['id']})
        self.assertEqual(status, 422)
        self.assertIn('already linked', duplicate['error'])
        status, unlinked = self.request(
            f'/api/cases/CASE-ALPHA/workspace-questions/{qid}/links/{linked["link_id"]}/unlink', {})
        self.assertEqual(status, 200)
        self.assertEqual(unlinked['result'], 'unlinked')
        status, listed = self.request('/api/cases/CASE-ALPHA/workspace-questions')
        mine = [q for q in listed['workspace_questions'] if q['id'] == qid][0]
        self.assertEqual(mine['links'][0]['state'], 'superseded')
        self.assertIsNotNone(mine['links'][0]['superseded_at'])

    def test_status_requires_reason_over_http(self):
        status, created = self.request('/api/cases/CASE-ALPHA/workspace-questions', {'question': QUESTION})
        qid = created['workspace_question_id']
        status, error = self.request(f'/api/cases/CASE-ALPHA/workspace-questions/{qid}/status',
                                     {'status': 'in_progress'})
        self.assertEqual(status, 422)
        self.assertIn('reason', error['error'])
        status, error = self.request(f'/api/cases/CASE-ALPHA/workspace-questions/{qid}/status',
                                     {'status': 'in_progress', 'reason': '  '})
        self.assertEqual(status, 422)
        status, error = self.request(f'/api/cases/CASE-ALPHA/workspace-questions/{qid}/status',
                                     {'status': 'answered', 'reason': REASON})
        self.assertEqual(status, 422)
        status, moved = self.request(f'/api/cases/CASE-ALPHA/workspace-questions/{qid}/status',
                                     {'status': 'in_progress', 'reason': REASON})
        self.assertEqual(status, 200)
        self.assertEqual(moved['status'], 'in_progress')

    def test_unknown_case_returns_422(self):
        status, error = self.request('/api/cases/CASE-NOPE/workspace-questions')
        self.assertEqual(status, 422)
        self.assertEqual(error['error'], 'Unknown case')
        status, error = self.request('/api/cases/CASE-NOPE/workspace-questions', {'question': QUESTION})
        self.assertEqual(status, 422)
        self.assertEqual(error['error'], 'Unknown case')
        status, error = self.request('/api/cases/CASE-NOPE/workspace-questions/1/status',
                                     {'status': 'open', 'reason': REASON})
        self.assertEqual(status, 422)
        self.assertEqual(error['error'], 'Unknown case')
        status, error = self.request('/api/cases/CASE-NOPE/workspace-questions/1/links',
                                     {'source_version_id': 1})
        self.assertEqual(status, 422)
        self.assertEqual(error['error'], 'Unknown case')
        status, error = self.request('/api/cases/CASE-NOPE/workspace-questions/1/links/1/unlink', {})
        self.assertEqual(status, 422)
        self.assertEqual(error['error'], 'Unknown case')


class WorkspaceUiContractTests(unittest.TestCase):
    def test_panel_markup_exists(self):
        html = (ROOT / 'web' / 'index.html').read_text()
        self.assertIn('href="#workspace-investigations"', html)
        self.assertIn('id="workspace-investigations"', html)
        self.assertIn('id="workspace-question-form"', html)
        self.assertIn('id="workspace-question-text"', html)
        self.assertIn('id="workspace-link-form"', html)
        self.assertIn('id="workspace-link-question"', html)
        self.assertIn('id="workspace-link-source"', html)
        self.assertIn('id="workspace-status-form"', html)
        self.assertIn('id="workspace-status-question"', html)
        self.assertIn('id="workspace-status-value"', html)
        self.assertIn('id="workspace-status-reason"', html)
        self.assertIn('id="workspace-status-answer"', html)
        self.assertIn('id="workspace-question-list"', html)
        self.assertIn('FICTIONAL DEMO QUESTIONS ONLY', html)
        self.assertIn('never answered by the system', html)

    def test_renderer_is_case_scoped_answer_safe_and_text_only(self):
        javascript = (ROOT / 'web' / 'app.js').read_text()
        self.assertIn("'/api/cases/' + requested + '/workspace-questions'", javascript)
        self.assertIn('loadWorkspaceQuestions', javascript)
        self.assertIn('renderWorkspaceQuestions', javascript)
        self.assertIn("item.status === 'answered' && item.answer", javascript)
        self.assertIn('No recorded answer.', javascript)
        self.assertIn('Earlier recorded answer (kept for review)', javascript)
        self.assertIn("'/links/' + link.id + '/unlink'", javascript)
        self.assertIn('workspace-status-reason', javascript)
        self.assertIn('workspace-status-answer', javascript)
        self.assertNotIn('innerHTML', javascript)

    def test_server_routes_exist(self):
        server = (ROOT / 'src' / 'open_intelligence' / '__main__.py').read_text()
        self.assertIn('workspace-questions', server)
        self.assertIn('list_workspace_questions', server)
        self.assertIn('create_workspace_question', server)
        self.assertIn('link_workspace_source', server)
        self.assertIn('unlink_workspace_source', server)
        self.assertIn('set_workspace_question_status', server)


if __name__ == '__main__':
    unittest.main()
