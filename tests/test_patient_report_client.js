'use strict';
// Execute the complete report client with controlled HTTP timing and a small DOM.
// Blob contents and object-URL lifetime use Node's real browser-compatible APIs.
const assert = require('node:assert/strict');
const {test} = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const script = fs.readFileSync(path.join(__dirname, '../web/report.js'), 'utf8');

class Element extends EventTarget {
  constructor(tag = 'div') {
    super();
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.dataset = {};
    this.attributes = new Map();
    const classes = new Set();
    this.classList = {
      add: name => classes.add(name), remove: name => classes.delete(name),
      contains: name => classes.has(name),
    };
    this.disabled = false;
    this.value = '';
    this._text = '';
  }
  get textContent() {
    return this._text + this.children.map(child => child.textContent).join('');
  }
  set textContent(value) { this._text = String(value); this.children = []; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this._text = ''; this.children = [...children]; }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  removeAttribute(name) { this.attributes.delete(name); }
  get href() { return this.getAttribute('href') || ''; }
  set href(value) { this.setAttribute('href', value); }
  get download() { return this.getAttribute('download') || ''; }
  set download(value) { this.setAttribute('download', value); }
}

function report(caseId = 'CASE-A', statement = 'Original fictional statement', eventId = 1) {
  return {
    case_id: caseId,
    case_label: 'Independent fictional fixture',
    fictional: true,
    demo_notice: 'Fictional demo report; not a clinical review.',
    reading_note: 'Recorded facts only. Missing information remains unknown.',
    generated_from: 'recorded case data only; no new inference',
    as_of: {event_id: eventId, occurred_at: '2026-11-02T12:00:00Z'},
    section_ids: ['overview'],
    sections: [{
      id: 'overview', title: 'Recorded information', summary: 'One fictional entry.',
      fictional_note: 'Fictional demo.',
      items: [{text: statement, detail: 'Pending review.', citation: 'Source version #1, line 8.'}],
      empty_text: 'No information recorded.', item_count: 1, cited_count: 1,
      sources_note: 'One source anchor.',
    }],
    text: `Fictional ${caseId} report at event ${eventId}\n${statement}\nPending review.\n`,
  };
}

function harness(t, initialCase = 'CASE-A') {
  const nodes = new Map([
    ['#case-picker', new Element('select')], ['#patient-report', new Element('section')],
    ['#report-reading-note', new Element('p')], ['#report-meta', new Element('p')],
    ['.report-actions', new Element('div')], ['#report-print', new Element('button')],
    ['#report-refresh', new Element('button')],
    ['#report-text-link', new Element('a')], ['#report-sections', new Element('div')],
    ['#event-list', new Element('div')],
  ]);
  const get = selector => nodes.get(selector);
  get('#case-picker').value = initialCase;
  const document = new EventTarget();
  document.querySelector = selector => get(selector) || null;
  document.createElement = tag => new Element(tag);
  document.body = new Element('body');
  const window = new EventTarget();
  const printed = [], printScopes = [], requests = [], urls = [];
  window.print = () => {
    printed.push(get('#report-sections').textContent);
    printScopes.push(document.body.classList.contains('printing-patient-report'));
  };
  const context = vm.createContext({
    document, window, Event, Blob, queueMicrotask,
    URL: {
      createObjectURL(blob) { const url = URL.createObjectURL(blob); urls.push(url); return url; },
      revokeObjectURL(url) { URL.revokeObjectURL(url); },
    },
    // The original client observes the event list; the new explicit host hooks
    // are exercised below. This adapter does not synthesize host state changes.
    MutationObserver: class { observe() {} },
    fetch: url => new Promise((resolve, reject) => requests.push({url, resolve, reject})),
  });
  t.after(() => urls.forEach(url => URL.revokeObjectURL(url)));
  vm.runInContext(script, context);
  const flush = () => new Promise(resolve => setImmediate(resolve));
  const signal = (type, caseId = get('#case-picker').value, detail = {}) => {
    const event = new Event(type);
    event.detail = {caseId, ...detail};
    document.dispatchEvent(event);
  };
  const changeCase = caseId => {
    get('#case-picker').value = caseId;
    get('#case-picker').dispatchEvent(new Event('change'));
  };
  const respond = async (index, payload, status = 200) => {
    assert.ok(requests[index], `Report request ${index} exists`);
    requests[index].resolve({ok: status < 400, status, json: async () => payload});
    await flush();
  };
  return {get, document, window, printed, printScopes, requests, urls, flush, signal, changeCase, respond};
}

