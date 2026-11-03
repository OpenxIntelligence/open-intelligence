'use strict';
// Exercise the existing host API, mounted intake, and complete report client
// together. Only the DOM and transport timing are controlled; no event is
// fabricated to stand in for an upload's actual write lifecycle.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const app = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
const apiSource = app.slice(app.indexOf('async function api('), app.indexOf('function pill('));
const intakeSource = fs.readFileSync(path.join(__dirname, '../web/intake.js'), 'utf8');
const reportSource = fs.readFileSync(path.join(__dirname, '../web/report.js'), 'utf8');
const raw = 'OI-SYNTHETIC-REPORT/1\nPatient: CASE-A\nDocument: DOC-A\nType: clinical\nEvent-Date: 2026-01-01\nIssued-At: 2026-01-02\nFinding: context|reported|Independently fictional original.\n';
const flush = () => new Promise(resolve => setImmediate(resolve));

class Element extends EventTarget {
  constructor(tag = 'div') {
    super(); this.tagName = tag.toUpperCase(); this.children = [];
    this.dataset = {}; this.attributes = new Map(); this.value = ''; this.files = [];
    this.disabled = false; this.checked = false; this.hidden = false; this._text = '';
    this.classList = {add() {}, remove() {}};
  }
  get textContent() { return this._text + this.children.map(c => c.textContent).join(''); }
  set textContent(value) { this._text = String(value); this.children = []; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this._text = ''; this.children = [...nodes]; }
  setAttribute(key, value) { this.attributes.set(key, String(value)); }
  getAttribute(key) { return this.attributes.get(key) ?? null; }
  removeAttribute(key) { this.attributes.delete(key); }
  get href() { return this.getAttribute('href') || ''; }
  set href(value) { this.setAttribute('href', value); }
  set download(value) { this.setAttribute('download', value); }
  reset() {}
}
function payload(text = 'Before the original import', event = 1) {
  return {case_id: 'CASE-A', case_label: 'Fictional A', reading_note: 'Not clinically reviewed.',
    as_of: {event_id: event, occurred_at: '2026-11-03T00:00:00Z'},
    sections: [{id: 'overview', title: 'Recorded source', summary: 'Fictional only.',
      items: [{text, detail: 'Unreviewed', citation: 'Source version #1'}], sources_note: 'Source-linked'}],
    text};
}
async function harness(t) {
  const ids = ['case-picker','patient-report','report-reading-note','report-meta','report-print',
    'report-refresh','report-text-link','report-sections','case-create-form','source-upload-form',
    'source-upload-submit','source-upload-confirm','source-file','source-upload-preview',
    'source-preview-details','source-import-receipts','source-upload-status','source-intake',
    'workspace-start','new-case-panel','source-intake-case','journey-steps'];
  const nodes = new Map(ids.map(id => [id, new Element()]));
  nodes.set('report-actions', new Element());
  const get = id => nodes.get(id);
  get('case-picker').value = 'CASE-A';
  const document = new EventTarget();
  document.getElementById = get;
  document.querySelector = sel => get(sel.replace(/^[#.]/, '')) || null;
  document.createElement = tag => new Element(tag);
  document.body = new Element('body');
  const requests = [], urls = [], imported = [], events = [];
  class CustomEvent extends Event { constructor(type, init) { super(type); this.detail = init?.detail; } }
  for (const name of ['oi:case-state-invalidated','oi:case-state-write-settled']) {
    document.addEventListener(name, event => events.push({name, ...event.detail}));
  }
  const window = new EventTarget(); window.print = () => {};
  const ctx = vm.createContext({document, window, Event, CustomEvent, Blob, TextEncoder, TextDecoder,
    queueMicrotask, fetch: (url, options) => new Promise((resolve, reject) => requests.push({url, options, resolve, reject})),
    URL: {createObjectURL(blob) { const url = URL.createObjectURL(blob); urls.push(url); return url; },
      revokeObjectURL(url) { URL.revokeObjectURL(url); }}});
  t.after(() => urls.forEach(url => URL.revokeObjectURL(url)));
  vm.runInContext('const pendingCaseWrites = new Map();\n' + apiSource, ctx);
  vm.runInContext(intakeSource, ctx);
  vm.runInContext(reportSource, ctx);
  const mounted = ctx.OIIntake.mount({api: ctx.api, getCase: () => get('case-picker').value,
    canSwitch: () => true, created: async () => {}, imported: async id => imported.push(id)});
  mounted.render({case: {case_id: 'CASE-A'}, sources: [{state: 'current'}], questions: [], snapshots: []});
  const respond = async (index, body, status = 200) => {
    assert.ok(requests[index], 'Transport request exists');
    requests[index].resolve({status, ok: status >= 200 && status < 300,
      headers: {get: () => 'application/json'}, json: async () => body});
    await flush();
  };
  await flush(); await respond(0, payload());
  async function select(count = 1) {
    get('source-file').files = Array.from({length: count}, (_, i) => ({name: `original-${i}.txt`,
      size: new TextEncoder().encode(raw).length,
      arrayBuffer: async () => new TextEncoder().encode(raw).buffer}));
    get('source-file').dispatchEvent(new Event('change')); await flush();
    get('source-upload-confirm').checked = true;
    get('source-upload-confirm').dispatchEvent(new Event('change'));
    assert.equal(get('source-upload-submit').disabled, false);
  }
  const submit = () => get('source-upload-form').dispatchEvent(new Event('submit', {cancelable: true}));
  return {ctx, document, get, requests, imported, events, respond, select, submit};
}
function blocked(h) {
  assert.equal(h.get('report-print').disabled, true, 'The displayed report is invalidated by the actual intake write');
  assert.equal(h.get('report-text-link').getAttribute('href'), null, 'The prior report cannot be downloaded');
}

test('inspecting files makes no write; submitting invalidates report before awaiting HTTP', async t => {
  const h = await harness(t); await h.select(2);
  assert.equal(h.requests.length, 1, 'Inspection alone never uploads');
  assert.equal(h.get('report-print').disabled, false);
  const oldUrl = h.get('report-text-link').href;
  h.submit(); blocked(h);
  assert.equal(h.get('report-refresh').disabled, true);
  assert.equal(h.requests.length, 2);
  await assert.rejects(fetch(oldUrl));
  await h.respond(1, {result: 'imported', source_id: 2, version: 1});
  blocked(h); assert.equal(h.get('report-refresh').disabled, true, 'Second file is still writing');
  assert.equal(h.requests.length, 3);
  await h.respond(2, {result: 'duplicate', source_id: 2, version: 1});
  blocked(h); assert.equal(h.get('report-refresh').disabled, false);
  assert.deepEqual(h.get('source-import-receipts').children.map(c => c.dataset.status), ['imported','duplicate']);
  assert.deepEqual(h.imported, ['CASE-A']);
  h.get('report-refresh').dispatchEvent(new Event('click')); await flush();
  await h.respond(3, payload('After a source-ledger reconciliation', 2));
  assert.equal(h.get('report-print').disabled, false);
  assert.equal(await (await fetch(h.get('report-text-link').href)).text(), 'After a source-ledger reconciliation');
});

test('unknown upload outcome stops later writes and never restores the previous report', async t => {
  const h = await harness(t); await h.select(2); h.submit();
  blocked(h);
  h.requests[1].reject(Error('Transport interrupted after possible commit')); await flush();
  assert.equal(h.requests.length, 2, 'No automatic retry or second-file write'); blocked(h);
  assert.deepEqual(h.get('source-import-receipts').children.map(c => c.dataset.status), ['unknown','not_attempted']);
  assert.match(h.get('source-upload-status').textContent, /unknown/i);
});

test('intake preserves rejection and quarantine statuses instead of relabeling them as network failure', async t => {
  const h = await harness(t); await h.select(2); h.submit();
  await h.respond(1, {error: 'Invalid original'}, 422);
  await h.respond(2, {result: 'quarantined', quarantine_id: 5}, 200);
  assert.deepEqual(h.get('source-import-receipts').children.map(c => c.dataset.status), ['rejected','quarantined']);
  blocked(h);
  assert.deepEqual(h.events.map(e => e.pendingWrites), [1,0,1,0]);
});

test('an unrelated unresolved write cannot be erased by intake settlement', async t => {
  const h = await harness(t);
  const other = h.ctx.api('/api/cases/CASE-A/questions', {question: 'A fictional question?'});
  const global = h.ctx.api('/api/rights/sources/1/revoke', {reason: 'Fictional withdrawal'});
  await h.select(); h.submit();
  assert.equal(h.requests.length, 4);
  await h.respond(3, {result: 'duplicate', source_id: 1, version: 1});
  blocked(h); assert.equal(h.get('report-refresh').disabled, true);
  await h.respond(1, {question_id: 1}, 201); await other;
  assert.equal(h.get('report-refresh').disabled, true);
  await h.respond(2, {revoked: true}); await global;
  assert.equal(h.get('report-refresh').disabled, false); blocked(h);
  assert.deepEqual(h.events.filter(e => e.caseId === 'CASE-A').map(e => e.pendingWrites), [1,2,1,0]);
});

test('document preview is read-only, while reviewed document save invalidates report', async t => {
  const h = await harness(t);
  const preview = h.ctx.api('/api/cases/CASE-A/documents/preview', {fictional: true});
  assert.equal(h.get('report-print').disabled, false);
  assert.equal(h.events.length, 0, 'Read-only preview cannot emit a write lifetime');
  await h.respond(1, {preview: true}); await preview;
  const save = h.ctx.api('/api/cases/CASE-A/documents', {fictional: true});
  blocked(h); assert.equal(h.get('report-refresh').disabled, true);
  await h.respond(2, {result: 'imported', source_id: 2, version: 1}); await save;
  blocked(h);
});
