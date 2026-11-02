'use strict';
// Exercise the real investigation-list loader with independently authored
// fictional responses. No network calls, browser packages or implementation copy.
const assert = require('node:assert/strict');
const {test} = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const app = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
const start = app.indexOf('async function loadModelInvestigations()');
const end = app.indexOf('async function loadChangesSinceReview()', start);
assert.ok(start >= 0 && end > start, 'Expected the actual investigation-list loader');
const loader = app.slice(start, end);

function element(text = '') {
  return {
    text: String(text ?? ''), children: [],
    append(...items) { this.children.push(...items); },
    replaceChildren() { this.text = ''; this.children = []; },
    get textContent() { return this.text + this.children.map(child => child.textContent).join(' '); },
  };
}
const flush = () => new Promise(setImmediate);
function detail(id, marker, stale = false) {
  return {id, template: 'evidence-summary', status: 'completed', mode: 'replay',
    model: 'recorded-replay', created_at: '2026-01-01T12:00:00Z', stale,
    kind: 'hypothesis', review_state: 'pending',
    claims: [{text: marker, uncertainty: 'high', citations: [], limits: 'Fictional research only.'}],
    abstentions: [], dropped: [], disclaimer: 'Unreviewed fictional research.'};
}
function harness() {
  const list = element(), requests = [], notices = [];
  const ctx = vm.createContext({
    caseId: 'CASE-A', renderedCaseId: 'CASE-A', refreshSequence: 1,
    active: {case: {case_id: 'CASE-A'}},
    api: url => new Promise((resolve, reject) => requests.push({url, resolve, reject})),
    el: id => { assert.equal(id, 'model-investigation-list'); return list; },
    clear: id => { assert.equal(id, 'model-investigation-list'); list.replaceChildren(); },
    node: (_tag, text) => element(text), pill: text => element(text),
    empty: (target, text) => target.append(element(text)),
    notice: (message, error) => notices.push({message, error}),
  });
  vm.runInContext(loader, ctx);
  function refresh(caseId = ctx.caseId, loaded = true) {
    // These are the host's actual request-lifetime inputs. Do not implement
    // stale-response filtering in the double; the production loader must do it.
    ctx.refreshSequence += 1;
    ctx.caseId = caseId;
    ctx.active = loaded ? {case: {case_id: caseId}} : null;
    if (loaded) ctx.renderedCaseId = caseId;
  }
  return {ctx, list, requests, notices, refresh, load: () => ctx.loadModelInvestigations()};
}
async function resolveList(request, ids) {
  request.resolve({investigations: ids.map(id => ({id}))});
  await flush();
}

test('late older list cannot clear or replace the newer same-case investigation list', async () => {
  const h = harness(), older = h.load();
  h.refresh();
  const newer = h.load();
  await resolveList(h.requests[1], [20]);
  h.requests[2].resolve(detail(20, 'CURRENT INVESTIGATION'));
  await newer;
  await resolveList(h.requests[0], [7]);
  // Let an unguarded implementation finish rather than leaving a pending promise.
  if (h.requests[3]) h.requests[3].resolve(detail(7, 'OBSOLETE INVESTIGATION'));
  await older;
  assert.match(h.list.textContent, /CURRENT INVESTIGATION/);
  assert.doesNotMatch(h.list.textContent, /OBSOLETE INVESTIGATION/);
  assert.equal(h.list.children.length, 1);
});

test('late pre-amendment detail cannot append an unmarked copy beside the current stale result', async () => {
  const h = harness(), older = h.load();
  await resolveList(h.requests[0], [7]);
  // The first detail response was obtained before amendment but has not arrived.
  h.refresh();
  const newer = h.load();
  await resolveList(h.requests[2], [7]);
  h.requests[3].resolve(detail(7, 'CURRENT AMENDED CONTEXT', true));
  await newer;
  h.requests[1].resolve(detail(7, 'OBSOLETE PRE-AMENDMENT CONTEXT', false));
  await older;
  assert.equal(h.list.children.length, 1, 'An old result revived a second card for the same investigation');
  assert.match(h.list.textContent, /CURRENT AMENDED CONTEXT/);
  assert.match(h.list.textContent, /This investigation is stale/);
  assert.doesNotMatch(h.list.textContent, /OBSOLETE PRE-AMENDMENT CONTEXT/);
});

for (const stage of ['list', 'detail']) {
  test(`late ${stage} failure cannot publish an error over a newer same-case result`, async () => {
    const h = harness(), older = h.load();
    if (stage === 'detail') await resolveList(h.requests[0], [7]);
    const oldRequest = h.requests.at(-1);
    h.refresh();
    const newer = h.load();
    await resolveList(h.requests.at(-1), []);
    await newer;
    oldRequest.reject(Error('OBSOLETE FAILURE'));
    await older;
    assert.equal(h.notices.length, 0, 'An invalidated request emitted a visible error');
    assert.match(h.list.textContent, /No model investigations yet/);
  });
}

test('A to B to A cannot revive an older A detail after the new A refresh', async () => {
  const h = harness(), older = h.load();
  await resolveList(h.requests[0], [7]);
  h.refresh('CASE-B', false);
  h.refresh('CASE-A');
  const current = h.load();
  await resolveList(h.requests[2], []);
  await current;
  h.requests[1].resolve(detail(7, 'OBSOLETE ROUND-TRIP RESULT'));
  await older;
  assert.match(h.list.textContent, /No model investigations yet/);
  assert.doesNotMatch(h.list.textContent, /OBSOLETE ROUND-TRIP RESULT/);
});

test('a detail completing while the case snapshot is unavailable cannot render', async () => {
  const h = harness(), pending = h.load();
  await resolveList(h.requests[0], [7]);
  h.ctx.active = null;
  h.requests[1].resolve(detail(7, 'NO LOADED CASE'));
  await pending;
  assert.equal(h.list.children.length, 0);
  assert.equal(h.notices.length, 0);
});

test('a current failure remains visible so the race guard does not hide real errors', async () => {
  const h = harness(), pending = h.load();
  h.requests[0].reject(Error('CURRENT FAILURE'));
  await pending;
  assert.deepEqual(h.notices, [{message: 'CURRENT FAILURE', error: true}]);
});