function assertBlocked(h) {
  assert.equal(h.get('#report-print').disabled, true, 'printing is unavailable');
  assert.equal(h.get('#report-text-link').getAttribute('href'), null, 'no previous download remains');
  assert.equal(h.get('#report-text-link').getAttribute('aria-disabled'), 'true');
  const click = new Event('click', {cancelable: true});
  h.get('#report-text-link').dispatchEvent(click);
  assert.equal(click.defaultPrevented, true, 'disabled download activation is rejected');
  const before = h.printed.length;
  h.get('#report-print').dispatchEvent(new Event('click'));
  assert.equal(h.printed.length, before, 'disabled print handler does nothing');
}

test('loading blocks both actions before any report response', async t => {
  const h = harness(t);
  assertBlocked(h);
  await h.flush();
  assert.equal(h.requests.length, 1);
  assert.equal(h.get('#report-sections').textContent, '');
});

test('download contains the exact accepted report text without a second HTTP read', async t => {
  const h = harness(t);
  await h.flush();
  const payload = report('CASE-A', '<img src=x onerror=alert(1)> — fictional only');
  await h.respond(0, payload);
  assert.match(h.get('#report-sections').textContent, /<img src=x onerror=alert\(1\)>/);
  assert.equal(h.get('#report-print').disabled, false);
  assert.equal(h.get('#report-text-link').getAttribute('aria-disabled'), 'false');
  const url = h.get('#report-text-link').href;
  assert.match(url, /^blob:/);
  const downloaded = await fetch(url);
  assert.equal(downloaded.headers.get('content-type'), 'text/plain;charset=utf-8');
  assert.equal(await downloaded.text(), payload.text);
  h.get('#report-print').dispatchEvent(new Event('click'));
  assert.equal(h.printed[0], h.get('#report-sections').textContent);
  assert.equal(h.printScopes[0], true, 'report action prints the report surface only');
  assert.equal(h.document.body.classList.contains('printing-patient-report'), false);
  h.window.print();
  assert.equal(h.printScopes[1], false, 'ordinary browser printing is unchanged');
  assert.equal(h.requests.length, 1, 'download does not fetch a later server report');
});

test('case change clears the old report and revokes its download synchronously', async t => {
  const h = harness(t);
  await h.flush();
  await h.respond(0, report());
  const oldUrl = h.get('#report-text-link').href;
  h.changeCase('CASE-B');
  assertBlocked(h);
  assert.equal(h.get('#report-sections').textContent, '');
  assert.equal(h.get('#report-reading-note').textContent, '');
  await assert.rejects(fetch(oldUrl));
  await h.flush();
  assert.equal(h.requests[1].url, '/api/cases/CASE-B/patient-report');
  await h.respond(1, report('CASE-B', 'A different fictional case'));
  assert.match(h.get('#report-sections').textContent, /A different fictional case/);
  assert.doesNotMatch(h.get('#report-sections').textContent, /Original fictional statement/);
});

test('a late old-case response cannot replace the accepted current-case report', async t => {
  const h = harness(t);
  await h.flush();
  h.changeCase('CASE-B');
  await h.flush();
  await h.respond(1, report('CASE-B', 'Current case report'));
  const currentUrl = h.get('#report-text-link').href;
  await h.respond(0, report('CASE-A', 'Obsolete case report'));
  assert.match(h.get('#report-sections').textContent, /Current case report/);
  assert.equal(h.get('#report-text-link').href, currentUrl);
  assert.equal(h.urls.length, 1, 'discarded response creates no downloadable artifact');
});

test('a changed same-case state invalidates pending responses until the host update', async t => {
  const h = harness(t);
  await h.flush();
  await h.respond(0, report());
  h.signal('oi:case-state-updated');
  assertBlocked(h);
  await h.flush();
  assert.equal(h.requests.length, 2);
  h.signal('oi:case-state-invalidated');
  await h.respond(1, report('CASE-A', 'Pre-amendment response', 2));
  assertBlocked(h);
  assert.doesNotMatch(h.get('#report-sections').textContent, /Pre-amendment/);
  assert.equal(h.requests.length, 2, 'invalidation waits for the accepted host state');
  h.signal('oi:case-state-updated');
  await h.flush();
  await h.respond(2, report('CASE-A', 'Source amended: task needs another look', 3));
  assert.match(h.get('#report-sections').textContent, /task needs another look/);
  assert.equal(h.get('#report-print').disabled, false);
});

