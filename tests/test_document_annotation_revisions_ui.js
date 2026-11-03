'use strict';
const assert = require('node:assert/strict');
const {test} = require('node:test');
const {createSession} = require('../web/intake.js');

function harness() {
  let selectedCase = 'CASE-ALPHA';
  const calls = [];
  const session = createSession({getCase: () => selectedCase,
    api: (route, body) => new Promise((resolve, reject) => calls.push({route, body, resolve, reject}))});
  return {session, calls, select: id => { selectedCase = id; }};
}
function review(overrides = {}) {
  return {case_id: 'CASE-ALPHA', source_id: 7, document_id: 'DOC-TEXT', version: 1,
    state: 'current', filename: 'fictional.txt', sha256: 'b'.repeat(64), byte_count: 30,
    text: 'Independently fictional.\r\n', lines: [{line: 1, text: 'Independently fictional.'}],
    current_revision: {id: 9, revision: 2, review_sha256: 'c'.repeat(64), findings: [],
      reason: 'Earlier selection', confirmed_at: '2026-11-02T20:00:00Z'}, history: [], ...overrides};
}
const findings = [{key: 'example', state: 'pending', quote: 'Independently fictional.', line: 1}];

function pdfReview() {
  return review({filename: 'fictional.pdf', media_type: 'application/pdf',
    extraction_sha256: 'e'.repeat(64), page_count: 2,
    extractor: {name: 'pypdf', version: '6.21.4', configuration: {mode: 'plain'}},
    text: 'Independent fictional PDF\nMarker P was not assessed.',
    lines: [{line: 1, text: 'Independent fictional PDF', page: 1, page_line: 1},
      {line: 2, text: 'Marker P was not assessed.', page: 2, page_line: 1}],
    extraction_method: 'pypdf-text-v1', annotation_method: 'manual-exact-extraction-line-selection',
    clinical_review: 'not_performed'});
}

test('saved PDF editing uses the frozen page rendition and binds both hashes without uploading bytes', async () => {
  const h = harness(), loading = h.session.editSource(7), preview = pdfReview();
  h.calls[0].resolve(preview); await loading;
  assert.equal(h.session.state().phase, 'ready');
  assert.deepEqual(h.session.state().preview.lines[1], preview.lines[1]);
  const selected = [{key: 'marker-p', state: 'not-assessed', quote: preview.lines[1].text, line: 2}];
  const saving = h.session.save({findings: selected, reason: 'Correct the saved classification', confirmed: true});
  assert.deepEqual(h.calls[1].body, {findings: selected, reason: 'Correct the saved classification',
    expected_revision: 2, expected_sha256: preview.sha256, expected_extraction_sha256: preview.extraction_sha256,
    confirmed_case_id: 'CASE-ALPHA', manual_transcription_confirmed: true});
  h.calls[1].reject(Error('Extraction identity changed; reopen the saved selections.')); await saving;
  assert.equal(h.session.state().phase, 'ready');
  assert.equal(h.session.state().preview.extraction_sha256, preview.extraction_sha256);
  assert.equal(h.session.state().preview.current_revision.revision, 2);
  assert.equal(h.session.hasDraft(), true);
});

for (const [name, mutate] of [
  ['missing extraction hash', p => { delete p.extraction_sha256; }],
  ['missing page anchor', p => { delete p.lines[1].page_line; }],
  ['out of range page', p => { p.lines[1].page = 3; }],
  ['downgraded media type', p => { p.media_type = 'text/plain; charset=utf-8'; }],
  ['missing revision identity', p => { delete p.current_revision.id; }],
]) {
  test(`saved PDF review with ${name} cannot become editable or submit a revision`, async () => {
    const h = harness(), loading = h.session.editSource(7), preview = pdfReview();
    mutate(preview); h.calls[0].resolve(preview); await loading;
    assert.equal(h.session.state().phase, 'idle');
    assert.equal(h.session.state().preview, null);
    await h.session.save({findings: [], reason: 'Change selection', confirmed: true});
    assert.equal(h.calls.length, 1);
  });
}

