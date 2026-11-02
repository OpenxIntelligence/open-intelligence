'use strict';
// Exercise the actual app renderers with fictional state and an inert DOM.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');
const app = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
const prefix = app.slice(0, app.indexOf('async function refresh()'));
const timeline = app.slice(app.indexOf('function groupedTimeline('), app.indexOf('function renderTimeline('));
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.value = ''; this.dataset = {}; this._text = ''; }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(x => typeof x === 'string' ? x : x.textContent).join(''); }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this._text = ''; this.children = items; }
  addEventListener() {}
}
function setup(state) {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element('div')); return elements.get(id); };
  const context = vm.createContext({document: {getElementById: get, createElement: tag => new Element(tag)}, state});
  vm.runInContext(prefix + '\n' + timeline, context);
  vm.runInContext('active = state;', context);
  return {context, get, render: () => { vm.runInContext('renderPatientView()', context); return get('patient-uncertainty').textContent; }};
}
function fixture() {
  return {case: {case_id: 'CASE-TEST', label: 'Fictional parser case'},
    sources: [], assertions: [], questions: [], snapshots: []};
}
function assertion(certainty, key = certainty) {
  return {certainty, finding_key: key, quote: 'Original fictional source statement.', source_version_id: 7, source_line: 9};
}
test('pending result appears under uncertainty without any amendment', () => {
  const state = fixture(); state.assertions.push(assertion('pending'));
  const text = setup(state).render();
  assert.match(text, /still pending/);
  assert.doesNotMatch(text, /Nothing in this fictional case/);
});
test('not reported and not assessed remain different states', () => {
  const state = fixture(); state.assertions.push(assertion('not-reported'), assertion('not-assessed'));
  const text = setup(state).render();
  assert.match(text, /not reported/); assert.match(text, /not assessed/);
  assert.match(text, /source version #7, line 9/);
});
test('indeterminate and conflicting statements keep their uncertainty', () => {
  const state = fixture(); state.assertions.push(assertion('indeterminate'), assertion('conflicting'));
  const text = setup(state).render();
  assert.match(text, /not certain yet/); assert.match(text, /different reports disagree/);
});
test('historical stale drafts do not reopen a resolved question', () => {
  const state = fixture(); state.questions.push({id: 1, state: 'resolved', question: 'Fictional question'});
  state.snapshots.push({id: 1, state: 'stale', question_id: 1}, {id: 2, state: 'reviewed', question_id: 1});
  const text = setup(state).render();
  assert.match(text, /0 open source-change review\(s\)/);
  assert.match(text, /1 older draft\(s\).*history/);
  assert.doesNotMatch(text, /earlier draft\(s\) need another look/);
});
test('two stale drafts for one open question count as one current review', () => {
  const state = fixture(); state.questions.push({id: 1, state: 'open', question: 'Fictional question'});
  state.snapshots.push({id: 1, state: 'stale', question_id: 1}, {id: 2, state: 'stale', question_id: 1});
  const text = setup(state).render();
  assert.match(text, /1 open source-change review\(s\)/);
  assert.match(text, /2 older draft\(s\).*history/);
});
test('an unanswered question is not an all-clear even with no stale drafts', () => {
  const state = fixture(); state.questions.push({id: 2, state: 'open', question: 'What is missing?'});
  const text = setup(state).render();
  assert.match(text, /1 open question\(s\)/);
  assert.doesNotMatch(text, /Nothing in this fictional case/);
});
test('empty data does not imply completeness or clinical approval', () => {
  const text = setup(fixture()).render();
  assert.match(text, /does not establish.*complete/i);
  assert.match(text, /not.*clinical/i);
});
test('original source text and state are preserved without executable markup', () => {
  const state = fixture(); const fact = assertion('pending', '<img src=x onerror=alert(1)>');
  fact.quote = '<script>untrusted fictional text</script>'; state.assertions.push(fact);
  const original = JSON.stringify(state); const {render, get} = setup(state); render();
  assert.equal(JSON.stringify(state), original);
  assert.match(get('patient-findings').textContent, /<script>untrusted fictional text<\/script>/);
  assert.equal(get('patient-findings').children[0].children[1].tag, 'p');
});
test('case list counts current review questions, not retained stale drafts', async () => {
  const state = fixture(); state.questions.push({id: 1, state: 'resolved', question: 'Answered'});
  state.snapshots.push({id: 1, state: 'stale', question_id: 1});
  const {context, get} = setup(state);
  vm.runInContext('api = async () => state', context);
  await vm.runInContext('renderIncomingBoard([{case_id: "CASE-TEST", label: "Fictional case"}])', context);
  assert.match(get('incoming-list').textContent, /Open source-change reviews: 0/);
  assert.match(get('incoming-list').textContent, /Historical stale drafts: 1/);
});
test('a slower older case-list response cannot replace a newer one', async () => {
  const state = fixture(); const {context, get} = setup(state); const pending = [];
  context.fetchState = () => new Promise(resolve => pending.push(resolve));
  vm.runInContext('api = fetchState', context);
  const first = vm.runInContext('renderIncomingBoard([{case_id: "CASE-TEST", label: "Older summary"}])', context);
  const second = vm.runInContext('renderIncomingBoard([{case_id: "CASE-TEST", label: "Newer summary"}])', context);
  pending[1](state); await second; pending[0](state); await first;
  assert.match(get('incoming-list').textContent, /Newer summary/);
  assert.doesNotMatch(get('incoming-list').textContent, /Older summary/);
});