test('a failed refresh leaves no stale body, print action or object URL', async t => {
  const h = harness(t);
  await h.flush();
  await h.respond(0, report());
  const oldUrl = h.get('#report-text-link').href;
  h.signal('oi:case-state-updated');
  await h.flush();
  await h.respond(1, {error: 'Report refresh failed'}, 503);
  assertBlocked(h);
  assert.doesNotMatch(h.get('#report-sections').textContent, /Original fictional statement/);
  assert.match(h.get('#report-meta').textContent, /unavailable/i);
  await assert.rejects(fetch(oldUrl));
});

test('a wrong-case response is rejected even when its HTTP request is current', async t => {
  const h = harness(t);
  await h.flush();
  await h.respond(0, report('CASE-B', 'Wrong patient canary'));
  assertBlocked(h);
  assert.doesNotMatch(h.get('#report-sections').textContent, /Wrong patient canary/);
  assert.equal(h.urls.length, 0);
});

test('a response without its matching text artifact cannot enable download or print', async t => {
  const h = harness(t);
  await h.flush();
  const payload = report();
  delete payload.text;
  await h.respond(0, payload);
  assertBlocked(h);
  assert.equal(h.urls.length, 0);
});

test('duplicate host updates coalesce and a late same-case failure cannot replace fresh data', async t => {
  const h = harness(t);
  await h.flush();
  h.signal('oi:case-state-updated');
  h.signal('oi:case-state-updated');
  await h.flush();
  assert.equal(h.requests.length, 2, 'one report request per batched host update');
  await h.respond(1, report('CASE-A', 'Accepted current update', 2));
  h.requests[0].reject(new Error('Obsolete request failure'));
  await h.flush();
  assert.match(h.get('#report-sections').textContent, /Accepted current update/);
  assert.equal(h.get('#report-print').disabled, false);
});

test('an unrelated case update does not discard the accepted current report', async t => {
  const h = harness(t);
  await h.flush();
  await h.respond(0, report());
  const url = h.get('#report-text-link').href;
  h.signal('oi:case-state-invalidated', 'CASE-B');
  h.signal('oi:case-state-updated', 'CASE-B');
  await h.flush();
  assert.equal(h.requests.length, 1);
  assert.equal(h.get('#report-text-link').href, url);
  assert.equal(h.get('#report-print').disabled, false);
});

test('leaving the page revokes its report artifact and disables actions', async t => {
  const h = harness(t);
  await h.flush();
  await h.respond(0, report());
  const url = h.get('#report-text-link').href;
  h.window.dispatchEvent(new Event('pagehide'));
  assertBlocked(h);
  await assert.rejects(fetch(url));
  assert.equal(h.get('#report-sections').textContent, '');
});

test('invalidation cancels a queued refresh until the next accepted host update', async t => {
  const h = harness(t);
  await h.flush();
  await h.respond(0, report());
  h.signal('oi:case-state-updated');
  h.signal('oi:case-state-invalidated');
  await h.flush();
  assert.equal(h.requests.length, 1);
  assertBlocked(h);
  h.signal('oi:case-state-updated');
  await h.flush();
  assert.equal(h.requests.length, 2);
});

test('refresh action recovers from a failed request with newly evaluated report data', async t => {
  const h = harness(t);
  await h.flush();
  await h.respond(0, {error: 'Temporary report failure'}, 503);
  assertBlocked(h);
  h.get('#report-refresh').dispatchEvent(new Event('click'));
  await h.flush();
  assert.equal(h.requests.length, 2);
  await h.respond(1, report('CASE-A', 'Due-date evaluation refreshed', 5));
  assert.equal(h.get('#report-print').disabled, false);
  assert.match(h.get('#report-sections').textContent, /Due-date evaluation refreshed/);
});

