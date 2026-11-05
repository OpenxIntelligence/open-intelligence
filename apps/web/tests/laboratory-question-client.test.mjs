import test from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {readLabPreparation,readLabQuestionList} from '../.test-dist/laboratory-question.js';
import {patient,caseId,projection} from './laboratory-projection-fixture.mjs';

const question='What does this source report about the specimen?', token='fictional_lab_preparation_token_00000000001';
const access='ACCESS-'+'D'.repeat(32);
const reply=(value,code=200)=>new Response(JSON.stringify(value),{status:code,headers:{'Content-Type':'application/json'}});
function prepared(w,o){
  return {contract:'oi.synthetic-laboratory-question-preflight/1',patient_id:patient,case_id:caseId,question,
    source_snapshot_contract:w.contract,source_snapshot_sha256:w.snapshot_fingerprint,synthetic:true,source_context_only:true,
    durable_question_created:false,durable_review_connected:false,biomedical_evidence_rights_verified:false,model_execution_authorized:false,
    clinical_approval:false,clinical_interpretation:'not_performed',terminology_validation:'not_performed',
    reassessment_policy:'revalidate_source_and_authority_before_any_future_write',access_receipt_id:access,preflight_sha256:'f'.repeat(64),
    selected_source:{anchor_kind:'fhir_observation',source_id:o.source_id,document_id:o.document_id,version:o.document_version,sha256:o.source_sha256,
      kind:'laboratory',resource_reference:o.observation_reference,specimen_reference:o.specimen_reference,specimen_type_text:o.specimen_type_text,
      specimen_collected_at:o.specimen_collected_at,report_reference:o.report_reference,loinc_code:o.loinc_code,effective_at:o.effective_at,
      issued_at:o.issued_at,status:o.status,value_text:o.value_text,unit_code:o.unit_code,absent_reason:o.absent_reason,
      source_reported:true,review_state:'not_established',clinical_review:'not_performed'}};
}
async function ready(onPost,onList,worldReply=projection){
  const binding={case_id:caseId,patient_id:patient,source_organization:'ORG-A',source_system:'SYS-A',source_subject_ref:'SUBJECT-A',review_ref:'REVIEW-A',status:'active',revision:1,created_at:'2026-11-02T10:00:00Z',revoked_at:null,source_identity_verified:false,clinical_sources_linked:false,clinical_conclusions:false};
  const session=new RegistrySession(async(url,init)=>{
    if(init.method==='POST')return onPost(url,JSON.parse(init.body));
    if(url.endsWith('/world-model'))return reply(worldReply());
    if(url.endsWith('/composer/laboratory-questions'))return onList(url,init);
    if(url.endsWith('/case-bindings'))return reply({patient_id:patient,mappings:[binding],synthetic:true,source_identity_verified:false,clinical_sources_linked:false});
    return reply({patient_id:patient,origin_org:'ORG-A',status:'active',revision:1,created_at:'2026-11-02T10:00:00Z'});
  });
  session.connect(token);await session.read(patient);await session.loadCases();await session.loadWorldModel(caseId);
  const world=session.snapshot().worldModel;assert.ok(world,session.snapshot().worldMessage);
  const item=world.laboratory_observations[0];
  return {session,world,item,send:(signal=new AbortController().signal)=>session.prepareLabQuestion(world,item.source_id,item.observation_reference,question,signal)};
}
test('submission sends only the selected source and local Observation; absent results require the exact original reason',async()=>{
  let count=0;
  const f=await ready((url,payload)=>{
    count++;assert.ok(url.endsWith('/composer/laboratory-preflight'));
    assert.deepEqual(payload,{synthetic:true,source_id:f.item.source_id,observation_reference:f.item.observation_reference,question,expected_source_snapshot_sha256:f.world.snapshot_fingerprint});
    return reply(prepared(f.world,f.item));
  });
  assert.equal(count,0);assert.equal((await f.send()).receipt,access);assert.equal(count,1);
  const absent=f.world.laboratory_observations.find(o=>o.value_text===null),p=prepared(f.world,absent);
  assert.equal(readLabPreparation(p,f.world,absent,question).receipt,access);
  for(const partial of [{absent_reason:'unknown'},{value_text:'0'},{specimen_reference:'Specimen/Other'},{resource_reference:f.item.observation_reference},{line:1}]){
    assert.throws(()=>readLabPreparation({...p,selected_source:{...p.selected_source,...partial}},f.world,absent,question));
  }
});
test('denied, changed-source and contradictory receipts withhold the preview and clear the current world',async()=>{
  for(const mode of ['deny','stale','claim','wrong patient','changed value']){
    const f=await ready(()=>{const p=prepared(f.world,f.item);
      if(mode==='claim')p.clinical_approval=true;
      if(mode==='wrong patient')p.patient_id='PAT-OTHER';
      if(mode==='changed value')p.selected_source.value_text='1';
      return reply(p,mode==='deny'?404:mode==='stale'?409:200);});
    assert.equal(await f.send(),null,mode);assert.equal(f.session.snapshot().worldModel,null,mode);
  }
});
test('late success or denial cannot cross a draft edit, disconnect, or fresh read of the same case',async()=>{
  for(const action of ['edit','disconnect','refresh'])for(const status of [200,404]){
    let release;const wait=new Promise(r=>{release=r;});
    const f=await ready(()=>wait);const control=new AbortController();const pending=f.send(control.signal);
    if(action==='edit')control.abort();else if(action==='disconnect')f.session.disconnect();else await f.session.loadWorldModel(caseId);
    const after=f.session.snapshot().worldModel;
    release(reply(prepared(f.world,f.item),status));assert.equal(await pending,null,action);
    assert.equal(f.session.snapshot().worldModel,after,action);
  }
});
test('world datetime and preflight string use equivalent UTC spellings without losing microseconds or date roles',()=>{
  const w=projection(), o={...w.laboratory_observations[0],effective_at:'2026-04-03T13:05:00.123456Z',
    specimen_collected_at:'2026-04-03T13:05:00.123455Z'}, p=prepared(w,o);
  for(const k of ['issued_at','effective_at','specimen_collected_at'])p.selected_source[k]=o[k].replace(/Z$/,'+00:00');
  assert.equal(readLabPreparation(p,w,o,question).receipt,access);
  for(const fields of [{issued_at:o.issued_at.replace(/Z$/,'-00:00')},{effective_at:p.selected_source.specimen_collected_at},
    {specimen_collected_at:p.selected_source.effective_at},{effective_at:o.effective_at.replace(/Z$/,'+01:00')}]){
    assert.throws(()=>readLabPreparation({...p,selected_source:{...p.selected_source,...fields}},w,o,question));
  }
});

