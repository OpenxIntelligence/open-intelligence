'use strict';
// Actual canonical app functions with an inert DOM and controlled responses.
// These are synthetic UI-state checks, not patient authentication or browser tests.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');
const app = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
const prefix = app.slice(0, app.indexOf('async function renderIncomingBoard('));
const refresh = app.slice(app.indexOf('async function refresh()'), app.indexOf('function readyCase()'));
const ready = app.slice(app.indexOf('function readyCase()'), app.indexOf('function renderEvidenceChoices()'));
function setup() {
  const elements = new Map();
  const get = id => {
    if (!elements.has(id)) elements.set(id, {value:'',textContent:'',className:'',hidden:true});
    return elements.get(id);
  };
  const context = vm.createContext({document:{getElementById:get}, renderCount:0});
  vm.runInContext(prefix + '\n' + refresh + '\n' + ready, context);
  vm.runInContext("caseId='CASE-ALPHA'; active={case:{case_id:caseId,label:'Fictional Alpha'}}; renderedCaseId=caseId; render=()=>{renderCount++;renderedCaseId=caseId};", context);
  return {context,get,run:script=>vm.runInContext(script,context)};
}
function deferred() { let resolve,reject; const promise=new Promise((a,b)=>{resolve=a;reject=b}); return {promise,resolve,reject}; }
function record(id='CASE-ALPHA') { return {case:{case_id:id,label:'Fictional '+id}}; }

test('unfinished question or source/evidence text cannot be discarded by new-case intake', () => {
  for (const id of ['question-text','report-text','evidence-text']) {
    const {get,run}=setup(); get(id).value='Unsubmitted original fictional work';
    assert.equal(run('hasUnsavedCaseWork()'), true, id);
  }
});
test('case mutations are unavailable while refreshed source state is in flight', async () => {
  const {context,run}=setup(); const pending=deferred(); context.pending=pending.promise;
  run('api=async()=>pending'); const request=run('refresh()');
  assert.throws(()=>run('readyCase()'), /loading/);
  pending.resolve(record()); assert.equal(await request,true);
  assert.equal(run('readyCase()'),'CASE-ALPHA');
});
test('refresh failure clears obsolete writable state and reports failure to intake', async () => {
  const {get,run}=setup();run("api=async()=>{throw Error('state unavailable')}");
  assert.equal(await run('refresh()'),false);
  assert.throws(()=>run('readyCase()'),/loading/);
  assert.equal(run('active'),null);
  assert.match(get('notice').textContent,/state unavailable/);
  assert.equal(run('renderCount'),0);
});
test('malformed or other-case state cannot be rendered as the selected case', async () => {
  for (const response of [null,{},record('CASE-BETA')]) {
    const {context,run}=setup();context.response=response;run('api=async()=>response');
    assert.equal(await run('refresh()'),false);
    assert.equal(run('active'),null);assert.equal(run('renderCount'),0);
    assert.throws(()=>run('readyCase()'),/loading/);
  }
});
test('render failure does not leave the partial state eligible for writes', async () => {
  const {context,run}=setup();context.response=record();
  run("api=async()=>response;render=()=>{throw Error('render unavailable')}");
  assert.equal(await run('refresh()'),false);
  assert.throws(()=>run('readyCase()'),/loading/);assert.equal(run('active'),null);
});
test('successful refresh explicitly confirms the selected rendered case', async () => {
  const {context,run}=setup();context.response=record();run('api=async()=>response');
  assert.equal(await run('refresh()'),true);assert.equal(run('renderCount'),1);
  assert.equal(run('readyCase()'),'CASE-ALPHA');
});
test('obsolete failure cannot clear a newer successful refresh', async () => {
  const {context,run}=setup();const older=deferred(),newer=deferred();
  const queue=[older.promise,newer.promise];context.next=()=>queue.shift();run('api=()=>next()');
  const first=run('refresh()'),second=run('refresh()');
  newer.resolve(record());await second;older.reject(Error('old failure'));await first;
  assert.equal(run('readyCase()'),'CASE-ALPHA');assert.equal(run('renderCount'),1);
});
test('late prior-case response cannot replace the newly selected case', async () => {
  const {context,run}=setup();const older=deferred();context.pending=older.promise;run('api=()=>pending');
  const first=run('refresh()');
  run("caseId='CASE-BETA';active={case:{case_id:'CASE-BETA'}};renderedCaseId=caseId;refreshSequence++");
  older.resolve(record());await first;
  assert.equal(run('readyCase()'),'CASE-BETA');assert.equal(run('renderCount'),0);
});