test('restoring a cached page refreshes instead of reusing its revoked download', async t => {
  const h = harness(t);
  await h.flush();
  await h.respond(0, report());
  h.window.dispatchEvent(new Event('pagehide'));
  const restore = new Event('pageshow');
  restore.persisted = true;
  h.window.dispatchEvent(restore);
  assertBlocked(h);
  await h.flush();
  assert.equal(h.requests.length, 2);
  await h.respond(1, report('CASE-A', 'Fresh after browser back', 7));
  assert.match(h.get('#report-text-link').href, /^blob:/);
  assert.match(h.get('#report-sections').textContent, /Fresh after browser back/);
});

test('pending writes block manual refresh and survive a count-free host refresh', async t => {
  const h = harness(t);
  await h.flush();
  await h.respond(0, report());
  h.signal('oi:case-state-invalidated', 'CASE-A', {pendingWrites: 1});
  assert.equal(h.get('#report-refresh').disabled, true);
  assertBlocked(h);
  // Ordinary state-read invalidation carries no new write count.
  h.signal('oi:case-state-invalidated');
  h.get('#report-refresh').dispatchEvent(new Event('click'));
  await h.flush();
  assert.equal(h.get('#report-refresh').disabled, true);
  assert.equal(h.requests.length, 1, 'no pre-commit report request is sent');
  assertBlocked(h);
});

test('overlapping writes keep refresh blocked until the final write settles', async t => {
  const h = harness(t);
  await h.flush();
  await h.respond(0, report());
  h.signal('oi:case-state-invalidated', 'CASE-A', {pendingWrites: 1});
  h.signal('oi:case-state-invalidated', 'CASE-A', {pendingWrites: 2});
  h.signal('oi:case-state-write-settled', 'CASE-A', {pendingWrites: 1});
  assert.equal(h.get('#report-refresh').disabled, true);
  h.signal('oi:case-state-updated');
  await h.flush();
  assert.equal(h.requests.length, 1, 'an intermediate host update cannot expose old state');
  h.signal('oi:case-state-write-settled', 'CASE-A', {pendingWrites: 0});
  assert.equal(h.get('#report-refresh').disabled, false);
  await h.flush();
  assert.equal(h.requests.length, 1, 'settlement does not independently reload');
  assertBlocked(h);
  h.signal('oi:case-state-updated');
  await h.flush();
  await h.respond(1, report('CASE-A', 'Both saved changes are present', 3));
  assert.match(h.get('#report-sections').textContent, /Both saved changes/);
});

test('a failed settled write leaves the report unavailable until manual retry', async t => {
  const h = harness(t);
  await h.flush();
  await h.respond(0, report());
  h.signal('oi:case-state-invalidated', 'CASE-A', {pendingWrites: 1});
  assert.equal(h.get('#report-refresh').disabled, true);
  // A failed mutation emits settled, with no accepted state-updated event.
  h.signal('oi:case-state-write-settled', 'CASE-A', {pendingWrites: 0});
  assert.equal(h.get('#report-refresh').disabled, false);
  await h.flush();
  assert.equal(h.requests.length, 1);
  assertBlocked(h);
  h.get('#report-refresh').dispatchEvent(new Event('click'));
  await h.flush();
  await h.respond(1, report('CASE-A', 'Unchanged record freshly checked after failure'));
  assert.equal(h.get('#report-print').disabled, false);
  assert.match(h.get('#report-sections').textContent, /freshly checked after failure/);
});

test('pending counts follow their own case across selection changes', async t => {
  const h = harness(t);
  await h.flush();
  await h.respond(0, report());
  const acceptedA = h.get('#report-text-link').href;
  h.signal('oi:case-state-invalidated', 'CASE-B', {pendingWrites: 1});
  assert.equal(h.get('#report-text-link').href, acceptedA);
  assert.equal(h.get('#report-refresh').disabled, false);
  h.changeCase('CASE-B');
  assert.equal(h.get('#report-refresh').disabled, true);
  assertBlocked(h);
  await h.flush();
  assert.equal(h.requests.length, 1, 'selecting a pending case cannot load its old report');
  h.changeCase('CASE-A');
  assert.equal(h.get('#report-refresh').disabled, false);
  await h.flush();
  await h.respond(1, report('CASE-A', 'Unaffected current case'));
  const currentA = h.get('#report-text-link').href;
  h.signal('oi:case-state-write-settled', 'CASE-B', {pendingWrites: 0});
  await h.flush();
  assert.equal(h.get('#report-text-link').href, currentA);
  assert.equal(h.requests.length, 2);
  h.changeCase('CASE-B');
  assert.equal(h.get('#report-refresh').disabled, false);
  await h.flush();
  await h.respond(2, report('CASE-B', 'Settled second case'));
  assert.match(h.get('#report-sections').textContent, /Settled second case/);
});

