import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {patientContinuity} from '../.test-dist/patient-continuity.js';

const token='fictional_test_credential_000000000001';
const patientId='PAT-EXAMPLE-001',caseId='CASE-ALPHA';
const questionId='QUESTION-'+'A'.repeat(32),sourceId='SRC-'+'B'.repeat(32);
const receiptId='REVIEW-'+'C'.repeat(32),fingerprint='d'.repeat(64);
const reason='Please independently verify this fictional source quotation and uncertainty.';
const canonical='oi.pg-source-world-model/1',legacy='oi.synthetic-postgres-world-model-sources/1';
const currentFingerprint='oi.synthetic-source-review-return/2',legacyFingerprint='oi.synthetic-source-review-return/1';
const response=(value,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
const deferred=()=>{let resolve;return{promise:new Promise(r=>resolve=r),resolve:value=>resolve(value)};};
const patient=(id=patientId)=>({patient_id:id,origin_org:'FICT-ORG',status:'active',revision:1,created_at:'2026-11-03T10:00:00Z'});
const cases=()=>({patient_id:patientId,synthetic:true,source_identity_verified:false,clinical_sources_linked:false,
 mappings:[caseId,'CASE-BETA'].map((id,i)=>({case_id:id,patient_id:patientId,source_organization:'FICT-ORG',
 source_system:'FICT-TEXT',source_subject_ref:'FICT-SUBJECT-'+i,review_ref:'FICT-REVIEW-'+i,status:'active',revision:1,
 created_at:'2026-11-03T10:00:00Z',revoked_at:null,source_identity_verified:false,clinical_sources_linked:false,clinical_conclusions:false}))});
const item=(overrides={})=>({question_id:questionId,patient_id:patientId,case_id:caseId,
 question:'What source provenance and reported uncertainty require independent verification?',
 source_id:sourceId,source_line:8,source_sha256:'e'.repeat(64),source_version:1,
 source_snapshot_sha256:'a'.repeat(64),source_snapshot_contract:canonical,
 preflight_sha256:'b'.repeat(64),created_at:'2026-11-03T10:00:00Z',kind:'source-question',
 queue_fingerprint:fingerprint,queue_fingerprint_contract:currentFingerprint,
 source_context_state:'current_unreviewed_question',review_state:'awaiting_independent_verification',
 current_return_receipt_id:null,return_count:0,prior_return_count:0,clinical_approval:false,
 reviewer_identity_verified:false,...overrides});
const receipt=(overrides={})=>({receipt_id:receiptId,question_id:questionId,queue_fingerprint:fingerprint,
 queue_fingerprint_contract:currentFingerprint,source_snapshot_contract:canonical,source_snapshot_sha256:'a'.repeat(64),
 actor_label:'ACTOR-FICTIONAL',action:'returned',reason,created_at:'2026-11-03T10:05:00Z',
 reviewer_identity_verified:false,external_notification_sent:false,clinical_approval:false,...overrides});
const queue=(items=[item()],receipts=[],overrides={})=>({contract:'oi.synthetic-question-review-return-queue/2',
 access_receipt_id:'ACCESS-'+'D'.repeat(32),patient_id:patientId,case_id:caseId,synthetic:true,items,receipts,
 external_notification_sent:false,reviewer_identity_verified:false,clinical_approval:false,review_completion_supported:false,...overrides});
const saved=(duplicate=false)=>({receipt_id:receiptId,question_id:questionId,duplicate});
const historyItem=(overrides={})=>item({queue_fingerprint:null,source_context_state:'source_reassessment_required',
 review_state:'source_reassessment_required',...overrides});
const queuePath='/v1/patients/'+patientId+'/cases/'+caseId+'/review-queue';
const returnPath='/v1/patients/'+patientId+'/cases/'+caseId+'/questions/'+questionId+'/return-for-verification';
const world=(id=caseId)=>({contract:canonical,patient_id:patientId,case_id:id,access_receipt_id:'ACCESS-'+'E'.repeat(32),
 synthetic:true,authority:'source_report_only_unreviewed',clinical_interpretation:false,
 research_review_invalidation_integrated:false,composer_execution_authorized:false,snapshot_fingerprint:'f'.repeat(64),
 as_of_received_at:null,summary:{current_sources:0,historical_sources:0,current_observations:0,unresolved_observations:0,source_disagreements:0},
 current_sources:[],history:[],observations:[],unresolved_refs:[],conflicts:[],limitations:['Independently fictional source context only.']});
function session(transport,readCases=()=>response(cases())){return new RegistrySession(async(url,init)=>{
 if(url.endsWith('/case-bindings'))return readCases();
 if(url==='/v1/patients/'+patientId)return response(patient());
 return transport(url,init);
});}
async function opened(s){s.connect(token);await s.read(patientId);await s.loadCases();
 assert.equal(typeof s.loadReviewQueue,'function','The existing Review owner must connect to the current patient client');
 await s.loadReviewQueue(caseId);}

test('canonical review queue is scoped and exposes a distinct access receipt without invoking Composer',async()=>{
 const calls=[];const s=session(async(url,init)=>{calls.push([url,init]);return response(queue());});
 await opened(s);
 assert.equal(s.snapshot().reviewPhase,'ready');
 assert.equal(s.snapshot().reviewQueue.access_receipt_id,'ACCESS-'+'D'.repeat(32));
 assert.equal(s.snapshot().reviewQueue.items[0].source_snapshot_contract,canonical);
 assert.equal(s.snapshot().reviewQueue.items[0].queue_fingerprint,fingerprint);
 assert.deepEqual(calls.map(([url])=>url),[queuePath]);
 assert.equal(calls[0][1].credentials,'omit');assert.equal(calls[0][1].redirect,'error');
 assert.equal(calls[0][1].cache,'no-store');assert.equal(calls[0][1].method,'GET');
 assert.equal(s.snapshot().composerPreview,null);
});
test('verification return sends the exact item fingerprint and editable reason, never a source access receipt',async()=>{
 const calls=[];const s=session(async(url,init)=>{calls.push([url,init]);return response(url===queuePath?queue():saved(),url===queuePath?200:201);});
 await opened(s);await s.returnReviewQuestion(questionId,fingerprint,reason);
 assert.equal(s.snapshot().reviewReturnPhase,'saved');assert.deepEqual(s.snapshot().reviewReturn,saved());
 const [url,init]=calls[1],body=JSON.parse(init.body);
 assert.equal(url,returnPath);assert.equal(init.method,'POST');
 assert.deepEqual(Object.keys(body).sort(),['expected_queue_fingerprint','reason','request_key','synthetic']);
 assert.equal(body.expected_queue_fingerprint,fingerprint);assert.equal(body.reason,reason);assert.equal(body.synthetic,true);
 assert.equal(typeof body.request_key,'string');assert.equal(s.snapshot().reviewQueue.clinical_approval,false);
 assert.ok(!JSON.stringify(body).includes('ACCESS-'));
});
test('old queue packets, missing provenance, malformed receipts and fabricated approval are withheld',async()=>{
 const bad=[
  queue(undefined,[],{contract:'oi.synthetic-question-review-return-queue/1'}),
  queue(undefined,[],{access_receipt_id:undefined}),
  queue(undefined,[],{access_receipt_id:'ACCESS-'+'D'.repeat(32)+'\n'}),
  queue([item({source_snapshot_contract:undefined})]),queue([item({queue_fingerprint_contract:legacyFingerprint})]),
  queue([item({source_snapshot_contract:'unrecognized'})]),queue([item({clinical_approval:true})]),
  queue(undefined,[],{review_completion_supported:true}),queue(undefined,[],{patient_id:'PAT-OTHER-001'}),
  queue([item({question_id:questionId+'\n'})]),queue([item({queue_fingerprint:fingerprint+'\n'})]),
  queue([item({prior_return_count:1})],[receipt({receipt_id:receiptId+'\n'})]),
 ];
 for(const packet of bad){const s=session(async()=>response(packet));await opened(s);
  assert.equal(s.snapshot().reviewQueue,null);assert.equal(s.snapshot().reviewPhase,'error');}
});
test('legacy questions remain reassessment even if their hash equals current canonical content',async()=>{
 const s=session(async()=>response(queue([historyItem({source_snapshot_contract:legacy})])));
 await opened(s);assert.equal(s.snapshot().reviewQueue.items[0].review_state,'source_reassessment_required');
 await s.returnReviewQuestion(questionId,fingerprint,reason);assert.equal(s.snapshot().reviewReturn,null);
 const forged=session(async()=>response(queue([item({source_snapshot_contract:legacy})])));
 await opened(forged);assert.equal(forged.snapshot().reviewQueue,null);
});
test('a legacy return with the same digest stays historical and cannot establish a current return',async()=>{
 const old=receipt({source_snapshot_contract:legacy,queue_fingerprint_contract:legacyFingerprint});
 const s=session(async()=>response(queue([item({prior_return_count:1})],[old])));await opened(s);
 assert.equal(s.snapshot().reviewQueue.items[0].return_count,0);assert.equal(s.snapshot().reviewQueue.receipts.length,1);
 const forged=session(async()=>response(queue([item({return_count:1,current_return_receipt_id:receiptId,
  review_state:'returned_for_independent_verification'})],[old])));await opened(forged);
 assert.equal(forged.snapshot().reviewQueue,null);
});
test('current return receipts must match canonical provenance and the exact saved source snapshot',async()=>{
 const current=item({return_count:1,current_return_receipt_id:receiptId,review_state:'returned_for_independent_verification'});
 const good=session(async()=>response(queue([current],[receipt()])));await opened(good);
 assert.equal(good.snapshot().reviewQueue.items[0].current_return_receipt_id,receiptId);
 await good.loadReviewQueue(caseId);
 assert.equal(good.snapshot().reviewQueue.receipts.length,1);
 assert.doesNotMatch(good.snapshot().reviewReturnMessage,/no.+return.+recorded/i,
  'Refreshing persisted return history must not describe that history as empty');
 for(const invalid of [receipt({source_snapshot_sha256:'0'.repeat(64)}),receipt({queue_fingerprint_contract:legacyFingerprint})]){
  const s=session(async()=>response(queue([current],[invalid])));await opened(s);assert.equal(s.snapshot().reviewQueue,null);
 }
});
for(const outcome of ['network',503])test('uncertain '+outcome+' return retains its captured intent and same key across receipt churn',async()=>{
 let attempt=0,reads=0;const bodies=[];
 const s=session(async(url,init)=>{
  if(url===queuePath)return response(queue(undefined,[],{access_receipt_id:'ACCESS-'+String(++reads).repeat(32)}));
  bodies.push(JSON.parse(init.body));
  if(++attempt===1){if(outcome==='network')throw Error('synthetic lost response');return response({},outcome);}
  return response(saved(true));
 });
 await opened(s);await s.returnReviewQuestion(questionId,fingerprint,reason);
 assert.equal(s.snapshot().reviewReturnPhase,'unknown');assert.equal(bodies.length,1);
 assert.equal(s.snapshot().reviewReturnIntent.reason,reason);
 await s.returnReviewQuestion(questionId,fingerprint,'A different fictional reason must not silently replace an uncertain return.');
 assert.equal(bodies.length,1);assert.equal(s.snapshot().reviewReturnIntent.reason,reason);
 await s.loadReviewQueue(caseId);await s.retryReviewReturn();
 assert.equal(bodies.length,2);assert.deepEqual(bodies[0],bodies[1]);assert.equal(s.snapshot().reviewReturn.duplicate,true);
});
test('503 then same-case source refresh preserves an exact historical retry after amendment',async()=>{
 let first=true;const bodies=[];const s=session(async(url,init)=>{
  if(url===queuePath)return response(queue());
  if(url.endsWith('/world-model'))return response(world());
  bodies.push(JSON.parse(init.body));if(first){first=false;return response({},503);}return response(saved(true));
 });
 await opened(s);await s.returnReviewQuestion(questionId,fingerprint,reason);await s.loadWorldModel(caseId);
 assert.equal(s.snapshot().reviewQueue,null);assert.equal(s.snapshot().worldPhase,'ready');
 assert.equal(s.snapshot().reviewReturnPhase,'unknown');
 await s.retryReviewReturn();assert.deepEqual(bodies[0],bodies[1]);assert.equal(s.snapshot().reviewReturn.duplicate,true);
});
test('a stale exact retry that never committed stops at409 without manufacturing a new key',async()=>{
 const bodies=[];const s=session(async(url,init)=>{
  if(url===queuePath)return response(queue());
  bodies.push(JSON.parse(init.body));return response({},bodies.length===1?503:409);
 });
 await opened(s);await s.returnReviewQuestion(questionId,fingerprint,reason);await s.retryReviewReturn();
 assert.deepEqual(bodies[0],bodies[1]);assert.equal(s.snapshot().reviewReturnPhase,'error');
 assert.equal(s.snapshot().reviewReturnIntent,null);await s.retryReviewReturn();assert.equal(bodies.length,2);
});
test('source context switch clears a prior queue and a denied source read cannot leave it actionable',async()=>{
 const s=session(async(url)=>url===queuePath?response(queue()):response({},404));await opened(s);
 await s.loadWorldModel('CASE-BETA');assert.equal(s.snapshot().reviewQueue,null);
 assert.notEqual(s.snapshot().reviewPhase,'ready');
});
test('same-case queue refresh cannot let an older return finally unlock a newer pending return',async()=>{
 const a=deferred(),b=deferred();let count=0;
 const s=session(async(url)=>url===queuePath?response(queue()):[a,b][count++].promise);
 await opened(s);const first=s.returnReviewQuestion(questionId,fingerprint,reason);
 await s.loadReviewQueue(caseId);const second=s.retryReviewReturn();
 a.resolve(response(saved(),201));await first;
 await s.returnReviewQuestion(questionId,fingerprint,'A different fictional return must wait until the pending operation finishes.');
 assert.equal(count,2);assert.equal(s.snapshot().reviewReturnPhase,'saving');
 b.resolve(response(saved(true)));await second;assert.equal(s.snapshot().reviewReturn.duplicate,true);
});
for(const action of ['patient','case','disconnect','denial'])test(action+' invalidation discards pending review responses and captured reasons',async()=>{
 const pending=deferred();let denied=false;
 const s=session(async(url)=>{
  if(url===queuePath)return denied?response({detail:'private synthetic detail'},404):response(queue());
  if(url===returnPath)return pending.promise;
  if(url.endsWith('/world-model'))return response(world('CASE-BETA'));
  return response(patient('PAT-OTHER-001'));
 });
 await opened(s);const returning=s.returnReviewQuestion(questionId,fingerprint,reason);
 if(action==='patient')await s.read('PAT-OTHER-001');
 if(action==='case')await s.loadWorldModel('CASE-BETA');
 if(action==='disconnect')s.disconnect();
 if(action==='denial'){denied=true;await s.loadReviewQueue(caseId);}
 pending.resolve(response(saved(),201));await returning;
 assert.equal(s.snapshot().reviewQueue,null);assert.equal(s.snapshot().reviewReturn,null);
 assert.equal(s.snapshot().reviewReturnIntent,null);assert.ok(!JSON.stringify(s.snapshot()).includes(reason));
 assert.ok(!JSON.stringify(s.snapshot()).includes('private synthetic detail'));
});
test('a later independent queue denial clears both loaded history and an uncertain return',async()=>{
 let denied=false;const s=session(async(url)=>url===queuePath?
  denied?response({},404):response(queue()):response({},503));await opened(s);
 await s.returnReviewQuestion(questionId,fingerprint,reason);denied=true;await s.loadReviewQueue(caseId);
 assert.equal(s.snapshot().reviewQueue,null);assert.equal(s.snapshot().reviewReturnIntent,null);
});
test('independent return denial clears review content without changing the authorized patient',async()=>{
 const s=session(async(url)=>url===queuePath?response(queue()):response({detail:'private return authority'},404));await opened(s);
 await s.returnReviewQuestion(questionId,fingerprint,reason);
 assert.equal(s.snapshot().reviewQueue,null);assert.equal(s.snapshot().reviewReturnIntent,null);
 assert.equal(s.snapshot().patient.patient_id,patientId);assert.ok(!JSON.stringify(s.snapshot()).includes('private return authority'));
});
test('invalid return reasons and malformed successful receipts never become a saved return',async()=>{
 let writes=0;const s=session(async(url)=>{if(url===queuePath)return response(queue());writes++;return response({...saved(),question_id:'QUESTION-'+'F'.repeat(32)},201);});
 await opened(s);
 for(const invalid of ['short',' '+reason,reason+'\n',reason+'\u200b',reason+'\ufeff',reason+'\ud800'])await s.returnReviewQuestion(questionId,fingerprint,invalid);
 assert.equal(writes,0);await s.returnReviewQuestion(questionId,fingerprint,reason);
 assert.equal(writes,1);assert.equal(s.snapshot().reviewReturn,null);assert.equal(s.snapshot().reviewReturnPhase,'unknown');
});
test('question-history denial clears review content governed by the same question-read permission',async()=>{
 for(const uncertain of [false,true]){
  const s=session(async(url)=>url===queuePath?response(queue()):
   url===returnPath?response({},503):response({detail:'private question history'},404));
  await opened(s);if(uncertain)await s.returnReviewQuestion(questionId,fingerprint,reason);
  await s.loadSavedQuestions(caseId);
  assert.equal(s.snapshot().questions,null);assert.equal(s.snapshot().reviewQueue,null);
  assert.equal(s.snapshot().reviewReturnIntent,null);
  assert.ok(!JSON.stringify(s.snapshot()).includes('private question history'));
 }
});
test('late inbox response cannot restore after source refresh, patient switch or disconnect',async()=>{
 for(const change of ['source','patient','disconnect']){
  const delayed=deferred();const s=session(async(url)=>url===queuePath?delayed.promise:
   url.endsWith('/world-model')?response(world()):response(patient('PAT-OTHER-001')));
  s.connect(token);await s.read(patientId);await s.loadCases();
  const pending=s.loadReviewQueue(caseId);
  if(change==='source')await s.loadWorldModel(caseId);
  if(change==='patient')await s.read('PAT-OTHER-001');
  if(change==='disconnect')s.disconnect();
  delayed.resolve(response(queue()));await pending;
  assert.equal(s.snapshot().reviewQueue,null);assert.notEqual(s.snapshot().reviewPhase,'loading');
 }
});

const amendedSource=`OI-SYNTHETIC-REPORT/1\nPatient: ${caseId}\nDocument: REVIEW-INTAKE\nType: pathology\nEvent-Date: 2026-01-01\nIssued-At: 2026-01-03\nSpecimen: REVIEW-SPEC\nFinding: marker|indeterminate|Independently fictional amended statement.\n`;
const sourceIndex=()=>({contract:'oi.synthetic-original-sources/1',patient_id:patientId,case_id:caseId,
 access_receipt_id:'ACCESS-'+'F'.repeat(32),sources:[],source_reported_assertions:[],synthetic:true,
 clinical_interpretation:false,research_review_invalidation_integrated:false});
for(const phase of ['unknown','saving'])test(phase+' return keeps exact retry intent through same-case source import',async()=>{
 const first=deferred(),bodies=[];let imports=0;
 const s=session(async(url,init)=>{
  if(url===queuePath)return response(queue());
  if(url.endsWith('/sources')){
   if(init.method==='GET')return response(sourceIndex());
   imports++;assert.deepEqual(JSON.parse(init.body),{synthetic:true,original_text:amendedSource});
   return response({result:'imported',duplicate:false,source_id:sourceId,version:2},201);
  }
  assert.equal(url,returnPath);bodies.push(JSON.parse(init.body));
  if(bodies.length===1)return phase==='saving'?first.promise:response({},503);
  return response(saved(true));
 });
 await opened(s);await s.loadSources(caseId);await s.loadReviewQueue(caseId);
 const pending=s.returnReviewQuestion(questionId,fingerprint,reason);
 if(phase==='unknown')await pending;
 await s.importSource(caseId,amendedSource,true);
 if(phase==='saving'){first.resolve(response(saved(),201));await pending;}
 assert.equal(imports,1);assert.equal(s.snapshot().importOutcome,'confirmed');
 assert.equal(s.snapshot().reviewQueue,null);assert.equal(s.snapshot().reviewReturn,null);
 assert.equal(s.snapshot().reviewReturnPhase,'unknown');
 assert.deepEqual(s.snapshot().reviewReturnIntent,{patient_id:patientId,case_id:caseId,
  question_id:questionId,queue_fingerprint:fingerprint,reason});
 assert.equal(bodies.length,1,'Source import must not automatically retry a return');
 await s.retryReviewReturn();assert.equal(bodies.length,2);assert.deepEqual(bodies[1],bodies[0]);
 assert.deepEqual(s.snapshot().reviewReturn,saved(true));
});
test('source import authority denial clears the retained verification-return intent',async()=>{
 for(const status of [403,404]){
  const bodies=[];const s=session(async(url,init)=>{
   if(url===queuePath)return response(queue());
   if(url.endsWith('/sources'))return init.method==='GET'?response(sourceIndex()):response({},status);
   bodies.push(JSON.parse(init.body));return response({},503);
  });
  await opened(s);await s.loadSources(caseId);await s.loadReviewQueue(caseId);
  await s.returnReviewQuestion(questionId,fingerprint,reason);
  assert.equal(s.snapshot().reviewReturnPhase,'unknown');
  await s.importSource(caseId,amendedSource,true);
  assert.equal(s.snapshot().importOutcome,'rejected');assert.equal(s.snapshot().sourceIndex,null);
  assert.equal(s.snapshot().reviewQueue,null);assert.equal(s.snapshot().reviewReturnIntent,null);
  assert.ok(!JSON.stringify(s.snapshot()).includes(reason));
  await s.retryReviewReturn();assert.equal(bodies.length,1);
 }
});

test('temporary source refresh failure after amendment preserves an exact return through case recheck',async()=>{
 const bodies=[];let amended=false,caseUnavailable=false;
 const s=session(async(url,init)=>{
  if(url===queuePath)return response(queue());
  if(url.endsWith('/sources')){
   if(init.method==='GET')return amended?response({},503):response(sourceIndex());
   amended=true;return response({result:'imported',duplicate:false,source_id:sourceId,version:2},201);
  }
  assert.equal(url,returnPath);bodies.push(JSON.parse(init.body));
  return bodies.length===1?response({},503):response(saved(true));
 },()=>caseUnavailable?response({},503):response(cases()));
 await opened(s);await s.loadSources(caseId);await s.loadReviewQueue(caseId);
 await s.returnReviewQuestion(questionId,fingerprint,reason);
 assert.equal(s.snapshot().reviewReturnPhase,'unknown');
 await s.importSource(caseId,amendedSource,true);
 assert.equal(s.snapshot().importOutcome,'confirmed');
 assert.equal(s.snapshot().sourceIndex,null);assert.equal(s.snapshot().cases,null);
 assert.equal(s.snapshot().reviewReturnPhase,'unknown');
 await s.retryReviewReturn();
 assert.equal(bodies.length,1,'Missing case metadata must not authorize an automatic or fresh return');
 assert.equal(s.snapshot().reviewReturnPhase,'unknown','A temporary metadata failure must not discard exact recovery');
 caseUnavailable=true;await s.loadCases();
 assert.equal(s.snapshot().cases,null);assert.equal(s.snapshot().reviewReturnPhase,'unknown');
 assert.equal(bodies.length,1);
 caseUnavailable=false;
 await s.loadCases();
 assert.equal(s.snapshot().reviewQueue,null);
 assert.deepEqual(s.snapshot().reviewReturnIntent,{patient_id:patientId,case_id:caseId,
  question_id:questionId,queue_fingerprint:fingerprint,reason});
 assert.equal(s.snapshot().reviewReturnPhase,'unknown');
 assert.equal(bodies.length,1,'Refreshing case authority must not submit the retained return');
 await s.retryReviewReturn();
 assert.equal(bodies.length,2);assert.deepEqual(bodies[1],bodies[0]);
 assert.deepEqual(s.snapshot().reviewReturn,saved(true));
});

for(const metadata of ['cases','sources'])for(const failure of [503,'network','invalid'])
test('inbox refresh after temporary '+metadata+' '+failure+' preserves exact recovery without reading',async()=>{
 const bodies=[];let unavailable=false,queueReads=0;
 const metadataResponse=value=>{
  if(!unavailable)return response(value);
  if(failure==='network')throw Error('temporary fictional metadata transport failure');
  return failure==='invalid'?response({invalid:true}):response({},failure);
 };
 const s=session(async(url,init)=>{
  if(url===queuePath){queueReads++;return response(queue());}
  if(url.endsWith('/sources'))return metadataResponse(sourceIndex());
  assert.equal(url,returnPath);bodies.push(JSON.parse(init.body));
  return bodies.length===1?response({},503):response(saved(true));
 },()=>metadataResponse(cases()));
 await opened(s);await s.returnReviewQuestion(questionId,fingerprint,reason);
 const captured=s.snapshot().reviewReturnIntent;
 unavailable=true;
 if(metadata==='cases')await s.loadCases();else await s.loadSources(caseId);
 assert.equal(s.snapshot().cases,null);assert.equal(s.snapshot().reviewReturnPhase,'unknown');
 for(let refresh=0;refresh<2;refresh++){
  await s.loadReviewQueue(caseId);
  assert.equal(s.snapshot().reviewReturnPhase,'unknown','Inbox refresh must not discard the exact uncertain return');
  assert.equal(s.snapshot().reviewReturnIntent,captured);
  assert.equal(s.snapshot().reviewQueue,null);assert.equal(s.snapshot().cases,null);
  assert.equal(s.snapshot().patient.patient_id,patientId);
  assert.match(s.snapshot().reviewMessage,/Recheck authorized cases/);
  assert.equal(queueReads,1,'Missing metadata cannot authorize another inbox request');
  assert.equal(bodies.length,1,'Inbox refresh must neither retry nor replace a return');
 }
 await s.retryReviewReturn();assert.equal(bodies.length,1);
 unavailable=false;await s.loadCases();
 assert.equal(s.snapshot().reviewReturnIntent,captured);assert.equal(bodies.length,1);
 await s.loadReviewQueue(caseId);assert.equal(queueReads,2);
 await s.retryReviewReturn();assert.deepEqual(bodies[1],bodies[0]);
 assert.deepEqual(s.snapshot().reviewReturn,saved(true));
});

for(const change of ['case','patient','credential'])
test('missing metadata recovery is discarded on '+change+' context change before inbox refresh',async()=>{
 const bodies=[];let unavailable=false,queueReads=0;
 const s=session(async(url,init)=>{
  if(url===queuePath){queueReads++;return response(queue());}
  if(url==='/v1/patients/PAT-OTHER-001')return response(patient('PAT-OTHER-001'));
  assert.equal(url,returnPath);bodies.push(JSON.parse(init.body));return response({},503);
 },()=>unavailable?response({},503):response(cases()));
 await opened(s);await s.returnReviewQuestion(questionId,fingerprint,reason);
 unavailable=true;await s.loadCases();assert.ok(s.snapshot().reviewReturnIntent);
 if(change==='patient')await s.read('PAT-OTHER-001');
 if(change==='credential')s.connect('fictional_replacement_credential_0000000001');
 await s.loadReviewQueue(change==='case'?'CASE-BETA':caseId);
 assert.equal(s.snapshot().reviewReturnIntent,null);assert.equal(s.snapshot().reviewQueue,null);
 assert.ok(!JSON.stringify(s.snapshot()).includes(reason));
 await s.retryReviewReturn();assert.equal(bodies.length,1);assert.equal(queueReads,1);
});

for(const outcome of [401,403,404,'missing','revoked'])test('case recheck '+outcome+' clears the retained exact return',async()=>{
 const bodies=[];let changed=false;
 const s=session(async(url,init)=>{
  if(url===queuePath)return response(queue());
  assert.equal(url,returnPath);bodies.push(JSON.parse(init.body));return response({},503);
 },()=>{
  if(!changed)return response(cases());
  if(typeof outcome==='number')return response({},outcome);
  const value=cases();
  if(outcome==='missing')value.mappings=value.mappings.filter(item=>item.case_id!==caseId);
  else value.mappings=value.mappings.map(item=>item.case_id===caseId?
   {...item,status:'revoked',revision:2,revoked_at:'2026-11-03T10:10:00Z'}:item);
  return response(value);
 });
 await opened(s);await s.returnReviewQuestion(questionId,fingerprint,reason);
 assert.equal(s.snapshot().reviewReturnPhase,'unknown');
 changed=true;await s.loadCases();
 assert.equal(s.snapshot().reviewQueue,null);assert.equal(s.snapshot().reviewReturnIntent,null);
 assert.ok(!JSON.stringify(s.snapshot()).includes(reason));
 await s.retryReviewReturn();assert.equal(bodies.length,1);
});

test('late case recheck cannot restore a retained return after patient change',async()=>{
 const pending=deferred(),bodies=[];let refreshing=false;
 const s=session(async(url,init)=>{
  if(url===queuePath)return response(queue());
  if(url==='/v1/patients/PAT-OTHER-001')return response(patient('PAT-OTHER-001'));
  assert.equal(url,returnPath);bodies.push(JSON.parse(init.body));return response({},503);
 },()=>refreshing?pending.promise:response(cases()));
 await opened(s);await s.returnReviewQuestion(questionId,fingerprint,reason);
 refreshing=true;const reload=s.loadCases();
 await s.read('PAT-OTHER-001');
 pending.resolve(response(cases()));await reload;
 assert.equal(s.snapshot().patient.patient_id,'PAT-OTHER-001');
 assert.equal(s.snapshot().cases,null);assert.equal(s.snapshot().reviewReturnIntent,null);
 assert.equal(s.snapshot().reviewQueue,null);assert.ok(!JSON.stringify(s.snapshot()).includes(reason));
 await s.retryReviewReturn();assert.equal(bodies.length,1);
});

const currentSourceWorld=()=>({...world(),snapshot_fingerprint:'a'.repeat(64),
 as_of_received_at:'2026-11-03T10:00:00Z',
 summary:{current_sources:1,historical_sources:0,current_observations:1,unresolved_observations:1,source_disagreements:0},
 current_sources:[{source_id:sourceId,document_id:'DOC-ONE',version:1,sha256:'e'.repeat(64),kind:'pathology',
  event_date:'2026-01-10',issued_at:'2026-01-11',received_at:'2026-11-03T10:00:00Z',specimen_id:'SPECIMEN-ONE',
  state:'current',supersedes_id:null}],
 observations:[{source_id:sourceId,document_id:'DOC-ONE',document_version:1,source_sha256:'e'.repeat(64),
  source_kind:'pathology',finding_key:'marker',reported_state:'not-reported',source_statement:'Independent fictional statement.',
  source_line:8,specimen_id:'SPECIMEN-ONE',event_date:'2026-01-10',issued_at:'2026-01-11',
  review_state:'not_established',clinical_meaning:null}],unresolved_refs:[{source_id:sourceId,source_line:8}]});
const savedQuestionHistory=()=>({contract:'oi.synthetic-source-questions/2',access_receipt_id:'ACCESS-'+'B'.repeat(32),
 patient_id:patientId,case_id:caseId,synthetic:true,clinical_review_connected:false,clinical_approval:false,
 questions:[{question_id:questionId,patient_id:patientId,case_id:caseId,question:item().question,
  source_id:sourceId,source_line:8,source_sha256:'e'.repeat(64),source_version:1,
  source_snapshot_sha256:'a'.repeat(64),source_snapshot_contract:canonical,preflight_sha256:'b'.repeat(64),
  created_at:'2026-11-03T10:00:00Z',source_context_state:'current_unreviewed_question',
  human_review_state:'not_submitted',clinical_approval:false,model_executed:false}]});

for(const operation of ['brief','preflight'])for(const outcome of [409,503,'network','invalid',401,403,404])
test(operation+' '+outcome+' clears source previews with the correct uncertain-return boundary',async()=>{
 const bodies=[];let attempts=0;
 const s=session(async(url,init)=>{
  if(url===queuePath)return response(queue());
  if(url.endsWith('/world-model'))return response(currentSourceWorld());
  if(url.endsWith('/questions'))return response(savedQuestionHistory());
  if(url.endsWith('/brief')||url.endsWith('/composer/source-preflight')){
   attempts++;
   assert.equal(url.endsWith('/brief'),operation==='brief');
   if(outcome==='network')throw Error('temporary fictional source preparation failure');
   return outcome==='invalid'?response({invalid:true}):response({},outcome);
  }
  assert.equal(url,returnPath);bodies.push(JSON.parse(init.body));
  return bodies.length===1?response({},503):response(saved(true));
 });
 await opened(s);await s.returnReviewQuestion(questionId,fingerprint,reason);
 const captured=s.snapshot().reviewReturnIntent;
 await s.loadWorldModel(caseId);await s.loadSavedQuestions(caseId);
 assert.equal(s.snapshot().worldPhase,'ready');assert.equal(s.snapshot().questionListPhase,'ready');
 if(operation==='brief')await s.prepareSourceBrief(questionId);else await s.prepareSourceContext(sourceId,8);
 assert.equal(attempts,1,'The independently authorized source operation must reach transport');
 assert.equal(s.snapshot().worldModel,null);assert.equal(s.snapshot().questions,null);
 assert.equal(s.snapshot().sourceBrief,null);assert.equal(s.snapshot().sourceQuotePacket,null);
 assert.equal(s.snapshot().composerPreview,null);assert.equal(s.snapshot().reviewQueue,null);
 assert.equal(bodies.length,1,'A failed source operation cannot submit a return');
 if([401,403,404].includes(outcome)){
  assert.equal(s.snapshot().reviewReturnIntent,null);assert.ok(!JSON.stringify(s.snapshot()).includes(reason));
  await s.retryReviewReturn();assert.equal(bodies.length,1);
 }else{
  assert.equal(s.snapshot().reviewReturnPhase,'unknown');assert.equal(s.snapshot().reviewReturnIntent,captured);
  assert.equal(s.snapshot().patient.patient_id,patientId);
  await s.retryReviewReturn();assert.deepEqual(bodies[1],bodies[0]);
  assert.deepEqual(s.snapshot().reviewReturn,saved(true));
 }
});

test('Overview recovery follows the case that the unchanged Review panel will open',async()=>{
 let worldReads=0;const bodies=[];
 const s=session(async(url,init)=>{
  if(url.endsWith('/sources'))return response({...sourceIndex(),
   case_id:url.includes('/cases/CASE-BETA/')?'CASE-BETA':caseId});
  if(url.endsWith('/world-model'))return ++worldReads===1?response(world()):response({},503);
  if(url===queuePath)return response(queue());
  assert.equal(url,returnPath);bodies.push(JSON.parse(init.body));
  return bodies.length===1?response({},503):response(saved(true));
 });
 await opened(s);
 await s.loadSources('CASE-BETA');
 await s.loadWorldModel(caseId);
 await s.loadReviewQueue(caseId);
 await s.returnReviewQuestion(questionId,fingerprint,reason);
 const captured=s.snapshot().reviewReturnIntent;
 assert.equal(s.snapshot().sourceIndex.case_id,'CASE-BETA');
 assert.equal(patientContinuity(s.snapshot()).recoveryCaseId,caseId,
  'A ready World Model is the Review panel winning case even if old record metadata remains');
 await s.loadWorldModel(caseId);
 const afterFailure=s.snapshot();
 assert.equal(afterFailure.worldPhase,'error');assert.equal(afterFailure.worldModel,null);
 assert.equal(afterFailure.sourceIndex.case_id,'CASE-BETA');
 assert.equal(afterFailure.reviewReturnPhase,'unknown');assert.equal(afterFailure.reviewReturnIntent,captured);
 assert.equal(patientContinuity(afterFailure).caseId,null);
 assert.equal(patientContinuity(afterFailure).recoveryCaseId,null,
  'Do not advertise ALPHA recovery when Review falls back to BETA and its inbox refresh would erase the exact ALPHA intent');
 assert.equal(s.snapshot(),afterFailure,'Reading Overview must not mutate retained intent or session state');
 assert.equal(bodies.length,1);
 await s.loadSources(caseId);
 assert.equal(s.snapshot().worldModel,null);
 assert.equal(s.snapshot().sourceIndex.case_id,caseId);
 assert.equal(patientContinuity(s.snapshot()).recoveryCaseId,caseId,
  'A successful same-case source refresh restores discoverability without requiring a World Model');
 assert.equal(s.snapshot().reviewReturnIntent,captured);assert.equal(bodies.length,1);
 await s.retryReviewReturn();assert.deepEqual(bodies[1],bodies[0]);
 assert.deepEqual(s.snapshot().reviewReturn,saved(true));
});
