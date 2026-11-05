import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {parseSourceWorldModel} from '../.test-dist/source-world-model.js';
import {readLabPreparation,readLabQuestionList} from '../.test-dist/laboratory-question.js';
import {patient,caseId,projection,codedProjection,fictionalCoding} from './laboratory-projection-fixture.mjs';

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
      ...(o.status==='reported_coded'?{coded_result:{...o.coded_result}}:{}),
      source_reported:true,review_state:'not_established',clinical_review:'not_performed'}};
}
async function ready(onPost,onList,worldReply=projection,onPatientRead=()=>null){
  const binding={case_id:caseId,patient_id:patient,source_organization:'ORG-A',source_system:'SYS-A',source_subject_ref:'SUBJECT-A',review_ref:'REVIEW-A',status:'active',revision:1,created_at:'2026-11-02T10:00:00Z',revoked_at:null,source_identity_verified:false,clinical_sources_linked:false,clinical_conclusions:false};
  const session=new RegistrySession(async(url,init)=>{
    if(init.method==='POST')return onPost(url,JSON.parse(init.body));
    if(url.endsWith('/world-model'))return reply(worldReply());
    if(url.endsWith('/composer/laboratory-questions'))return onList(url,init);
    if(url.endsWith('/case-bindings'))return reply({patient_id:patient,mappings:[binding],synthetic:true,source_identity_verified:false,clinical_sources_linked:false});
    return onPatientRead(url)??reply({patient_id:patient,origin_org:'ORG-A',status:'active',revision:1,created_at:'2026-11-02T10:00:00Z'});
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


test('same-patient access recheck preserves the exact lab save, including an in-flight or temporarily unreachable response',async()=>{
 for(const mode of ['lost','in flight','transient patient failure']){
  let release, status=200;
  const writes=[];
  const f=await ready((url,body)=>{
   if(url.endsWith('/laboratory-preflight'))return reply(prepared(f.world,f.item));
   writes.push(JSON.stringify(body));
   if(writes.length===1)return mode==='in flight'?new Promise(resolve=>{release=resolve;}):reply({},503);
   return reply({question_id:qid,duplicate:true},200);
  },undefined,projection,()=>status===200?null:reply({},status));
  const outstanding=f.session.saveLabQuestion(f.world,await f.send());
  if(mode!=='in flight')await outstanding;
  assert.equal(f.session.snapshot().labQuestionWritePhase,mode==='in flight'?'saving':'unknown');
  if(mode==='transient patient failure')status=503;
  await f.session.read(patient);
  assert.equal(f.session.snapshot().labQuestionWritePhase,'unknown',mode);
  assert.equal(f.session.snapshot().worldModel,null);
  await f.session.retryLabQuestion(f.world);assert.equal(writes.length,1);
  if(status===503){status=200;await f.session.read(patient);}
  await f.session.loadCases();await f.session.loadWorldModel(caseId);
  await f.session.retryLabQuestion(f.session.snapshot().worldModel);
  assert.deepEqual(writes,[writes[0],writes[0]],mode);
  assert.equal(f.session.snapshot().labQuestionSavedId,qid);
  if(release){release(reply({},404));await outstanding;assert.equal(f.session.snapshot().labQuestionSavedId,qid);}
 }
});

test('a denied patient recheck or a switch to a different patient clears the uncertain lab save',async()=>{
 for(const reason of [401,403,404,'different patient']){
  let deny=false;const writes=[];
  const f=await ready((url,body)=>{
   if(url.endsWith('/laboratory-preflight'))return reply(prepared(f.world,f.item));
   writes.push(body);return reply({},503);
  },undefined,projection,url=>{
   if(url.endsWith('/PAT-OTHER'))return reply({patient_id:'PAT-OTHER',origin_org:'ORG-A',status:'active',revision:1,created_at:'2026-11-02T10:00:00Z'});
   return deny?reply({},reason):null;
  });
  await f.session.saveLabQuestion(f.world,await f.send());
  assert.equal(f.session.snapshot().labQuestionWritePhase,'unknown');
  deny=true;await f.session.read(reason==='different patient'?'PAT-OTHER':patient);
  assert.equal(f.session.snapshot().labQuestionWritePhase,'idle');
  if(reason==='different patient')assert.equal(f.session.snapshot().patient.patient_id,'PAT-OTHER');
  deny=false;if(!f.session.snapshot().connected)f.session.connect(token);
  await f.session.read(patient);await f.session.loadCases();await f.session.loadWorldModel(caseId);
  await f.session.retryLabQuestion(f.session.snapshot().worldModel);
  assert.equal(writes.length,1);
 }
});

test('text question conflict in the same case retains the uncertain laboratory command for exact recovery',async()=>{
 const world=projection(),source={...world.current_sources[0],kind:'pathology',source_id:'SRC-'+'F'.repeat(32),document_id:'FICT-PATH'};
 world.current_sources.push(source);
 const text={source_id:source.source_id,document_id:source.document_id,document_version:source.version,source_sha256:source.sha256,
   source_kind:source.kind,finding_key:'marker',reported_state:'reported',source_statement:'Independently fictional text.',
   source_line:8,specimen_id:source.specimen_id,event_date:source.event_date,issued_at:source.issued_at,
   review_state:'not_established',clinical_meaning:null};
 world.observations=[text];world.summary.current_sources++;world.summary.current_observations++;
 const textReceipt={contract:'oi.synthetic-source-composer-preflight/2',source_snapshot_contract:world.contract,access_receipt_id:access,
   patient_id:patient,case_id:caseId,question,source_snapshot_sha256:world.snapshot_fingerprint,
   selected_source:{source_id:source.source_id,document_id:source.document_id,version:source.version,sha256:source.sha256,
     kind:source.kind,line:text.source_line,finding_key:text.finding_key,reported_state:text.reported_state,statement:text.source_statement,
     event_date:source.event_date,issued_at:source.issued_at,specimen_id:source.specimen_id},
   source_context_only:true,biomedical_evidence_rights_verified:false,model_execution_authorized:false,durable_question_created:false,
   durable_review_connected:false,clinical_approval:false,clinical_interpretation:'not_performed',
   reassessment_policy:'revalidate_source_and_authority_before_any_future_write',limitations:'Independently authored fictional text.',preflight_sha256:'c'.repeat(64)};
 const labWrites=[];
 const f=await ready((url,body)=>{
   if(url.endsWith('/laboratory-preflight'))return reply(prepared(world,world.laboratory_observations[0]));
   if(url.endsWith('/source-preflight'))return reply(textReceipt);
   if(url.endsWith('/questions'))return reply({},409);
   assert.ok(url.endsWith('/composer/laboratory-questions'));labWrites.push(JSON.stringify(body));
   return labWrites.length===1?reply({},503):reply({question_id:qid,duplicate:true});
 },undefined,()=>world);
 await f.session.saveLabQuestion(f.world,await f.send());
 assert.equal(f.session.snapshot().labQuestionWritePhase,'unknown');
 await f.session.prepareSourceContext(source.source_id,text.source_line,question);
 assert.equal(f.session.snapshot().composerPhase,'ready');
 await f.session.savePreparedQuestion();
 assert.equal(f.session.snapshot().worldModel,null);
 assert.equal(f.session.snapshot().labQuestionWritePhase,'unknown');
 await f.session.loadWorldModel(caseId);await f.session.retryLabQuestion(f.session.snapshot().worldModel);
 assert.deepEqual(labWrites,[labWrites[0],labWrites[0]]);assert.equal(f.session.snapshot().labQuestionSavedId,qid);
});

test('denied laboratory preparation, save or history clears patient, sources, World Model and drafts until access is rechecked',async()=>{
 for(const operation of ['prepare','save','history'])for(const status of [403,404]){
  let deny=false;let writes=0;
  const captured=projection(), lab=captured.current_sources[0];
  const originalText=`OI-SYNTHETIC-REPORT/1\nPatient: ${caseId}\nDocument: PREVIOUS-FICTIONAL-REPORT\nType: clinical\nEvent-Date: 2026-04-03\nIssued-At: 2026-04-04\n`;
  const earlier={...lab,kind:'clinical',document_id:'PREVIOUS-FICTIONAL-REPORT',source_id:'SRC-'+'9'.repeat(32),sha256:createHash('sha256').update(originalText).digest('hex')};
  captured.current_sources.push(earlier);captured.summary.current_sources++;
  const index={contract:'oi.synthetic-original-sources/1',patient_id:patient,case_id:caseId,access_receipt_id:access,sources:captured.current_sources,source_reported_assertions:[],synthetic:true,clinical_interpretation:false,research_review_invalidation_integrated:false};
  const original={case_id:caseId,source_id:earlier.source_id,document_id:earlier.document_id,version:1,state:'current',sha256:earlier.sha256,synthetic:true,clinical_review_state:'not_established',original_text:originalText,access_receipt_id:access};
  const f=await ready((url)=>{
   if(url.endsWith('/laboratory-preflight'))return deny&&operation==='prepare'?new Response('Unavailable',{status}):reply(prepared(f.world,f.item));
   writes++;return reply({},status);
  },()=>deny?new Response('Unavailable',{status}):reply(history()),()=>captured,url=>{
   if(url.endsWith('/sources'))return reply(index);
   if(url.endsWith('/'+earlier.source_id))return reply(original);
   return null;
  });
  await f.session.loadSources(caseId);await f.session.loadOriginal(earlier.source_id);await f.session.loadWorldModel(caseId);
  assert.equal(f.session.snapshot().original.original_text,originalText);assert.equal(f.session.snapshot().sourceIndex.sources.length,2);
  const world=f.session.snapshot().worldModel;
  const draft=await f.session.prepareLabQuestion(world,f.item.source_id,f.item.observation_reference,question,new AbortController().signal);
  await f.session.loadLabQuestions(world);
  assert.equal(f.session.snapshot().labQuestionHistory.questions[0].question_id,qid);
  assert.ok(f.session.snapshot().cases.length);assert.ok(f.session.snapshot().worldModel);
  deny=true;
  if(operation==='prepare')await f.session.prepareLabQuestion(world,f.item.source_id,f.item.observation_reference,question,new AbortController().signal);
  if(operation==='history')await f.session.loadLabQuestions(world);
  if(operation==='save')await f.session.saveLabQuestion(world,draft);
  const cleared=f.session.snapshot();assert.equal(cleared.connected,true);assert.equal(cleared.patient,null);
  for(const field of ['cases','sourceIndex','original','worldModel','labQuestionHistory','labQuestionSavedId','questions','reviewQueue'])assert.equal(cleared[field],null,field);
  assert.equal(cleared.worldPhase,'error');
  if(operation==='save')assert.equal(cleared.labQuestionWritePhase,'error');
  if(operation==='history')assert.equal(cleared.labQuestionListPhase,'error');
  const count=writes;await f.session.retryLabQuestion(f.world);await f.session.saveLabQuestion(f.world,draft);assert.equal(writes,count);
  deny=false;await f.session.read(patient);await f.session.loadCases();await f.session.loadWorldModel(caseId);
  await f.session.retryLabQuestion(f.session.snapshot().worldModel);assert.equal(writes,count);
  await f.session.loadLabQuestions(f.session.snapshot().worldModel);assert.equal(f.session.snapshot().labQuestionHistory.questions.length,1);
 }
});

const record={citation:'FICT-LAB-CATALOG@1',id:'FICT-LAB-CATALOG',version:'1',source_kind:'fictional',
 title:'Fictional laboratory record metadata',licence:'Original synthetic fixture',link:'https://example.invalid/fictional/catalog/1',
 metadata_sha256:'e'.repeat(64),availability:'metadata_only',rights_status:'granted'};
const link={link_id:'EVIDENCE-LINK-'+'9'.repeat(32),citation:record.citation,metadata_sha256:record.metadata_sha256,
 actor_label:'ACTOR-FICTIONAL',created_at:'2026-11-03T10:00:00Z',status:'available',record};
const qBase='/v1/patients/'+patient+'/cases/'+caseId+'/composer/laboratory-questions/'+qid;
const labRow=savedRow(),{question_id:_id,question:_q,source_context_state:_state,...anchor}=labRow;
const catalogScope={patient_id:patient,case_id:caseId,question_id:qid,source_context_state:'current_unreviewed_question',
 source_access_receipt_id:access,synthetic:true,model_executed:false,content_appraised:false,clinical_approval:false,question_anchor:anchor};
const hits=()=>({...catalogScope,contract:'oi.pg-question-evidence-search/1',query:'catalog',records:[record]});
const links=(rows=[],state=catalogScope.source_context_state)=>({...catalogScope,contract:'oi.pg-question-evidence-links/1',source_context_state:state,links:rows});
const receipt=(duplicate=false)=>({link_id:link.link_id,citation:link.citation,metadata_sha256:link.metadata_sha256,duplicate});
async function catalogSession(respond,rows=()=>[labRow]){
 const f=await ready((url,body)=>respond(url,'POST',body),()=>reply(history(rows())),projection,
   url=>url.startsWith(qBase+'/')?respond(url,'GET'):null);
 await f.session.loadLabQuestions(f.world);return f.session;
}
test('lab catalog search requires the Observation anchor; it never sends the question text or a lab value',async()=>{
 let actual=hits();const calls=[];const s=await catalogSession((url,method,body)=>{calls.push({url,method,body});return reply(actual);});
 await s.searchQuestionEvidence(qid,'catalog','laboratory');assert.equal(s.snapshot().evidenceSearch.records[0].title,record.title);
 assert.deepEqual(calls,[{url:qBase+'/evidence-search',method:'POST',body:{synthetic:true,query:'catalog'}}]);
 for(const invalid of [undefined,{...anchor,source_id:'SRC-'+'C'.repeat(32)},{...anchor,source_version:2},
   {...anchor,observation_reference:'Observation/Other'},{...anchor,source_sha256:'1'.repeat(64)},
   {...anchor,source_snapshot_sha256:'1'.repeat(64)},{...anchor,preflight_sha256:'1'.repeat(64)},{...anchor,source_line:12}]){
   actual={...hits(),question_anchor:invalid};await s.searchQuestionEvidence(qid,'catalog','laboratory');
   assert.equal(s.snapshot().evidenceSearch,null);assert.equal(s.snapshot().evidenceSearchPhase,'error');
   await s.saveQuestionEvidence(qid,record.citation,'laboratory');assert.ok(calls.every(call=>call.url.endsWith('/evidence-search')));
 }
});
test('lab citation uncertain write reopens the exact question on same-patient recheck, and can recover its receipt after amendment',async()=>{
 const writes=[];let historical=false;
 const s=await catalogSession((url,method,body)=>{
   if(url.endsWith('/evidence-search'))return reply(hits());assert.equal(url,qBase+'/evidence-links');
   if(method==='GET')return reply(links([link],historical?'source_reassessment_required':'current_unreviewed_question'));
   writes.push(body);return writes.length===1?reply({},503):reply(receipt(true));
 },()=>[{...labRow,source_context_state:historical?'source_reassessment_required':'current_unreviewed_question'}]);
 await s.searchQuestionEvidence(qid,'catalog','laboratory');await s.saveQuestionEvidence(qid,record.citation,'laboratory');
 assert.equal(s.snapshot().evidenceLinkPhase,'unknown');
 const {request_key,...body}=writes[0];assert.match(request_key,/^[\w-]{36}$/);
 assert.deepEqual(body,{synthetic:true,citation:record.citation,expected_metadata_sha256:record.metadata_sha256,
   source_snapshot_contract:'oi.pg-source-world-model/1',expected_source_snapshot_sha256:labRow.source_snapshot_sha256,expected_preflight_sha256:labRow.preflight_sha256});
 historical=true;await s.read(patient);await s.loadCases();await s.loadWorldModel(caseId);
 await s.retryQuestionEvidenceLink();assert.equal(writes.length,1,'must reopen exact historical anchor first');
 await s.loadLabQuestions(s.snapshot().worldModel);await s.retryQuestionEvidenceLink();
 assert.deepEqual(writes,[writes[0],writes[0]]);assert.equal(s.snapshot().evidenceLinkReceipt.link_id,link.link_id);
 assert.equal(s.snapshot().evidenceLinkReceipt.duplicate,true);assert.equal(s.snapshot().evidenceLinks.source_context_state,'source_reassessment_required');
});
test('lab history alone is available after reassessment; wrong anchors and restricted metadata disclosures are refused',async()=>{
 let read=links([{...link,status:'rights_restricted',record:null}],'source_reassessment_required');let sent=0;
 const s=await catalogSession((url,method)=>{sent++;assert.equal(url,qBase+'/evidence-links');assert.equal(method,'GET');return reply(read);},()=>[{...labRow,source_context_state:'source_reassessment_required'}]);
 await s.searchQuestionEvidence(qid,'catalog','laboratory');await s.saveQuestionEvidence(qid,record.citation,'laboratory');assert.equal(sent,0);
 await s.loadQuestionEvidenceLinks(qid,'laboratory');assert.equal(s.snapshot().evidenceLinks.links[0].record,null);
 for(const corrupt of [{question_anchor:{...anchor,observation_reference:'Observation/Another'}},{source_context_state:'current_unreviewed_question'},{links:[{...link,status:'rights_restricted'}]}]){
   read={...links([],'source_reassessment_required'),...corrupt};await s.loadQuestionEvidenceLinks(qid,'laboratory');assert.equal(s.snapshot().evidenceLinks,null);
 }
});
test('denied laboratory catalog actions clear the full patient scope and all citation metadata and retry material',async()=>{
 for(const status of [403,404])for(const op of ['read','search','save']){
   let deny=false;const s=await catalogSession((url,method)=>deny?reply({},status):reply(url.endsWith('/evidence-search')?hits():links([])));
   await s.searchQuestionEvidence(qid,'catalog','laboratory');assert.equal(s.snapshot().evidenceSearch.records.length,1);deny=true;
   if(op==='read')await s.loadQuestionEvidenceLinks(qid,'laboratory');
   if(op==='search')await s.searchQuestionEvidence(qid,'catalog','laboratory');
   if(op==='save')await s.saveQuestionEvidence(qid,record.citation,'laboratory');
   const st=s.snapshot();for(const key of ['patient','cases','worldModel','labQuestionHistory','evidenceSearch','evidenceLinks','evidenceLinkIntent','evidenceLinkReceipt'])assert.equal(st[key],null,op+' '+key);
 }
});
test('an older laboratory catalog result cannot restore a title after rights-checked history or a fresh question list',async()=>{
 for(const action of ['rights refresh','new list']){
   let release;const held=new Promise(r=>release=r);
   const s=await catalogSession(url=>url.endsWith('/evidence-search')?held:reply(links([{...link,status:'rights_restricted',record:null}])));
   const search=s.searchQuestionEvidence(qid,'catalog','laboratory');
   if(action==='rights refresh')await s.loadQuestionEvidenceLinks(qid,'laboratory');else await s.loadLabQuestions(s.snapshot().worldModel);
   release(reply(hits()));await search;assert.equal(s.snapshot().evidenceSearch,null);
   if(action==='rights refresh')assert.equal(s.snapshot().evidenceLinks.links[0].record,null);
 }
});
test('an authenticated laboratory question history retains its source case and read snapshot for the overview',()=>{
 const w=projection(),raw=history(),parsed=readLabQuestionList(raw,w);
 assert.equal(parsed.patient_id,patient);
 assert.equal(parsed.case_id,caseId);
 assert.equal(parsed.checked_source_snapshot_sha256,w.snapshot_fingerprint);
});

test('coded question preflight binds the whole source tuple; edits, substitutions and legacy field injection fail closed',async()=>{
 const {system,code,display,version}=fictionalCoding;
 const getWorld=()=>codedProjection();
 const session=await ready(()=>reply(prepared(session.world,session.item)),undefined,getWorld);
 assert.equal((await session.send()).receipt,access);
 const p=prepared(session.world,session.item);
 const reordered={display,code,system,version};
 const changed=fields=>({...p,selected_source:{...p.selected_source,...fields}});
 assert.equal(readLabPreparation(changed({coded_result:reordered}),session.world,session.item,question).receipt,access);
 for(const fields of [{coded_result:{system,code}},{coded_result:{...reordered,version:'v2'}},
   {coded_result:{...reordered,code:'different'}},{coded_result:{...reordered,system:'http://loinc.org'}},
   {coded_result:{...reordered,display:display.toUpperCase()}},{coded_result:{...reordered,text:display}},
   {coded_result:null},{value_text:'0'},{absent_reason:'unknown'},{unit_code:'1'}]){
   assert.throws(()=>readLabPreparation(changed(fields),session.world,session.item,question));
 }
 for(const o of projection().laboratory_observations){
   const v=prepared(session.world,o);v.selected_source.coded_result=null;
   assert.throws(()=>readLabPreparation(v,session.world,o,question));
 }
 const bad=await ready(()=>reply(changed({coded_result:{...reordered,code:'REPLACEMENT'}})),undefined,getWorld);
 assert.equal(await bad.send(),null);assert.equal(bad.session.snapshot().worldModel,null);
});

test('Journey and preflight preserve legacy quantity strings, UTF-16 bounds and source locators',async()=>{
 for(const [value_text,unit_code] of [['0','mg\u00ad/L'],[' 4.20 ',' 1 '],['-0.0','x\u2028y'],['x'.repeat(64),'🧪'.repeat(16)]]){
   const wire=projection(),o=wire.laboratory_observations[0];
   Object.assign(o,{value_text,unit_code});
   const f=await ready(()=>reply(prepared(f.world,f.item)),undefined,()=>wire);
   assert.equal(f.item.value_text,value_text);assert.equal(f.item.unit_code,unit_code);
   assert.equal((await f.send()).receipt,access);
   const changed=prepared(f.world,f.item);changed.selected_source.unit_code=unit_code+'X';
   assert.throws(()=>readLabPreparation(changed,f.world,f.item,question));
 }
 const raw=projection(),o=raw.laboratory_observations[0];
 const entry=raw.laboratory_timeline.find(t=>t.observation_reference===o.observation_reference);
 Object.assign(o,{observation_reference:'Observation/legacy_reference',report_reference:'Legacy report locator',specimen_reference:'Legacy specimen locator'});
 Object.assign(entry,{observation_reference:o.observation_reference,specimen_reference:o.specimen_reference});
 const f=await ready(()=>reply(prepared(f.world,f.item)),undefined,()=>raw);
 assert.equal((await f.send()).receipt,access);
 const invalid=projection();
 for(const fields of [{unit_code:'🧪'.repeat(17)}, {unit_code:''},{value_text:'x'.repeat(65)},{value_text:''}]){
   const bad=structuredClone(invalid);Object.assign(bad.laboratory_observations[0],fields);
   assert.throws(()=>parseSourceWorldModel(bad,patient,caseId));
 }
});
