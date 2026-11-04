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
