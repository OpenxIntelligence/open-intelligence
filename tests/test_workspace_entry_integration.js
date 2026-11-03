'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const app = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
const hostFunctions = app.slice(app.indexOf('async function api('), app.indexOf('function pill('));
const entry = fs.readFileSync(path.join(__dirname, '../web/workspace-entry.js'), 'utf8');
function harness() {
  const nodes = new Map(), opened = [], notices = [], callbacks = {};
  const get = id => {
    if (!nodes.has(id)) {
      const node = new EventTarget();
      Object.assign(node, {value: '', checked: false, files: [], options: [], textContent: '', dataset: {},
        replaceChildren() {}, append() {}, scrollIntoView() {}, focus() {}});
      nodes.set(id, node);
    }
    return nodes.get(id);
  };
  const document = new EventTarget(); document.getElementById = get; document.body = {dataset: {}};
  class CustomEvent extends Event { constructor(type, args) { super(type); this.detail = args?.detail; } }
  const active = {case: {case_id: 'CASE-A'},
    sources: [{id: 2, state: 'current'}, {id: 1, state: 'superseded'}],
    assertions: [{source_version_id: 2, source_line: 8}]};
  const context = vm.createContext({document, Event, CustomEvent, active, caseId: 'CASE-A',
    readyCase: () => 'CASE-A', openSource: (...args) => opened.push(args),
    notice: (...args) => notices.push(args),
    MutationObserver: class { observe() {} }, queueMicrotask: () => {},
    fetch: () => new Promise(() => {}),
    OIIntake: {mount(options) { Object.assign(callbacks, options); return {render() {}, resetScope() {}}; }}});
  vm.runInContext('const el = id => document.getElementById(id); const pendingCaseWrites = new Map();\n' + hostFunctions, context);
  const start = app.indexOf("document.addEventListener('oi:composer-open-source'");
  const end = app.indexOf("el('model-investigation-form')", start);
  vm.runInContext(app.slice(start, end), context);
  vm.runInContext(entry, context);
  const send = detail => document.dispatchEvent(new CustomEvent('oi:composer-open-source', {detail}));
  return {get, callbacks, context, opened, notices, send};
}

test('workspace creation and case-switch protection share all follow-through input guards', () => {
  const h = harness(); assert.equal(h.callbacks.canSwitch(), true);
  for (const id of ['ft-title', 'ft-detail', 'ft-due', 'ft-trigger', 'ft-actor', 'ft-reason',
    'ft-owner', 'ft-update-due', 'ft-update-actor', 'ft-update-reason']) {
    h.get(id).value = 'Unsubmitted case-bound work';
    assert.equal(h.callbacks.canSwitch(), false, `${id} must veto a new workspace`);
    h.get(id).value = '';
  }
  h.get('ft-clear-due').checked = true;
  assert.equal(h.callbacks.canSwitch(), false);
  h.get('ft-clear-due').checked = false;
  assert.equal(h.callbacks.canSwitch(), true);
});

test('original drafts and selected files retain the existing case-switch veto', () => {
  const h = harness();
  for (const id of ['question-text','report-text','draft-summary','evidence-rationale']) {
    h.get(id).value = 'Unsubmitted original'; assert.equal(h.callbacks.canSwitch(), false); h.get(id).value = '';
  }
  h.get('source-file').files = [{name: 'original.txt'}]; assert.equal(h.callbacks.canSwitch(), false);
  h.get('source-file').files = []; assert.equal(h.callbacks.canSwitch(), true);
});

test('an unresolved host write vetoes scope creation even after an input is cleared', () => {
  const h = harness(); h.context.api('/api/cases/CASE-A/imports', {text: 'Fictional original'});
  assert.equal(h.callbacks.canSwitch(), false);
});

test('Composer exact-source action reaches the existing inspector only for a current case anchor', () => {
  const h = harness();
  h.send({caseId: 'CASE-A', sourceId: 2, line: 8});
  assert.equal(h.opened.length, 1, 'Source preview action is wired to the original inspector');
  assert.equal(h.opened[0][0].id, 2); assert.equal(h.opened[0][1], 8);
  for (const invalid of [undefined, {caseId: 'CASE-B', sourceId: 2, line: 8},
    {caseId: 'CASE-A', sourceId: 1, line: 8}, {caseId: 'CASE-A', sourceId: 999, line: 8},
    {caseId: 'CASE-A', sourceId: 2, line: 1}, {caseId: 'CASE-A', sourceId: '2', line: 8}]) {
    h.send(invalid); assert.equal(h.opened.length, 1, 'Invalid or stale source event was not followed');
  }
});

test('source actions cannot use the old accepted state while any host write is unresolved', () => {
  const h = harness(); h.context.api('/api/cases/CASE-A/imports', {});
  h.send({caseId: 'CASE-A', sourceId: 2, line: 8});
  assert.equal(h.opened.length, 0, 'Source change in flight must not open the old accepted anchor');
});


test('reviewed text or PDF draft vetoes new workspace without erasing selected bytes', () => {
  const h = harness(); const original = {name: 'fictional.pdf'};
  h.get('intake-file').files = [original];
  assert.equal(h.callbacks.canSwitch(), false);
  assert.equal(h.get('intake-file').files[0], original);
});
