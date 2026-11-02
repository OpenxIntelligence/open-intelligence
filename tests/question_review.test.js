'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');
const app = fs.readFileSync(path.join(__dirname, '../web/app.js'), 'utf8');
const helpers = app.slice(app.indexOf('function currentReviewQuestionIds('), app.indexOf('function renderPatientView('));
const mission = fs.readFileSync(path.join(__dirname, '../web/mission.js'), 'utf8');
const start = mission.indexOf('// Begin question review handoff.');
const end = mission.indexOf('// End question review handoff.');
const implementation = start < 0 || end < 0 ? '' : mission.slice(start, end);
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this._text = ''; this.value = ''; this.dataset = {}; this.handlers = {}; this.options = []; this.inputs = []; }
  set textContent(v) { this._text = String(v); this.children = []; }
  get textContent() { return this._text + this.children.map(c => c.textContent || '').join(''); }
  append(...xs) { this.children.push(...xs); }
  replaceChildren(...xs) { this._text = ''; this.children = xs; }
  addEventListener(name, fn) { this.handlers[name] = fn; }
  dispatchEvent(e) { this.handlers[e.type]?.(e); }
  querySelectorAll() { return this.inputs.filter(i => i.checked); }
  focus() { this.focused = true; }
  scrollIntoView() { this.scrolled = true; }
}
function setup(state) {
  const elements = new Map(), calls = [];
  const el = id => { if (!elements.has(id)) elements.set(id, new Element('div')); return elements.get(id); };
  const context = vm.createContext({state, active:state, caseId:state.case.case_id, renderedCaseId:state.case.case_id,
    refreshSequence:1, document:{createElement:tag => new Element(tag)}, Event:class {constructor(type){this.type=type;}},
    el, clear:id=>el(id).replaceChildren(), empty:(e,t)=>e.append(node('p',t)), node,
    pill:(v)=>node('span',v), readyCase:()=>context.caseId,
    notice:(message)=>calls.push(['notice',message]), openSource:s=>calls.push(['source',s.id]),
    openComparison:(a,b)=>calls.push(['compare',a.id,b.id]), openEvidence:e=>calls.push(['evidence',e.id])});
  function node(tag,text='',cls='') {const e=new Element(tag);e.textContent=text;e.className=cls;return e;}
  vm.runInContext(helpers + '\n' + implementation, context);
  el('question-choice').options = state.questions.map(q=>({value:String(q.id)}));
  el('question-choice').value = String(state.questions[0]?.id || '');
  function call(name,...args) {
    assert.equal(vm.runInContext('typeof '+name,context),'function','Missing source-to-review interaction: '+name);
    context.args=args;return vm.runInContext(name+'(...args)',context);
  }
  return {context,el,calls,call,items:()=>JSON.parse(JSON.stringify(call('questionReviewItems',state)))};
}
function source(id,version,previous,state='superseded') {
  return {id,version,supersedes_id:previous,state,document_id:'PATH-A',kind:'pathology',event_date:'2026-05-03',specimen_id:'SPEC-A'};
}
function fixture() {
  return {case:{case_id:'CASE-A'},questions:[{id:1,state:'open',question:'What changed?'}],
    snapshots:[{id:1,question_id:1,state:'stale',source_ids:[1],evidence_assessment_ids:[],broker_link_ids:[]}],
    sources:[source(1,1,null),source(2,2,1,'current')],evidence:[],evidence_assessments:[],broker_links:[]};
}
function buttons(el) {return [el,...el.children.flatMap(buttons)].filter(e=>e.tag==='button');}
test('one row per open review question; old snapshots remain unchanged',()=>{
 const state=fixture();state.snapshots.push({...state.snapshots[0],id:2});const before=JSON.stringify(state);
 const rows=setup(state).items();assert.equal(rows.length,1);assert.equal(rows[0].snapshots.length,2);
 assert.equal(rows[0].reportChanges.length,1);assert.equal(JSON.stringify(state),before);
});
test('resolved historical snapshots do not produce current work; empty is not all-clear',()=>{
 const state=fixture();state.questions[0].state='resolved';const h=setup(state);
 assert.equal(h.items().length,0);h.call('renderQuestionReviews');
 assert.match(h.el('review-question-list').textContent,/does not establish.*complete/i);
});
test('multiple amendments are compared only as consecutive linked pairs',()=>{
 const state=fixture();state.sources[1].state='superseded';state.sources.push(source(3,3,2,'current'));
 const pairs=setup(state).items()[0].reportChanges[0].pairs;
 assert.deepEqual(pairs.map(p=>[p.before.id,p.after.id]),[[1,2],[2,3]]);
});
test('missing predecessor or changed specimen never generates inferred comparison',()=>{
 const state=fixture();state.sources[1].specimen_id='OTHER';
 assert.deepEqual(setup(state).items()[0].reportChanges[0].pairs,[]);
 state.sources=[];const h=setup(state);h.call('renderQuestionReviews');
 assert.match(h.el('review-question-list').textContent,/unavailable/i);
 assert.equal(buttons(h.el('review-question-list')).filter(b=>b.textContent.startsWith('Compare')).length,0);
});
test('withdrawn evidence and unavailable broker rights are not called report amendments',()=>{
 const state=fixture();state.sources=[source(1,1,null,'current')];
 state.evidence=[{id:7,evidence_key:'EVID-A',version:1,state:'withdrawn'}];
 state.evidence_assessments=[{id:9,case_id:'CASE-A',question_id:1,evidence_version_id:7}];
 state.broker_links=[{id:11,rights_state:'revoked',excerpt:'RESTRICTED TEXT',citation_title:'RESTRICTED TITLE'}];
 state.snapshots[0].evidence_assessment_ids=[9];state.snapshots[0].broker_link_ids=[11];
 const h=setup(state);const row=h.items()[0];assert.equal(row.reportChanges.length,0);
 assert.equal(row.evidenceChanges.length,1);assert.equal(row.rightsChanges.length,1);
 h.call('renderQuestionReviews');const text=h.el('review-question-list').textContent;
 assert.match(text,/withdrawn/);assert.match(text,/revoked/);assert.doesNotMatch(text,/RESTRICTED/);
});
test('all review questions remain reachable; no three-card cap or executable labels',()=>{
 const state=fixture();state.questions=[];state.snapshots=[];
 for(let n=1;n<=7;n++){state.questions.push({id:n,state:'open',question:'<script>Q'+n+'</script>'});state.snapshots.push({id:n,question_id:n,state:'stale',source_ids:[1]});}
 const h=setup(state);h.call('renderQuestionReviews');assert.equal(h.el('review-question-list').children.length,7);
 assert.match(h.el('review-question-list').textContent,/<script>Q7<\/script>/);
});
test('current exact source objects are used by direct source and comparison actions',()=>{
 const h=setup(fixture());h.call('renderQuestionReviews');const actions=buttons(h.el('review-question-list'));
 actions.find(b=>b.textContent.startsWith('Compare')).handlers.click();
 actions.find(b=>b.textContent.startsWith('Open')).handlers.click();
 assert.deepEqual(h.calls,[['compare',1,2],['source',1]]);
});
test('handoff selects exact question and focuses existing form without saving or replacing source selection',()=>{
 const state=fixture();state.questions.push({id:2,state:'open',question:'Other'});const h=setup(state);
 h.el('question-choice').value='2';h.el('source-choice').inputs=[{value:'1',checked:true}];
 h.call('prepareQuestionReview',1,{caseId:'CASE-A',sequence:1});
 assert.equal(h.el('question-choice').value,'1');assert.equal(h.el('draft-observations').focused,true);
 assert.equal(h.el('source-choice').inputs[0].checked,true);assert.equal(state.snapshots.length,1);
});
test('another question cannot take unfinished draft text or evidence selections',()=>{
 for(const occupied of ['draft-observations','draft-summary','draft-assumptions','evidence-choice']) {
  const state=fixture();state.questions.push({id:2,state:'open',question:'Other'});const h=setup(state);h.el('question-choice').value='2';
  if(occupied==='evidence-choice')h.el(occupied).inputs=[{checked:true}];else h.el(occupied).value='Keep this';
  h.call('prepareQuestionReview',1,{caseId:'CASE-A',sequence:1});
  assert.equal(h.el('question-choice').value,'2');assert.match(h.calls.at(-1)[1],/unfinished/i);
 }
});
test('same-question handoff preserves narrative and only focuses it',()=>{
 const h=setup(fixture());h.el('draft-observations').value='Keep this';
 h.call('prepareQuestionReview',1,{caseId:'CASE-A',sequence:1});
 assert.equal(h.el('draft-observations').value,'Keep this');assert.equal(h.el('draft-observations').focused,true);
});
test('stale UI actions fail closed after refresh or wrong-case switch',()=>{
 for(const mode of ['refresh','case']){const h=setup(fixture());h.call('renderQuestionReviews');
 const action=buttons(h.el('review-question-list')).find(b=>b.textContent.startsWith('Compare'));
 if(mode==='refresh')h.context.refreshSequence=2;else h.context.caseId='CASE-B';
 action.handlers.click();assert.equal(h.calls.some(x=>x[0]==='compare'),false);assert.match(h.calls.at(-1)[1],/changed|loading/i);
 }
});
test('resolved question cannot be reopened by an old handoff action',()=>{
 const state=fixture();const h=setup(state);state.questions[0].state='resolved';
 h.call('prepareQuestionReview',1,{caseId:'CASE-A',sequence:1});
 assert.notEqual(h.el('draft-observations').focused,true);assert.equal(state.questions[0].state,'resolved');
});
