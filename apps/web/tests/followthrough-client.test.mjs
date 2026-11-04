import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {projectFollowthroughAttention} from '../.test-dist/followthrough-view.js';

// Independently authored fictional task and source context; transport is the only mock.
const token='fictional_test_credential_000000000001';
const pid='PAT-EXAMPLE-001',cid='CASE-ALPHA',otherCase='CASE-BETA';
const qid='QUESTION-'+'A'.repeat(32),sid='SRC-'+'B'.repeat(32),tid='TASK-'+'C'.repeat(32);
const contract='oi.pg-source-world-model/1',snapshot='a'.repeat(64),preflight='b'.repeat(64),sha='c'.repeat(64);
const path='/v1/patients/'+pid+'/cases/'+cid;
const response=(value,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
const deferred=()=>{let resolve;return{promise:new Promise(r=>resolve=r),resolve:value=>resolve(value)};};
const patient=(id=pid)=>({patient_id:id,origin_org:'FICT-ORG',status:'active',revision:1,created_at:'2026-11-03T10:00:00Z'});
const cases=()=>({patient_id:pid,synthetic:true,source_identity_verified:false,clinical_sources_linked:false,
 mappings:[cid,otherCase].map((id,i)=>({case_id:id,patient_id:pid,source_organization:'FICT-ORG',source_system:'FICT-TEXT',
 source_subject_ref:'FICT-SUBJECT-'+i,review_ref:'FICT-REVIEW-'+i,status:'active',revision:1,
 created_at:'2026-11-03T10:00:00Z',revoked_at:null,source_identity_verified:false,clinical_sources_linked:false,clinical_conclusions:false}))});
const world=(caseId=cid,hash=snapshot)=>({contract,patient_id:pid,case_id:caseId,access_receipt_id:'ACCESS-'+'D'.repeat(32),
 synthetic:true,authority:'source_report_only_unreviewed',clinical_interpretation:false,research_review_invalidation_integrated:false,
 composer_execution_authorized:false,snapshot_fingerprint:hash,as_of_received_at:'2026-11-03T10:00:00Z',
 summary:{current_sources:1,historical_sources:0,current_observations:1,unresolved_observations:1,source_disagreements:0},
 current_sources:[{source_id:sid,document_id:'DOC-ONE',version:1,sha256:sha,kind:'pathology',event_date:'2026-01-10',issued_at:'2026-01-11',
 received_at:'2026-11-03T10:00:00Z',specimen_id:'SPECIMEN-ONE',state:'current',supersedes_id:null}],history:[],
 observations:[{source_id:sid,document_id:'DOC-ONE',document_version:1,source_sha256:sha,source_kind:'pathology',finding_key:'marker',
 reported_state:'not-reported',source_statement:'Independently fictional example.',source_line:8,specimen_id:'SPECIMEN-ONE',
 event_date:'2026-01-10',issued_at:'2026-01-11',review_state:'not_established',clinical_meaning:null}],
 unresolved_refs:[{source_id:sid,source_line:8}],conflicts:[],limitations:['Independently fictional source context only.']});
const question=(overrides={})=>({question_id:qid,patient_id:pid,case_id:cid,question:'Which fictional source detail needs independent verification?',
 source_id:sid,source_line:8,source_sha256:sha,source_version:1,source_snapshot_sha256:snapshot,source_snapshot_contract:contract,
 preflight_sha256:preflight,created_at:'2026-11-03T10:00:00Z',source_context_state:'current_unreviewed_question',
 human_review_state:'not_submitted',clinical_approval:false,model_executed:false,...overrides});
const questions=(rows=[question()])=>({contract:'oi.synthetic-source-questions/2',access_receipt_id:'ACCESS-'+'E'.repeat(32),
 patient_id:pid,case_id:cid,questions:rows,synthetic:true,clinical_review_connected:false,clinical_approval:false});
const fields=()=>({title:'Check fictional source detail',detail:'Compare the original quotation at the next discussion.',
 owner_label:'Fictional coordinator',due_date:null,review_trigger:'At the next fictional source discussion',reason:'Record the agreed verification work.'});
const eventId=n=>'TASK-EVENT-'+n.toString(16).toUpperCase().padStart(32,'0');
const history=(statuses=['created'],owners=[])=>statuses.map((status,i)=>({event_id:eventId(i+1),revision:i+1,
 previous_status:i?statuses[i-1]:null,status,owner_label:owners[i]??'Fictional coordinator',actor_label:'ACTOR-FICTIONAL',
 reason:i?'Fictional work status recorded.':fields().reason,recorded_at:'2026-11-03T10:'+String(i).padStart(2,'0')+':00Z'}));
const task=(statuses=['created'],overrides={})=>({task_id:tid,question_id:qid,patient_id:pid,case_id:cid,...fields(),
 created_at:'2026-11-03T10:00:00Z',status:statuses.at(-1),revision:statuses.length,
 source_id:sid,source_line:8,source_sha256:sha,source_version:1,source_snapshot_contract:contract,
 source_snapshot_sha256:snapshot,preflight_sha256:preflight,source_context_state:'current_unreviewed_question',
 manual_dependency_revision_id:null,manual_context_state:null,
 needs_recheck:false,is_overdue:false,is_due_soon:false,clinical_approval:false,history:history(statuses),...overrides});
// Reason belongs to the creation event, not to the immutable task envelope.
function taskRow(statuses=['created'],overrides={}){const row=task(statuses,overrides);delete row.reason;return row;}
const projection=(tasks=[taskRow()],overrides={})=>({contract:'oi.pg-question-followthrough/1',patient_id:pid,case_id:cid,
 access_receipt_id:'ACCESS-'+'F'.repeat(32),evaluated_on:'2026-11-03',tasks,synthetic:true,clinical_approval:false,
 external_notification_sent:false,...overrides});
const receipt=(revision=1,duplicate=false,overrides={})=>({task_id:tid,question_id:qid,event_id:eventId(revision),revision,duplicate,...overrides});
function session(transport){return new RegistrySession(async(url,init)=>{
 if(url.endsWith('/case-bindings'))return response(cases());
 if(url.startsWith('/v1/patients/')&&!url.includes('/cases/'))return response(patient(url.split('/').at(-1)));
 return transport(url,init);
});}
async function open(s){s.connect(token);await s.read(pid);await s.loadCases();}
async function ready(s){await open(s);await s.loadWorldModel(cid);await s.loadSavedQuestions(cid);}
const basic=(url)=>response(url.endsWith('/world-model')?world(url.includes(otherCase)?otherCase:cid):
 url.endsWith('/questions')?questions():projection());

test('unsent follow-up fields survive same-case source and question refresh without writes',async()=>{
 let writes=0;const s=session(async(url,init)=>{if(init.method==='POST')writes++;return basic(url);});
 await ready(s);const draft={...fields(),title:'Still drafting',detail:'Literal unfinished text',due_date:'2026-12-09'};
 s.editFollowthroughDraft(qid,draft);
 await s.loadCases();
 await s.loadWorldModel(cid);await s.loadSavedQuestions(cid);await s.loadFollowthrough(cid);
 assert.deepEqual(s.snapshot().followthroughDrafts[qid].fields,draft);
 assert.equal(s.snapshot().followthroughDrafts[qid].source_snapshot_sha256,snapshot);
 assert.equal(Object.isFrozen(s.snapshot().followthroughDrafts[qid].fields),true);
 assert.equal(writes,0);s.clearFollowthroughDraft(qid);
 assert.deepEqual(s.snapshot().followthroughDrafts,{});assert.equal(writes,0);
});

test('unsent follow-up fields are cleared on changed source, missing question or denied scope',async()=>{
 for(const change of ['amendment','missing','preflight','question-denial','world-denial','task-denial','case','patient','disconnect']){
  let changed=false,writes=0;
  const s=session(async(url,init)=>{
   if(init.method==='POST')writes++;
   if(changed&&url.endsWith('/world-model')&&change==='amendment')return response(world(cid,'d'.repeat(64)));
   if(changed&&url.endsWith('/questions')&&change==='missing')return response(questions([]));
   if(changed&&url.endsWith('/questions')&&change==='preflight')return response(questions([question({preflight_sha256:'e'.repeat(64)})]));
   if(changed&&((change==='question-denial'&&url.endsWith('/questions'))||
    (change==='world-denial'&&url.endsWith('/world-model'))||(change==='task-denial'&&url.endsWith('/followthrough'))))return response({},403);
   return basic(url);
  });
  await ready(s);s.editFollowthroughDraft(qid,fields());changed=true;
  if(change==='amendment'||change==='world-denial')await s.loadWorldModel(cid);
  else if(change==='task-denial')await s.loadFollowthrough(cid);
  else if(change==='case'){await s.loadWorldModel(otherCase);await s.loadWorldModel(cid);}
  else if(change==='patient'){await s.read('PAT-OTHER-002');await s.read(pid);}
  else if(change==='disconnect'){s.disconnect();s.connect(token);}
  else await s.loadSavedQuestions(cid);
  assert.deepEqual(s.snapshot().followthroughDrafts,{},change);assert.equal(writes,0,change);
 }
});

test('task transitions preserve an unsent creation draft; exact creation recovery clears it once',async()=>{
 const posts=[];let creates=0;
 const s=session(async(url,init)=>{
  if(init.method==='POST'){
   posts.push(init.body);
   if(url.endsWith('/transitions'))return response(receipt(2),201);
   if(++creates===1)throw Error('Delivery lost after commit');
   return response(receipt(1,true));
  }
  return basic(url);
 });
 await ready(s);s.editFollowthroughDraft(qid,fields());await s.loadFollowthrough(cid);
 await s.transitionFollowthrough(tid,{status:'assigned',owner_label:'Fictional coordinator',reason:'Record the assignment.'});
 assert.deepEqual(s.snapshot().followthroughDrafts[qid].fields,fields());
 await s.createFollowthrough(qid,fields());const captured=s.snapshot().followthroughIntent;
 assert.equal(s.snapshot().followthroughWritePhase,'unknown');
 s.editFollowthroughDraft(qid,{...fields(),title:'Must not replace the captured write'});
 s.clearFollowthroughDraft(qid);
 assert.equal(s.snapshot().followthroughIntent,captured);
 assert.deepEqual(s.snapshot().followthroughDrafts[qid].fields,fields());
 await s.retryFollowthroughWrite();assert.equal(posts[1],posts[2]);
 assert.equal(s.snapshot().followthroughReceipt.duplicate,true);
 assert.deepEqual(s.snapshot().followthroughDrafts,{});
 s.editFollowthroughDraft(qid,{...fields(),title:'A different unsent task'});
 await s.loadSavedQuestions(cid);
 assert.equal(s.snapshot().followthroughDrafts[qid].fields.title,'A different unsent task');
 assert.equal(posts.length,3);
});

test('a refused follow-up input preserves editable fields unless access itself was denied',async()=>{
 for(const status of [400,409,413,422,403,404]){
  const s=session(async(url,init)=>init.method==='POST'?response({},status):basic(url));
  await ready(s);s.editFollowthroughDraft(qid,fields());await s.createFollowthrough(qid,fields());
  assert.equal(s.snapshot().followthroughWritePhase,'error');
  assert.equal(s.snapshot().followthroughIntent,null);
  if([403,404].includes(status))assert.deepEqual(s.snapshot().followthroughDrafts,{});
  else assert.deepEqual(s.snapshot().followthroughDrafts[qid]?.fields,fields(),String(status));
 }
});

test('unsent status-change fields survive matching task refresh and clear independently of creation fields',async()=>{
 let writes=0;const s=session(async(url,init)=>{if(init.method==='POST')writes++;return basic(url);});
 const draft={owner_label:'Proposed fictional owner',reason:'Still checking the source before assigning.'};
 await ready(s);await s.loadFollowthrough(cid);s.editFollowthroughDraft(qid,fields());
 s.editFollowthroughTransitionDraft(tid,draft);
 await s.loadCases();await s.loadWorldModel(cid);await s.loadSavedQuestions(cid);await s.loadFollowthrough(cid);
 assert.deepEqual(s.snapshot().followthroughTransitionDrafts[tid].fields,draft);
 assert.equal(Object.isFrozen(s.snapshot().followthroughTransitionDrafts[tid].fields),true);
 assert.deepEqual(s.snapshot().followthroughDrafts[qid].fields,fields());
 assert.equal(writes,0);s.clearFollowthroughTransitionDraft(tid);
 assert.deepEqual(s.snapshot().followthroughTransitionDrafts,{});
 assert.deepEqual(s.snapshot().followthroughDrafts[qid].fields,fields());assert.equal(writes,0);
});

test('fresh task revision, source context or missing task discards an earlier unsent status change',async()=>{
 for(const changed of [[],[taskRow(['created','assigned'])],
  [taskRow(['created'],{source_context_state:'source_reassessment_required',needs_recheck:true})],
  [taskRow(['created'],{source_snapshot_sha256:'d'.repeat(64)})],
  [taskRow(['created'],{preflight_sha256:'e'.repeat(64)})]]){
  let refresh=false,writes=0;
  const s=session(async(url,init)=>{if(init.method==='POST')writes++;return response(projection(refresh?changed:[taskRow()]));});
  await open(s);await s.loadFollowthrough(cid);
  s.editFollowthroughTransitionDraft(tid,{owner_label:'Fictional owner',reason:'A reason for the earlier task context.'});
  refresh=true;await s.loadFollowthrough(cid);
  assert.deepEqual(s.snapshot().followthroughTransitionDrafts,{});assert.equal(writes,0);
 }
});

test('status-change drafts cannot survive denied authority, patient/case changes or disconnect',async()=>{
 for(const change of ['task','question','world','case','patient','disconnect']){
  let denied=false;const s=session(async(url)=>denied&&url.endsWith('/'+({task:'followthrough',question:'questions',world:'world-model'}[change]))?
   response({},403):basic(url));
  await ready(s);await s.loadFollowthrough(cid);
  s.editFollowthroughTransitionDraft(tid,{owner_label:'Fictional owner',reason:'Unsent private coordination note.'});denied=true;
  if(change==='task')await s.loadFollowthrough(cid);
  else if(change==='question')await s.loadSavedQuestions(cid);
  else if(change==='world')await s.loadWorldModel(cid);
  else if(change==='case'){await s.loadWorldModel(otherCase);await s.loadWorldModel(cid);}
  else if(change==='patient'){await s.read('PAT-OTHER-002');await s.read(pid);}
  else{s.disconnect();s.connect(token);}
  assert.deepEqual(s.snapshot().followthroughTransitionDrafts,{},change);
 }
});

test('a new evaluation date preserves status-change input for the same historical task',async()=>{
 let tomorrow=false;
 const s=session(async()=>response(projection([taskRow(['created'],{due_date:'2026-11-03',
  source_context_state:'source_reassessment_required',needs_recheck:true,
  is_due_soon:!tomorrow,is_overdue:tomorrow})],{evaluated_on:tomorrow?'2026-11-04':'2026-11-03'})));
 await open(s);await s.loadFollowthrough(cid);
 const draft={owner_label:'Fictional recheck owner',reason:'Keep this note while the revisit date passes.'};
 s.editFollowthroughTransitionDraft(tid,draft);tomorrow=true;await s.loadFollowthrough(cid);
 assert.deepEqual(s.snapshot().followthroughTransitionDrafts[tid].fields,draft);
 assert.equal(s.snapshot().followthrough.tasks[0].is_overdue,true);
});

test('a confirmed transition consumes only its own task draft',async()=>{
 const secondId='TASK-'+'D'.repeat(32);let assigned=false;
 const second=taskRow(['created'],{task_id:secondId,history:[{...history()[0],event_id:eventId(101)}]});
 const s=session(async(url,init)=>{
  if(init.method==='POST'){assigned=true;return response(receipt(2),201);}
  return response(projection([taskRow(assigned?['created','assigned']:['created']),second]));
 });
 await open(s);await s.loadFollowthrough(cid);
 const first={owner_label:'Fictional coordinator',reason:'Assign this exact task.'};
 const other={owner_label:'Another fictional coordinator',reason:'Leave this different task unfinished.'};
 s.editFollowthroughTransitionDraft(tid,first);s.editFollowthroughTransitionDraft(secondId,other);
 await s.transitionFollowthrough(tid,{...first,status:'assigned'});
 assert.equal(s.snapshot().followthroughTransitionDrafts[tid],undefined);
 assert.deepEqual(s.snapshot().followthroughTransitionDrafts[secondId].fields,other);
 assert.equal(s.snapshot().followthroughReceipt.revision,2);
});

test('an uncertain transition keeps its exact intent when fresh task history clears obsolete input',async()=>{
 const posts=[];let advanced=false;
 const s=session(async(url,init)=>{
  if(init.method==='POST'){posts.push(init.body);if(posts.length===1)throw Error('Receipt lost after commit');return response(receipt(2,true));}
  return response(projection([taskRow(advanced?['created','assigned','acknowledged']:['created'])]));
 });
 await open(s);await s.loadFollowthrough(cid);
 const draft={owner_label:'Fictional coordinator',reason:'Assign the recorded fictional work.'};
 s.editFollowthroughTransitionDraft(tid,draft);await s.transitionFollowthrough(tid,{...draft,status:'assigned'});
 const intent=s.snapshot().followthroughIntent;
 s.editFollowthroughTransitionDraft(tid,{...draft,reason:'Changed draft must not replace captured intent.'});
 s.clearFollowthroughTransitionDraft(tid);
 assert.deepEqual(s.snapshot().followthroughTransitionDrafts[tid].fields,draft);
 assert.equal(s.snapshot().followthroughIntent,intent);
 advanced=true;await s.loadFollowthrough(cid);
 assert.deepEqual(s.snapshot().followthroughTransitionDrafts,{});
 assert.equal(s.snapshot().followthroughIntent,intent);
 await s.retryFollowthroughWrite();assert.equal(posts[0],posts[1]);
 assert.equal(JSON.parse(posts[1]).expected_revision,1);
 assert.equal(s.snapshot().followthroughReceipt.revision,2);
 assert.equal(s.snapshot().followthrough.tasks[0].revision,3);
});

test('status-change input requires a current authorized task and cannot be restored by a late read',async()=>{
 const late=deferred();let hold=false;
 const s=session(async()=>hold?late.promise:response(projection()));
 await open(s);s.editFollowthroughTransitionDraft(tid,{owner_label:'Fictional owner',reason:'No task read exists.'});
 assert.deepEqual(s.snapshot().followthroughTransitionDrafts,{});
 await s.loadFollowthrough(cid);s.editFollowthroughTransitionDraft(tid,{owner_label:'Fictional owner',reason:'This authorized draft must clear.'});
 hold=true;const pending=s.loadFollowthrough(cid);s.disconnect();late.resolve(response(projection()));await pending;
 assert.deepEqual(s.snapshot().followthroughTransitionDrafts,{});assert.equal(s.snapshot().followthrough,null);
});

test('a refused status change preserves editable input but access denial clears it',async()=>{
 for(const status of [400,409,413,422,403,404]){
  const s=session(async(url,init)=>init.method==='POST'?response({},status):basic(url));
  await ready(s);await s.loadFollowthrough(cid);
  const draft={owner_label:'Fictional owner',reason:'Proposed assignment before explicit submission.'};
  s.editFollowthroughTransitionDraft(tid,draft);await s.transitionFollowthrough(tid,{...draft,status:'assigned'});
  assert.equal(s.snapshot().followthroughWritePhase,'error');assert.equal(s.snapshot().followthroughIntent,null);
  if([403,404].includes(status))assert.deepEqual(s.snapshot().followthroughTransitionDrafts,{});
  else assert.deepEqual(s.snapshot().followthroughTransitionDrafts[tid]?.fields,draft,String(status));
 }
});

test('follow-through read uses the existing scoped session and immutable task history',async()=>{
 const calls=[];const s=session(async(url,init)=>{calls.push([url,init]);return response(projection());});
 await open(s);await s.loadFollowthrough(cid);
 assert.equal(s.snapshot().followthroughPhase,'ready');
 assert.equal(s.snapshot().followthrough.tasks[0].history[0].reason,fields().reason);
 assert.equal(s.snapshot().followthrough.access_receipt_id,'ACCESS-'+'F'.repeat(32));
 assert.equal(s.snapshot().followthrough.tasks[0].clinical_approval,false);
 assert.equal(Object.isFrozen(s.snapshot().followthrough.tasks[0].history),true);
 assert.deepEqual(calls.map(([url])=>url),[path+'/followthrough']);
 assert.equal(calls[0][1].method,'GET');assert.equal(calls[0][1].credentials,'omit');
 assert.equal(calls[0][1].cache,'no-store');assert.equal(calls[0][1].redirect,'error');
});

test('create captures the exact saved question snapshot and preflight with a separate write request',async()=>{
 const posts=[];let saved=false;
 const s=session(async(url,init)=>{if(init.method==='POST'){posts.push([url,JSON.parse(init.body)]);saved=true;return response(receipt(),201);}
  if(url.endsWith('/followthrough'))return response(projection(saved?[taskRow()]:[]));return basic(url);});
 await ready(s);await s.createFollowthrough(qid,fields());
 assert.equal(s.snapshot().followthroughWritePhase,'saved');assert.deepEqual(s.snapshot().followthroughReceipt,receipt());
 assert.equal(posts.length,1);assert.equal(posts[0][0],path+'/questions/'+qid+'/followthrough');
 const {request_key,...body}=posts[0][1];assert.match(request_key,/^[A-Za-z0-9._:-]{3,128}$/);
 assert.deepEqual(body,{synthetic:true,...fields(),source_snapshot_contract:contract,
  expected_source_snapshot_sha256:snapshot,expected_preflight_sha256:preflight});
 assert.equal(s.snapshot().followthrough.tasks[0].task_id,tid);
});

test('patient access alone cannot create work and obsolete question contexts are not retargeted',async()=>{
 for(const change of [{source_context_state:'source_reassessment_required'},
  {source_snapshot_sha256:'d'.repeat(64)},
  {source_snapshot_contract:'oi.synthetic-postgres-world-model-sources/1',source_context_state:'source_reassessment_required'}]){
  let writes=0;const s=session(async(url,init)=>{if(init.method==='POST')writes++;
   return url.endsWith('/questions')?response(questions([question(change)])):basic(url);});
  await open(s);await s.createFollowthrough(qid,fields());assert.equal(writes,0);
  await s.loadWorldModel(cid);await s.loadSavedQuestions(cid);await s.createFollowthrough(qid,fields());
  assert.equal(writes,0);assert.equal(s.snapshot().followthroughReceipt,null);
 }
});

test('invalid task text, controls and dates never leave the client as write requests',async()=>{
 const bad=[{title:'x'},{title:'x'.repeat(161)},{detail:'x'.repeat(2001)},{owner_label:'x'.repeat(81)},
  {reason:'x'},{title:'Hidden\u202E text'},{reason:'line\nbreak'},{due_date:'2026-02-30'},
  {due_date:null,review_trigger:''},{review_trigger:'x'.repeat(501)}];
 let writes=0;const s=session(async(url,init)=>{if(init.method==='POST')writes++;return basic(url);});
 await ready(s);for(const overrides of bad)await s.createFollowthrough(qid,{...fields(),...overrides});
 assert.equal(writes,0);assert.equal(s.snapshot().followthroughReceipt,null);
});

test('transitions use the displayed revision and cannot skip assignment or acknowledgment',async()=>{
 const posts=[];let statuses=['created'];
 const s=session(async(url,init)=>{if(init.method==='POST'){
   const body=JSON.parse(init.body);posts.push([url,body]);statuses.push(body.status);return response(receipt(statuses.length),201);}
  return response(projection([taskRow(statuses)]));});
 await open(s);await s.loadFollowthrough(cid);
 await s.transitionFollowthrough(tid,{status:'completed',owner_label:'',reason:'Fictional work complete.'});
 await s.transitionFollowthrough(tid,{status:'assigned',owner_label:'',reason:'Assign the fictional work.'});
 assert.equal(posts.length,0);
 await s.transitionFollowthrough(tid,{status:'assigned',owner_label:'Fictional coordinator',reason:'Assign the fictional work.'});
 await s.transitionFollowthrough(tid,{status:'completed',owner_label:'',reason:'Fictional work complete.'});
 assert.equal(posts.length,1);
 await s.transitionFollowthrough(tid,{status:'acknowledged',owner_label:'',reason:'Fictional work acknowledged.'});
 await s.transitionFollowthrough(tid,{status:'completed',owner_label:'',reason:'Fictional work complete.'});
 assert.deepEqual(posts.map(([,body])=>body.expected_revision),[1,2,3]);
 assert.deepEqual(posts.map(([,body])=>body.status),['assigned','acknowledged','completed']);
 assert.ok(posts.every(([url,body])=>url===path+'/followthrough/'+tid+'/transitions'&&body.synthetic===true));
 assert.equal(s.snapshot().followthrough.tasks[0].status,'completed');
 assert.equal(s.snapshot().followthrough.tasks[0].history.length,4);
});

test('amended task provenance remains historical while defer and reassign remain operational',async()=>{
 const statuses=['created','deferred','assigned'];
 const row=taskRow(statuses,{source_context_state:'source_reassessment_required',needs_recheck:true});
 const s=session(async()=>response(projection([row])));await open(s);await s.loadFollowthrough(cid);
 assert.equal(s.snapshot().followthrough.tasks[0].source_id,sid);
 assert.equal(s.snapshot().followthrough.tasks[0].needs_recheck,true);
 assert.deepEqual(s.snapshot().followthrough.tasks[0].history.map(e=>e.status),statuses);
});

test('distinct valid task and creation-event timestamps survive the real PostgreSQL insert contract',async()=>{
 const recorded='2026-11-03T10:00:00.002345Z';
 const row=taskRow(undefined,{created_at:'2026-11-03T10:00:00.001234Z',history:[{...history()[0],recorded_at:recorded}]});
 const s=session(async()=>response(projection([row])));await open(s);await s.loadFollowthrough(cid);
 assert.equal(s.snapshot().followthroughPhase,'ready');
 assert.equal(s.snapshot().followthrough.tasks[0].created_at,row.created_at);
 assert.equal(s.snapshot().followthrough.tasks[0].history[0].recorded_at,recorded);
});

// Fault-injected wire responses, not claims that the real API emits these values.
for(const field of ['created_at','recorded_at']){
 for(const invalid of ['2026-02-30T10:00:00Z','2026-02-29T10:00:00Z',
  '2026-04-31T10:00:00+00:00','1900-02-29T10:00:00Z','0000-01-01T10:00:00Z',
  '2026-11-03T24:00:00Z','2026-11-03T10:00Z','2026-11-03T10:00:00.1234567Z']){
  test('invalid follow-up '+field+' '+invalid+' withholds refreshed history and controls',async()=>{
   const row=taskRow(['created','assigned']);
   if(field==='created_at')row.created_at=invalid;
   else row.history[1].recorded_at=invalid;
   let bad=false,writes=0;
   const s=session(async(url,init)=>{if(init.method==='POST')writes++;
    return response(projection(bad?[row]:[taskRow(['created','assigned'])]));});
   await open(s);await s.loadFollowthrough(cid);
   assert.equal(s.snapshot().followthroughPhase,'ready');
   assert.equal(projectFollowthroughAttention(s.snapshot()).counts.all,1);
   bad=true;await s.loadFollowthrough(cid);
   assert.equal(s.snapshot().followthroughPhase,'error');
   assert.equal(s.snapshot().followthrough,null);
   assert.equal(projectFollowthroughAttention(s.snapshot()),null);
   await s.transitionFollowthrough(tid,{status:'acknowledged',owner_label:'',reason:'Fictional acknowledgment.'});
   assert.equal(writes,0);
   bad=false;await s.loadFollowthrough(cid);
   assert.equal(s.snapshot().followthroughPhase,'ready');
   assert.equal(s.snapshot().followthrough.tasks[0].task_id,tid);
  });
 }
}

test('follow-up timestamps preserve valid seconds, microseconds, offsets and leap dates literally',async()=>{
 for(const stamp of ['2026-11-03T10:00:00Z','2026-11-03T10:00:00.1+00:00',
  '2026-11-03T10:00:00.123456+05:30','2026-11-03T10:00:00.000001-04:00',
  '2000-02-29T10:00:00Z','2024-02-29T23:59:59.999999Z']){
  const row=taskRow(['created','assigned'],{created_at:stamp});
  row.history[1].recorded_at=stamp;
  const s=session(async()=>response(projection([row])));await open(s);await s.loadFollowthrough(cid);
  assert.equal(s.snapshot().followthroughPhase,'ready',stamp);
  assert.equal(s.snapshot().followthrough.tasks[0].created_at,stamp);
  assert.equal(s.snapshot().followthrough.tasks[0].history[1].recorded_at,stamp);
  assert.deepEqual(s.snapshot().followthrough.tasks[0].history.map(e=>e.revision),[1,2]);
 }
});

test('task history accepts the canonical 3–128 character actor range without hiding legal long actors',async()=>{
 for(const length of [128,81,3,2,129]){
  const actor='A'.repeat(length),row=taskRow(undefined,{history:[{...history()[0],actor_label:actor}]});
  const s=session(async()=>response(projection([row])));await open(s);await s.loadFollowthrough(cid);
  if(length>=3&&length<=128){
   assert.equal(s.snapshot().followthroughPhase,'ready','canonical actor length '+length);
   assert.equal(s.snapshot().followthrough.tasks[0].history[0].actor_label,actor);
  }else{assert.equal(s.snapshot().followthrough,null);assert.equal(s.snapshot().followthroughPhase,'error');}
 }
});

test('wrong scope, forged status, corrupt provenance and impossible history fail closed',async()=>{
 const bad=[projection(undefined,{patient_id:'PAT-OTHER-001'}),projection(undefined,{case_id:otherCase}),
  projection(undefined,{clinical_approval:true}),projection(undefined,{external_notification_sent:true}),
  projection(undefined,{evaluated_on:'2026-02-30'}),projection(undefined,{access_receipt_id:'ACCESS-'+'F'.repeat(32)+'\n'}),
  projection([taskRow(undefined,{patient_id:'PAT-OTHER-001'})]),projection([taskRow(undefined,{task_id:tid+'\n'})]),
  projection([taskRow(undefined,{source_sha256:sha+'\n'})]),projection([taskRow(undefined,{clinical_approval:true})]),
  projection([taskRow(['created','completed'])]),projection([taskRow(undefined,{revision:2})]),
  projection([taskRow(undefined,{history:[]})]),projection([taskRow(),taskRow()]),
  projection([taskRow(undefined,{needs_recheck:true})]),projection([taskRow(undefined,{is_overdue:true})]),
  projection([taskRow(undefined,{history:[{...history()[0],previous_status:'assigned'}]})]),
  projection([taskRow(undefined,{history:[{...history()[0],owner_label:'Different owner'}]})]),
  projection([taskRow(undefined,{title:'Obscured\u202E title'})]),projection([taskRow(undefined,{unknown:'extra field'})])];
 for(const value of bad){const s=session(async()=>response(value));await open(s);await s.loadFollowthrough(cid);
  assert.equal(s.snapshot().followthrough,null);assert.equal(s.snapshot().followthroughPhase,'error');}
});

test('refresh removes old task data immediately and a delayed older read cannot overwrite the latest',async()=>{
 const delayed=deferred();let calls=0;
 const s=session(async()=>++calls===2?delayed.promise:response(projection(calls===3?[]:[taskRow()])));
 await open(s);await s.loadFollowthrough(cid);assert.equal(s.snapshot().followthrough.tasks.length,1);
 const pending=s.loadFollowthrough(cid);assert.equal(s.snapshot().followthrough,null);
 await s.loadFollowthrough(cid);delayed.resolve(response(projection()));await pending;
 assert.equal(s.snapshot().followthrough.tasks.length,0);
});

test('patient change, case navigation and disconnect reject late task lists',async()=>{
 for(const change of [s=>s.read('PAT-EXAMPLE-002'),s=>s.loadWorldModel(otherCase),s=>s.disconnect()]){
  const delayed=deferred();const s=session(async(url)=>url.endsWith('/followthrough')?delayed.promise:basic(url));
  await ready(s);const pending=s.loadFollowthrough(cid);await change(s);
  delayed.resolve(response(projection()));await pending;assert.equal(s.snapshot().followthrough,null);
  assert.equal(s.snapshot().followthroughReceipt,null);assert.equal(s.snapshot().followthroughIntent,null);
 }
});

test('late write receipts cannot restore tasks or drafts after patient, case or credential navigation',async()=>{
 for(const change of [s=>s.read('PAT-EXAMPLE-002'),s=>s.loadWorldModel(otherCase),s=>s.disconnect()]){
  const delayed=deferred();const s=session(async(url,init)=>init.method==='POST'?delayed.promise:basic(url));
  await ready(s);const pending=s.createFollowthrough(qid,fields());await change(s);
  assert.equal(s.snapshot().followthroughIntent,null);delayed.resolve(response(receipt(),201));await pending;
  assert.equal(s.snapshot().followthroughReceipt,null);assert.equal(s.snapshot().followthrough,null);
 }
});

test('lost create response retains exact intent across same-case amendment and explicit retry recovers receipt',async()=>{
 const posts=[];let changed=false;
 const s=session(async(url,init)=>{if(init.method==='POST'){
   posts.push([url,init.body]);if(posts.length===1)throw Error('response lost after commit');return response(receipt(1,true));}
  if(url.endsWith('/world-model'))return response(world(cid,changed?'d'.repeat(64):snapshot));
  if(url.endsWith('/questions'))return response(questions([question(changed?{source_context_state:'source_reassessment_required'}:{})]));
  return response(projection([taskRow(undefined,changed?{source_context_state:'source_reassessment_required',needs_recheck:true}:{})]));});
 await ready(s);await s.createFollowthrough(qid,fields());assert.equal(s.snapshot().followthroughWritePhase,'unknown');
 changed=true;await s.loadWorldModel(cid);await s.loadSavedQuestions(cid);await s.loadFollowthrough(cid);
 assert.equal(s.snapshot().followthroughWritePhase,'unknown');
 await s.retryFollowthroughWrite();assert.deepEqual(posts[1],posts[0]);
 assert.equal(s.snapshot().followthroughReceipt.duplicate,true);assert.equal(s.snapshot().followthroughWritePhase,'saved');
 assert.equal(s.snapshot().followthrough.tasks[0].needs_recheck,true);
});

test('uncertain writes block edits and other intents until explicit abandonment',async()=>{
 const posts=[];const s=session(async(url,init)=>{if(init.method==='POST'){posts.push(init.body);throw Error('lost');}return basic(url);});
 await ready(s);await s.createFollowthrough(qid,fields());const first=s.snapshot().followthroughIntent;
 await s.createFollowthrough(qid,{...fields(),title:'A changed fictional task'});
 await s.transitionFollowthrough(tid,{status:'assigned',owner_label:'Another coordinator',reason:'Assign work.'});
 assert.equal(posts.length,1);assert.equal(s.snapshot().followthroughIntent,first);
 s.abandonFollowthroughWrite();assert.equal(s.snapshot().followthroughIntent,null);
 await s.createFollowthrough(qid,{...fields(),title:'A changed fictional task'});
 assert.equal(posts.length,2);assert.notEqual(JSON.parse(posts[0]).request_key,JSON.parse(posts[1]).request_key);
});

test('refresh during an in-flight write preserves recovery but ignores its delayed receipt',async()=>{
 const delayed=deferred();const posts=[];
 const s=session(async(url,init)=>{if(init.method==='POST'){posts.push(init.body);return posts.length===1?delayed.promise:response(receipt(1,true));}return basic(url);});
 await ready(s);const pending=s.createFollowthrough(qid,fields());await s.loadWorldModel(cid);
 assert.equal(s.snapshot().followthroughWritePhase,'unknown');delayed.resolve(response(receipt(),201));await pending;
 assert.equal(s.snapshot().followthroughReceipt,null);assert.equal(s.snapshot().followthroughWritePhase,'unknown');
 await s.retryFollowthroughWrite();assert.equal(posts[0],posts[1]);assert.equal(s.snapshot().followthroughReceipt.duplicate,true);
});

test('retry of uncertain transition keeps the original revision even after later history is read',async()=>{
 const posts=[];let later=false;
 const s=session(async(url,init)=>{if(init.method==='POST'){posts.push(init.body);later=true;
   if(posts.length===1)throw Error('lost after commit');return response(receipt(2,true));}
  return response(projection([taskRow(later?['created','assigned','acknowledged']:['created'])]));});
 await open(s);await s.loadFollowthrough(cid);await s.transitionFollowthrough(tid,{status:'assigned',owner_label:'Fictional coordinator',reason:'Assign fictional work.'});
 await s.loadFollowthrough(cid);assert.equal(s.snapshot().followthrough.tasks[0].revision,3);
 await s.retryFollowthroughWrite();assert.equal(posts[0],posts[1]);assert.equal(JSON.parse(posts[1]).expected_revision,1);
 assert.equal(s.snapshot().followthroughReceipt.revision,2);assert.equal(s.snapshot().followthrough.tasks[0].revision,3);
});

test('malformed or mismatched success receipts retain an uncertain exact write for recovery',async()=>{
 const bad=[receipt(1,false,{task_id:tid+'\n'}),receipt(1,false,{question_id:'QUESTION-'+'D'.repeat(32)}),
  receipt(2),receipt(1,false,{event_id:'bad'}),receipt(1,false,{duplicate:'yes'})];
 for(const value of bad){const posts=[];const s=session(async(url,init)=>{if(init.method==='POST'){
    posts.push(init.body);return response(posts.length===1?value:receipt(1,true),posts.length===1?201:200);}return basic(url);});
  await ready(s);await s.createFollowthrough(qid,fields());assert.equal(s.snapshot().followthroughWritePhase,'unknown');
  assert.equal(s.snapshot().followthroughReceipt,null);await s.retryFollowthroughWrite();
  assert.equal(posts[0],posts[1]);assert.equal(s.snapshot().followthroughWritePhase,'saved');}
});

test('denied or failed refresh clears task content and independent write denials never display server detail',async()=>{
 for(const status of [403,404,503]){let denied=false;const s=session(async()=>denied?response({detail:'private task text'},status):response(projection()));
  await open(s);await s.loadFollowthrough(cid);denied=true;await s.loadFollowthrough(cid);
  assert.equal(s.snapshot().followthrough,null);assert.equal(s.snapshot().followthroughPhase,'error');
  assert.ok(!JSON.stringify(s.snapshot()).includes('private task text'));}
 for(const status of [403,404,409,422]){const s=session(async(url,init)=>init.method==='POST'?response({detail:'private task text'},status):basic(url));
  await ready(s);await s.createFollowthrough(qid,fields());assert.equal(s.snapshot().followthroughWritePhase,'error');
  assert.equal(s.snapshot().followthroughIntent,null);assert.equal(s.snapshot().followthroughReceipt,null);
  assert.ok(!JSON.stringify(s.snapshot()).includes('private task text'));}
});

test('question or source authority revocation clears dependent task reads and uncertain intents',async()=>{
 for(const revoke of ['questions','world-model','sources']){let denied=false;
  const s=session(async(url,init)=>{if(denied&&url.endsWith('/'+revoke))return response({},404);
   if(init.method==='POST')throw Error('lost');return basic(url);});
  await ready(s);await s.loadFollowthrough(cid);await s.createFollowthrough(qid,fields());assert.equal(s.snapshot().followthroughWritePhase,'unknown');
  denied=true;if(revoke==='questions')await s.loadSavedQuestions(cid);else if(revoke==='world-model')await s.loadWorldModel(cid);else await s.loadSources(cid);
  assert.equal(s.snapshot().followthrough,null);assert.equal(s.snapshot().followthroughIntent,null);assert.equal(s.snapshot().followthroughReceipt,null);
 }
});

test('credential revocation during write clears all task state and late read completions',async()=>{
 const late=deferred();let reads=0;const s=session(async(url,init)=>init.method==='POST'?response({},401):
  url.endsWith('/followthrough')&&++reads===2?late.promise:basic(url));
 await ready(s);await s.loadFollowthrough(cid);const pending=s.loadFollowthrough(cid);
 await s.createFollowthrough(qid,fields());assert.equal(s.snapshot().connected,false);
 late.resolve(response(projection()));await pending;assert.equal(s.snapshot().followthrough,null);
 assert.equal(s.snapshot().followthroughIntent,null);assert.equal(s.snapshot().followthroughReceipt,null);
});

test('task envelopes enforce the stream bound and content type before showing any text',async()=>{
 for(const reply of [()=>new Response(JSON.stringify(projection()),{headers:{'Content-Type':'text/html'}}),
  ()=>new Response(' '.repeat(4194305),{headers:{'Content-Type':'application/json'}})]){
  const s=session(async()=>reply());await open(s);await s.loadFollowthrough(cid);
  assert.equal(s.snapshot().followthrough,null);assert.equal(s.snapshot().followthroughPhase,'error');}
 let cancelled=false;
 const oversized=new Response(new ReadableStream({start(controller){controller.enqueue(new Uint8Array(4194305));},
  cancel(){cancelled=true;}}),{headers:{'Content-Type':'application/json','Content-Length':'100'}});
 const s=session(async()=>oversized);await open(s);await s.loadFollowthrough(cid);
 assert.equal(cancelled,true,'a dishonest or absent length cannot force the complete response into memory');
});

test('same-patient case-permission refresh retains exact unknown intent, while revoked mapping clears it',async()=>{
 for(const revoked of [false,true]){
  const posts=[];let refreshing=false;
  const s=new RegistrySession(async(url,init)=>{
   if(url.endsWith('/case-bindings'))return response({...cases(),mappings:refreshing&&revoked?[]:cases().mappings});
   if(url==='/v1/patients/'+pid)return response(patient());
   if(init.method==='POST'){posts.push(init.body);if(posts.length===1)throw Error('lost');return response(receipt(1,true));}
   return basic(url);
  });
  await ready(s);await s.createFollowthrough(qid,fields());refreshing=true;await s.loadCases();
  if(revoked){assert.equal(s.snapshot().followthroughIntent,null);await s.retryFollowthroughWrite();assert.equal(posts.length,1);}
  else{assert.equal(s.snapshot().followthroughWritePhase,'unknown');await s.retryFollowthroughWrite();
   assert.equal(posts[0],posts[1]);assert.equal(s.snapshot().followthroughReceipt.duplicate,true);}
 }
});

test('case selection through question or review reads clears tasks and earlier uncertain intent',async()=>{
 for(const select of [s=>s.loadSavedQuestions(otherCase),s=>s.loadReviewQueue(otherCase)]){
  const s=session(async(url,init)=>init.method==='POST'?Promise.reject(Error('lost')):basic(url));
  await ready(s);await s.createFollowthrough(qid,fields());await select(s);
  assert.equal(s.snapshot().followthrough,null);assert.equal(s.snapshot().followthroughIntent,null);
 }
});

test('late original write cannot unlock a newer exact retry or dispatch duplicate retry requests',async()=>{
 const old=deferred(),retry=deferred(),posts=[];
 const s=session(async(url,init)=>{if(init.method==='POST'){posts.push(init.body);return posts.length===1?old.promise:retry.promise;}return basic(url);});
 await ready(s);const first=s.createFollowthrough(qid,fields());
 await s.loadWorldModel(cid);const second=s.retryFollowthroughWrite();
 old.resolve(response(receipt(),201));await first;
 await s.retryFollowthroughWrite();await s.createFollowthrough(qid,fields());
 assert.equal(posts.length,2);assert.equal(posts[0],posts[1]);assert.equal(s.snapshot().followthroughWritePhase,'saving');
 retry.resolve(response(receipt(1,true)));await second;assert.equal(s.snapshot().followthroughReceipt.duplicate,true);
});

test('merged question and task workflows preserve both exact unknown writes through temporary metadata loss',async()=>{
 const reviewBodies=[],taskBodies=[];let unavailable=false,taskReads=0;
 const {human_review_state,model_executed,...savedQuestion}=question();
 const queue={contract:'oi.synthetic-question-review-return-queue/2',access_receipt_id:'ACCESS-'+'D'.repeat(32),
  patient_id:pid,case_id:cid,synthetic:true,receipts:[],external_notification_sent:false,reviewer_identity_verified:false,
  clinical_approval:false,review_completion_supported:false,items:[{...savedQuestion,kind:'source-question',
   queue_fingerprint:'d'.repeat(64),queue_fingerprint_contract:'oi.synthetic-source-review-return/2',
   review_state:'awaiting_independent_verification',current_return_receipt_id:null,return_count:0,prior_return_count:0,
   reviewer_identity_verified:false}]};
 const s=new RegistrySession(async(url,init)=>{
  if(url.endsWith('/case-bindings'))return unavailable?response({},503):response(cases());
  if(url==='/v1/patients/'+pid)return response(patient());
  if(url.endsWith('/review-queue'))return response(queue);
  if(url.endsWith('/return-for-verification')){
   reviewBodies.push(init.body);return reviewBodies.length===1?response({},503):
    response({receipt_id:'REVIEW-'+'D'.repeat(32),question_id:qid,duplicate:true});
  }
  if(init.method==='POST'){
   taskBodies.push(init.body);return taskBodies.length===1?response({},503):response(receipt(1,true));
  }
  if(url.endsWith('/followthrough'))taskReads++;
  return basic(url);
 });
 await ready(s);await s.loadReviewQueue(cid);
 await s.returnReviewQuestion(qid,'d'.repeat(64),'Please independently verify this fictional source detail.');
 await s.createFollowthrough(qid,fields());
 const reviewIntent=s.snapshot().reviewReturnIntent,taskIntent=s.snapshot().followthroughIntent;
 assert.equal(s.snapshot().reviewReturnPhase,'unknown');assert.equal(s.snapshot().followthroughWritePhase,'unknown');
 s.chooseQuestionDraft(sid,8);s.changeQuestionDraft('Which other fictional source detail needs verification?');
 assert.equal(s.snapshot().followthroughIntent,taskIntent);
 unavailable=true;await s.loadCases();await s.loadReviewQueue(cid);await s.loadFollowthrough(cid);
 assert.equal(s.snapshot().reviewReturnIntent,reviewIntent);
 assert.equal(s.snapshot().followthroughIntent,taskIntent);
 assert.equal(s.snapshot().followthroughWritePhase,'unknown');assert.equal(taskReads,0);
 await s.retryReviewReturn();await s.retryFollowthroughWrite();
 assert.equal(reviewBodies.length,1);assert.equal(taskBodies.length,1);
 unavailable=false;await s.loadCases();await s.retryReviewReturn();await s.retryFollowthroughWrite();
 assert.equal(reviewBodies[1],reviewBodies[0]);assert.equal(taskBodies[1],taskBodies[0]);
 assert.equal(s.snapshot().reviewReturn.duplicate,true);assert.equal(s.snapshot().followthroughReceipt.duplicate,true);
});