test('edit uses stored original and sends a revision-bound selection without replacing bytes or metadata', async () => {
  const h = harness();
  const loading = h.session.editSource(7);
  assert.equal(h.calls[0].route, '/api/cases/CASE-ALPHA/sources/7/annotations');
  assert.equal(h.calls[0].body, undefined);
  h.calls[0].resolve(review()); await loading;
  assert.equal(h.session.state().mode, 'annotations');
  assert.equal(h.session.state().phase, 'ready');
  const saving = h.session.save({findings, reason: 'Correct an earlier selection', confirmed: true});
  assert.equal(h.calls[1].route, h.calls[0].route);
  assert.deepEqual(h.calls[1].body, {findings, reason: 'Correct an earlier selection',
    expected_revision: 2, expected_sha256: 'b'.repeat(64), confirmed_case_id: 'CASE-ALPHA',
    manual_transcription_confirmed: true});
  h.calls[1].resolve({result: 'revised', source_id: 7, annotation_revision: 3}); await saving;
  assert.equal(h.session.state().phase, 'saved');
  assert.equal(h.session.hasDraft(), false);
});

test('a stale save keeps the original revision and the edit available for explicit recovery', async () => {
  const h = harness(), loading = h.session.editSource(7);
  h.calls[0].resolve(review()); await loading;
  const saving = h.session.save({findings, reason: 'Correct status', confirmed: true});
  await h.session.save({findings, reason: 'Correct status', confirmed: true});
  assert.equal(h.calls.length, 2);
  h.calls[1].reject(Error('Annotation revision changed; reopen the current selections.')); await saving;
  assert.equal(h.session.state().phase, 'ready');
  assert.equal(h.session.state().preview.current_revision.revision, 2);
  assert.equal(h.session.hasDraft(), true);
  assert.match(h.session.state().error, /revision changed/);
});

test('delayed annotation reads cannot cross cases or restore a discarded edit', async () => {
  const h = harness(), old = h.session.editSource(7);
  h.select('CASE-BETA'); h.session.discard();
  h.calls[0].resolve(review()); await old;
  assert.equal(h.session.state().preview, null);
  h.select('CASE-ALPHA');
  const next = h.session.editSource(7); h.session.discard();
  h.calls[1].resolve(review()); await next;
  assert.equal(h.session.state().phase, 'idle');
});

test('cross-case, wrong-source and malformed review responses cannot become editable', async () => {
  for (const overrides of [{case_id: 'CASE-BETA'}, {source_id: 8}, {current_revision: null}]) {
    const h = harness(), loading = h.session.editSource(7);
    h.calls[0].resolve(review(overrides)); await loading;
    assert.equal(h.session.state().phase, 'idle');
    assert.equal(h.session.state().preview, null);
    assert.ok(h.session.state().error);
  }
});

test('superseded source history is readable but cannot be saved', async () => {
  const h = harness(), loading = h.session.editSource(7);
  h.calls[0].resolve(review({state: 'superseded'})); await loading;
  await h.session.save({findings, reason: 'Correct status', confirmed: true});
  assert.equal(h.calls.length, 1);
  assert.match(h.session.state().error, /superseded/);
});

test('reason and explicit transcription confirmation are required before revision submission', async () => {
  const h = harness(), loading = h.session.editSource(7);
  h.calls[0].resolve(review()); await loading;
  await h.session.save({findings, reason: 'Correct status', confirmed: false});
  assert.equal(h.calls.length, 1);
  await h.session.save({findings, reason: '  ', confirmed: true});
  assert.equal(h.calls.length, 1);
  assert.match(h.session.state().error, /reason/i);
});

test('an old save completion is ignored when an edit was cleared for a different case', async () => {
  const h = harness(), loading = h.session.editSource(7);
  h.calls[0].resolve(review()); await loading;
  const saving = h.session.save({findings, reason: 'Correct status', confirmed: true});
  h.select('CASE-BETA'); h.session.discard();
  h.calls[1].resolve({result: 'revised', source_id: 7, annotation_revision: 3}); await saving;
  assert.equal(h.session.state().phase, 'idle');
  assert.equal(h.session.state().result, null);
});
