import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
const {secondOpinionPreparation}=await import('../.test-dist/second-opinion-preparation.js');

const base=()=>({...new RegistrySession().snapshot(),connected:true,phase:'ready',
 patient:{patient_id:'PAT-ONE',origin_org:'ORG-ONE',created_at:'2026-11-03T10:00:00Z',status:'active',revision:1},
 cases:[{patient_id:'PAT-ONE',case_id:'CASE-ONE',status:'active'}],
 worldPhase:'ready',worldModel:{patient_id:'PAT-ONE',case_id:'CASE-ONE',snapshot_fingerprint:'v1'},
 questionsCaseId:'CASE-ONE',questionsAccessReceiptId:'ACCESS-'+'A'.repeat(32),questionListPhase:'ready',questions:[]});
const sourceIndex=(sources=[])=>({contract:'oi.synthetic-original-sources/1',patient_id:'PAT-ONE',case_id:'CASE-ONE',
 access_receipt_id:'ACCESS-'+'B'.repeat(32),sources,source_reported_assertions:[],synthetic:true,
 clinical_interpretation:false,research_review_invalidation_integrated:false});
const source=(state='current',n=1)=>({source_id:'SRC-'+String(n).padStart(32,'0'),document_id:'DOC-'+n,version:n,
 sha256:'a'.repeat(64),kind:'clinical',event_date:'2026-11-01',issued_at:'2026-11-01',
 received_at:'2026-11-01T10:00:00Z',specimen_id:null,state,supersedes_id:null});
const question=sourceState=>({question_id:'QUESTION-'+'C'.repeat(32),patient_id:'PAT-ONE',case_id:'CASE-ONE',
 question:'What fictional finding should be prepared for discussion?',source_id:'SRC-'+String(1).padStart(32,'0'),
 source_line:1,source_sha256:'a'.repeat(64),source_version:1,source_snapshot_sha256:'b'.repeat(64),
 source_snapshot_contract:'oi.pg-source-world-model/1',preflight_sha256:'c'.repeat(64),
 created_at:'2026-11-03T10:00:00Z',source_context_state:sourceState,human_review_state:'not_submitted',
 clinical_approval:false,model_executed:false});

test('second-opinion preparation is unavailable without an authorized selected case',()=>{
 assert.equal(secondOpinionPreparation(new RegistrySession().snapshot()),null);
 assert.equal(secondOpinionPreparation({...base(),worldPhase:'error'}),null);
});

test('unchecked records or questions are never presented as complete',()=>{
 assert.equal(secondOpinionPreparation(base()).state,'needs_check');
 assert.equal(secondOpinionPreparation({...base(),recordsPhase:'ready',sourceIndex:sourceIndex([source()]),questions:null}).state,'needs_check');
});

test('current records without a current question require a focused question',()=>{
 const view=secondOpinionPreparation({...base(),recordsPhase:'ready',sourceIndex:sourceIndex([source()])});
 assert.equal(view.state,'needs_question');assert.deepEqual(view.records,{current:1,historical:0});
});

test('source reassessment blocks current preparation even when another question is current',()=>{
 const view=secondOpinionPreparation({...base(),recordsPhase:'ready',sourceIndex:sourceIndex([source()]),
  questions:[question('current_unreviewed_question'),{...question('source_reassessment_required'),question_id:'QUESTION-'+'D'.repeat(32)}]});
 assert.equal(view.state,'needs_reassessment');assert.deepEqual(view.questions,{current:1,reassessment:1});
});

test('organized inputs remain preparation only and coordination is descriptive',()=>{
 const view=secondOpinionPreparation({...base(),recordsPhase:'ready',sourceIndex:sourceIndex([source(),source('superseded',2)]),
  questions:[question('current_unreviewed_question')],followthroughPhase:'ready',followthroughCaseId:'CASE-ONE',
  followthrough:{contract:'oi.pg-question-followthrough/1',patient_id:'PAT-ONE',case_id:'CASE-ONE',
   access_receipt_id:'ACCESS-'+'E'.repeat(32),evaluated_on:'2026-11-03',synthetic:true,clinical_approval:false,
   external_notification_sent:false,tasks:[]}});
 assert.equal(view.state,'inputs_prepared');assert.deepEqual(view.records,{current:1,historical:1});
 assert.deepEqual(view.coordination,{open:0,assigned:0,sourceChanged:0});
});

const labModel=()=>({...base().worldModel,current_sources:[{source_id:'SRC-LAB',version:1,
 sha256:'a'.repeat(64),kind:'laboratory',state:'current'}],history:[],
 laboratory_observations:[{source_id:'SRC-LAB',observation_reference:'Observation/ROW-1'}]});
const labHistory=(status='current_unreviewed_question')=>({
 patient_id:'PAT-ONE',case_id:'CASE-ONE',checked_source_snapshot_sha256:'v1',
 access_receipt_id:'ACCESS-'+'D'.repeat(32),questions:[{
 question_id:'QUESTION-'+'F'.repeat(32),source_id:'SRC-LAB',source_version:1,
 source_sha256:'a'.repeat(64),observation_reference:'Observation/ROW-1',
 source_context_state:status}],
});

test('second-opinion agenda does not claim no saved questions when only laboratory questions exist',()=>{
 const view=secondOpinionPreparation({...base(),worldModel:labModel(),recordsPhase:'ready',
  sourceIndex:sourceIndex([source()]),labQuestionListPhase:'ready',labQuestionHistory:labHistory()});
 assert.deepEqual(view.questions,{current:0,reassessment:0});
 assert.deepEqual(view.laboratoryQuestions,{current:1,reassessment:0});
 assert.equal(view.state,'needs_laboratory_review');
 assert.equal(view.agenda.total,0,'a text-only agenda must not fabricate a source line');
});

test('source-amended laboratory question blocks an all-current second-opinion status',()=>{
 const view=secondOpinionPreparation({...base(),worldModel:labModel(),recordsPhase:'ready',
  sourceIndex:sourceIndex([source()]),questions:[question('current_unreviewed_question')],
  labQuestionListPhase:'ready',labQuestionHistory:labHistory('source_reassessment_required')});
 assert.equal(view.state,'needs_reassessment');
 assert.deepEqual(view.laboratoryQuestions,{current:0,reassessment:1});
});

test('a current text question does not conceal an unreviewed laboratory question in second-opinion readiness',()=>{
 const view=secondOpinionPreparation({...base(),worldModel:labModel(),recordsPhase:'ready',
  sourceIndex:sourceIndex([source()]),questions:[question('current_unreviewed_question')],
  labQuestionListPhase:'ready',labQuestionHistory:labHistory()});
 assert.equal(view.state,'needs_laboratory_review');
 assert.deepEqual(view.laboratoryQuestions,{current:1,reassessment:0});
});

test('unavailable laboratory history cannot make a known laboratory case fully prepared',()=>{
 const view=secondOpinionPreparation({...base(),worldModel:labModel(),recordsPhase:'ready',
  sourceIndex:sourceIndex([source()]),questions:[question('current_unreviewed_question')],
  labQuestionListPhase:'error',labQuestionHistory:labHistory()});
 assert.equal(view.state,'needs_check');
 assert.equal(view.laboratoryAvailable,true);
 assert.equal(view.laboratoryQuestions,null);
});
