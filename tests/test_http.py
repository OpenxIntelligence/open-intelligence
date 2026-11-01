import json
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence.__main__ import Handler, seed


class HttpTests(unittest.TestCase):
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

    def request(self, path, data=None, headers=None):
        values = {'Content-Type': 'application/json'} if data is not None else {}
        values.update(headers or {})
        request = Request(f'http://127.0.0.1:{self.port}{path}',
                          data=None if data is None else json.dumps(data).encode(), headers=values)
        try:
            with urlopen(request, timeout=5) as response:
                content = response.read()
                return response.status, json.loads(content) if 'json' in response.headers.get('Content-Type') else content
        except HTTPError as err:
            return err.code, json.loads(err.read())

    def test_source_and_state_api(self):
        status, data = self.request('/api/cases/CASE-ALPHA/state')
        self.assertEqual(status, 200)
        self.assertEqual(len(data['sources']), 2)
        sid = data['sources'][0]['id']
        status, raw = self.request(f'/api/cases/CASE-ALPHA/sources/{sid}')
        self.assertEqual(status, 200)
        self.assertIn('OI-SYNTHETIC-REPORT/1', raw['text'])
        status, other = self.request(f'/api/cases/CASE-BETA/sources/{sid}')
        self.assertEqual(status, 422)
        self.assertEqual(other['error'], 'Source not in this case')

    def test_unexpected_host_rejected_for_reads_and_writes(self):
        # A browser-controlled DNS name resolving to loopback must not become
        # a same-origin API entry point for this unauthenticated local demo.
        requests = [
            ('GET', '/api/cases', None),
            ('POST', '/api/cases/CASE-ALPHA/questions',
             json.dumps({'question': 'Should this foreign host be rejected?'})),
        ]
        for method, path, body in requests:
            with self.subTest(method=method):
                conn = HTTPConnection('127.0.0.1', self.port, timeout=5)
                try:
                    conn.request(method, path, body=body, headers={
                        'Host': 'untrusted.example:' + str(self.port),
                        'Content-Type': 'application/json',
                    })
                    response = conn.getresponse()
                    self.assertEqual(response.status, 403)
                    self.assertIn('Unexpected Host', response.read().decode())
                finally:
                    conn.close()

    def test_foreign_origin_cannot_post(self):
        status, error = self.request('/api/cases/CASE-ALPHA/questions',
                                     {'question': 'May foreign webpages write to the local demo?'},
                                     {'Origin': 'https://untrusted.example'})
        self.assertEqual(status, 403)
        self.assertIn('Cross-origin', error['error'])

    def test_create_question_through_api(self):
        status, result = self.request('/api/cases/CASE-ALPHA/questions',
                                      {'question': 'Does this synthetic record require expert review?'},
                                      {'Origin': f'http://127.0.0.1:{self.port}'})
        self.assertEqual(status, 201)
        self.assertIsInstance(result['question_id'], int)
        status, data = self.request('/api/cases/CASE-ALPHA/state')
        self.assertIn(result['question_id'], [q['id'] for q in data['questions']])


    def test_bibliography_fixture_and_default_egress_gate(self):
        status, config = self.request('/api/bibliography/status')
        self.assertEqual(status, 200)
        self.assertEqual(config, {'live_enabled': False})
        status, record = self.request('/api/bibliography/example')
        self.assertEqual(status, 200)
        self.assertEqual(record['kind'], 'bibliographic_metadata_only')
        self.assertEqual(record['doi'], '10.5555/oi-synthetic-001')
        self.assertFalse(record['clinical_evidence_appraised'])
        self.assertNotIn('COPYRIGHTED ABSTRACT', json.dumps(record))
        with patch('open_intelligence.__main__.fetch_public_doi',
                   side_effect=AssertionError('No outbound calls when disabled')) as mock_fetch:
            status, error = self.request('/api/bibliography/lookup',
                                         {'doi': '10.5555/oi-synthetic-001'})
            self.assertEqual(status, 403)
            self.assertIn('disabled by default', error['error'])
            mock_fetch.assert_not_called()

    def test_wrong_patient_example_serves_declared_other_case(self):
        status, record = self.request('/api/examples/wrong-patient')
        self.assertEqual(status, 200)
        self.assertIn('Patient: CASE-BETA', record['text'])
        self.assertIn('PATH-OTHER', record['text'])

    def test_bibliography_live_gate_passes_only_doi_and_is_operator_controlled(self):
        handler = self.server.RequestHandlerClass
        prior = handler.allow_crossref_live
        last_request = handler.metadata_last_request
        handler.allow_crossref_live = True
        handler.metadata_last_request = 0.0
        try:
            with patch('open_intelligence.__main__.fetch_public_doi',
                       return_value={'kind': 'bibliographic_metadata_only',
                                     'doi': '10.5555/oi-synthetic-001',
                                     'clinical_evidence_appraised': False}) as mock_fetch:
                status, record = self.request('/api/bibliography/lookup',
                                             {'doi': '10.5555/oi-synthetic-001',
                                              'patient_id': 'MUST-NOT-EGRESS',
                                              'question': 'MUST-NOT-EGRESS'})
                self.assertEqual(status, 200)
                mock_fetch.assert_called_once_with('10.5555/oi-synthetic-001', contact=None)
                self.assertNotIn('MUST-NOT-EGRESS', json.dumps(record))
                status, error = self.request('/api/bibliography/lookup',
                                             {'doi': '10.5555/oi-synthetic-001'})
                self.assertEqual(status, 429)
        finally:
            handler.allow_crossref_live = prior
            handler.metadata_last_request = last_request

    def test_static_ui_and_csp(self):
        with urlopen(f'http://127.0.0.1:{self.port}/') as response:
            body = response.read().decode()
            self.assertIn('FICTIONAL DEMO DATA — not a real patient', body)
            self.assertIn("default-src 'self'", response.headers['Content-Security-Policy'])
            # The incoming board and patient view are derived presentations of
            # the same case state, not separate data: both must be served.
            self.assertIn('id="incoming-board"', body)
            self.assertIn('id="patient-view"', body)
        for name in ('style.css', 'tokens.css', 'base.css'):
            with urlopen(f'http://127.0.0.1:{self.port}/{name}') as response:
                self.assertEqual(response.headers.get('Content-Type'), 'text/css; charset=utf-8')
                self.assertTrue(response.read().decode('utf-8').strip())


if __name__ == '__main__':
    unittest.main()
