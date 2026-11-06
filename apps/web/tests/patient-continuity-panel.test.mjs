import {test,before} from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {build} from 'vite';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {ready,transportFor,response,deferred,packet,question,history,patientId,caseId,
 questionId,sourceId,sourceHash,fingerprint,preflightHash} from './authored-evidence-fixtures.mjs';

let PatientContinuity;
before(async()=>{
 await build({configFile:false,logLevel:'silent',build:{ssr:resolve('src/patient-continuity-view.tsx'),
  outDir:'.test-dist/patient-continuity-ui',emptyOutDir:true,
  rollupOptions:{output:{entryFileNames:'patient-continuity-view.mjs'}}}});
 ({PatientContinuity}=await import(pathToFileURL(resolve('.test-dist/patient-continuity-ui/patient-continuity-view.mjs')).href));
});

// Complete fictional API responses exercise the real session, decoder and component.
const otherQuestion='QUESTION-'+'B'.repeat(32);
const taskId=n=>'TASK-'+n.toString(16).toUpperCase().padStart(32,'0');
function task(n,status='created',changes={}){
 const sequence={created:['created'],assigned:['created','assigned'],
  acknowledged:['created','assigned','acknowledged'],completed:['created','assigned','acknowledged','completed'],
  deferred:['created','deferred']}[status];
 const owner=['assigned','acknowledged','completed'].includes(status)?'Fictional coordinator':'';
 return {task_id:taskId(n),question_id:n%2?questionId:otherQuestion,patient_id:patientId,case_id:caseId,
  title:'Fictional follow-up '+n,detail:'Prepare the original fictional quotation for discussion.',
  owner_label:owner,due_date:null,review_trigger:'At the next fictional discussion',
  created_at:'2026-11-01T10:00:00Z',status,revision:sequence.length,
  source_id:sourceId,source_line:8,source_sha256:sourceHash,source_version:1,
  source_snapshot_contract:'oi.pg-source-world-model/1',source_snapshot_sha256:fingerprint,
  preflight_sha256:preflightHash,source_context_state:'current_unreviewed_question',
  manual_dependency_revision_id:null,manual_context_state:null,
  needs_recheck:false,is_overdue:false,is_due_soon:false,clinical_approval:false,
  history:sequence.map((value,i)=>({event_id:'TASK-EVENT-'+(n*10+i).toString(16).toUpperCase().padStart(32,'0'),
   revision:i+1,previous_status:i?sequence[i-1]:null,status:value,owner_label:owner,
   actor_label:'ACTOR-FICTIONAL',reason:'Recorded fictional coordination work.',
   recorded_at:'2026-11-01T10:0'+i+':00Z'})),...changes};
}
const tasks=()=>[
 task(1,'created',{due_date:'2026-11-02',is_overdue:true,needs_recheck:true,
  source_context_state:'source_reassessment_required'}),
 task(2,'assigned',{due_date:'2026-11-07',is_due_soon:true}),
 task(3,'acknowledged'),task(4),
 task(5,'completed',{source_context_state:'source_reassessment_required'}),task(6,'deferred'),
];
const list=(rows=tasks())=>({contract:'oi.pg-question-followthrough/1',patient_id:patientId,case_id:caseId,
 access_receipt_id:'ACCESS-'+'D'.repeat(32),evaluated_on:'2026-11-03',tasks:rows,
 synthetic:true,clinical_approval:false,external_notification_sent:false});
async function open(read=()=>response(list())){
 const fallback=transportFor(()=>response(packet()));
 const session=new RegistrySession((url,init)=>{
  if(url.endsWith('/followthrough'))return read(url,init);
  if(url.endsWith('/questions'))return response({...history(),questions:[question(),
   {...question(),question_id:otherQuestion,question:'What fictional detail should be prepared for discussion?'}]});
  return fallback(url,init);
 });
 await ready(session);return session;
}
const render=(state,props={})=>renderToStaticMarkup(createElement(PatientContinuity,
 {state,onNavigate:()=>{},onRefreshFollowthrough:()=>{},busy:false,...props}));