const qid='QUESTION-'+'E'.repeat(32);
function savedRow(w=projection()){
 const item=w.laboratory_observations[0];return {question_id:qid,question,source_id:item.source_id,source_version:item.document_version,source_sha256:item.source_sha256,
  observation_reference:item.observation_reference,source_snapshot_sha256:w.snapshot_fingerprint,preflight_sha256:'f'.repeat(64),source_context_state:'current_unreviewed_question'};
}
const history=(rows=[savedRow()])=>({patient_id:patient,case_id:caseId,access_receipt_id:access,questions:rows});
test('only a verified preparation saves once; it binds exact Observation, question, snapshot and fingerprint',async()=>{
 const calls=[];const f=await ready((url,body)=>{calls.push([url,body]);return url.endsWith('/laboratory-preflight')?reply(prepared(f.world,f.item)):reply({question_id:qid,duplicate:false},201);});
 const p=await f.send();await f.session.saveLabQuestion(f.world,{...p});assert.equal(calls.length,1);
 await f.session.saveLabQuestion(f.world,p);await f.session.saveLabQuestion(f.world,p);
 assert.equal(calls.length,2);assert.ok(calls[1][0].endsWith('/composer/laboratory-questions'));
 const{request_key,...sent}=calls[1][1];assert.match(request_key,/^[\w-]{36}$/);
 assert.deepEqual(sent,{synthetic:true,source_id:f.item.source_id,observation_reference:f.item.observation_reference,question,expected_source_snapshot_sha256:f.world.snapshot_fingerprint,expected_preflight_sha256:p.fingerprint});
 assert.equal(f.session.snapshot().labQuestionSavedId,qid);assert.equal(f.session.snapshot().labQuestionWritePhase,'saved');
});
test('ambiguous write is never auto-repeated, and exact retry survives same-case World Model refresh',async()=>{
 const commands=[];const f=await ready((url,body)=>{if(url.endsWith('/laboratory-preflight'))return reply(prepared(f.world,f.item));commands.push(JSON.stringify(body));return commands.length===1?reply({},503):reply({question_id:qid,duplicate:true});});
 const p=await f.send();await f.session.saveLabQuestion(f.world,p);assert.equal(f.session.snapshot().labQuestionWritePhase,'unknown');
 await f.session.saveLabQuestion(f.world,p);await f.session.loadWorldModel(caseId);assert.equal(commands.length,1);assert.equal(f.session.snapshot().labQuestionWritePhase,'unknown');
 await f.session.retryLabQuestion(f.world);assert.equal(commands.length,1,'old model cannot issue a retry');
 await f.session.retryLabQuestion(f.session.snapshot().worldModel);assert.deepEqual(commands,[commands[0],commands[0]]);assert.equal(f.session.snapshot().labQuestionSavedId,qid);
});
test('invalid success is uncertain; definitive denial clears pending receipt, and stale results cannot restore it after disconnect',async()=>{
 let n=0;const f=await ready((url)=>{if(url.endsWith('/laboratory-preflight'))return reply(prepared(f.world,f.item));return ++n===1?reply({question_id:qid,duplicate:true},201):reply({},404);});
 await f.session.saveLabQuestion(f.world,await f.send());assert.equal(f.session.snapshot().labQuestionWritePhase,'unknown');
 await f.session.retryLabQuestion(f.world);assert.equal(f.session.snapshot().labQuestionWritePhase,'error');assert.equal(f.session.snapshot().labQuestionSavedId,null);
 await f.session.retryLabQuestion(f.world);assert.equal(n,2);
 let release;const hold=new Promise(r=>release=r),g=await ready(url=>url.endsWith('/laboratory-preflight')?reply(prepared(g.world,g.item)):hold);
 const save=g.session.saveLabQuestion(g.world,await g.send());g.session.disconnect();release(reply({question_id:qid,duplicate:false},201));await save;
 assert.equal(g.session.snapshot().labQuestionSavedId,null);assert.equal(g.session.snapshot().labQuestionWritePhase,'idle');
});
test('explicit history reopen uses a fresh scoped GET and clears previously displayed data on denial',async()=>{
 let reads=0;const f=await ready(()=>assert.fail('reading must not POST'),(url,init)=>{assert.equal(url,`/v1/patients/${patient}/cases/${caseId}/composer/laboratory-questions`);assert.equal(init.method,'GET');return ++reads===1?reply(history()):reply({},404);});
 assert.equal(reads,0);await f.session.loadLabQuestions(f.world);assert.equal(f.session.snapshot().labQuestionHistory.questions[0].question_id,qid);
 await f.session.loadLabQuestions(f.world);assert.equal(reads,2);assert.equal(f.session.snapshot().labQuestionHistory,null);
});
test('reopening historical question retains its original anchor without inventing current result or line',()=>{
 const w=projection(),row=savedRow(w),old=w.current_sources[0];
 assert.throws(()=>readLabQuestionList(history([{...row,source_snapshot_sha256:'1'.repeat(64)}]),w));
 w.history=[{...old,state:'superseded'}];w.current_sources=[];w.laboratory_observations=[];
 const past={...row,source_context_state:'source_reassessment_required'};
 assert.equal(readLabQuestionList(history([past]),w).questions[0].observation_reference,row.observation_reference);
 for(const raw of [history([row]),history([{...past,source_sha256:'1'.repeat(64)}]),history([{...past,source_line:1}]),history([past,past]),{...history([past]),patient_id:'PAT-WRONG'},{...history([past]),case_id:'CASE-FORGERY'}])assert.throws(()=>readLabQuestionList(raw,w));
});
test('late list success cannot reappear after an authorized same-case refresh',async()=>{
 let release;const hold=new Promise(r=>release=r);const f=await ready(()=>assert.fail(),()=>hold);
 const read=f.session.loadLabQuestions(f.world);await f.session.loadWorldModel(caseId);release(reply(history()));await read;assert.equal(f.session.snapshot().labQuestionHistory,null);
});

 test('failed independent history read clears the save receipt and invalidates previously prepared new writes',async()=>{
 let writes=0;const f=await ready(url=>{if(url.endsWith('/laboratory-preflight'))return reply(prepared(f.world,f.item));writes++;return reply({question_id:qid,duplicate:false},201);},()=>reply({},404));
 await f.session.saveLabQuestion(f.world,await f.send());assert.equal(f.session.snapshot().labQuestionSavedId,qid);
 const later=await f.send();await f.session.loadLabQuestions(f.world);assert.equal(f.session.snapshot().labQuestionSavedId,null);
 await f.session.saveLabQuestion(f.world,later);assert.equal(writes,1);
});
