import json
import tempfile
import threading
import unittest
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

    def test_static_ui_and_csp(self):
        with urlopen(f'http://127.0.0.1:{self.port}/') as response:
            body = response.read().decode()
            self.assertIn('SYNTHETIC DATA ONLY', body)
            self.assertIn("default-src 'self'", response.headers['Content-Security-Policy'])


if __name__ == '__main__':
    unittest.main()
