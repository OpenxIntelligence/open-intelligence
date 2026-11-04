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
