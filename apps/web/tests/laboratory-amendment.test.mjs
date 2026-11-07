import {test} from 'node:test';
import assert from 'node:assert/strict';
import {decodeAmendmentReview,decodeAmendmentInbox,amendmentAction} from '../.test-dist/laboratory-amendment.js';
import {AmendmentSession,emptyAmendment} from '../.test-dist/laboratory-amendment-session.js';
const key=(prefix,c)=>prefix+'-'+c.repeat(32);
const patient='PAT-EXAMPLE',caseId='CASE-EXAMPLE',taskId=key('TASK','A'),qid=key('QUESTION','B');
const first=key('SRC','A'),latest=key('SRC','B'),request=key('VERIFY','A'),answer=key('VERIFY','B');
const originalHash='a'.repeat(64),latestHash='b'.repeat(64),ref='Observation/EXAMPLE';
const scope={patient_id:patient,case_id:caseId};
const task={...scope,task_id:taskId,question_id:qid,source_line:null,source_context_state:'source_reassessment_required',
 source_id:first,source_sha256:originalHash,source_version:1,observation_reference:ref};
const obs={loinc_code:'777-3',status:'reported_value',value_text:'0.00',unit_code:'10*9/L',absent_reason:null,
 specimen_reference:'Specimen/EXAMPLE',effective_at:'2026-04-03T12:00:00Z',issued_at:'2026-04-04T12:00:00Z'};
const posted={entry_id:request,request_id:request,action:'request',actor:'ACTOR-EXAMPLE',recorded_at:'2026-11-01T12:00:00Z',
 reason:'Please compare both source reports.',disposition:null,original_source_id:first,latest_source_id:latest,latest_sha256:latestHash};
const answered={...posted,entry_id:answer,action:'respond',actor:'ACTOR-REVIEWER',recorded_at:'2026-11-01T15:00:00Z',
 reason:'The two transcriptions were compared.',disposition:'transcription_checked'};
const detail=(entries=[])=>({contract:'oi.laboratory-amendment-review/1',...scope,task_id:taskId,question_id:qid,observation_reference:ref,
 original:{source_id:first,version:1,sha256:originalHash,document_id:'EXAMPLE-REPORT',observation:obs},
 latest:{source_id:latest,version:2,sha256:latestHash,document_id:'EXAMPLE-REPORT',observation:{...obs,value_text:'1.0'}},
 entries,clinical_approval:false});
const item={request_id:request,task_id:taskId,question_id:qid,latest_source_id:latest};
const inbox=(rows=[item])=>({contract:'oi.laboratory-amendment-inbox/1',...scope,requests:rows,clinical_approval:false});

test('an amendment comparison binds both versions and the selected request, preserving precision, absent and missing',()=>{
 const read=x=>decodeAmendmentReview(x,task);
 const d=detail([posted]);assert.equal(read(d).original.observation.value_text,'0.00');
 const missing={...d,latest:{...d.latest,observation:null}};assert.equal(read(missing).latest.observation,null);
 const absent={...obs,status:'reported_absent',absent_reason:'not-performed',unit_code:null,value_text:null};
 assert.equal(read({...d,latest:{...d.latest,observation:absent}}).latest.observation.absent_reason,'not-performed');
 assert.equal(amendmentAction(read(detail()),null),'request');assert.equal(amendmentAction(read(d),null),null);
 assert.equal(amendmentAction(read(d),item),'respond');assert.equal(amendmentAction(read(detail([posted,answered])),item),null);
 const changed={...d,latest:{...d.latest,source_id:key('SRC','C'),version:3,sha256:'c'.repeat(64)}};
 assert.equal(amendmentAction(read(changed),item),null);assert.equal(amendmentAction(read(changed),null),'request');
 for(const bad of [{...d,patient_id:'PAT-OTHER'},{...d,task_id:key('TASK','F')},{...d,clinical_approval:true},
  {...d,observation_reference:'Observation/OTHER'},{...d,original:{...d.original,sha256:'c'.repeat(64)}},
  {...d,latest:{...d.latest,document_id:'OTHER'}},{...d,latest:{...d.latest,source_id:first}},{...d,latest:{...d.latest,version:1}},
  {...d,entries:[answered]},{...d,entries:[posted,{...answered,actor:posted.actor}]},{...d,entries:[posted,posted]},
  {...d,entries:[posted,{...answered,latest_sha256:'e'.repeat(64)}]},{...d,latest:{...d.latest,observation:{...obs,absent_reason:'unknown'}}}]){
  assert.throws(()=>read(bad));
 }
 assert.throws(()=>decodeAmendmentReview(d,task,{...item,request_id:key('VERIFY','F')}));
 assert.equal(decodeAmendmentInbox(inbox(),scope)[0].request_id,request);
 for(const bad of [inbox([item,item]),{...inbox(),case_id:'CASE-OTHER'},inbox([{...item,question_id:taskId}])]){
  assert.throws(()=>decodeAmendmentInbox(bad,scope));
 }
});

