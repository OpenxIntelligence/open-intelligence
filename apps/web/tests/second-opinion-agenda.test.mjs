import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {secondOpinionPreparation} from '../.test-dist/second-opinion-preparation.js';

const patientId='PAT-AGENDA';
const caseId='CASE-AGENDA';
const sourceId='SRC-'+'A'.repeat(32);
function ready(){
 return {...new RegistrySession().snapshot(),connected:true,phase:'ready',
  patient:{patient_id:patientId,origin_org:'ORG-ONE',created_at:'2026-11-03T10:00:00Z',status:'active',revision:1},
  cases:[{patient_id:patientId,case_id:caseId,status:'active'}],
  worldPhase:'ready',worldModel:{patient_id:patientId,case_id:caseId,snapshot_fingerprint:'v1'},
  questionsCaseId:caseId,questionsAccessReceiptId:'ACCESS-'+'B'.repeat(32),questionListPhase:'ready',questions:[],
  recordsPhase:'ready',sourceIndex:{contract:'oi.synthetic-original-sources/1',patient_id:patientId,case_id:caseId,
   access_receipt_id:'ACCESS-'+'C'.repeat(32),sources:[{source_id:sourceId,state:'current'}],
   source_reported_assertions:[],synthetic:true,clinical_interpretation:false,research_review_invalidation_integrated:false}};
}
function question(i,source_context_state='current_unreviewed_question'){
 return {question_id:'QUESTION-'+String(i).padStart(32,'A'),patient_id:patientId,case_id:caseId,
  question:'Can we discuss fictional finding '+i+' & <reported observation>?',
  source_id:sourceId,source_line:i,source_sha256:'a'.repeat(64),source_version:i,
  source_snapshot_sha256:'b'.repeat(64),source_snapshot_contract:'oi.pg-source-world-model/1',
  preflight_sha256:'c'.repeat(64),created_at:'2026-11-03T10:00:00Z',source_context_state,
  human_review_state:'not_submitted',clinical_approval:false,model_executed:false};
}
test('a saved discussion agenda preserves literal question content, provenance and original order',()=>{
 const rows=[question(1,'source_reassessment_required'),question(2)];
 const view=secondOpinionPreparation({...ready(),questions:rows});
 assert.equal(view.state,'needs_reassessment');
 assert.deepEqual(view.agenda,{total:2,preview:[
  {questionId:rows[0].question_id,text:rows[0].question,sourceVersion:1,sourceLine:1,
   sourceContextState:'source_reassessment_required'},
  {questionId:rows[1].question_id,text:rows[1].question,sourceVersion:2,sourceLine:2,
   sourceContextState:'current_unreviewed_question'}]});
});
test('a bounded preview carries its full count, rather than silently losing remaining questions',()=>{
 const rows=Array.from({length:7},(_,i)=>question(i+1));
 const view=secondOpinionPreparation({...ready(),questions:rows});
 assert.equal(view.agenda.total,7);
 assert.deepEqual(view.agenda.preview.map(x=>x.questionId),rows.slice(0,5).map(x=>x.question_id));
});
test('access loss, reloading and case mismatch hide the previously authorized question text',()=>{
 const state={...ready(),questions:[question(1)]};
 assert.equal(secondOpinionPreparation(state).agenda.total,1);
 for(const change of [
  {questionListPhase:'loading'}, {questionListPhase:'error'}, {questionsCaseId:'CASE-OTHER'},
  {questionsAccessReceiptId:null}, {questions:[{...question(1),patient_id:'PAT-OTHER'}]},
  {worldPhase:'error'}, {connected:false},
 ]){
  const view=secondOpinionPreparation({...state,...change});
  assert.equal(view?.agenda??null,null,JSON.stringify(change));
 }
});
test('verified empty is different from unverified or denied question history',()=>{
 const state=ready();
 assert.deepEqual(secondOpinionPreparation(state).agenda,{total:0,preview:[]});
 assert.equal(secondOpinionPreparation({...state,questionListPhase:'idle'}).agenda,null);
});
