'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../web/composer.js'), 'utf8');
const app = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
const apiSource = app.slice(app.indexOf('async function api('), app.indexOf('function pill('));
const flush = () => new Promise(resolve => setImmediate(resolve));
class Element extends EventTarget {
  constructor() { super(); this.value = ''; this.children = []; this.attributes = {}; this.dataset = {}; }
  setAttribute(key, value) { this.attributes[key] = value; }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = [...nodes]; }
}
function harness() {
  const nodes = new Map(['case-picker','model-investigation-question','composer-context',
    'composer-context-fingerprint','model-investigation-run'].map(id => [id, new Element()]));
  const get = id => nodes.get(id);
  get('case-picker').value = 'CASE-A'; get('model-investigation-question').value = '1';
  const document = new EventTarget(); document.getElementById = get;
  document.createElement = () => new Element();
  class CustomEvent extends Event { constructor(type, init) { super(type); this.detail = init?.detail; } }
  const requests = [];
  const context = vm.createContext({document, Event, CustomEvent, queueMicrotask,
    MutationObserver: class {observe() {}},
    fetch: (url, options) => new Promise((resolve, reject) => requests.push({url, options, resolve, reject}))});
  vm.runInContext('const pendingCaseWrites = new Map();\n' + apiSource, context);
  vm.runInContext(source, context);
  const response = async (index, body, status = 200) => {
    requests[index].resolve({ok: status < 400, status, headers: {get: () => 'application/json'}, json: async () => body});
    await flush();
  };
  const preview = {case_id: 'CASE-A', question_id: 1, fingerprint: 'a'.repeat(64),
    source_count: 1, source_anchors: [], evidence_assessment_count: 0};
  const signal = (type, detail = {caseId: 'CASE-A'}) => document.dispatchEvent(new CustomEvent(type, {detail}));
  return {context, get, requests, response, preview, signal};
}
function blocked(h) {
  assert.equal(h.get('model-investigation-run').disabled, true, 'Prior preview cannot enable a run during a write');
  assert.equal(h.get('composer-context-fingerprint').value, '', 'Old source fingerprint was cleared');
}

test('actual case and shared writes invalidate Composer until a fresh context read', async () => {
  const h = harness(); await h.response(0, h.preview);
  assert.equal(h.get('model-investigation-run').disabled, false);
  const local = h.context.api('/api/cases/CASE-A/imports', {text: 'Fictional original'});
  blocked(h);
  const shared = h.context.api('/api/rights/sources/1/revoke', {reason: 'Fictional withdrawal'});
  h.signal('oi:composer-refresh'); assert.equal(h.requests.length, 3, 'No context read while writes are pending');
  await h.response(1, {result: 'imported'}); await local;
  h.signal('oi:composer-refresh'); blocked(h); assert.equal(h.requests.length, 3);
  await h.response(2, {revoked: true}); await shared; blocked(h);
  h.signal('oi:case-state-updated'); await flush();
  assert.equal(h.requests.length, 4, 'Accepted host state requests new context');
  await h.response(3, {...h.preview, fingerprint: 'b'.repeat(64)});
  assert.equal(h.get('composer-context-fingerprint').value, 'b'.repeat(64));
});

test('a delayed context reply cannot revive the preview invalidated by an import', async () => {
  const h = harness(); const write = h.context.api('/api/cases/CASE-A/imports', {text: 'Fictional original'});
  await h.response(0, h.preview); blocked(h);
  await h.response(1, {result: 'duplicate'}); await write; blocked(h);
  h.signal('oi:composer-refresh'); await h.response(2, {...h.preview, fingerprint: 'c'.repeat(64)});
  assert.equal(h.get('composer-context-fingerprint').value, 'c'.repeat(64));
});

test('failed writes leave the old preview cleared and permit an explicit fresh retry', async () => {
  const h = harness(); await h.response(0, h.preview);
  const write = h.context.api('/api/cases/CASE-A/imports', {});
  const rejected = assert.rejects(write, /unknown/);
  h.requests[1].reject(Error('unknown outcome')); await rejected; await flush(); blocked(h);
  h.signal('oi:composer-refresh'); await h.response(2, h.preview);
  assert.equal(h.get('model-investigation-run').disabled, false);
});

test('another case write does not clear the selected preview but switching to it blocks reads', async () => {
  const h = harness(); await h.response(0, h.preview);
  const write = h.context.api('/api/cases/CASE-B/imports', {});
  assert.equal(h.get('model-investigation-run').disabled, false);
  h.get('case-picker').value = 'CASE-B'; h.get('case-picker').dispatchEvent(new Event('change'));
  h.signal('oi:composer-refresh'); blocked(h); assert.equal(h.requests.length, 2);
  await h.response(1, {result: 'imported'}); await write;
});
