import test from 'node:test';
import assert from 'node:assert/strict';
import * as view from '../.test-dist/followthrough-view.js';

const patient='PATIENT-'+'A'.repeat(32), caseId='CASE-ATTENTION';
const taskId=n=>'TASK-'+n.toString(16).toUpperCase().padStart(32,'0');
const eventId=(n,i)=>'TASK-EVENT-'+(n*10+i).toString(16).toUpperCase().padStart(32,'0');
function task(n,status='created',changes={}){
 const sequence={created:['created'],assigned:['created','assigned'],
  acknowledged:['created','assigned','acknowledged'],completed:['created','assigned','acknowledged','completed'],
  deferred:['created','deferred']}[status];
 const owner=['assigned','acknowledged','completed'].includes(status)?'Fictional coordinator':'';
 return {task_id:taskId(n),question_id:'QUESTION-'+'B'.repeat(32),patient_id:patient,case_id:caseId,
  title:'Independently fictional follow-up '+n,detail:'Inspect the original fictional quotation.',
  owner_label:owner,due_date:null,review_trigger:'At the recorded discussion',created_at:'2026-11-01T10:00:00Z',
  status,revision:sequence.length,source_id:'SRC-'+'C'.repeat(32),source_line:8,source_sha256:'a'.repeat(64),
  source_version:1,source_snapshot_contract:'oi.pg-source-world-model/1',source_snapshot_sha256:'b'.repeat(64),
  preflight_sha256:'c'.repeat(64),source_context_state:'current_unreviewed_question',needs_recheck:false,
  is_overdue:false,is_due_soon:false,clinical_approval:false,
  history:sequence.map((s,i)=>({event_id:eventId(n,i),revision:i+1,previous_status:i?sequence[i-1]:null,
   status:s,owner_label:s==='created'?'':owner,actor_label:'ACTOR-FICTIONAL',reason:'Recorded fictional work.',
   recorded_at:'2026-11-01T10:0'+i+':00Z'})),...changes};
}
function state(rows=[],changes={}){
 const list=view.decodeFollowthrough({contract:'oi.pg-question-followthrough/1',patient_id:patient,case_id:caseId,
  access_receipt_id:'ACCESS-'+'D'.repeat(32),evaluated_on:'2026-11-03',tasks:rows,synthetic:true,
  clinical_approval:false,external_notification_sent:false},patient,caseId);
 return {connected:true,phase:'ready',patient:{patient_id:patient,status:'active'},
  cases:[{patient_id:patient,case_id:caseId,status:'active'}],worldModel:null,
  followthroughPhase:'ready',followthroughCaseId:caseId,followthrough:list,...changes};
}
const project=s=>view.projectFollowthroughAttention?.(s);
const match=(row,filter)=>view.matchesFollowthroughFilter?.(row,filter);
const selected=(selection,attention)=>view.followthroughFilterForRead?.(selection,attention);

test('a successful empty read is known zero, not unavailable',()=>{
 const result=project(state());
 assert.deepEqual(result?.counts,{all:0,recheck:0,overdue:0,unassigned:0,history:0});
});

test('attention counts overlap, preserve historical work and use server date flags',()=>{
 const s=state([task(1,'created',{due_date:'2026-11-02',is_overdue:true,
  source_context_state:'source_reassessment_required',needs_recheck:true}),
  task(2,'assigned',{due_date:'2026-11-04',is_due_soon:true}),task(3,'completed',{
   source_context_state:'source_reassessment_required'}),task(4,'deferred')]);
 const result=project(s);
 assert.deepEqual(result?.counts,{all:4,recheck:1,overdue:1,unassigned:1,history:2});
 assert.equal(result?.list,s.followthrough);
 assert.equal(Object.isFrozen(result),true);assert.equal(Object.isFrozen(result.counts),true);
});

