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


const uncertain=()=>({...base(),reviewReturnPhase:'unknown',
 reviewReturnIntent:{patient_id:'PAT-ONE',case_id:'CASE-ONE',
  question_id:'QUESTION-'+'A'.repeat(32),queue_fingerprint:'a'.repeat(64),
  reason:'Independently verify the fictional original statement.'}});
test('Overview preserves exact return-recovery navigation without a current World Model',()=>{
 const state={...uncertain(),worldPhase:'idle',worldModel:null,questions:null};
 const view=projection(state);
 assert.equal(view?.caseId,null);
 assert.equal(view?.questions,null);
 assert.equal(view?.draft,null);
 assert.equal(view?.recoveryCaseId,'CASE-ONE');
});
test('Overview never advertises uncertain return for another patient or revoked case',()=>{
 const state=uncertain();
 for(const change of [
  {reviewReturnIntent:{...state.reviewReturnIntent,patient_id:'PAT-OTHER'}},
  {reviewReturnIntent:{...state.reviewReturnIntent,case_id:'CASE-FOREIGN'}},
  {cases:null},
  {cases:[]},
  {cases:[{patient_id:'PAT-ONE',case_id:'CASE-ONE',status:'revoked'}]},
  {cases:[{patient_id:'PAT-OTHER',case_id:'CASE-ONE',status:'active'}]},
 ]) assert.equal(projection({...state,...change})?.recoveryCaseId,null);
});
test('Overview does not turn a completed, failed, or absent return into recovery',()=>{
 const state=uncertain();
 for(const phase of ['saved','saving','idle','error']){
  assert.equal(projection({...state,reviewReturnPhase:phase})?.recoveryCaseId,null);
 }
 assert.equal(projection({...state,reviewReturnIntent:null})?.recoveryCaseId,null);
});
test('Overview does not silently switch back to an older return from a different selected case',()=>{
 const state=uncertain();
 const other={patient_id:'PAT-ONE',case_id:'CASE-OTHER',status:'active'};
 const switched={...state,cases:[state.cases[0],other],
  worldModel:{patient_id:'PAT-ONE',case_id:'CASE-OTHER',snapshot_fingerprint:'v2'}};
 assert.equal(projection(switched)?.caseId,'CASE-OTHER');
 assert.equal(projection(switched)?.recoveryCaseId,null);
 assert.equal(projection({...state,reviewReturnPhase:'unknown'})?.recoveryCaseId,'CASE-ONE');
});
