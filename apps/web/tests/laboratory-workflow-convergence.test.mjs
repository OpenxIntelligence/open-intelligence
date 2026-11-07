import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {readLabQuestionList} from '../.test-dist/laboratory-question.js';
import {parseSourceWorldModel} from '../.test-dist/source-world-model.js';
import {patientContinuity} from '../.test-dist/patient-continuity.js';
import {secondOpinionPreparation} from '../.test-dist/second-opinion-preparation.js';
import {patient,caseId,sourceId,hash,projection} from './laboratory-projection-fixture.mjs';

function saved(){
 return {question_id:'QUESTION-'+'E'.repeat(32),question:'Which record explains this fictional laboratory result?',
  source_id:sourceId,source_version:1,source_sha256:hash,observation_reference:'Observation/FICTIONAL-OBS-0',
  source_snapshot_sha256:'d'.repeat(64),preflight_sha256:'f'.repeat(64),source_context_state:'current_unreviewed_question'};
}
function read(model,row=saved()){
 return readLabQuestionList({patient_id:patient,case_id:caseId,access_receipt_id:'ACCESS-'+'F'.repeat(32),questions:[row]},model);
}
function state(model,history){
 return {...new RegistrySession().snapshot(),connected:true,phase:'ready',
  patient:{patient_id:patient,origin_org:'ORG-FICTIONAL',created_at:'2026-11-05T12:00:00Z',status:'active',revision:1},
  cases:[{patient_id:patient,case_id:caseId,status:'active'}],worldPhase:'ready',worldModel:model,
  recordsPhase:'ready',sourceIndex:{patient_id:patient,case_id:caseId,sources:[...model.current_sources,...model.history]},
  questionsCaseId:caseId,questionsAccessReceiptId:'ACCESS-'+'A'.repeat(32),questionListPhase:'ready',questions:[],
  labQuestionListPhase:'ready',labQuestionHistory:history};
}

test('a decoded saved result reaches Overview without becoming a fictitious text-line question',()=>{
 const model=parseSourceWorldModel(projection(),patient,caseId),view=state(model,read(model));
 assert.deepEqual(patientContinuity(view).laboratoryQuestions,{current:1,reassessment:0});
 assert.deepEqual(patientContinuity(view).questions,{current:0,reassessment:0});
 const preparation=secondOpinionPreparation(view);
 assert.equal(preparation.state,'needs_laboratory_review');
 assert.equal(preparation.agenda.total,0);
 assert.equal(view.labQuestionHistory.questions[0].observation_reference,'Observation/FICTIONAL-OBS-0');
 assert.equal(Object.hasOwn(view.labQuestionHistory.questions[0],'source_line'),false);
});

test('a fresh amended history reopens reassessment while an earlier authorized read becomes unknown',()=>{
 const original=parseSourceWorldModel(projection(),patient,caseId),earlier=read(original);
 const next=projection(),replacement='SRC-'+'B'.repeat(32),digest='c'.repeat(64);
 next.history=[{...next.current_sources[0],state:'superseded'}];
 next.current_sources=[{...next.current_sources[0],source_id:replacement,version:2,sha256:digest,supersedes_id:sourceId}];
 next.laboratory_observations=next.laboratory_observations.map(o=>({...o,source_id:replacement,document_version:2,source_sha256:digest}));
 next.laboratory_timeline=next.laboratory_timeline.map(o=>({...o,source_id:replacement}));
 next.summary.historical_sources=1;next.snapshot_fingerprint='e'.repeat(64);
 const amended=parseSourceWorldModel(next,patient,caseId);
 assert.equal(patientContinuity(state(amended,earlier)).laboratoryQuestions,null);
 const currentRead=read(amended,{...saved(),source_context_state:'source_reassessment_required'});
 const reopened=state(amended,currentRead);
 assert.deepEqual(patientContinuity(reopened).laboratoryQuestions,{current:0,reassessment:1});
 assert.equal(secondOpinionPreparation(reopened).state,'needs_reassessment');
 assert.ok(patientContinuity(reopened).preparation.some(p=>p.key==='laboratory-question-recheck'&&p.destination==='Journey'));
 assert.equal(currentRead.questions[0].source_id,sourceId);
 assert.equal(currentRead.questions[0].source_sha256,hash);
});

test('a failed independent laboratory read withholds its count while retaining the authorized text history',()=>{
 const model=parseSourceWorldModel(projection(),patient,caseId),view=state(model,read(model));
 for(const patch of [{labQuestionListPhase:'error'},{labQuestionListPhase:'loading'},
   {labQuestionHistory:{...view.labQuestionHistory,case_id:'CASE-OTHER'}},
   {labQuestionHistory:{...view.labQuestionHistory,patient_id:'PAT-OTHER'}}]){
  const denied={...view,...patch};
  assert.equal(patientContinuity(denied).laboratoryQuestions,null);
  assert.deepEqual(patientContinuity(denied).questions,{current:0,reassessment:0});
  assert.equal(secondOpinionPreparation(denied).state,'needs_check');
 }
});
