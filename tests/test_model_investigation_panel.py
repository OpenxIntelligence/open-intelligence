"""Tests for the model-assisted investigation panel (stacked on OI-008).

The panel is a presentation layer over the existing investigation
endpoints: it adds no backend contract, no free-text model prompt, and
no new store. Live model calls are not made here; replay mode covers
the full panel flow deterministically.
"""

import json
import re
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence.__main__ import Handler, seed


class PanelHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = str(Path(cls.tmp.name) / 'server.sqlite')
        seed(cls.path)
        bound = type('BoundHandlerForPanel', (Handler,), {'db_path': cls.path})
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), bound)
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
        values = {'Content-Type': 'application/json'} if data is not None else {}
        request = Request(f'http://127.0.0.1:{self.port}{path}',
                          data=None if data is None else json.dumps(data).encode(),
                          headers=values)
        try:
            with urlopen(request, timeout=10) as response:
                raw = response.read()
                try:
                    return response.status, json.loads(raw)
                except ValueError:
                    return response.status, raw.decode()
        except HTTPError as err:
            return err.code, json.loads(err.read())

    def test_panel_markup_has_selects_only_and_disclaimer(self):
        status, html = self.request('/')
        self.assertEqual(status, 200)
        for element_id in ('model-investigation-form', 'model-investigation-question',
                           'model-investigation-template', 'model-investigation-mode',
                           'model-investigation-list'):
            self.assertIn(f'id="{element_id}"', html)
        self.assertIn('Research demonstration only', html)
        form = re.search(r'<form id="model-investigation-form">(.*?)</form>',
                         html, re.DOTALL).group(1)
        self.assertNotIn('<textarea', form)
        self.assertNotIn('type="text"', form)
        self.assertNotIn('prompt', form.lower())

    def test_replay_flow_visible_through_list_and_detail(self):
        status, question = self.request('/api/cases/CASE-ALPHA/questions',
                                        {'question': 'What do the sources report?'})
        self.assertEqual(status, 201)
        status, created = self.request('/api/cases/CASE-ALPHA/investigations',
                                       {'question_id': question['question_id'],
                                        'template': 'evidence-summary', 'mode': 'replay'})
        self.assertEqual(status, 201, created)
        self.assertEqual(created['kind'], 'hypothesis')
        self.assertEqual(created['review_state'], 'pending')
        status, listed = self.request('/api/cases/CASE-ALPHA/investigations')
        self.assertEqual(status, 200)
        self.assertTrue(any(item['id'] == created['id']
                            for item in listed['investigations']))
        status, detail = self.request(
            f"/api/cases/CASE-ALPHA/investigations/{created['id']}")
        self.assertEqual(status, 200)
        self.assertEqual(detail['kind'], 'hypothesis')
        self.assertEqual(detail['review_state'], 'pending')
        self.assertIn('Research demonstration only', detail['disclaimer'])
        self.assertTrue(detail['claims'])
        for claim in detail['claims']:
            self.assertIn(claim['uncertainty'], ('low', 'moderate', 'high'))
            self.assertTrue(claim['citations'])


if __name__ == '__main__':
    unittest.main()
