import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {activeComparisonDraft} from '../.test-dist/authored-evidence-session.js';
import {secondOpinionPreparation} from '../.test-dist/second-opinion-preparation.js';
import {ready,transportFor,response,packet,question,questionId,patientId,caseId,
 evidenceId,reportId,report,time} from './authored-evidence-fixtures.mjs';

// Independently fictional work linked to the same canonical question fixtures.
const taskId='TASK-'+'C'.repeat(32);
const fields={title:'Unsent coordination plan',detail:'Keep the source discussion separate.',
 owner_label:'Proposed fictional coordinator',due_date:null,review_trigger:'After the source discussion',
 reason:'Record work only after an explicit decision.'};
const transition={owner_label:'Another proposed coordinator',reason:'Unsent assignment reason.'};
function tasks(){
 const q=question();
 return {contract:'oi.pg-question-followthrough/1',patient_id:patientId,case_id:caseId,
  access_receipt_id:'ACCESS-'+'C'.repeat(32),evaluated_on:'2026-11-03',synthetic:true,
  clinical_approval:false,external_notification_sent:false,tasks:[{
   task_id:taskId,question_id:questionId,patient_id:patientId,case_id:caseId,
   title:'Previously recorded work',detail:'',owner_label:'Recorded fictional owner',
   due_date:null,review_trigger:'At the next discussion',created_at:time,status:'created',revision:1,
   ...Object.fromEntries(['source_id','source_line','source_sha256','source_version','source_snapshot_contract',
    'source_snapshot_sha256','preflight_sha256','source_context_state'].map(key=>[key,q[key]])),
   needs_recheck:false,is_overdue:false,is_due_soon:false,clinical_approval:false,
   history:[{event_id:'TASK-EVENT-'+'D'.repeat(32),revision:1,previous_status:null,status:'created',
    owner_label:'Recorded fictional owner',actor_label:'FICT-OPERATOR',reason:'Previously agreed work.',recorded_at:time}],
  }]};
}

for(const mode of ['historical','denied']){
 test('fresh report '+mode+' keeps independent follow-up input and saved preparation work separate',async()=>{
  let writes=0;
  const evidenceTransport=transportFor(url=>url.includes('/evidence-reports/')?
   mode==='denied'?response({},403):response({...report(),state:'historical_reassessment_required'}):response(packet()));
  const s=new RegistrySession((url,init)=>{
   if(init.method==='POST')writes++;
   return url.endsWith('/followthrough')?response(tasks()):evidenceTransport(url,init);
  });
  await ready(s);await s.loadFollowthrough(caseId);await s.loadQuestionEvidence(questionId);
  assert.equal(s.snapshot().followthroughPhase,'ready');
  s.editFollowthroughDraft(questionId,fields);s.editFollowthroughTransitionDraft(taskId,transition);
  assert.equal(s.selectEvidenceComparison(questionId,evidenceId),true);
  assert.equal(s.editEvidenceComparison({quote:'café experiment',rationale:'Unfinished fictional evidence appraisal.'}),true);
  const captured=s.snapshot().evidenceComparisonDraft;
  const before=secondOpinionPreparation(s.snapshot());
  await s.readEvidenceReport(questionId,reportId);
  assert.equal(s.snapshot().evidencePacket,null);
  assert.equal(activeComparisonDraft(s.snapshot()),null);
  assert.equal(s.snapshot().evidenceComparisonDraft,mode==='historical'?captured:null);
  assert.deepEqual(s.snapshot().followthroughDrafts[questionId].fields,fields);
  assert.deepEqual(s.snapshot().followthroughTransitionDrafts[taskId].fields,transition);
  assert.deepEqual(secondOpinionPreparation(s.snapshot()),before);
  assert.equal(before.agenda.preview[0].work.recordedCount,1);
  assert.equal(before.agenda.preview[0].work.preview[0].ownerLabel,'Recorded fictional owner');
  await s.saveEvidenceComparison();
  assert.equal(writes,0);
  s.disconnect();
  assert.deepEqual(s.snapshot().followthroughDrafts,{});
  assert.deepEqual(s.snapshot().followthroughTransitionDrafts,{});
  assert.equal(s.snapshot().evidenceComparisonDraft,null);
  assert.equal(secondOpinionPreparation(s.snapshot()),null);
 });
}
