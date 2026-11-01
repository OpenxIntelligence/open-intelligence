'use strict';
// Focused asynchronous tests of the actual app.js reader functions; no third-party packages.
const assert = require('node:assert/strict');
const {test} = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const app = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
const start = app.indexOf('function renderOriginalSource(');
const end = app.indexOf('async function downloadSnapshot(', start);
assert.ok(start >= 0 && end > start, 'Expected source-reader functions in actual app.js');
const reader = app.slice(start, end);

function element() {
  return {children: [], open: false, _text: '', dataset: {},
    get textContent() {return this._text + this.children.map(x => x.textContent).join('');},
    set textContent(v) {this._text = String(v); this.children = [];},
    replaceChildren() {this._text = ''; this.children = [];},
    append(...items) {this.children.push(...items);},
    showModal() {this.open = true;}, close() {this.open = false;},
    querySelector() {return this.children.find(x => x.tag === 'mark') || null;},
    scrollIntoView() {}};
}
function harness() {
  const nodes = new Map(), requests = [], notices = [];
  const el = id => {if (!nodes.has(id)) nodes.set(id, element()); return nodes.get(id);};
  const before = {id: 1, document_id: 'PATH-A', version: 1, state: 'superseded',
    kind: 'pathology', event_date: '2026-01-02', specimen_id: 'TISSUE-A', supersedes_id: null};
  const after = {...before, id: 2, version: 2, state: 'current', supersedes_id: 1};
  const other = {...before, id: 3, document_id: 'SCAN-A', kind: 'imaging', specimen_id: null};
  const evidence = {id: 4, evidence_key: 'EVID-A', version: 1, state: 'current'};
  const ctx = vm.createContext({caseId:'CASE-A', renderedCaseId:'CASE-A',
    active:{case:{case_id:'CASE-A'}, sources:[before,after,other], evidence:[evidence]},
    el, node:(tag,text,className)=>Object.assign(element(), {tag,className,_text:String(text)}),
    document:{createTextNode:text=>({textContent:text})},
    readyCase() {if (!ctx.active || ctx.active.case.case_id !== ctx.caseId || ctx.renderedCaseId !== ctx.caseId)
      throw Error('Selected case is loading'); return ctx.caseId;},
    notice:(message,error)=>notices.push({message,error}),
    api:url=>new Promise((resolve,reject)=>requests.push({url,resolve,reject}))});
  vm.runInContext(reader, ctx);
  const cancel = () => {if (typeof ctx.cancelSourceRead === 'function') ctx.cancelSourceRead();};
  return {ctx,el,requests,notices,before,after,other,evidence,cancel};
}

test('a later source selection wins even if the older request finishes last', async()=>{
  const h=harness(); const first=h.ctx.openSource(h.before), second=h.ctx.openSource(h.other);
  h.requests[1].resolve({text:'new selection'}); await second;
  h.requests[0].resolve({text:'old selection'}); await first;
  assert.equal(h.el('dialog-text').textContent,'new selection');
});
test('evidence selection wins over an older source request', async()=>{
  const h=harness(); const first=h.ctx.openSource(h.before), second=h.ctx.openEvidence(h.evidence);
  h.requests[1].resolve({text:'evidence selected'}); await second;
  h.requests[0].resolve({text:'old source'}); await first;
  assert.equal(h.el('dialog-text').textContent,'selected source' === 'new selection' ? 'selected source' : 'evidence selected');
});
test('a late comparison cannot open over a newer source inspection', async()=>{
  const h=harness(); const first=h.ctx.openComparison(h.before,h.after), second=h.ctx.openSource(h.other);
  h.requests[2].resolve({text:'selected source'}); await second;
  h.requests[0].resolve({text:'before'}); h.requests[1].resolve({text:'after'}); await first;
  assert.equal(h.el('compare-dialog').open,false);
  assert.equal(h.el('dialog-text').textContent,'selected source');
});
test('dismissal invalidates an outstanding read rather than reopening a dialog', async()=>{
  const h=harness(); const p=h.ctx.openSource(h.before); h.cancel();
  h.requests[0].resolve({text:'late response'}); await p;
  assert.equal(h.el('source-dialog').open,false);
});
test('case A to B to A does not revive an older A request', async()=>{
  const h=harness(); const p=h.ctx.openSource(h.before);
  h.cancel(); h.ctx.caseId='CASE-B'; h.cancel(); h.ctx.caseId='CASE-A';
  h.requests[0].resolve({text:'obsolete response'}); await p;
  assert.equal(h.el('source-dialog').open,false);
});
test('a stale error does not replace the newer view with an error notice', async()=>{
  const h=harness(); const first=h.ctx.openSource(h.before), second=h.ctx.openSource(h.other);
  h.requests[1].resolve({text:'new selection'}); await second;
  h.requests[0].reject(Error('obsolete failure')); await first;
  assert.equal(h.notices.length,0);
});
test('comparison rejects unrelated same-case sources before any read', async()=>{
  const h=harness(); const p=h.ctx.openComparison(h.before,h.other);
  assert.equal(h.requests.length,0);
  await p; assert.equal(h.el('compare-dialog').open,false);
});
for (const [key,value] of [['specimen_id','OTHER'],['event_date','2026-02-02'],
  ['kind','imaging'],['supersedes_id',3],['version',4]]) {
  test(`comparison rejects mismatched ${key}`, async()=>{
    const h=harness(); h.after[key]=value;
    const p=h.ctx.openComparison(h.before,h.after);
    assert.equal(h.requests.length,0); await p;
  });
}
test('canonical source metadata is used instead of caller-supplied labels', async()=>{
  const h=harness(); const p=h.ctx.openSource({...h.before,document_id:'FORGED-LABEL'});
  h.requests[0].resolve({text:'original'}); await p;
  assert.ok(h.el('dialog-title').textContent.startsWith('PATH-A@1'));
});
test('source ID outside selected case is rejected before a read', async()=>{
  const h=harness(); const p=h.ctx.openSource({...h.before,id:999});
  assert.equal(h.requests.length,0); await p;
});
test('a valid comparison preserves both originals, including markup-like text', async()=>{
  const h=harness(); const p=h.ctx.openComparison(h.before,h.after);
  h.requests[0].resolve({text:'<script>untrusted</script>\nuntested\n'});
  h.requests[1].resolve({text:'negative\n'}); await p;
  assert.equal(h.el('compare-before').textContent,'<script>untrusted</script>\nuntested\n');
  assert.equal(h.el('compare-after').textContent,'negative\n');
  assert.equal(h.el('compare-dialog').open,true);
});
test('source highlighting preserves the original text and invalid anchors are honest',()=>{
  const h=harness(); const text='<b>not markup</b>\nnegative\n';
  assert.equal(h.ctx.renderOriginalSource(text,2),true);
  assert.equal(h.el('dialog-text').textContent,text);
  assert.equal(h.ctx.renderOriginalSource(text,999),false);
  assert.equal(h.el('dialog-text').textContent,text);
});
