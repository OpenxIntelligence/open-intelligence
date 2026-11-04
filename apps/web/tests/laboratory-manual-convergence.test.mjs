import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import {RegistrySession} from '../.test-dist/registry-client.js';

// Original fictional fixtures; only HTTP transport is substituted. No server/clinical claim.
const PID='PAT-LAB-JOIN',CID='CASE-LAB-JOIN',TOKEN='fictional_test_credential_000000000001';
const SID='SRC-'+'A'.repeat(32),TASK='TASK-'+'B'.repeat(32),QID='QUESTION-'+'C'.repeat(32);
const MANUAL='PASSAGES-'+'D'.repeat(32),TASK_SOURCE='SRC-'+'E'.repeat(32);
const RAW=readFileSync(new URL('../../../examples/synthetic/fictional-fhir-r4-lab-bundle.json',import.meta.url),'utf8');
const HASH=createHash('sha256').update(RAW).digest('hex');
const reply=(value,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
const deferred=()=>{let resolve;return{promise:new Promise(r=>resolve=r),resolve:value=>resolve(value)};};
function taskProjection(stale=false){
 const statuses=['created','assigned','acknowledged'];
 return {contract:'oi.pg-question-followthrough/1',patient_id:PID,case_id:CID,
  access_receipt_id:'ACCESS-'+'F'.repeat(32),evaluated_on:'2026-11-04',synthetic:true,
  clinical_approval:false,external_notification_sent:false,tasks:[{
   task_id:TASK,question_id:QID,patient_id:PID,case_id:CID,title:'Inspect fictional passage',detail:'',
   owner_label:'Fictional coordinator',due_date:null,review_trigger:'When the source changes',
   created_at:'2026-11-04T10:00:00Z',status:'acknowledged',revision:3,
   source_id:TASK_SOURCE,source_line:2,source_sha256:'e'.repeat(64),source_version:1,
   source_snapshot_contract:'oi.pg-source-world-model/1',source_snapshot_sha256:'a'.repeat(64),
   preflight_sha256:'b'.repeat(64),source_context_state:'current_unreviewed_question',
   manual_dependency_revision_id:MANUAL,manual_context_state:stale?'reassessment_required':'current_unreviewed',
   needs_recheck:stale,is_overdue:false,is_due_soon:false,clinical_approval:false,
   history:statuses.map((status,i)=>({event_id:'TASK-EVENT-'+String(i+1).repeat(32),revision:i+1,
    previous_status:i?statuses[i-1]:null,status,owner_label:'Fictional coordinator',
    actor_label:'ACTOR-FICTIONAL',reason:'Record fictional coordination.',recorded_at:`2026-11-04T10:0${i}:00Z`}))
  }]};
}
async function setup({stale=false}={}){
 const calls=[],flags={denied:false,hold:null};
 const session=new RegistrySession(async(url,init)=>{
  calls.push({url,method:init.method,body:init.body});
  if(url==='/v1/patients/'+PID)return reply({patient_id:PID,origin_org:'FICT-ORG',status:'active',revision:1,created_at:'2026-11-04T10:00:00Z'});
  if(url.endsWith('/case-bindings'))return reply({patient_id:PID,synthetic:true,source_identity_verified:false,clinical_sources_linked:false,mappings:[{
   case_id:CID,patient_id:PID,source_organization:'FICT-ORG',source_system:'FICT-SYSTEM',source_subject_ref:'FICTIONAL-PATIENT-A',review_ref:'FICT-REVIEW',status:'active',revision:1,
   created_at:'2026-11-04T10:00:00Z',revoked_at:null,source_identity_verified:false,clinical_sources_linked:false,clinical_conclusions:false}]});
  if(init.method==='POST'&&url.endsWith('/laboratory/fhir-r4/sources'))return reply({source_id:SID,version:1,duplicate:false,original_sha256:HASH,observation_count:1},201);
  if(init.method==='GET'&&url.endsWith('/sources'))return reply({contract:'oi.synthetic-original-sources/1',patient_id:PID,case_id:CID,access_receipt_id:'ACCESS-'+'9'.repeat(32),
   sources:[],source_reported_assertions:[],synthetic:true,clinical_interpretation:false,research_review_invalidation_integrated:false});
  if(init.method==='GET'&&url.endsWith('/followthrough'))return flags.hold?flags.hold.promise:reply(flags.denied?{}:taskProjection(stale),flags.denied?403:200);
  throw Error('Unexpected fictional request: '+init.method+' '+url);
 });
 session.connect(TOKEN);await session.read(PID);await session.loadCases();await session.loadSources(CID);
 assert.equal(typeof session.importLaboratory,'function','Laboratory import must coexist with the manual-task owner');
 await session.importLaboratory(CID,RAW,true);
 assert.equal(session.snapshot().laboratoryPhase,'saved');
 assert.equal(session.snapshot().laboratoryReceipt.original_sha256,HASH);
 return {session,calls,flags};
}

test('lab import retains exact bytes and fresh manual-task identity without creating a task or binding it to the new lab',async()=>{
 const {session,calls}=await setup();
 await session.loadFollowthrough(CID);
 assert.equal(session.snapshot().followthroughPhase,'ready');
 const row=session.snapshot().followthrough.tasks[0];
 assert.equal(row.manual_dependency_revision_id,MANUAL);assert.equal(row.source_id,TASK_SOURCE);
 assert.notEqual(row.source_id,SID);assert.equal(row.manual_context_state,'current_unreviewed');
 const writes=calls.filter(c=>c.method==='POST');assert.equal(writes.length,1);
 assert.equal(JSON.parse(writes[0].body).bundle_json,RAW);assert.equal(row.clinical_approval,false);
});

test('lab import does not permit completion of a freshly read stale manual-dependent task',async()=>{
 const {session,calls}=await setup({stale:true});await session.loadFollowthrough(CID);
 assert.equal(session.snapshot().followthroughPhase,'ready');
 assert.equal(session.snapshot().followthrough.tasks[0].needs_recheck,true);
 await session.transitionFollowthrough(TASK,{status:'completed',owner_label:'',reason:'Try the fictional completion.'});
 assert.equal(session.snapshot().followthroughWritePhase,'error');
 assert.equal(calls.filter(c=>c.method==='POST').length,1);
 assert.equal(session.snapshot().followthrough.tasks[0].manual_dependency_revision_id,MANUAL);
});

test('independent task denial after lab import clears prior task projection without a compensating write',async()=>{
 const {session,calls,flags}=await setup();await session.loadFollowthrough(CID);
 assert.equal(session.snapshot().followthroughPhase,'ready');flags.denied=true;await session.loadFollowthrough(CID);
 assert.equal(session.snapshot().followthrough,null);assert.equal(session.snapshot().followthroughPhase,'error');
 assert.equal(calls.filter(c=>c.method==='POST').length,1);
});

test('disconnect after lab import prevents a late manual-task reply from restoring protected state',async()=>{
 const {session,flags}=await setup();flags.hold=deferred();const read=session.loadFollowthrough(CID);
 assert.equal(session.snapshot().followthroughPhase,'loading');session.disconnect();
 flags.hold.resolve(reply(taskProjection()));await read;
 assert.equal(session.snapshot().followthrough,null);assert.equal(session.snapshot().laboratoryReceipt,null);
 assert.equal(session.snapshot().laboratoryIntent,null);assert.equal(session.snapshot().connected,false);
});