const tag=(html,id)=>html.match(new RegExp('<[^>]*data-testid="'+id+'"[^>]*>'))?.[0]??'';
const hasNoTaskSummary=html=>{
 assert.doesNotMatch(html,/data-testid="continuity-followthrough-count-/);
 assert.doesNotMatch(html,/data-testid="continuity-followthrough-task"/);
 assert.doesNotMatch(html,/Fictional follow-up \d/);
};

test('Overview summarizes work across questions and previews only three open tasks',async()=>{
 const session=await open();await session.loadFollowthrough(caseId);
 assert.equal(session.snapshot().followthroughPhase,'ready');
 const html=render(session.snapshot());
 for(const [key,count] of [['all',6],['recheck',1],['overdue',1],['unassigned',2],['history',2]]){
  assert.match(tag(html,'continuity-followthrough-count-'+key),new RegExp('data-count="'+count+'"'));
 }
 const previews=Array.from(html.matchAll(/<li[^>]*data-testid="continuity-followthrough-task"[^>]*>[\s\S]*?<\/li>/g),match=>match[0]);
 assert.equal(previews.length,3);
 for(const [i,preview] of previews.entries())assert.match(preview,new RegExp('data-task-id="'+taskId(i+1)+'"'));
 assert.match(previews[0],new RegExp('data-question-id="'+questionId+'"'));
 assert.match(previews[1],new RegExp('data-question-id="'+otherQuestion+'"'));
 assert.match(previews[0],/Unassigned/);
 assert.match(previews[1],/Recorded owner[\s\S]*Fictional coordinator/);
 assert.match(previews[0],/Revisit date[\s\S]*2026-11-02/);
 assert.match(previews[2],/Revisit date[\s\S]*Not recorded/);
 assert.match(previews[2],/Review trigger[\s\S]*At the next fictional discussion/);
 assert.match(previews[0],/Source changed/);
 assert.doesNotMatch(html,/Fictional follow-up [456]/,'history and unpreviewed work remain in the full task panel');
 assert.match(html,/data-testid="continuity-followthrough-coverage"[^>]*>Showing 3 of 4 open/);
 assert.match(html,/data-testid="continuity-followthrough-evaluated-on"[^>]*>[\s\S]*2026-11-03/);
 assert.match(html,/not clinical urgency/);
 assert.match(tag(html,'continuity-open-followthrough'),/^<button/);
});

test('unchecked follow-up is distinct from a verified empty list',async()=>{
 const session=await open(()=>response(list([])));
 const unchecked=render(session.snapshot());
 assert.match(tag(unchecked,'continuity-followthrough-status'),/data-phase="idle"/);
 assert.match(unchecked,/Follow-up work has not been checked/);
 hasNoTaskSummary(unchecked);
 assert.doesNotMatch(tag(unchecked,'continuity-followthrough-refresh'),/disabled/);
 await session.loadFollowthrough(caseId);
 const checked=render(session.snapshot());
 assert.match(tag(checked,'continuity-followthrough-status'),/data-phase="ready"/);
 assert.match(tag(checked,'continuity-followthrough-count-all'),/data-count="0"/);
 assert.match(checked,/No recorded follow-up work was returned/);
 assert.match(checked,/does not mean there are no care needs/);
});

test('a new read withholds prior task details while access is checked',async()=>{
 const waiting=deferred();let refresh=false;
 const session=await open(()=>refresh?waiting.promise:response(list()));
 await session.loadFollowthrough(caseId);refresh=true;
 const pending=session.loadFollowthrough(caseId);
 try{
  const html=render(session.snapshot());
  assert.match(tag(html,'continuity-followthrough-status'),/data-phase="loading"/);
  hasNoTaskSummary(html);
  assert.match(tag(html,'continuity-followthrough-refresh'),/disabled/);
 }finally{waiting.resolve(response(list()));await pending;}
});

test('independent task denial clears its summary while keeping authorized questions',async()=>{
 let denied=false;
 const session=await open(()=>denied?response({detail:'Denied'},403):response(list()));
 await session.loadFollowthrough(caseId);
 assert.match(render(session.snapshot()),/Fictional follow-up 1/);
 denied=true;await session.loadFollowthrough(caseId);
 const html=render(session.snapshot());
 assert.match(tag(html,'continuity-followthrough-status'),/data-phase="error"/);
 hasNoTaskSummary(html);
 assert.match(html,/data-testid="continuity-current">2<\/strong>/);
 assert.match(tag(html,'continuity-open-questions'),/^<button/);
 assert.match(html,/Follow-up work is unavailable/);
});

test('an unavailable Overview case hides task details and disables refresh',async()=>{
 const session=await open();await session.loadFollowthrough(caseId);
 const html=render({...session.snapshot(),worldPhase:'error'});
 hasNoTaskSummary(html);
 assert.match(tag(html,'continuity-followthrough-refresh'),/disabled/);
 assert.match(html,/Open a case in Investigations/);
});

test('a busy session cannot start a follow-up refresh',async()=>{
 const session=await open();
 assert.match(tag(render(session.snapshot(),{busy:true}),'continuity-followthrough-refresh'),/disabled/);
});

for(const phase of ['saving','unknown']){
 test(`Overview keeps the ${phase} follow-up recovery route without a ready list`,async()=>{
  const session=await open();
  const html=render({...session.snapshot(),followthroughWritePhase:phase,followthrough:null,
   followthroughPhase:'idle',followthroughCaseId:caseId});
  hasNoTaskSummary(html);
  assert.match(tag(html,'continuity-followthrough-refresh'),/disabled/);
  assert.match(tag(html,'continuity-followthrough-recovery'),new RegExp('data-phase="'+phase+'"'));
  assert.match(tag(html,'continuity-recover-followthrough'),/^<button/);
  assert.match(html,phase==='unknown'?/unknown outcome/:/submission is in progress/);
 });
}

test('Overview renders saved laboratory questions separately from text-anchored counts',async()=>{
 const session=await open(); const previous=session.snapshot(),model=previous.worldModel;
 const sid='SRC-'+'F'.repeat(32),sha='e'.repeat(64);
 const world={...model,current_sources:[...model.current_sources,
  {source_id:sid,version:1,sha256:sha,kind:'laboratory',state:'current'}]};
 const labQuestion={question_id:'QUESTION-'+'F'.repeat(32),question:'What does the fictional laboratory result report?',
  source_id:sid,source_version:1,source_sha256:sha,observation_reference:'Observation/FICTIONAL-OBS',
  source_snapshot_sha256:world.snapshot_fingerprint,preflight_sha256:'b'.repeat(64),
  source_context_state:'current_unreviewed_question'};
 const scope={...previous,worldModel:world,labQuestionListPhase:'ready',labQuestionHistory:{
  patient_id:patientId,case_id:caseId,checked_source_snapshot_sha256:world.snapshot_fingerprint,
  access_receipt_id:'ACCESS-'+'D'.repeat(32),questions:[labQuestion]}};
 const html=render(scope);
 assert.match(html,/data-testid="continuity-lab-questions"/);
 assert.match(html,/data-testid="continuity-lab-current">1<\/strong>/);
 assert.match(html,/data-testid="continuity-lab-reassessment">0<\/strong>/);
 assert.match(html,/data-testid="continuity-open-lab-questions"/);
 assert.doesNotMatch(html,/No saved questions were returned for this case and grant\./);
 const unknown=render({...scope,labQuestionListPhase:'error',labQuestionHistory:null});
 assert.match(unknown,/A missing check is not zero/);
 assert.doesNotMatch(unknown,/data-testid="continuity-lab-current"/);
});
