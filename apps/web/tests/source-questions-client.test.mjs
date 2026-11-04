import {test} from 'node:test';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {decodeComposerPreflight} from '../.test-dist/composer-preflight-view.js';
import {decodeSavedQuestion,decodeSourceQuestions} from '../.test-dist/source-questions-view.js';
const token='fictional_test_credential_000000000001';
const receiptPatient='PAT-EXAMPLE-001',receiptCase='CASE-ALPHA',receiptSource='SRC-'+'A'.repeat(32);
const sha256='d'.repeat(64);
const response=(value,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
const deferred=()=>{let resolve;return{promise:new Promise(r=>resolve=r),resolve:x=>resolve(x)};};
const patient=(id=receiptPatient)=>({patient_id:id,origin_org:'FICT-ORG',status:'active',revision:1,created_at:'2026-11-02T10:00:00Z'});
const caseList=()=>({patient_id:receiptPatient,synthetic:true,source_identity_verified:false,clinical_sources_linked:false,mappings:[
 {case_id:receiptCase,patient_id:receiptPatient,source_organization:'FICT-ORG',source_system:'FICT-TEXT',
 source_subject_ref:'FICT-SUBJECT',review_ref:'FICT-REVIEW',status:'active',revision:1,
 created_at:'2026-11-02T10:00:00Z',revoked_at:null,source_identity_verified:false,clinical_sources_linked:false,clinical_conclusions:false},
 {case_id:'CASE-BETA',patient_id:receiptPatient,source_organization:'FICT-ORG',source_system:'FICT-TEXT',
 source_subject_ref:'FICT-OTHER',review_ref:'FICT-OTHER',status:'active',revision:1,
 created_at:'2026-11-02T10:00:00Z',revoked_at:null,source_identity_verified:false,clinical_sources_linked:false,clinical_conclusions:false},
]});
const worldFixture=()=>({
 contract:'oi.pg-source-world-model/1',patient_id:receiptPatient,case_id:receiptCase,access_receipt_id:'ACCESS-'+'A'.repeat(32),
 synthetic:true,authority:'source_report_only_unreviewed',clinical_interpretation:false,
 research_review_invalidation_integrated:false,composer_execution_authorized:false,
 snapshot_fingerprint:'a'.repeat(64),as_of_received_at:'2026-11-02T10:00:00Z',
 summary:{current_sources:1,historical_sources:0,current_observations:1,unresolved_observations:1,source_disagreements:0},
 current_sources:[{source_id:receiptSource,document_id:'DOC-ONE',version:1,sha256,kind:'pathology',
 event_date:'2026-01-10',issued_at:'2026-01-11',received_at:'2026-11-02T10:00:00Z',specimen_id:'SPECIMEN-ONE',state:'current',supersedes_id:null}],
 history:[],observations:[{source_id:receiptSource,document_id:'DOC-ONE',document_version:1,source_sha256:sha256,
 source_kind:'pathology',finding_key:'marker',reported_state:'not-reported',source_statement:'Independently fictional example.',
 source_line:8,specimen_id:'SPECIMEN-ONE',event_date:'2026-01-10',issued_at:'2026-01-11',review_state:'not_established',clinical_meaning:null}],
 unresolved_refs:[{source_id:receiptSource,source_line:8}],conflicts:[],limitations:['Independently fictional source context only.'],
});
const newSession=transport=>new RegistrySession((url,init)=>url.endsWith('/case-bindings')?response(caseList()):transport(url,init));

// A deterministic standard question exercises context verification only;
// it is not a stored patient question, clinical decision or AI prompt run.
const composerQuestion='What source provenance and reported uncertainty require independent verification?';
const composerFixture=()=>({
 contract:'oi.synthetic-source-composer-preflight/2',
 source_snapshot_contract:'oi.pg-source-world-model/1',access_receipt_id:'ACCESS-'+'B'.repeat(32),
 patient_id:receiptPatient,case_id:receiptCase,question:composerQuestion,
 source_snapshot_sha256:'a'.repeat(64),
 selected_source:{
  source_id:receiptSource,document_id:'DOC-ONE',version:1,sha256,line:8,
  finding_key:'marker',reported_state:'not-reported',
  statement:'Independently fictional example.',kind:'pathology',
  event_date:'2026-01-10',issued_at:'2026-01-11',specimen_id:'SPECIMEN-ONE'
 },
 source_context_only:true,biomedical_evidence_rights_verified:false,
 model_execution_authorized:false,durable_question_created:false,
 durable_review_connected:false,clinical_approval:false,
 clinical_interpretation:'not_performed',
 reassessment_policy:'revalidate_source_and_authority_before_any_future_write',
 limitations:'Fictional source text only. No model, clinician review, real consent or medical conclusion.',
 preflight_sha256:'b'.repeat(64),
});
const sourcePreflightPath='/v1/patients/'+receiptPatient+'/cases/'+receiptCase+
 '/composer/source-preflight';
test('Composer source preflight is a read-only bounded POST with independent grant semantics',async()=>{
 const requests=[];
 const s=newSession(async(url,opts)=>{
  requests.push([url,opts]);
  if(url===sourcePreflightPath)return response(composerFixture());
  if(url.endsWith('/world-model'))return response(worldFixture());
  return response(patient());
 });
 s.connect(token);
 await s.read(receiptPatient);await s.loadCases();await s.loadWorldModel(receiptCase);
 assert.equal(s.snapshot().composerPreview,null);
 await s.prepareSourceContext(receiptSource,8,composerQuestion);
 assert.equal(s.snapshot().composerPhase,'ready');
 assert.equal(s.snapshot().composerPreview?.selected_source.source_id,receiptSource);
 assert.equal(s.snapshot().composerPreview?.model_execution_authorized,false);
 assert.equal(s.snapshot().composerPreview?.durable_review_connected,false);
 assert.equal(s.snapshot().composerPreview?.durable_question_created,false);
 assert.equal(s.snapshot().composerPreview?.clinical_approval,false);
 assert.equal(requests.length,3);
 assert.equal(requests[2][0],sourcePreflightPath);
 assert.equal(requests[2][1].method,'POST');
 assert.equal(requests[2][1].credentials,'omit');
 assert.equal(requests[2][1].redirect,'error');
 assert.equal(requests[2][1].cache,'no-store');
 assert.deepEqual(JSON.parse(requests[2][1].body),{
  synthetic:true,expected_source_snapshot_sha256:'a'.repeat(64),
  source_id:receiptSource,source_line:8,question:composerQuestion
 });
});
test('Composer preflight cannot be started without selected current source observation',async()=>{
 let calls=0;
 const s=newSession(async(url)=>{
  calls++;return response(url.endsWith('/world-model')?worldFixture():patient());
 });
 s.connect(token);await s.prepareSourceContext(receiptSource,8);
 assert.equal(calls,0);
 await s.read(receiptPatient);await s.loadCases();await s.prepareSourceContext(receiptSource,8);
 assert.equal(calls,1);
 await s.loadWorldModel(receiptCase);
 await s.prepareSourceContext(receiptSource,9);
 assert.equal(calls,2);assert.equal(s.snapshot().composerPreview,null);
});
test('Composer preflight permission denial clears previously read World Model context',async()=>{
 let reject=false;
 const s=newSession(async(url)=>{
  if(url===sourcePreflightPath)return reject?response({detail:'private'},404):response(composerFixture());
  return response(url.endsWith('/world-model')?worldFixture():patient());
 });
 s.connect(token);await s.read(receiptPatient);await s.loadCases();await s.loadWorldModel(receiptCase);
 await s.prepareSourceContext(receiptSource,8);
 assert.ok(s.snapshot().composerPreview);
 reject=true;await s.prepareSourceContext(receiptSource,8);
 assert.equal(s.snapshot().composerPreview,null);
 assert.equal(s.snapshot().worldModel,null);
 assert.equal(s.snapshot().composerPhase,'error');
 assert.ok(!JSON.stringify(s.snapshot()).includes('private'));
});
test('stale source snapshot demands refresh and cannot be used for an old preflight',async()=>{
 let stale=false;
 const s=newSession(async(url)=>{
  if(url===sourcePreflightPath)return stale?response({detail:'stale source'},409):response(composerFixture());
  return response(url.endsWith('/world-model')?worldFixture():patient());
 });
 s.connect(token);await s.read(receiptPatient);await s.loadCases();await s.loadWorldModel(receiptCase);
 await s.prepareSourceContext(receiptSource,8);assert.ok(s.snapshot().composerPreview);
 stale=true;await s.prepareSourceContext(receiptSource,8);
 assert.equal(s.snapshot().worldModel,null);
 assert.equal(s.snapshot().composerPreview,null);
 assert.ok(s.snapshot().composerMessage.includes('Refresh Investigations'));
});
test('forged Composer authority, source line, patient or source statement is rejected',async()=>{
 const wrong=[
  {...composerFixture(),model_execution_authorized:true},
  {...composerFixture(),clinical_approval:true},
  {...composerFixture(),durable_review_connected:true},
  {...composerFixture(),selected_source:{...composerFixture().selected_source,line:9}},
  {...composerFixture(),selected_source:{...composerFixture().selected_source,statement:'fabricated'}},
  {...composerFixture(),patient_id:'PAT-OTHER-001'},
  {...composerFixture(),source_snapshot_sha256:'0'.repeat(64)},
 ];
 for(const forged of wrong){
  const s=newSession(async(url)=>
   response(url===sourcePreflightPath?forged:url.endsWith('/world-model')?worldFixture():patient()));
  s.connect(token);await s.read(receiptPatient);await s.loadCases();await s.loadWorldModel(receiptCase);
  await s.prepareSourceContext(receiptSource,8);
  assert.equal(s.snapshot().composerPreview,null);
  assert.equal(s.snapshot().composerPhase,'error');
 }
});
test('source refresh, patient switch and disconnect invalidate pending Composer preflight',async()=>{
 const delayed=deferred();
 const s=newSession(async(url)=>{
  if(url===sourcePreflightPath)return delayed.promise;
  if(url.endsWith('/world-model'))return response(worldFixture());
  return response(patient(url.endsWith('PAT-EXAMPLE-002')?'PAT-EXAMPLE-002':receiptPatient));
 });
 s.connect(token);await s.read(receiptPatient);await s.loadCases();await s.loadWorldModel(receiptCase);
 const pending=s.prepareSourceContext(receiptSource,8);
 await s.read('PAT-EXAMPLE-002');
 delayed.resolve(response(composerFixture()));await pending;
 assert.equal(s.snapshot().composerPreview,null);
 assert.equal(s.snapshot().worldModel,null);
 const t=newSession(async(url)=>
  response(url===sourcePreflightPath?composerFixture():url.endsWith('/world-model')?worldFixture():patient()));
 t.connect(token);await t.read(receiptPatient);await t.loadCases();await t.loadWorldModel(receiptCase);
 await t.prepareSourceContext(receiptSource,8);
 assert.ok(t.snapshot().composerPreview);
 await t.loadWorldModel(receiptCase);
 assert.equal(t.snapshot().composerPreview,null);
 t.disconnect();assert.equal(t.snapshot().composerPreview,null);
});


const savedQuestionId='QUESTION-'+'A'.repeat(32);
const sourceQuestion=(
 state='current_unreviewed_question',overrides={}
)=>({
 question_id:savedQuestionId,patient_id:receiptPatient,case_id:receiptCase,
 question:composerQuestion,source_id:receiptSource,source_line:8,
 source_sha256:sha256,source_version:1,
 source_snapshot_sha256:'a'.repeat(64),source_snapshot_contract:'oi.pg-source-world-model/1',preflight_sha256:'b'.repeat(64),
 created_at:'2026-11-02T12:00:00Z',source_context_state:state,
 human_review_state:'not_submitted',clinical_approval:false,
 model_executed:false,...overrides,
});
const sourceQuestions=(questions=[sourceQuestion()])=>({
 contract:'oi.synthetic-source-questions/2',access_receipt_id:'ACCESS-'+'C'.repeat(32),
 patient_id:receiptPatient,case_id:receiptCase,questions,
 synthetic:true,clinical_review_connected:false,clinical_approval:false,
});
const questionsPath='/v1/patients/'+receiptPatient+'/cases/'+receiptCase+'/questions';
test('source questions persist only after explicit source preflight and idempotent POST',async()=>{
 const calls=[];
 let n=0;
 const s=newSession(async(url,init)=>{
  calls.push([url,init]);
  if(url===sourcePreflightPath)return response(composerFixture());
  if(url===questionsPath)return response({question_id:savedQuestionId,duplicate:++n>1},n>1?200:201);
  if(url.endsWith('/world-model'))return response(worldFixture());
  return response(patient());
 });
 s.connect(token);
 await s.savePreparedQuestion();
 assert.equal(s.snapshot().savedQuestion,null);
 assert.equal(calls.length,0);
 await s.read(receiptPatient);await s.loadCases();await s.loadWorldModel(receiptCase);
 await s.prepareSourceContext(receiptSource,8,composerQuestion);
 assert.equal(s.snapshot().savedQuestion,null);
 await s.savePreparedQuestion();
 assert.equal(s.snapshot().savedQuestion.question_id,savedQuestionId);
 assert.equal(s.snapshot().questionSavePhase,'saved');
 assert.equal(s.snapshot().composerPreview.clinical_approval,false);
 assert.equal(s.snapshot().composerPreview.durable_review_connected,false);
 assert.equal(calls[3][0],questionsPath);
 assert.equal(calls[3][1].method,'POST');
 assert.equal(calls[3][1].credentials,'omit');
 assert.equal(calls[3][1].redirect,'error');
 assert.equal(calls[3][1].cache,'no-store');
 const body=JSON.parse(calls[3][1].body);
 assert.equal(body.synthetic,true);
 assert.equal(body.source_id,receiptSource);
 assert.equal(body.source_line,8);
 assert.equal(body.expected_source_snapshot_sha256,'a'.repeat(64));
 assert.equal(body.expected_preflight_sha256,'b'.repeat(64));
 assert.ok(typeof body.request_key==='string'&&body.request_key.length>=3);
 await s.savePreparedQuestion();
 assert.deepEqual(JSON.parse(calls[4][1].body),body);
 assert.equal(s.snapshot().savedQuestion.duplicate,true);
});
test('network uncertainty retries with one stable question-intent key',async()=>{
 const posts=[];
 const s=newSession(async(url,init)=>{
  if(url===questionsPath){
   posts.push(init.body);
   if(posts.length===1)throw Error('network may have saved the request');
   return response({question_id:savedQuestionId,duplicate:true},200);
  }
  return response(url===sourcePreflightPath?composerFixture():url.endsWith('/world-model')?worldFixture():patient());
 });
 s.connect(token);await s.read(receiptPatient);await s.loadCases();await s.loadWorldModel(receiptCase);
 await s.prepareSourceContext(receiptSource,8,composerQuestion);
 await s.savePreparedQuestion();
 assert.equal(s.snapshot().savedQuestion,null);
 assert.ok(s.snapshot().questionSaveMessage.includes('outcome unknown'));
 await s.savePreparedQuestion();
 assert.equal(posts.length,2);
 assert.equal(posts[0],posts[1]);
 assert.equal(s.snapshot().savedQuestion.duplicate,true);
});
test('saved questions read current versus reassessment states, never clinician approval',async()=>{
 let changed=false;
 const s=newSession(async url=>{
  if(url===questionsPath)return response(sourceQuestions([
    sourceQuestion(changed?'source_reassessment_required':'current_unreviewed_question')
  ]));
  return response(patient());
 });
 s.connect(token);await s.read(receiptPatient);await s.loadCases();
 await s.loadSavedQuestions(receiptCase);
 assert.equal(s.snapshot().questions[0].source_context_state,'current_unreviewed_question');
 assert.equal(s.snapshot().questions[0].human_review_state,'not_submitted');
 assert.equal(s.snapshot().questions[0].clinical_approval,false);
 changed=true;await s.loadSavedQuestions(receiptCase);
 assert.equal(s.snapshot().questions[0].source_context_state,'source_reassessment_required');
 assert.equal(s.snapshot().questions[0].source_id,receiptSource);
});
test('cross-patient question list, forged review status and bad source references fail closed',async()=>{
 const forged=[
  {...sourceQuestions(),patient_id:'PAT-OTHER-001'},
  {...sourceQuestions(),case_id:'CASE-BETA'},
  {...sourceQuestions(),clinical_review_connected:true},
  sourceQuestions([sourceQuestion('current_unreviewed_question',{clinical_approval:true})]),
  sourceQuestions([sourceQuestion('current_unreviewed_question',{human_review_state:'approved'})]),
  sourceQuestions([sourceQuestion('current_unreviewed_question',{source_id:'SRC-'+'F'.repeat(31)})]),
 ];
 for(const responseBody of forged){
  const s=newSession(async url=>response(url===questionsPath?responseBody:patient()));
  s.connect(token);await s.read(receiptPatient);await s.loadCases();await s.loadSavedQuestions(receiptCase);
  assert.equal(s.snapshot().questions,null);
  assert.equal(s.snapshot().questionListPhase,'error');
 }
});
test('question read revocation removes an earlier visible history',async()=>{
 let revoked=false;
 const s=newSession(async url=>response(url===questionsPath?
  revoked?{detail:'private review data'}:sourceQuestions():patient(),revoked&&url===questionsPath?404:200));
 s.connect(token);await s.read(receiptPatient);await s.loadCases();await s.loadSavedQuestions(receiptCase);
 assert.equal(s.snapshot().questions.length,1);
 revoked=true;await s.loadSavedQuestions(receiptCase);
 assert.equal(s.snapshot().questions,null);
 assert.equal(s.snapshot().questionListPhase,'error');
 assert.ok(!JSON.stringify(s.snapshot()).includes('private review data'));
});
test('changed source before question save rejects and clears obsolete preflight',async()=>{
 let stale=false;
 const s=newSession(async url=>{
  if(url===questionsPath)return stale?response({detail:'source changed'},409):
    response({question_id:savedQuestionId,duplicate:false},201);
  return response(url===sourcePreflightPath?composerFixture():
    url.endsWith('/world-model')?worldFixture():patient());
 });
 s.connect(token);await s.read(receiptPatient);await s.loadCases();await s.loadWorldModel(receiptCase);
 await s.prepareSourceContext(receiptSource,8,composerQuestion);
 stale=true;await s.savePreparedQuestion();
 assert.equal(s.snapshot().worldModel,null);
 assert.equal(s.snapshot().composerPreview,null);
 assert.equal(s.snapshot().savedQuestion,null);
 assert.equal(s.snapshot().questionSavePhase,'error');
});
test('patient switching, case refresh and disconnect invalidate durable question UI responses',async()=>{
 const late=deferred();
 const s=newSession(async url=>{
  if(url===questionsPath)return late.promise;
  return response(patient(url.endsWith('PAT-EXAMPLE-002')?'PAT-EXAMPLE-002':receiptPatient));
 });
 s.connect(token);await s.read(receiptPatient);await s.loadCases();
 const pending=s.loadSavedQuestions(receiptCase);
 await s.read('PAT-EXAMPLE-002');
 late.resolve(response(sourceQuestions()));await pending;
 assert.equal(s.snapshot().questions,null);
 const t=newSession(async url=>response(
  url===questionsPath?sourceQuestions():
  url===sourcePreflightPath?composerFixture():
  url.endsWith('/world-model')?worldFixture():patient()
 ));
 t.connect(token);await t.read(receiptPatient);await t.loadCases();await t.loadSavedQuestions(receiptCase);
 assert.equal(t.snapshot().questions.length,1);
 await t.loadCases();
 assert.equal(t.snapshot().questions,null);
 await t.loadWorldModel(receiptCase);await t.prepareSourceContext(receiptSource,8,composerQuestion);
 await t.savePreparedQuestion();
 t.disconnect();assert.equal(t.snapshot().questions,null);
 assert.equal(t.snapshot().savedQuestion,null);
});


test('new access receipts for unchanged preflight preserve an uncertain question request key',async()=>{
 const writes=[];let prepared=0;
 const s=newSession(async(url,init)=>{
  if(url===sourcePreflightPath)return response({...composerFixture(),
    access_receipt_id:'ACCESS-'+(++prepared===1?'D':'E').repeat(32)});
  if(url===questionsPath){writes.push(JSON.parse(init.body));
   if(writes.length===1)throw Error('lost synthetic reply');
   return response({question_id:savedQuestionId,duplicate:true});
  }
  return response(url.endsWith('/world-model')?worldFixture():patient());
 });
 s.connect(token);await s.read(receiptPatient);await s.loadCases();await s.loadWorldModel(receiptCase);
 await s.prepareSourceContext(receiptSource,8,composerQuestion);await s.savePreparedQuestion();
 assert.ok(s.snapshot().questionSaveMessage.includes('outcome unknown'));
 await s.prepareSourceContext(receiptSource,8,composerQuestion);await s.savePreparedQuestion();
 assert.equal(writes.length,2);assert.deepEqual(writes[0],writes[1]);
 assert.equal(writes[0].expected_source_snapshot_sha256,worldFixture().snapshot_fingerprint);
 assert.equal(s.snapshot().composerPreview.access_receipt_id,'ACCESS-'+'E'.repeat(32));
 assert.equal(s.snapshot().savedQuestion.duplicate,true);
});
test('question save HTTP503 is uncertain and explicit retry keeps its original intent',async()=>{
 const writes=[];
 const s=newSession(async(url,init)=>{
  if(url===sourcePreflightPath)return response(composerFixture());
  if(url===questionsPath){writes.push(init.body);return writes.length===1?response({},503):
   response({question_id:savedQuestionId,duplicate:true});}
  return response(url.endsWith('/world-model')?worldFixture():patient());
 });
 s.connect(token);await s.read(receiptPatient);await s.loadCases();await s.loadWorldModel(receiptCase);
 await s.prepareSourceContext(receiptSource,8);await s.savePreparedQuestion();
 assert.equal(writes.length,1);assert.equal(s.snapshot().savedQuestion,null);
 assert.ok(s.snapshot().questionSaveMessage.includes('outcome unknown'));
 await s.savePreparedQuestion();assert.equal(writes.length,2);assert.equal(writes[0],writes[1]);
});
for(const operation of ['preflight','history','save']){
 test('late '+operation+' responses cannot restore after case, source, patient or credential changes',async()=>{
  for(const reset of ['case','source','patient','disconnect']){
   const late=deferred();
   const otherWorld={...worldFixture(),case_id:'CASE-BETA',snapshot_fingerprint:'f'.repeat(64),
    summary:{current_sources:0,historical_sources:0,current_observations:0,unresolved_observations:0,source_disagreements:0},
    current_sources:[],history:[],observations:[],unresolved_refs:[]};
   const index={contract:'oi.synthetic-original-sources/1',patient_id:receiptPatient,case_id:receiptCase,
    access_receipt_id:'ACCESS-'+'F'.repeat(32),sources:[],source_reported_assertions:[],
    synthetic:true,clinical_interpretation:false,research_review_invalidation_integrated:false};
   const s=newSession(async(url,init)=>{
    if(url===sourcePreflightPath)return operation==='preflight'?late.promise:response(composerFixture());
    if(url===questionsPath)return late.promise;
    if(url.endsWith('/CASE-BETA/world-model'))return response(otherWorld);
    if(url.endsWith('/world-model'))return response(worldFixture());
    if(url.endsWith('/sources'))return response(index);
    return response(patient(url.endsWith('PAT-EXAMPLE-002')?'PAT-EXAMPLE-002':receiptPatient));
   });
   s.connect(token);await s.read(receiptPatient);await s.loadCases();await s.loadWorldModel(receiptCase);
   if(operation==='save')await s.prepareSourceContext(receiptSource,8);
   const waiting=operation==='preflight'?s.prepareSourceContext(receiptSource,8):
    operation==='history'?s.loadSavedQuestions(receiptCase):s.savePreparedQuestion();
   const body=operation==='preflight'?composerFixture():operation==='history'?sourceQuestions():
    {question_id:savedQuestionId,duplicate:false};
   try{
    if(reset==='case')await s.loadWorldModel('CASE-BETA');
    else if(reset==='source')await s.loadSources(receiptCase);
    else if(reset==='patient')await s.read('PAT-EXAMPLE-002');
    else s.disconnect();
    late.resolve(response(body,operation==='save'?201:200));await waiting;
    assert.equal(s.snapshot().composerPreview,null,operation+'/'+reset);
    assert.equal(s.snapshot().questions,null,operation+'/'+reset);
    assert.equal(s.snapshot().savedQuestion,null,operation+'/'+reset);
    assert.equal(s.snapshot().questionsAccessReceiptId,null);
    assert.notEqual(s.snapshot().composerPhase,'loading');
    assert.notEqual(s.snapshot().questionListPhase,'loading');
    assert.notEqual(s.snapshot().questionSavePhase,'saving');
    if(reset==='case')assert.equal(s.snapshot().worldModel.case_id,'CASE-BETA');
    if(reset==='patient')assert.equal(s.snapshot().patient.patient_id,'PAT-EXAMPLE-002');
   }finally{late.resolve(response(body));await waiting;s.disconnect();}
  }
 });
}

test('question and preflight opaque identifiers reject terminal control whitespace',()=>{
 const model=worldFixture(),packet=composerFixture();
 for(const suffix of ['\n','\r','\u0000',' ']){
  assert.throws(()=>decodeSavedQuestion({question_id:savedQuestionId+suffix,duplicate:false}));
  for(const key of ['access_receipt_id','preflight_sha256']){
   assert.throws(()=>decodeComposerPreflight({...packet,[key]:packet[key]+suffix},model,model.observations[0],composerQuestion));
  }
  for(const key of ['question_id','source_id','source_sha256','source_snapshot_sha256','preflight_sha256']){
   const row=sourceQuestion();row[key]+=suffix;
   assert.throws(()=>decodeSourceQuestions(sourceQuestions([row]),receiptPatient,receiptCase));
  }
  const history=sourceQuestions();history.access_receipt_id+=suffix;
  assert.throws(()=>decodeSourceQuestions(history,receiptPatient,receiptCase));
 }
 for(const created_at of ['prefix2026-11-02T12:00:00Z','2026-11-02T12:00:00Z\n']){
  assert.throws(()=>decodeSourceQuestions(sourceQuestions([sourceQuestion('current_unreviewed_question',{created_at})]),receiptPatient,receiptCase));
 }
});

test('canonical preflight binds source content fingerprint while access receipts change',()=>{
 const first=worldFixture(),second={...worldFixture(),access_receipt_id:'ACCESS-'+'F'.repeat(32)};
 const packet=composerFixture();
 const a=decodeComposerPreflight(packet,first,first.observations[0],composerQuestion);
 const b=decodeComposerPreflight({...packet,access_receipt_id:'ACCESS-'+'E'.repeat(32)},second,second.observations[0],composerQuestion);
 assert.equal(a.source_snapshot_sha256,first.snapshot_fingerprint);
 assert.equal(b.preflight_sha256,a.preflight_sha256);
 assert.notEqual(a.access_receipt_id,b.access_receipt_id);
 for(const change of [
  {contract:'oi.synthetic-source-composer-preflight/1'},
  {source_snapshot_contract:'oi.synthetic-postgres-world-model-sources/1'},
  {source_snapshot_sha256:second.access_receipt_id},
  {access_receipt_id:'ACCESS-bad'},
 ]){
  assert.throws(()=>decodeComposerPreflight({...packet,...change},first,first.observations[0],composerQuestion));
 }
});
test('versioned question history retains access receipt and quarantines legacy context as reassessment',()=>{
 const packet=sourceQuestions([
  sourceQuestion(),
  sourceQuestion('source_reassessment_required',{question_id:'QUESTION-'+'B'.repeat(32),
   source_snapshot_contract:'oi.synthetic-postgres-world-model-sources/1'}),
 ]);
 const decoded=decodeSourceQuestions(packet,receiptPatient,receiptCase);
 assert.equal(decoded.access_receipt_id,packet.access_receipt_id);
 assert.equal(decoded.questions.length,2);
 assert.equal(decoded.questions[1].source_context_state,'source_reassessment_required');
 const {contract,...unversioned}=packet;
 assert.throws(()=>decodeSourceQuestions(unversioned,receiptPatient,receiptCase));
 for(const change of [{contract:'oi.synthetic-source-questions/1'},{access_receipt_id:'bad'}]){
  assert.throws(()=>decodeSourceQuestions({...packet,...change},receiptPatient,receiptCase));
 }
 assert.throws(()=>decodeSourceQuestions(sourceQuestions([sourceQuestion('current_unreviewed_question',{
  source_snapshot_contract:'oi.synthetic-postgres-world-model-sources/1',
 })]),receiptPatient,receiptCase));
});


const quotePacketPath=questionsPath+'/'+savedQuestionId+'/source-review-packet';
const quoteDetail=()=>({
 source_id:receiptSource,document_id:'DOC-ONE',document_version:1,
 source_sha256:sha256,source_line:8,finding_key:'marker',
 reported_state:'not-reported',source_statement:'Independently fictional example.',
 source_kind:'pathology',specimen_id:'SPECIMEN-ONE',event_date:'2026-01-10',
 issued_at:'2026-01-11',review_state:'not_established',clinical_meaning:null
});
function stableQuoteJson(value){
 if(Array.isArray(value))return '['+value.map(stableQuoteJson).join(',')+']';
 if(value!==null&&typeof value==='object')return '{'+
   Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+stableQuoteJson(value[k])).join(',')+'}';
 return JSON.stringify(value);
}
const packetFixture=(historical=false)=>{
 const q=sourceQuestion(historical?'source_reassessment_required':'current_unreviewed_question');
 const p={
  contract:'oi.synthetic-question-source-review-packet/1',
  patient_id:receiptPatient,case_id:receiptCase,question_id:q.question_id,question:q.question,
  original_anchor:{
    source_id:q.source_id,source_line:q.source_line,source_sha256:q.source_sha256,
    source_version:q.source_version,source_snapshot_sha256:q.source_snapshot_sha256,
    source_snapshot_contract:q.source_snapshot_contract,preflight_sha256:q.preflight_sha256
  },
  source_context_state:historical?'source_reassessment_required':'current_unreviewed_source',
  current_source_snapshot_sha256:historical?'f'.repeat(64):'a'.repeat(64),
  selected_statement:historical?null:quoteDetail(),
  related_statements:[],related_statement_count_total:0,related_statements_truncated:false,
  current_source_count:1,current_observation_count:1,
  external_biomedical_evidence_qualified:false,published_evidence_rights_verified:false,
  medical_interpretation_performed:false,clinical_review_connected:false,
  clinical_approval:false,reviewer_identity_verified:false,synthetic:true,
  review_next_step:historical?'refresh_source_and_create_new_question':
    'independent_source_verification_required',
 };
 return {...p,packet_sha256:createHash('sha256').update(stableQuoteJson(p),'utf8').digest('hex'),
   source_access_receipt_id:'ACCESS-'+'F'.repeat(32)};
};
const quoteSession=(packet=packetFixture(),status=200)=>newSession(async(url)=>{
 if(url===questionsPath)return response(sourceQuestions([
   sourceQuestion(packet.source_context_state==='source_reassessment_required'?
     'source_reassessment_required':'current_unreviewed_question')]));
 if(url===quotePacketPath)return response(packet,status);
 return response(patient());
});
test('source quotation packet requires selected authorized question before any HTTP read',async()=>{
 let calls=0;
 const s=newSession(async(url)=>{calls++;return response(url===questionsPath?sourceQuestions():patient())});
 s.connect(token);await s.loadQuestionSourcePacket(savedQuestionId);
 assert.equal(calls,0);
 await s.read(receiptPatient);await s.loadCases();await s.loadQuestionSourcePacket(savedQuestionId);
 assert.equal(calls,1);
 assert.equal(s.snapshot().sourceQuotePacket,null);
 assert.equal(s.snapshot().sourceQuotePhase,'error');
});
test('source-only quote packet has separate read, stable content hash and explicit no-approval flags',async()=>{
 const requests=[];
 const s=newSession(async(url,init)=>{
   requests.push([url,init]);
   return response(url===questionsPath?sourceQuestions():
     url===quotePacketPath?packetFixture():patient());
 });
 s.connect(token);await s.read(receiptPatient);await s.loadCases();
 await s.loadSavedQuestions(receiptCase);await s.loadQuestionSourcePacket(savedQuestionId);
 assert.equal(s.snapshot().sourceQuotePhase,'ready');
 const p=s.snapshot().sourceQuotePacket;
 assert.equal(p?.selected_statement?.source_statement,'Independently fictional example.');
 assert.equal(p?.selected_statement?.review_state,'not_established');
 assert.equal(p?.clinical_approval,false);
 assert.equal(p?.external_biomedical_evidence_qualified,false);
 assert.equal(p?.published_evidence_rights_verified,false);
 assert.equal(p?.review_next_step,'independent_source_verification_required');
 const req=requests.at(-1);
 assert.equal(req[0],quotePacketPath);
 assert.equal(req[1].method,'GET');
 assert.equal(req[1].credentials,'omit');
 assert.equal(req[1].redirect,'error');
 assert.equal(req[1].cache,'no-store');
 assert.equal(req[1].headers.Authorization,'Bearer '+token);
 assert.equal(JSON.stringify(s.snapshot()).includes(token),false);
});
test('historical source question keeps original anchor but never promotes old quote',async()=>{
 const s=quoteSession(packetFixture(true));
 s.connect(token);await s.read(receiptPatient);await s.loadCases();
 await s.loadSavedQuestions(receiptCase);await s.loadQuestionSourcePacket(savedQuestionId);
 assert.equal(s.snapshot().sourceQuotePhase,'ready');
 assert.equal(s.snapshot().sourceQuotePacket.source_context_state,'source_reassessment_required');
 assert.equal(s.snapshot().sourceQuotePacket.selected_statement,null);
 assert.equal(s.snapshot().sourceQuotePacket.original_anchor.source_id,receiptSource);
 assert.equal(s.snapshot().sourceQuotePacket.review_next_step,'refresh_source_and_create_new_question');
});
test('modified packet hash, mismatched original, forged rights and clinical approval fail closed',async()=>{
 for(const bad of [
   {...packetFixture(),packet_sha256:'0'.repeat(64)},
   {...packetFixture(),patient_id:'PAT-OTHER-001'},
   {...packetFixture(),original_anchor:{...packetFixture().original_anchor,source_id:'SRC-'+'B'.repeat(32)}},
   {...packetFixture(),selected_statement:{...quoteDetail(),source_line:7}},
   {...packetFixture(),selected_statement:{...quoteDetail(),source_statement:'Fabricated'}},
   {...packetFixture(),clinical_approval:true},
   {...packetFixture(),published_evidence_rights_verified:true},
   {...packetFixture(),reviewer_identity_verified:true},
   {...packetFixture(),medical_interpretation_performed:true}
 ]){
   const s=quoteSession(bad);
   s.connect(token);await s.read(receiptPatient);await s.loadCases();
   await s.loadSavedQuestions(receiptCase);await s.loadQuestionSourcePacket(savedQuestionId);
   assert.equal(s.snapshot().sourceQuotePacket,null);
   assert.equal(s.snapshot().sourceQuotePhase,'error');
 }
});
test('source quotation access denial removes prior quote without echoing forbidden details',async()=>{
 let denied=false;
 const s=newSession(async url=>{
   if(url===questionsPath)return response(sourceQuestions());
   if(url===quotePacketPath)return denied?response({detail:'private source quote'},404):response(packetFixture());
   return response(patient());
 });
 s.connect(token);await s.read(receiptPatient);await s.loadCases();
 await s.loadSavedQuestions(receiptCase);await s.loadQuestionSourcePacket(savedQuestionId);
 assert.ok(s.snapshot().sourceQuotePacket);
 denied=true;await s.loadQuestionSourcePacket(savedQuestionId);
 assert.equal(s.snapshot().sourceQuotePacket,null);
 assert.equal(s.snapshot().sourceQuotePhase,'error');
 assert.equal(JSON.stringify(s.snapshot()).includes('private source quote'),false);
});
test('patient switch, renewed question list and navigation invalidate in-flight source quote',async()=>{
 const pending=deferred();
 const s=newSession(async url=>{
   if(url===quotePacketPath)return pending.promise;
   if(url===questionsPath)return response(sourceQuestions());
   return response(patient(url.endsWith('PAT-OTHER')?'PAT-OTHER':receiptPatient));
 });
 s.connect(token);await s.read(receiptPatient);await s.loadCases();
 await s.loadSavedQuestions(receiptCase);
 const reading=s.loadQuestionSourcePacket(savedQuestionId);
 await s.read('PAT-OTHER');pending.resolve(response(packetFixture()));await reading;
 assert.equal(s.snapshot().sourceQuotePacket,null);
 const t=quoteSession();
 t.connect(token);await t.read(receiptPatient);await t.loadCases();
 await t.loadSavedQuestions(receiptCase);await t.loadQuestionSourcePacket(savedQuestionId);
 assert.ok(t.snapshot().sourceQuotePacket);
 t.dismissSourceQuotePacket();assert.equal(t.snapshot().sourceQuotePacket,null);
 await t.loadQuestionSourcePacket(savedQuestionId);assert.ok(t.snapshot().sourceQuotePacket);
 await t.loadSavedQuestions(receiptCase);assert.equal(t.snapshot().sourceQuotePacket,null);
 t.disconnect();assert.equal(t.snapshot().sourceQuotePacket,null);
});


