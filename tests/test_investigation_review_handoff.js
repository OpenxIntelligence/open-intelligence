'use strict';
// Exercise the actual app.js handoff functions with a deterministic DOM/API harness.
const assert = require('node:assert/strict');
const {test} = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const app = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
const start = app.indexOf('function modelViewIsCurrent(');
const end = app.indexOf('async function loadChangesSinceReview(', start);

function element(tag = 'div', text = '') {
  return {tag, children: [], disabled: false, events: {}, _text: text == null ? '' : String(text),
    get textContent() {return this._text + this.children.map(x => x.textContent).join('');},
    set textContent(v) {this._text = String(v); this.children = [];},
    append(...items) {this.children.push(...items);},
    replaceChildren() {this._text = ''; this.children = [];},
    addEventListener(name, fn) {this.events[name] = fn;}};
}
function harness() {
  assert.ok(start >= 0 && end > start, 'Actual app.js handoff functions must exist');
  const requests = [], notices = [], readers = [], nodes = new Map();
  let refreshes = 0;
  const el = id => {if (!nodes.has(id)) nodes.set(id, element()); return nodes.get(id);};
  const ctx = vm.createContext({caseId:'CASE-ALPHA', renderedCaseId:'CASE-ALPHA', refreshSequence:1,
    active:{case:{case_id:'CASE-ALPHA'}, sources:[{id:1}], evidence:[{id:8}]},
    node:element, el, clear:id=>el(id).replaceChildren(),
    empty:(target,text)=>target.append(element('p',text)), pill:text=>element('span',text),
    notice:(message,error)=>notices.push({message,error}),
    readyCase() {if (!ctx.active || ctx.caseId !== ctx.active.case.case_id || ctx.renderedCaseId !== ctx.caseId)
      throw Error('Case is still loading'); return ctx.caseId;},
    api:(url,payload)=>new Promise((resolve,reject)=>requests.push({url,payload,resolve,reject})),
    refresh:async()=>{refreshes++; ctx.refreshSequence++;},
    openSource:item=>readers.push({type:'source',id:item.id}),
    openEvidence:item=>readers.push({type:'evidence',id:item.id})});
  vm.runInContext(app.slice(start, end), ctx);
  const detail = {id:5,case_id:'CASE-ALPHA',question_id:2,template:'evidence-summary',
    status:'completed',mode:'replay',model:'recorded-replay',stale:0,
    context_fingerprint:'a'.repeat(64),claims:[],abstentions:[],dropped:[],review_draft:null};
  return {ctx,el,requests,notices,readers,detail,get refreshes(){return refreshes;}};
}
function allButtons(element) {
  return [...(element.tag === 'button' ? [element] : []), ...element.children.flatMap(allButtons)];
}

test('one prepare click disables submission and only prepares a draft', async()=>{
  const h=harness(), button=element('button','Prepare review draft');
  const pending=h.ctx.prepareModelReviewDraft(h.detail,'CASE-ALPHA',1,button);
  assert.equal(button.disabled,true);
  await h.ctx.prepareModelReviewDraft(h.detail,'CASE-ALPHA',1,button);
  assert.equal(h.requests.length,1);
  assert.equal(h.requests[0].url,'/api/cases/CASE-ALPHA/investigations/5/review-draft');
  assert.deepEqual(JSON.parse(JSON.stringify(h.requests[0].payload)),{question_id:2});
  h.requests[0].resolve({snapshot_id:9,state:'draft',duplicate:false}); await pending;
  assert.equal(h.refreshes,1);
  assert.match(h.notices[0].message,/review/i);
  assert.equal(h.requests.some(r=>r.url.endsWith('/review')),false);
});
test('wrong case, stale investigation, and strict ID failures produce no writes', async()=>{
  const h=harness();
  for (const detail of [{...h.detail,case_id:'CASE-BETA'}, {...h.detail,stale:1},
    {...h.detail,id:true}, {...h.detail,question_id:'2'}, {...h.detail,context_fingerprint:null}]) {
    await h.ctx.prepareModelReviewDraft(detail,'CASE-ALPHA',1,element('button'));
  }
  assert.equal(h.requests.length,0);
});
test('A to B to A selection does not revive a late prepare response or error', async()=>{
  for (const rejected of [false,true]) {
    const h=harness(), pending=h.ctx.prepareModelReviewDraft(h.detail,'CASE-ALPHA',1,element('button'));
    h.ctx.caseId='CASE-BETA'; h.ctx.refreshSequence++;
    h.ctx.caseId='CASE-ALPHA'; h.ctx.refreshSequence++;
    if(rejected) h.requests[0].reject(Error('Old request failed'));
    else h.requests[0].resolve({snapshot_id:9,state:'draft'});
    await pending; assert.equal(h.notices.length,0); assert.equal(h.refreshes,0);
  }
});
test('a current server rejection permits an explicit retry', async()=>{
  const h=harness(), button=element('button','Prepare review draft');
  const pending=h.ctx.prepareModelReviewDraft(h.detail,'CASE-ALPHA',1,button);
  h.requests[0].reject(Error('Investigation context is stale')); await pending;
  assert.equal(button.disabled,false); assert.equal(button.textContent,'Prepare review draft');
  assert.equal(h.notices[0].error,true); assert.equal(h.refreshes,0);
});
test('current model card exposes one prepare action and linked reports expose their existing draft', async()=>{
  for (const linked of [false,true]) {
    const h=harness(); if(linked) h.detail.review_draft={snapshot_id:9,state:'draft'};
    const pending=h.ctx.loadModelInvestigations();
    h.requests[0].resolve({investigations:[{id:5}]}); await new Promise(resolve=>setImmediate(resolve));
    h.requests[1].resolve(h.detail); await pending;
    const list=h.el('model-investigation-list');
    assert.equal(allButtons(list).filter(b=>b.textContent==='Prepare review draft').length,linked ? 0 : 1);
    if(linked) assert.match(list.textContent,/Review draft #9/);
  }
});
test('late model listing does not replace the selected case after an A to B to A switch', async()=>{
  const h=harness(), pending=h.ctx.loadModelInvestigations();
  h.ctx.caseId='CASE-BETA'; h.ctx.refreshSequence++;
  h.ctx.caseId='CASE-ALPHA'; h.ctx.refreshSequence++;
  h.el('model-investigation-list').textContent='Current case view';
  h.requests[0].resolve({investigations:[{id:5}]}); await pending;
  assert.equal(h.requests.length,1);
  assert.equal(h.el('model-investigation-list').textContent,'Current case view');
});
test('resolved source and evidence citations open canonical readers only in their selected case', async()=>{
  const h=harness(), container=element();
  h.ctx.appendReviewCitations(container,[
    {type:'source',id:1,label:'source #1: DOC@1'},
    {type:'assessment',id:4,evidence_version_id:8,label:'assessment #4: EVID@1'},
  ],'CASE-ALPHA',1);
  const buttons=allButtons(container);
  assert.equal(buttons.length,2);
  await buttons[0].events.click(); await buttons[1].events.click();
  assert.deepEqual(h.readers,[{type:'source',id:1},{type:'evidence',id:8}]);
  h.ctx.caseId='CASE-BETA'; h.ctx.refreshSequence++;
  await buttons[0].events.click(); await buttons[1].events.click();
  assert.equal(h.readers.length,2);
});