test('global evidence writes invalidate the current report and block every selected case', async t => {
  const h = harness(t);
  await h.flush();
  await h.respond(0, report());
  const oldUrl = h.get('#report-text-link').href;
  h.signal('oi:case-state-invalidated', null, {scope: 'all-cases', pendingWrites: 1});
  assertBlocked(h);
  assert.equal(h.get('#report-refresh').disabled, true);
  assert.equal(h.get('#report-sections').textContent, '');
  await assert.rejects(fetch(oldUrl));
  h.changeCase('CASE-B');
  assert.equal(h.get('#report-refresh').disabled, true);
  h.get('#report-refresh').dispatchEvent(new Event('click'));
  await h.flush();
  assert.equal(h.requests.length, 1, 'another case cannot expose pre-write shared evidence');
  h.signal('oi:case-state-write-settled', null, {scope: 'all-cases', pendingWrites: 0});
  assert.equal(h.get('#report-refresh').disabled, false);
  assertBlocked(h);
  h.signal('oi:case-state-updated', 'CASE-B');
  await h.flush();
  await h.respond(1, report('CASE-B', 'Shared evidence withdrawal is reflected', 4));
  assert.match(h.get('#report-sections').textContent, /withdrawal is reflected/);
});

test('global and case write counts must both reach zero before refresh is allowed', async t => {
  const h = harness(t);
  await h.flush();
  await h.respond(0, report());
  h.signal('oi:case-state-invalidated', 'CASE-A', {scope: 'case', pendingWrites: 1});
  h.signal('oi:case-state-invalidated', null, {scope: 'all-cases', pendingWrites: 2});
  assert.equal(h.get('#report-refresh').disabled, true);
  h.signal('oi:case-state-write-settled', null, {scope: 'all-cases', pendingWrites: 1});
  h.signal('oi:case-state-write-settled', 'CASE-A', {scope: 'case', pendingWrites: 0});
  h.signal('oi:case-state-updated');
  await h.flush();
  assert.equal(h.get('#report-refresh').disabled, true);
  assert.equal(h.requests.length, 1);
  h.signal('oi:case-state-invalidated', 'CASE-A', {scope: 'case', pendingWrites: 1});
  h.signal('oi:case-state-write-settled', null, {scope: 'all-cases', pendingWrites: 0});
  assert.equal(h.get('#report-refresh').disabled, true, 'remaining case write still blocks');
  h.signal('oi:case-state-write-settled', 'CASE-A', {scope: 'case', pendingWrites: 0});
  assert.equal(h.get('#report-refresh').disabled, false);
  await h.flush();
  assert.equal(h.requests.length, 1, 'settlement alone does not fetch');
  assertBlocked(h);
});

test('failed global writes permit manual recovery only after settlement', async t => {
  const h = harness(t);
  await h.flush();
  await h.respond(0, report());
  h.signal('oi:case-state-invalidated', null, {scope: 'all-cases', pendingWrites: 1});
  assert.equal(h.get('#report-refresh').disabled, true);
  // A case state refresh has no authority to reset the global write count.
  h.signal('oi:case-state-invalidated');
  h.signal('oi:case-state-updated');
  await h.flush();
  assert.equal(h.requests.length, 1);
  h.signal('oi:case-state-write-settled', null, {scope: 'all-cases', pendingWrites: 0});
  assert.equal(h.get('#report-refresh').disabled, false);
  await h.flush();
  assert.equal(h.requests.length, 1);
  assertBlocked(h);
  h.get('#report-refresh').dispatchEvent(new Event('click'));
  await h.flush();
  await h.respond(1, report('CASE-A', 'Record checked after failed global update'));
  assert.match(h.get('#report-sections').textContent, /failed global update/);
  assert.equal(h.get('#report-print').disabled, false);
});
