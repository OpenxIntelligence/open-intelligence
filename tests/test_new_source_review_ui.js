'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const app = fs.readFileSync(require('node:path').join(__dirname,'../web/app.js'),'utf8');
function element(tag, text) {
  return {tag, textContent:text || '', children:[], listeners:{}, isConnected:true, value:'', disabled:false,
    append(...items) { this.children.push(...items); }, replaceChildren(...items) { this.children=items; },
    remove() { this.isConnected=false; }, addEventListener(name,cb) {this.listeners[name]=cb;}, reportValidity() {return true;},
    setAttribute() {}, focus() {}};
}
function flatten(el) { return [el,...el.children.flatMap(flatten)]; }
function harness() {
  const begin=app.indexOf('async function openNewSourceReview(');
  const end=app.indexOf("\nel('model-investigation-form')",begin);
  assert.ok(begin>=0 && end>begin,'new-source review UI handler is missing');
  const requests=[],notices=[];const box=element('div');
  const ctx=vm.createContext({caseId:'CASE-ALPHA',refreshSequence:0,readyCase:()=>ctx.caseId,
    node:element,notice:(...args)=>notices.push(args),refresh:async()=>{ctx.refreshed=true;},
    api:(url,body)=>new Promise((resolve,reject)=>requests.push({url,body,resolve,reject}))});
  vm.runInContext(app.slice(begin,end),ctx);
  return {ctx,requests,notices,box};
}
function payload(allowed=true) {
  return {disclaimer:'Unranked inputs only; no clinical relevance assessed.',request_allowed:allowed,requests:[],
    sources:[{source_version_id:9,document_id:'PLAN-NEW',version:1,received_at:'2026-06-02',
    findings:[{source_line:8,certainty:'reported',quote:'<script>fictional later plan</script>'}]}]};
}
test('opens a bounded source-line request with untrusted text rendered as text',async()=>{
  const h=harness();const run=h.ctx.openNewSourceReview({id:4},h.box);
  h.requests[0].resolve(payload());await run;
  const nodes=flatten(h.box);
  assert.ok(nodes.some(n=>n.textContent.includes('no clinical relevance')));
  assert.ok(nodes.some(n=>n.textContent.includes('<script>fictional later plan</script>')));
  assert.ok(!nodes.some(n=>Object.hasOwn(n,'innerHTML')));
  assert.ok(nodes.some(n=>n.tag==='form'));
});
test('submits the selected source and line for the captured case and snapshot',async()=>{
  const h=harness();const run=h.ctx.openNewSourceReview({id:4},h.box);
  h.requests[0].resolve(payload());await run;
  const nodes=flatten(h.box),form=nodes.find(n=>n.tag==='form');
  nodes.find(n=>n.tag==='textarea').value='The later plan requires a source-linked review.';
  const submission=form.listeners.submit({preventDefault(){}});
  assert.equal(h.requests[1].url,'/api/cases/CASE-ALPHA/snapshots/4/new-source-review');
  assert.equal(h.requests[1].body.source_version_id,9);
  assert.equal(h.requests[1].body.source_line,8);
  assert.ok(!Object.hasOwn(h.requests[1].body,'approve'));
  h.requests[1].resolve({result:'review_requested'});await submission;
  assert.equal(h.ctx.refreshed,true);
});
test('stale snapshots show request history without a new submit control',async()=>{
  const h=harness();const run=h.ctx.openNewSourceReview({id:4},h.box);
  const data=payload(false);data.requests=[{event_id:7,source_version_id:9,source_line:8,
      reviewer_label:'Demo reader',rationale:'Source review requested.',source_quote:'Earlier exact quote.'}];
  h.requests[0].resolve(data);await run;
  assert.ok(!flatten(h.box).some(n=>n.tag==='form'));
  assert.ok(flatten(h.box).some(n=>n.textContent.includes('Earlier exact quote.')));
});
test('changing case while context loads cannot display or submit old-case work',async()=>{
  const h=harness();const run=h.ctx.openNewSourceReview({id:4},h.box);
  h.ctx.caseId='CASE-BETA';h.requests[0].resolve(payload());await run;
  assert.ok(!flatten(h.box).some(n=>n.tag==='form'));
  assert.equal(h.requests.length,1);
});
test('removed card and late failed response do not overwrite current view',async()=>{
  const h=harness();const run=h.ctx.openNewSourceReview({id:4},h.box);
  h.box.isConnected=false;h.requests[0].reject(Error('obsolete failure'));await run;
  assert.equal(h.notices.length,0);
});
test('snapshot stale explanation does not imply every cause is an amendment',()=>{
  assert.ok(!app.includes('A source was amended. This version remains historical'));
});

test('A to B to A during loading does not revive the old response',async()=>{
  const h=harness();const run=h.ctx.openNewSourceReview({id:4},h.box);
  h.ctx.caseId='CASE-BETA';h.ctx.refreshSequence++;
  h.ctx.caseId='CASE-ALPHA';h.ctx.refreshSequence++;
  h.requests[0].resolve(payload());await run;
  assert.ok(!flatten(h.box).some(n=>n.tag==='form'));
});

test('failed context load offers a bounded retry instead of a permanent loading state',async()=>{
  const h=harness();const run=h.ctx.openNewSourceReview({id:4},h.box);
  h.requests[0].reject(Error('Temporary connection failure'));await run;
  const retry=flatten(h.box).find(n=>n.tag==='button' && n.textContent==='Retry source review');
  assert.ok(retry,'Missing context retry control');
  retry.listeners.click();assert.equal(h.requests.length,2);
  h.requests[1].resolve(payload());await new Promise(resolve=>setImmediate(resolve));
  assert.ok(flatten(h.box).some(n=>n.tag==='form'));
});