// Records -> Investigations handoff: an old source read must not authorize
// a draft until the canonical PG World Model confirms the same literal line.
const handoffIndex=()=>({
 contract:'oi.synthetic-original-sources/1',patient_id:receiptPatient,case_id:receiptCase,
 access_receipt_id:'ACCESS-'+'E'.repeat(32),
 sources:worldFixture().current_sources.map(v=>({...v})),
 source_reported_assertions:[{
  source_id:receiptSource,finding_key:'marker',reported_state:'not-reported',
  source_statement:'Independently fictional example.',source_line:8,
  clinical_review_state:'not_established',
 }],
 synthetic:true,clinical_interpretation:false,research_review_invalidation_integrated:false,
});
const handoffSession=({world=()=>response(worldFixture()),question=()=>response(composerFixture()),
                       save=()=>response({question_id:'QUESTION-'+'F'.repeat(32),duplicate:false},201)}={})=>{
 const calls=[];
 const s=newSession((url,options)=>{
  calls.push([url,options]);
  if(url.endsWith('/sources'))return response(handoffIndex());
  if(url.endsWith('/world-model'))return world(url,options);
  if(url.endsWith('/composer/source-preflight'))return question(url,options);
  if(url.endsWith('/questions'))return save(url,options);
  return response(patient(url.endsWith('/PAT-OTHER')?'PAT-OTHER':receiptPatient));
 });
 return {s,calls};
};
async function loadedHandoff(fixture){
 fixture.s.connect(token);
 await fixture.s.read(receiptPatient);
 await fixture.s.loadCases();
 await fixture.s.loadSources(receiptCase);
 assert.equal(fixture.s.snapshot().recordsPhase,'ready');
 assert.equal(fixture.s.snapshot().sourceIndex.sources.length,1);
 return fixture;
}
test('Records exact quote opens a draft only after a fresh authorized World Model GET',async()=>{
 const f=await loadedHandoff(handoffSession());
 const before=f.calls.length;
 const ok=await f.s.beginQuestionFromSourceReading(receiptCase,receiptSource,8);
 assert.equal(ok,true);
 assert.equal(f.calls.length,before+1);
 assert.equal(f.calls.at(-1)[0],'/v1/patients/'+receiptPatient+'/cases/'+receiptCase+'/world-model');
 assert.equal(f.calls.at(-1)[1].method,'GET');
 assert.equal(f.calls.at(-1)[1].credentials,'omit');
 assert.equal(f.s.snapshot().questionDraft.source_id,receiptSource);
 assert.equal(f.s.snapshot().questionDraft.source_line,8);
 assert.equal(f.s.snapshot().composerPreview,null);
 assert.equal(f.s.snapshot().savedQuestion,null);
 assert.equal(f.s.snapshot().worldPhase,'ready');
 assert.equal(f.s.snapshot().questionSavePhase,'idle');
});
test('Records handoff rejects version/hash drift without asking a question',async()=>{
 const changed=worldFixture();
 changed.current_sources[0].sha256='e'.repeat(64);
 changed.observations[0].source_sha256='e'.repeat(64);
 const f=await loadedHandoff(handoffSession({world:()=>response(changed)}));
 assert.equal(await f.s.beginQuestionFromSourceReading(receiptCase,receiptSource,8),false);
 assert.equal(f.s.snapshot().questionDraft,null);
 assert.equal(f.s.snapshot().worldModel,null);
 assert.equal(f.s.snapshot().worldPhase,'error');
 assert.ok(f.s.snapshot().worldMessage.includes('changed during the handoff'));
 assert.ok(!f.calls.some(([url])=>url.endsWith('/questions')));
});
test('Records handoff rejects edited or forged literal quote despite unchanged source hash',async()=>{
 const changed=worldFixture();
 changed.observations[0].source_statement='Different fictional quote from stored source.';
 const f=await loadedHandoff(handoffSession({world:()=>response(changed)}));
 assert.equal(await f.s.beginQuestionFromSourceReading(receiptCase,receiptSource,8),false);
 assert.equal(f.s.snapshot().questionDraft,null);
 assert.equal(f.s.snapshot().worldModel,null);
});
test('Revoked derived-source permission never creates a draft or an implicit preflight',async()=>{
 const f=await loadedHandoff(handoffSession({world:()=>response({detail:'sensitive'},404)}));
 assert.equal(await f.s.beginQuestionFromSourceReading(receiptCase,receiptSource,8),false);
 assert.equal(f.s.snapshot().questionDraft,null);
 assert.equal(f.s.snapshot().worldModel,null);
 assert.equal(f.s.snapshot().worldPhase,'error');
 assert.ok(!JSON.stringify(f.s.snapshot()).includes('sensitive'));
 assert.ok(!f.calls.some(([url])=>url.includes('/composer/')));
});
test('Wrong case or unreferenced original line is refused without network calls',async()=>{
 const f=await loadedHandoff(handoffSession());
 const before=f.calls.length;
 assert.equal(await f.s.beginQuestionFromSourceReading('CASE-BETA',receiptSource,8),false);
 assert.equal(await f.s.beginQuestionFromSourceReading(receiptCase,receiptSource,9),false);
 assert.equal(await f.s.beginQuestionFromSourceReading(receiptCase,'SRC-'+'F'.repeat(32),8),false);
 assert.equal(f.calls.length,before);
 assert.equal(f.s.snapshot().questionDraft,null);
});
test('Outstanding draft cannot be silently overwritten by choosing a second quote',async()=>{
 const f=await loadedHandoff(handoffSession());
 assert.equal(await f.s.beginQuestionFromSourceReading(receiptCase,receiptSource,8),true);
 f.s.changeQuestionDraft('Which originally fictional source explains this observation?');
 const before=f.calls.length;
 assert.equal(await f.s.beginQuestionFromSourceReading(receiptCase,receiptSource,8),false);
 assert.equal(f.calls.length,before);
 assert.equal(f.s.snapshot().questionDraft.question,'Which originally fictional source explains this observation?');
 assert.ok(f.s.snapshot().worldMessage.includes('unfinished question'));
});
test('Uncertain save locks the Records handoff and preserves the original retry',async()=>{
 let writes=0;
 const f=await loadedHandoff(handoffSession({save:()=>{
  if(++writes===1)throw Error('Lost response after possible commit');
  return response({question_id:'QUESTION-'+'F'.repeat(32),duplicate:true});
 }}));
 assert.equal(await f.s.beginQuestionFromSourceReading(receiptCase,receiptSource,8),true);
 await f.s.prepareDraftQuestion();
 await f.s.savePreparedQuestion();
 assert.equal(writes,1);
 assert.ok(f.s.snapshot().questionSaveMessage.startsWith('Save outcome unknown.'));
 const before=f.calls.length;
 assert.equal(await f.s.beginQuestionFromSourceReading(receiptCase,receiptSource,8),false);
 assert.equal(f.calls.length,before);
 assert.ok(f.s.snapshot().composerPreview);
 await f.s.savePreparedQuestion();
 assert.equal(writes,2);
 const posts=f.calls.filter(([url])=>url.endsWith('/questions'));
 assert.equal(posts.length,2);
 assert.deepEqual(JSON.parse(posts[0][1].body),JSON.parse(posts[1][1].body));
 assert.equal(f.s.snapshot().savedQuestion.duplicate,true);
});
test('Late read after a patient switch cannot reopen an old source question',async()=>{
 const pending=deferred();
 const f=await loadedHandoff(handoffSession({world:()=>pending.promise}));
 const waiting=f.s.beginQuestionFromSourceReading(receiptCase,receiptSource,8);
 await f.s.read('PAT-OTHER');
 pending.resolve(response(worldFixture()));
 assert.equal(await waiting,false);
 assert.equal(f.s.snapshot().patient?.patient_id,'PAT-OTHER');
 assert.equal(f.s.snapshot().questionDraft,null);
 assert.equal(f.s.snapshot().worldModel,null);
});