const held=()=>{let resolve;return {promise:new Promise(r=>resolve=r),resolve:v=>resolve(v)};};
function session(exchange){
 const selected={...task,status:'acknowledged',owner_label:'Fictional coordinator',needs_recheck:true};
 let state={connected:true,phase:'ready',patient:{patient_id:patient,status:'active'},
  cases:[{...scope,status:'active'}],worldModel:null,followthroughPhase:'ready',followthroughCaseId:caseId,
  followthrough:{...scope,tasks:[selected]},amendment:emptyAmendment()};
 const s=new AmendmentSession(()=>state,amendment=>{state={...state,amendment};},exchange);
 return {s,selected,state:()=>state,reset:(keep)=>{state={...state,amendment:s.reset(keep)};},
  change:patch=>{state={...state,...patch};}};
}
const ok=value=>({status:200,value});

test('an uncertain action retries its exact key and body after another amendment and verifies historical receipt',async()=>{
 let writes=[],current=detail();
 const h=session(async(_scope,path,control,body)=>{
  if(!body)return ok(current);
  writes.push(body);
  if(writes.length===1)throw Error('Response lost after commit');
  return ok({entry_id:request,request_id:request,duplicate:true});
 });
 await h.s.openTask(h.selected);
 const before=h.state().amendment.detail;
 await h.s.submit(before,posted.reason);
 assert.equal(h.state().amendment.phase,'unknown');
 const command=h.state().amendment.command;
 assert.equal(Object.isFrozen(command.body),true);
 h.s.dismiss();assert.equal(h.state().amendment.command,command);
 await h.s.openTask(h.selected);assert.equal(writes.length,1);
 current={...detail([posted]),latest:{...detail().latest,source_id:key('SRC','C'),version:3,sha256:'c'.repeat(64)}};
 await h.s.retry();
 assert.equal(writes.length,2);assert.equal(writes[0],writes[1]);
 assert.equal(h.state().amendment.phase,'ready');assert.equal(h.state().amendment.command,null);
 assert.equal(h.state().amendment.detail.latest.version,3);
 assert.equal(h.state().amendment.detail.entries[0].latest_source_id,latest);
 assert.equal(h.selected.status,'acknowledged');assert.equal(h.selected.needs_recheck,true);
});

test('navigation during an in-flight write retains only exact recovery and suppresses a late reply',async()=>{
 const wait=held();let writes=0;
 const h=session(async(_scope,_path,_control,body)=>{if(body){writes++;return wait.promise;}return ok(detail());});
 await h.s.openTask(h.selected);
 const pending=h.s.submit(h.state().amendment.detail,posted.reason);
 assert.equal(h.state().amendment.phase,'saving');h.s.dismiss();
 assert.equal(h.state().amendment.phase,'unknown');assert.equal(h.state().amendment.detail,null);
 wait.resolve({status:201,value:{entry_id:request,request_id:request,duplicate:false}});await pending;
 assert.equal(h.state().amendment.phase,'unknown');assert.equal(writes,1);
 h.reset();assert.equal(h.state().amendment.command,null);await h.s.retry();assert.equal(writes,1);
});

test('dismissed, disconnected and revoked reads cannot repopulate the comparison',async()=>{
 for(const invalidate of [h=>h.s.dismiss(),h=>{h.reset();h.change({connected:false});},
  h=>{h.reset();h.change({cases:[{...scope,status:'revoked'}]});}]){
  const wait=held(),h=session(async()=>wait.promise);
  const pending=h.s.openTask(h.selected);invalidate(h);wait.resolve(ok(detail()));await pending;
  assert.equal(h.state().amendment.detail,null);assert.equal(h.state().amendment.command,null);
 }
});

test('explicit refusal discards retry material, while unconfirmed success never invents history',async()=>{
 for(const status of [400,403,404,409,413,422]){
  let writes=0;const h=session(async(_s,_p,_c,body)=>{if(body){writes++;return {status,value:null};}return ok(detail());});
  await h.s.openTask(h.selected);await h.s.submit(h.state().amendment.detail,posted.reason);
  assert.equal(h.state().amendment.phase,'error');assert.equal(h.state().amendment.command,null);
  assert.equal(h.state().amendment.detail,null);await h.s.retry();assert.equal(writes,1);
 }
 const h=session(async(_s,_p,_c,body)=>body?{status:201,value:{entry_id:request,request_id:request,duplicate:false}}:ok(detail()));
 await h.s.openTask(h.selected);await h.s.submit(h.state().amendment.detail,posted.reason);
 assert.equal(h.state().amendment.phase,'error');assert.equal(h.state().amendment.detail,null);
 assert.match(h.state().amendment.message,/History could not be verified/);
});

test('an old comparison and an unselected task cannot initiate a mutation',async()=>{
 let calls=0;const h=session(async()=>{calls++;return ok(detail());});
 await h.s.openTask({...h.selected});assert.equal(calls,0);
 await h.s.openTask(h.selected);const previous=h.state().amendment.detail;
 h.s.dismiss();await h.s.openTask(h.selected);
 await h.s.submit(previous,posted.reason);assert.equal(calls,2);
 await h.s.submit(h.state().amendment.detail,'  hidden spaces  ');assert.equal(calls,2);
});
