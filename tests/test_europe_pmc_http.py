"""Local HTTP and actual UI-function tests; Europe PMC traffic uses doubles."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from open_intelligence.__main__ import Handler
from tools import europe_pmc_metadata as metadata
from test_europe_pmc_metadata import Response, Transport, provider_fixture

ROOT = Path(__file__).resolve().parents[1]
BASE = "/api/bibliography/europe-pmc"


class EuropePMCHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.db = str(Path(cls.tmp.name) / "unused.sqlite")
        cls.handler = type("EuropePMCHandler", (Handler,), {"db_path": cls.db})
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), cls.handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def setUp(self):
        self.handler.allow_europe_pmc_live = False
        patcher = patch.object(metadata, "_last_request_at", None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def request(self, path, body=None, origin=None):
        headers = {"Content-Type": "application/json"} if body is not None else {}
        if origin:
            headers["Origin"] = origin
        request = Request(f"http://127.0.0.1:{self.port}{path}",
                          data=json.dumps(body).encode() if body is not None else None,
                          headers=headers)
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except HTTPError as error:
            return error.code, json.loads(error.read())

    def test_status_and_example_work_without_live_access_or_a_database(self):
        with patch.object(metadata, "build_opener", side_effect=AssertionError("No outbound access")):
            status, result = self.request(BASE + "/status")
            self.assertEqual(status, 200)
            self.assertFalse(result["live_enabled"])
            status, result = self.request(BASE + "/example")
            self.assertEqual(status, 200)
            self.assertEqual(result["mode"], "offline_demo")
            self.assertEqual(result["results"][0]["source"], "DEMO")
        self.assertFalse(Path(self.db).exists(), "Discovery must not open a new ledger")

    def test_live_is_disabled_before_any_outbound_request(self):
        with patch.object(metadata, "build_opener", side_effect=AssertionError("No outbound access")):
            status, result = self.request(BASE + "/search", {"topic": "melanoma"})
        self.assertEqual(status, 403)
        self.assertIn("disabled", result["error"])

    def test_enabled_http_flow_uses_the_real_projection_without_persistence(self):
        self.handler.allow_europe_pmc_live = True
        transport = Transport(Response(json.dumps(provider_fixture()).encode()))
        with patch.object(metadata, "build_opener", return_value=transport):
            status, result = self.request(BASE + "/search", {"topic": "melanoma", "page_size": 2})
            self.assertEqual(status, 200, result)
            self.assertEqual(result["mode"], "live")
            self.assertEqual(result["results"][0]["id"], "999000001")
            self.assertEqual(result["provenance"]["rights_status"], "unassessed")
            self.assertFalse(result["saved_to_ledger"])
            self.assertNotIn("ABSTRACT-MUST-NOT-PASS", json.dumps(result))
            status, result = self.request(BASE + "/search", {"topic": "melanoma"})
            self.assertEqual(status, 429)
        self.assertEqual(len(transport.requests), 1)
        self.assertFalse(Path(self.db).exists())

    def test_unknown_fields_and_invalid_types_never_reach_the_provider(self):
        self.handler.allow_europe_pmc_live = True
        with patch.object(metadata, "build_opener", side_effect=AssertionError("Invalid input must not egress")):
            for body in ({"topic": "melanoma", "patient_id": "MUST-NOT-SEND"},
                         {"topic": "melanoma", "query": "SRC:PPR"},
                         {"topic": "melanoma", "page_size": True},
                         {"topic": "melanoma", "start_date": "2025-01-01"},
                         {"topic": "melanoma\npatient narrative"}):
                with self.subTest(body=body):
                    status, result = self.request(BASE + "/search", body)
                    self.assertEqual(status, 422, result)
                    self.assertNotIn("MUST-NOT-SEND", json.dumps(result))

    def test_oversized_json_integer_is_rejected_before_provider_access(self):
        self.handler.allow_europe_pmc_live = True
        body = b'{"topic":"melanoma","page_size":' + b"9" * 5000 + b"}"
        request = Request(f"http://127.0.0.1:{self.port}{BASE}/search", data=body,
                          headers={"Content-Type": "application/json"})
        with patch.object(metadata, "build_opener", side_effect=AssertionError("Invalid input must not egress")):
            with self.assertRaises(HTTPError) as caught:
                urlopen(request, timeout=5)
        with caught.exception as response:
            self.assertEqual(response.code, 422)
            self.assertEqual(json.loads(response.read()), {"error": "Invalid JSON body"})

    def test_upstream_empty_envelope_is_a_failure_not_an_empty_result(self):
        self.handler.allow_europe_pmc_live = True
        transport = Transport(Response(b'{"version":"6.9"}'))
        with patch.object(metadata, "build_opener", return_value=transport):
            status, result = self.request(BASE + "/search", {"topic": "melanoma"})
        self.assertEqual(status, 502)
        self.assertIn("error", result)
        self.assertNotIn("results", result)

    def test_foreign_origin_cannot_trigger_live_search(self):
        self.handler.allow_europe_pmc_live = True
        with patch.object(metadata, "build_opener", side_effect=AssertionError("No cross-origin egress")):
            status, result = self.request(BASE + "/search", {"topic": "melanoma"},
                                          origin="https://untrusted.example")
        self.assertEqual(status, 403)


@unittest.skipUnless(shutil.which("node"), "Node is not installed")
class EuropePMCUIBehaviorTests(unittest.TestCase):
    def test_actual_panel_functions_gate_requests_and_render_live_results_as_data(self):
        script = r'''
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const app = fs.readFileSync('web/app.js', 'utf8');
const start = app.indexOf('let europePmcEnabled = false;');
const end = app.indexOf("el('timeline-filter').addEventListener", start);
assert.ok(start >= 0 && end > start, 'Europe PMC panel is not implemented');
function element(tag = 'div') {
  return {tag, children: [], _text: '', value: '', disabled: true, events: {},
    get textContent() { return this._text + this.children.map(x => x.textContent).join(''); },
    set textContent(value) { this._text = String(value); this.children = []; },
    set innerHTML(value) { throw Error('Provider data must not be rendered as HTML'); },
    append(...items) { this.children.push(...items); },
    replaceChildren() { this._text = ''; this.children = []; },
    addEventListener(name, listener) { this.events[name] = listener; },
    setAttribute(name, value) { this[name] = value; }};
}
const nodes = new Map(), requests = [], notices = [];
const el = id => { if (!nodes.has(id)) nodes.set(id, element()); return nodes.get(id); };
let enabled = false;
const page = {mode: 'live', returned_count: 1, hit_count: 3, has_more: true,
  provenance: {provider: 'Europe PMC REST API', retrieved_at: '2026-11-02T12:00:00Z',
    query_fingerprint: 'abc123', rights_status: 'unassessed'},
  results: [{source: 'MED', id: '999000001', title: '<script>citation text</script>',
    authors: 'Example A', year: 2025, journal: 'Authored fixture',
    canonical_url: 'https://untrusted.example', metadata_sha256: 'def456'}]};
const ctx = vm.createContext({el, node: (tag, text, className) => {
    const item = element(tag); if (text != null) item.textContent = text;
    item.className = className; return item; },
  clear: id => el(id).replaceChildren(), document: {createElement: element},
  notice: (message, error) => notices.push({message, error}),
  caseId: 'CASE-MUST-NOT-EGRESS', active: {secret: 'CONTEXT-MUST-NOT-EGRESS'},
  api: async (path, body) => {
    requests.push({path, body});
    if (path.endsWith('/status')) return {live_enabled: enabled};
    if (path.endsWith('/search')) return page;
    if (path.endsWith('/example')) return {...page, mode: 'offline_demo',
      provenance: {...page.provenance, provider: 'Open Intelligence authored demonstration'},
      results: [{source: 'DEMO', title: 'Fictional example', id: 'DEMO-1'}]};
    throw Error('Unexpected endpoint'); }});
vm.runInContext(app.slice(start, end), ctx);
(async () => {
  await ctx.initializeEuropePmc();
  assert.equal(el('europe-pmc-search-button').disabled, true);
  const count = requests.length;
  await el('europe-pmc-form').events.submit({preventDefault() {}});
  assert.equal(requests.length, count, 'Disabled search must not submit');
  enabled = true;
  await ctx.initializeEuropePmc();
  assert.equal(el('europe-pmc-search-button').disabled, false);
  el('europe-pmc-topic').value = 'melanoma';
  el('europe-pmc-page-size').value = '10';
  el('europe-pmc-start-date').value = '';
  el('europe-pmc-end-date').value = '';
  await el('europe-pmc-form').events.submit({preventDefault() {}});
  const request = requests.at(-1);
  assert.equal(request.path, '/api/bibliography/europe-pmc/search');
  assert.equal(JSON.stringify(request.body), JSON.stringify({topic: 'melanoma', page_size: 10}));
  const output = el('europe-pmc-results').textContent;
  assert.ok(output.includes('<script>citation text</script>'));
  assert.ok(output.includes('Europe PMC'));
  assert.ok(!output.includes('Fictional'));
  const all = item => [item, ...item.children.flatMap(all)];
  for (const link of all(el('europe-pmc-results')).filter(x => x.tag === 'a'))
    assert.equal(link.href, 'https://europepmc.org/article/MED/999000001');
  await el('europe-pmc-example-button').events.click();
  assert.ok(el('europe-pmc-results').textContent.includes('Fictional'));
  console.log('Europe PMC UI behavior passed');
})().catch(error => {console.error(error); process.exitCode = 1;});
'''
        process = subprocess.run(["node", "-e", script], cwd=ROOT, capture_output=True,
                                 text=True, timeout=15)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)


if __name__ == "__main__":
    unittest.main()
