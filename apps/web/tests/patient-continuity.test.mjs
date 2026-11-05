import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
const module = await import('../.test-dist/registry-client.js');
const projection = s => module.patientContinuity?.(s);
const base = () => ({...new RegistrySession().snapshot(),connected:true,phase:'ready',
 patient:{patient_id:'PAT-ONE',status:'active'},
 cases:[{patient_id:'PAT-ONE',case_id:'CASE-ONE',status:'active'}],
 worldPhase:'ready',worldModel:{patient_id:'PAT-ONE',case_id:'CASE-ONE',snapshot_fingerprint:'v1'},
 questionsCaseId:'CASE-ONE',questionsAccessReceiptId:'ACCESS-ONE',questionListPhase:'ready',questions:[]});
const row = status => ({patient_id:'PAT-ONE',case_id:'CASE-ONE',source_context_state:status});
test('overview distinguishes unchecked questions from a checked empty list',()=>{
 const state=base();
 assert.deepEqual(projection(state)?.questions,{current:0,reassessment:0});
 assert.equal(projection({...state,questions:null})?.questions,null);
});
test('overview separates current unreviewed questions from source reassessment',()=>{
 assert.deepEqual(projection({...base(),questions:[row('current_unreviewed_question'),row('source_reassessment_required')]})?.questions,{current:1,reassessment:1});
});
test('overview withholds all patient context after disconnect, failed read or suspension',()=>{
 for(const patch of [{connected:false},{patient:null},{phase:'reading'},{phase:'error'},
 {patient:{patient_id:'PAT-ONE',status:'suspended'}}]) assert.equal(projection({...base(),...patch}),null);
});
test('overview excludes wrong-patient, wrong-case and revoked mappings',()=>{
 for(const patch of [{cases:[]},{cases:[{patient_id:'PAT-OTHER',case_id:'CASE-ONE',status:'active'}]},
 {cases:[{patient_id:'PAT-ONE',case_id:'CASE-ONE',status:'revoked'}]},
 {worldModel:{patient_id:'PAT-OTHER',case_id:'CASE-ONE'}}]) {
  const view=projection({...base(),...patch});assert.equal(view?.caseId,null);assert.equal(view?.questions,null);
 }
});
test('question counts need successful scoped history and never hide mixed rows',()=>{
 for(const patch of [{questionListPhase:'loading'},{questionListPhase:'error'},
 {questionsCaseId:'CASE-OTHER'},{questionsAccessReceiptId:null},
 {questions:[{...row('current_unreviewed_question'),patient_id:'PAT-OTHER'}]},
 {questions:[{...row('current_unreviewed_question'),case_id:'CASE-OTHER'}]}])
  assert.equal(projection({...base(),...patch})?.questions,null);
});
test('draft resume distinguishes confirmed, in-flight and uncertain saves',()=>{
 const state={...base(),questionDraft:{case_id:'CASE-ONE',snapshot_fingerprint:'v1',question:'Fictional question'}};
 assert.equal(projection(state)?.draft,'unsaved');
 assert.equal(projection({...state,questionSavePhase:'saving'})?.draft,'saving');
 assert.equal(projection({...state,questionSavePhase:'error'})?.draft,'needs_attention');
 assert.equal(projection({...state,questionSavePhase:'saved',savedQuestion:{question_id:'Q'}})?.draft,'saved');
 assert.equal(projection({...state,questionDraft:{...state.questionDraft,case_id:'CASE-OTHER'}})?.draft,null);
 assert.equal(projection({...state,questionDraft:{...state.questionDraft,snapshot_fingerprint:'old'}})?.draft,null);
});
test('failed world read cannot reuse an earlier source index as the selected case',()=>{
 assert.equal(projection({...base(),worldPhase:'error',sourceIndex:{patient_id:'PAT-ONE',case_id:'CASE-ONE'}})?.caseId,null);
});

const checkedTasks=()=>({followthroughPhase:'ready',followthroughCaseId:'CASE-ONE',followthrough:{
 contract:'oi.pg-question-followthrough/1',patient_id:'PAT-ONE',case_id:'CASE-ONE',
 access_receipt_id:'ACCESS-'+'D'.repeat(32),evaluated_on:'2026-11-03',tasks:[],
 synthetic:true,clinical_approval:false,external_notification_sent:false}});

test('overview exposes a checked empty follow-up read separately from unchecked work',()=>{
 assert.deepEqual(projection({...base(),...checkedTasks()})?.followthrough?.counts,
  {all:0,recheck:0,overdue:0,unassigned:0,history:0});
 assert.equal(projection(base())?.followthrough,null);
});