for(const [name,change] of [
 ['disconnected',{connected:false}],['reading patient',{phase:'reading'}],['missing patient',{patient:null}],
 ['suspended patient',{patient:{patient_id:patient,status:'suspended'}}],['missing bindings',{cases:null}],
 ['revoked binding',{cases:[{patient_id:patient,case_id:caseId,status:'revoked'}]}],
 ['wrong-patient binding',{cases:[{patient_id:'PATIENT-OTHER',case_id:caseId,status:'active'}]}],
 ['loading task read',{followthroughPhase:'loading'}],['failed task read',{followthroughPhase:'error'}],
 ['missing list',{followthrough:null}],['different selected case',{followthroughCaseId:'CASE-OTHER'}],
 ['contrary World Model case',{worldModel:{patient_id:patient,case_id:'CASE-OTHER'}}],
 ['contrary World Model patient',{worldModel:{patient_id:'PATIENT-OTHER',case_id:caseId}}],
 ]){
 test(name+' withholds counts rather than asserting zero',()=>assert.equal(project(state([task(1)],change)),null));
}

test('foreign envelope or task scope and duplicate task IDs are withheld',()=>{
 const s=state([task(1)]),list=s.followthrough;
 for(const changes of [{patient_id:'PATIENT-OTHER'},{case_id:'CASE-OTHER'},
  {tasks:[{...list.tasks[0],patient_id:'PATIENT-OTHER'}]},
  {tasks:[{...list.tasks[0],case_id:'CASE-OTHER'}]}, {tasks:[list.tasks[0],list.tasks[0]]}]){
  assert.equal(project({...s,followthrough:{...list,...changes}}),null);
 }
});

test('filters classify open flags and historical states without modifying source/history',()=>{
 const s=state([task(1,'created',{source_context_state:'source_reassessment_required',needs_recheck:true,
  due_date:'2026-11-02',is_overdue:true}),task(2,'completed'),task(3,'deferred')]);
 const before=JSON.stringify(s.followthrough),rows=s.followthrough.tasks;
 for(const [filter,ids] of [['all',[1,2,3]],['recheck',[1]],['overdue',[1]],['unassigned',[1]],['history',[2,3]]]){
  assert.deepEqual(rows.filter(row=>match(row,filter)).map(row=>row.task_id),ids.map(taskId));
 }
 assert.equal(JSON.stringify(s.followthrough),before);
 assert.equal(match(rows[0],'unrecognized'),false);
});

test('an owner label on created work is not silently called unassigned',()=>{
 const row=task(1);row.owner_label='Fictional recorder';row.history[0].owner_label=row.owner_label;
 assert.equal(project(state([row]))?.counts.unassigned,0);
});

test('filters never promote completed/deferred rows to open-work attention',()=>{
 for(const status of ['completed','deferred']){
  const row=task(1,status,{needs_recheck:true,is_overdue:true,owner_label:''});
  assert.equal(match(row,'recheck'),false);assert.equal(match(row,'overdue'),false);
  assert.equal(match(row,'unassigned'),false);assert.equal(match(row,'history'),true);
 }
});

test('browser date is not used to recompute an existing evaluated-on snapshot',()=>{
 const row=task(1,'created',{due_date:'2026-11-04',is_due_soon:true});
 const s=state([row]);
 const original=Date.now;
 try{Date.now=()=>Date.parse('2099-01-01');assert.equal(project(s)?.counts.overdue,0);}
 finally{Date.now=original;}
});

test('filter is scoped to exact access receipt, patient and case; new reads reset to all',()=>{
 const attention=project(state([task(1)]));
 const selection={access_receipt_id:'ACCESS-'+'D'.repeat(32),patient_id:patient,case_id:caseId,filter:'recheck'};
 assert.equal(selected(selection,attention),'recheck');
 for(const change of [{access_receipt_id:'ACCESS-'+'E'.repeat(32)}, {patient_id:'PATIENT-OTHER'},
  {case_id:'CASE-OTHER'},{filter:'unrecognized'}])assert.equal(selected({...selection,...change},attention),'all');
 assert.equal(selected(null,attention),'all');assert.equal(selected(selection,null),'all');
});
