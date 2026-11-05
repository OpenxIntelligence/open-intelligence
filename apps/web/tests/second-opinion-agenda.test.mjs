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
   sourceContextState:'source_reassessment_required',
   evidenceReadiness:{original:'changed',citations:null},work:null},
  {questionId:rows[1].question_id,text:rows[1].question,sourceVersion:2,sourceLine:2,
   sourceContextState:'current_unreviewed_question',
   evidenceReadiness:{original:'not_matched',citations:null},work:null}]});
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

const task=(n,questionId,{status='assigned',owner='Fictional coordinator',dueDate='2026-11-05',needsRecheck=false}={})=>({
 task_id:'TASK-'+String(n).padStart(32,'0'),patient_id:patientId,case_id:caseId,question_id:questionId,
 title:'Fictional follow-up '+n,owner_label:owner,status,due_date:dueDate,
 review_trigger:'Review when new fictional source arrives',needs_recheck:needsRecheck,is_overdue:n===1,
});
const readTasks=tasks=>({followthroughPhase:'ready',followthroughCaseId:caseId,followthrough:{
 contract:'oi.pg-question-followthrough/1',patient_id:patientId,case_id:caseId,
 access_receipt_id:'ACCESS-'+'D'.repeat(32),evaluated_on:'2026-11-03',
 synthetic:true,clinical_approval:false,external_notification_sent:false,tasks}});

test('each question shows only its independently authorized canonical tasks, with exact recorded owner and date',()=>{
 const a=question(1,'source_reassessment_required'),b=question(2),other='QUESTION-'+'E'.repeat(32);
 const state={...ready(),questions:[a,b],...readTasks([
  task(1,a.question_id,{needsRecheck:true}),task(2,a.question_id,{status:'completed',owner:'Fictional finished owner'}),
  task(3,b.question_id,{owner:'Fictional second owner',dueDate:null}),task(4,other),
 ])};
 const view=secondOpinionPreparation(state),[qa,qb]=view.agenda.preview;
 assert.equal(view.state,'needs_reassessment');
 assert.deepEqual([qa.work.recordedCount,qa.work.openCount,qa.work.historicalCount],[2,1,1]);
 assert.deepEqual([qb.work.recordedCount,qb.work.openCount,qb.work.historicalCount],[1,1,0]);
 assert.equal(qa.work.evaluatedOn,'2026-11-03');
 assert.deepEqual(qa.work.preview,[{
  taskId:'TASK-'+String(1).padStart(32,'0'),title:'Fictional follow-up 1',status:'assigned',
  ownerLabel:'Fictional coordinator',dueDate:'2026-11-05',
  reviewTrigger:'Review when new fictional source arrives',needsRecheck:true,revisitDatePassed:true,
 }]);
 assert.equal(qb.work.preview[0].ownerLabel,'Fictional second owner');
 assert.equal(qb.work.preview[0].dueDate,null);
 assert.ok(!qa.work.preview.some(t=>t.taskId===qb.work.preview[0].taskId));
 assert.equal(view.coordination.open,3); // Includes the separate, independently authorized third question.
});

test('bounded per-question task previews never claim the full list is displayed',()=>{
 const q=question(1),state={...ready(),questions:[q],...readTasks(Array.from({length:6},(_,i)=>task(i+1,q.question_id)))};
 const view=secondOpinionPreparation(state);
 assert.equal(view.agenda.preview[0].work.openCount,6);
 assert.equal(view.agenda.preview[0].work.preview.length,2);
 assert.equal(view.agenda.preview[0].work.recordedCount,6);
});

test('task denial, refresh or other-case data never become an authorized zero count',()=>{
 const q=question(1),state={...ready(),questions:[q],...readTasks([task(1,q.question_id)])};
 assert.equal(secondOpinionPreparation(state).agenda.preview[0].work.recordedCount,1);
 assert.deepEqual(secondOpinionPreparation({...state,...readTasks([])}).agenda.preview[0].work,{evaluatedOn:'2026-11-03',recordedCount:0,openCount:0,historicalCount:0,preview:[]});
 for(const patch of [{followthroughPhase:'loading'},{followthroughPhase:'error'},
  {followthroughCaseId:'CASE-OTHER'},{followthrough:{...state.followthrough,patient_id:'PAT-OTHER'}},
  {followthrough:{...state.followthrough,case_id:'CASE-OTHER'}},
  {followthrough:{...state.followthrough,tasks:[{...task(1,q.question_id),case_id:'CASE-OTHER'}]}}]){
  const actual=secondOpinionPreparation({...state,...patch});
  assert.equal(actual.agenda.preview[0].work,null,JSON.stringify(patch));
  assert.equal(actual.agenda.preview[0].text,q.question); // Separate question grant remains readable.
 }
});
