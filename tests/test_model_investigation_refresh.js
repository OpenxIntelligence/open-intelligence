'use strict';
// Exercise the actual asynchronous UI loader with delayed synthetic responses.
const assert = require('node:assert/strict');
const {test} = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
const functionStart = source.indexOf('async function loadModelInvestigations()');
const declarationStart = source.indexOf('let modelInvestigationLoadSequence =');
const start = declarationStart >= 0 ? declarationStart : functionStart;
const end = source.indexOf('async function loadChangesSinceReview()', functionStart);
assert.ok(functionStart >= 0 && end > functionStart);

function element(text = '') {
  return {text: text || '', children: [], append(...children) {this.children.push(...children);}};
}
function textOf(item) {return item.text + item.children.map(textOf).join(' ');}
function harness() {
  const list = element(), pending = [], notices = [];
  const ctx = vm.createContext({caseId: 'CASE-ALPHA',
    api: async route => route.endsWith('/investigations')
      ? {investigations: [{id: 1}]}
      : new Promise((resolve, reject) => pending.push({resolve, reject})),
    clear: () => {list.children = [];}, el: () => list,
    node: (tag, text) => element(text), pill: text => element(text),
    empty: () => {}, notice: message => notices.push(message)});
  vm.runInContext(source.slice(start, end), ctx);
  return {ctx, list, pending, notices};
}
const basic = {id: 1, template: 'evidence-summary', mode: 'replay', kind: 'hypothesis',
  status: 'complete', review_state: 'pending', model: 'recorded-fixture',
  claims: [], abstentions: [], dropped: [], input_receipts: []};
const turn = () => new Promise(setImmediate);

test('a delayed pre-revocation response cannot restore withdrawn text after a newer refresh', async () => {
  const h = harness();
  const oldLoad = h.ctx.loadModelInvestigations(); await turn();
  const newLoad = h.ctx.loadModelInvestigations(); await turn();
  h.pending[1].resolve({...basic, output_withheld: true, stale: 1});
  await newLoad;
  h.pending[0].resolve({...basic, output_withheld: false,
    claims: [{text: 'WITHDRAWN FICTIONAL DERIVED TEXT', uncertainty: 'high', citations: []}]});
  await oldLoad;
  assert.equal(h.list.children.length, 1);
  assert.ok(textOf(h.list).includes('Output withheld:'));
  assert.ok(!textOf(h.list).includes('WITHDRAWN FICTIONAL DERIVED TEXT'));
});

test('refresh clears previously displayed output immediately and ignores older errors', async () => {
  const h = harness();
  h.list.append(element('PREVIOUS FICTIONAL OUTPUT'));
  const oldLoad = h.ctx.loadModelInvestigations();
  assert.ok(!textOf(h.list).includes('PREVIOUS FICTIONAL OUTPUT'));
  await turn();
  const newLoad = h.ctx.loadModelInvestigations(); await turn();
  h.pending[1].resolve({...basic, output_withheld: true, stale: 1}); await newLoad;
  h.pending[0].reject(Error('Obsolete synthetic response')); await oldLoad;
  assert.deepEqual(h.notices, []);
});