test('overview requires its own successfully loaded case before showing follow-up',()=>{
 for(const patch of [{worldPhase:'error'},{worldPhase:'loading'},{worldModel:null},
  {worldModel:{patient_id:'PAT-ONE',case_id:'CASE-OTHER',snapshot_fingerprint:'v1'}}]){
  assert.equal(projection({...base(),...checkedTasks(),...patch})?.followthrough,null);
 }
});

test('an independent follow-up read failure preserves the question counts and draft',()=>{
 const state={...base(),...checkedTasks(),questions:[row('current_unreviewed_question')],
  questionDraft:{case_id:'CASE-ONE',snapshot_fingerprint:'v1',question:'Fictional question'},
  followthroughPhase:'error',followthrough:null};
 const view=projection(state);
 assert.equal(view?.followthrough,null);
 assert.deepEqual(view?.questions,{current:1,reassessment:0});
 assert.equal(view?.draft,'unsaved');
});

const modelSummary=(current_sources=2,source_disagreements=0,unresolved_observations=0)=>({
 patient_id:'PAT-ONE',case_id:'CASE-ONE',snapshot_fingerprint:'v1',
 observations:current_sources?[{source_id:'SRC-ONE',source_line:2}]:[],
 summary:{current_sources,historical_sources:0,current_observations:2,
  unresolved_observations,source_disagreements}
});
test('preparation prompts derive only from verified case sources and questions, not clinical inference',()=>{
 const state={...base(),worldModel:modelSummary(2,1,2),
  questions:[row('current_unreviewed_question'),row('source_reassessment_required')]};
 const view=projection(state);
 assert.deepEqual(view?.preparation.map(x=>x.key),
  ['question-recheck','source-disagreements','unresolved-statements']);
 assert.equal(view?.preparationTotal,3);
 assert.deepEqual(view?.preparation.map(x=>x.destination),
  ['Investigations','Journey','Journey']);
 assert.ok(view.preparation.every(x=>!/(treat|prescribe|eligible|cure)/i.test(x.title)));
});
test('preparation distinguishes unchecked question history from zero questions',()=>{
 const checked=projection({...base(),worldModel:modelSummary()});
 assert.equal(checked?.preparation.find(x=>x.key==='prepare-a-question')?.destination,'Journey');
 assert.ok(!checked?.preparation.some(x=>x.key==='questions-unchecked'));
 const unknown=projection({...base(),worldModel:modelSummary(),questionListPhase:'error'});
 assert.ok(unknown?.preparation.some(x=>x.key==='questions-unchecked'));
 assert.ok(!unknown?.preparation.some(x=>x.key==='prepare-a-question'));
});
test('empty structured-source coverage is not a claim about all originals',()=>{
 const view=projection({...base(),worldModel:modelSummary(0)});
 const cue=view?.preparation.find(x=>x.key==='check-record-coverage');
 assert.equal(cue?.destination,'Records');
 assert.match(cue?.detail||'',/Reviewed text\/PDF records and unconnected providers are outside this count/);
 assert.ok(!view?.preparation.some(x=>x.key==='prepare-a-question'));
});
test('preparation caps visible prompts but reports full supported coverage',()=>{
 const state={...base(),worldModel:modelSummary(0,1,2),
  questions:[row('source_reassessment_required')]};
 const view=projection(state);
 assert.deepEqual(view?.preparation.map(x=>x.key),
  ['question-recheck','source-disagreements','unresolved-statements']);
 assert.equal(view?.preparationTotal,4);
});
test('preparation never discloses cached other-patient, revoked or failed-read case context',()=>{
 const state={...base(),worldModel:modelSummary(2,1,2),
  questions:[row('source_reassessment_required')]};
 for(const patch of [{connected:false},{worldPhase:'error'},{patient:{patient_id:'PAT-ONE',status:'suspended'}},
  {cases:[{patient_id:'PAT-ONE',case_id:'CASE-ONE',status:'revoked'}]},
  {worldModel:{...modelSummary(2,1,2),patient_id:'PAT-TWO'}},
  {worldModel:{...modelSummary(2,1,2),case_id:'CASE-TWO'}}]){
  const result=projection({...state,...patch});
  assert.ok(result===null||result.preparation.length===0);
 }
 const unrelated={...state,questions:[{...row('source_reassessment_required'),patient_id:'PAT-TWO'}]};
 assert.ok(!projection(unrelated)?.preparation.some(x=>x.key==='question-recheck'));
});

test('laboratory-only cases offer inspection and withhold the source-line question action',()=>{
 const laboratoryOnly={...modelSummary(),observations:[],
  summary:{current_sources:1,historical_sources:0,current_observations:1,
   current_laboratory_observations:1,unresolved_observations:1,source_disagreements:0}};
 const view=projection({...base(),worldModel:laboratoryOnly});
 assert.ok(!view.preparation.some(item=>item.key==='prepare-a-question'));
 assert.equal(view.preparation.find(item=>item.key==='unresolved-statements')?.destination,'Journey');
});
