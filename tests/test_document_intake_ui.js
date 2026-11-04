'use strict';
const assert = require('node:assert/strict');
const {test} = require('node:test');
const {createSession} = require('../web/intake.js');

const turn = () => new Promise(setImmediate);
const file = (name, text) => ({name, size: Buffer.byteLength(text),
  arrayBuffer: async () => Uint8Array.from(Buffer.from(text)).buffer});
function harness() {
  let selectedCase = 'CASE-ALPHA';
  const calls = [], changes = [];
  const session = createSession({
    getCase: () => selectedCase,
    api: (route, body) => new Promise((resolve, reject) => calls.push({route, body, resolve, reject})),
    onChange: state => changes.push(state),
  });
  return {session, calls, changes, select: value => {selectedCase = value;}};
}
const preview = (name = 'record.txt') => ({case_id: 'CASE-ALPHA', filename: name,
  sha256: 'a'.repeat(64), byte_count: 22, text: 'Independently fictional.',
  lines: [{line: 1, text: 'Independently fictional.'}]});

test('original file bytes survive browser transport, including BOM, CRLF and unicode', async () => {
  const h = harness(), original = '\ufeffFictional report\r\nMarker α is pending.\r\n';
  const pending = h.session.previewFile(file('record.txt', original));
  await turn();
  assert.deepEqual(Buffer.from(h.calls[0].body.content_base64, 'base64'), Buffer.from(original));
  h.calls[0].resolve(preview()); await pending;
  const save = h.session.save({metadata: {document_id: 'DOC-A'}, findings: [], confirmed: true});
  await turn();
  assert.equal(h.calls[1].route, '/api/cases/CASE-ALPHA/documents');
  assert.equal(h.calls[1].body.content_base64, h.calls[0].body.content_base64);
  assert.equal(h.calls[1].body.expected_sha256, 'a'.repeat(64));
  assert.equal(h.calls[1].body.confirmed_case_id, 'CASE-ALPHA');
  assert.equal(h.calls[1].body.metadata.manual_transcription_confirmed, true);
  h.calls[1].resolve({result: 'imported', source_id: 1, version: 1}); await save;
  assert.equal(h.session.state().phase, 'saved');
  assert.equal(h.session.hasDraft(), false);
});

test('an older preview cannot replace a newer file or restore a discarded record', async () => {
  const h = harness();
  const old = h.session.previewFile(file('old.txt', 'Old fictional record.')); await turn();
  const fresh = h.session.previewFile(file('new.txt', 'New fictional record.')); await turn();
  h.calls[1].resolve(preview('new.txt')); await fresh;
  h.calls[0].resolve(preview('old.txt')); await old;
  assert.equal(h.session.state().preview.filename, 'new.txt');
  const discarded = h.session.previewFile(file('discard.txt', 'Discarded fictional record.')); await turn();
  h.session.discard();
  h.calls[2].resolve(preview('discard.txt')); await discarded;
  assert.equal(h.session.state().phase, 'idle');
  assert.equal(h.session.state().preview, null);
});

test('case changes cannot attach a preview or save the old case under the new case', async () => {
  const h = harness();
  const pending = h.session.previewFile(file('record.txt', 'Independently fictional.')); await turn();
  h.select('CASE-BETA'); h.session.discard();
  h.calls[0].resolve(preview()); await pending;
  assert.equal(h.session.state().preview, null);
  h.select('CASE-ALPHA');
  const next = h.session.previewFile(file('record.txt', 'Independently fictional.')); await turn();
  h.calls[1].resolve(preview()); await next;
  h.select('CASE-BETA');
  await h.session.save({metadata: {}, findings: [], confirmed: true});
  assert.equal(h.calls.length, 2);
  assert.match(h.session.state().error, /case/i);
});

test('confirmation is required and a repeated save while in flight creates one request', async () => {
  const h = harness();
  const pending = h.session.previewFile(file('record.txt', 'Independently fictional.')); await turn();
  h.calls[0].resolve(preview()); await pending;
  await h.session.save({metadata: {}, findings: [], confirmed: false});
  assert.equal(h.calls.length, 1);
  assert.match(h.session.state().error, /confirm/i);
  const first = h.session.save({metadata: {}, findings: [], confirmed: true});
  await h.session.save({metadata: {}, findings: [], confirmed: true});
  assert.equal(h.calls.length, 2);
  h.calls[1].reject(Error('Stale amendment: refresh the latest source version.')); await first;
  assert.equal(h.session.state().phase, 'ready');
  assert.match(h.session.state().error, /Stale amendment/);
  assert.equal(h.session.hasDraft(), true);
});

test('oversized files are rejected before reading or transmitting their contents', async () => {
  const h = harness();
  await h.session.previewFile({name: 'large.txt', size: 65537,
    arrayBuffer: () => {throw Error('Must not read oversized file');}});
  assert.equal(h.calls.length, 0);
  assert.match(h.session.state().error, /64 KiB/);
});

test('the total envelope is bounded without truncating the original or discarding the draft', async () => {
  const h = harness();
  const pending = h.session.previewFile(file('record.txt', 'x'.repeat(65000))); await turn();
  h.calls[0].resolve(preview()); await pending;
  const findings = Array.from({length: 30}, (_, i) => ({key: 'finding-' + i,
    state: 'reported', quote: 'α'.repeat(1200), line: 1}));
  await h.session.save({metadata: {}, findings, confirmed: true});
  assert.equal(h.calls.length, 1);
  assert.match(h.session.state().error, /128 KiB/);
  assert.equal(h.session.state().phase, 'ready');
  assert.equal(h.session.hasDraft(), true);
  assert.equal(Buffer.from(h.calls[0].body.content_base64, 'base64').length, 65000);
});
