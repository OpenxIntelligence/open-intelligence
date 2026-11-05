import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {secondOpinionPreparation} from '../.test-dist/second-opinion-preparation.js';
import {caseId,cases,deferred,digest,history,patient,patientId,questionId,response,selectedSource,sourceId,token,world} from './authored-evidence-fixtures.mjs';

const episode={role:'primary',episode_id:'EP-ALPHA'};

async function inspected({recordsContext=episode,journeyContext=episode,ambiguous=false}={}){
 const model=world(),source=model.current_sources[0],obs=model.observations[0];
 const originalText=['OI-SYNTHETIC-REPORT/2','Patient: '+caseId,'Document: '+source.document_id,
  'Type: pathology','Event-Date: '+source.event_date,'Issued-At: '+source.issued_at,'Specimen: '+source.specimen_id,
  recordsContext?'Oncology-Finding: marker|'+recordsContext.role+'|'+(recordsContext.episode_id??'?')+'|not-reported|'+obs.source_statement:
   'Finding: marker|not-reported|'+obs.source_statement,''].join('\n');
 source.sha256=obs.source_sha256=digest(originalText);
 if(journeyContext)obs.oncology=journeyContext;
 const index={contract:'oi.synthetic-original-sources/1',patient_id:patientId,case_id:caseId,
  access_receipt_id:model.access_receipt_id,sources:[source],source_reported_assertions:[{
   source_id:sourceId,source_line:obs.source_line,source_statement:obs.source_statement,
   finding_key:obs.finding_key,reported_state:obs.reported_state,clinical_review_state:'not_established',
   ...(recordsContext?{oncology:recordsContext}:{})}],
  synthetic:true,clinical_interpretation:false,research_review_invalidation_integrated:false};
 if(ambiguous)index.source_reported_assertions.push({...index.source_reported_assertions[0],
  oncology:{...episode,episode_id:'EP-BETA'}});
 const original={source_id:sourceId,case_id:caseId,access_receipt_id:model.access_receipt_id,
  document_id:source.document_id,version:source.version,state:source.state,sha256:source.sha256,
  original_text:originalText,synthetic:true,clinical_review_state:'not_established'};
 const calls=[],writes=[],documentReply=deferred(),replies=new Map();
 let worldReply=()=>response(model);
 const session=new RegistrySession(async (url,init)=>{
  calls.push(url);
  const action=url.endsWith('/source-preflight')?'preflight':url.endsWith('/brief')?'brief':
   url.endsWith('/source-review-packet')?'packet':url.endsWith('/questions')?(init.method==='POST'?'save':'history'):
   url.endsWith('/sources')?'sources':url.endsWith('/followthrough')?'followthrough':null;
  if(action==='save')writes.push(init.body);
  if(replies.has(action))return replies.get(action)();
  if(action==='save')return response({question_id:questionId,duplicate:true});
  if(action==='history'){
   const items=history();items.questions[0].source_sha256=source.sha256;
   return response(items);
  }
  if(action==='preflight')return response({contract:'oi.synthetic-source-composer-preflight/2',
   source_snapshot_contract:model.contract,access_receipt_id:model.access_receipt_id,patient_id:patientId,
   case_id:caseId,question:JSON.parse(init.body).question,source_snapshot_sha256:model.snapshot_fingerprint,
   selected_source:{...selectedSource(),sha256:source.sha256,oncology:obs.oncology},
   source_context_only:true,biomedical_evidence_rights_verified:false,model_execution_authorized:false,
   durable_question_created:false,durable_review_connected:false,clinical_approval:false,clinical_interpretation:'not_performed',
   reassessment_policy:'revalidate_source_and_authority_before_any_future_write',limitations:'Fictional source only.',
   preflight_sha256:'b'.repeat(64)});
  if(url.endsWith('/case-bindings'))return response(cases());
  if(url.endsWith('/sources'))return response(index);
  if(url.endsWith('/sources/'+sourceId))return response(original);
  if(url.endsWith('/world-model'))return worldReply();
  if(url.endsWith('/documents'))return documentReply.promise;
  assert.equal(url,'/v1/patients/'+patientId);
  return response(patient());
 });
 session.connect(token);await session.read(patientId);await session.loadCases();await session.loadSources(caseId);
 await session.loadOriginal(sourceId);
 assert.equal(session.snapshot().original?.original_text,originalText);
 return {session,calls,writes,replies,documentReply,changeWorld:(reply=()=>response(model))=>{worldReply=reply;}};
}

for(const status of [403,404])test('World Model '+status+' clears inspected Records and blocks late document reads until case reauthorization',async()=>{
 const {session,calls,documentReply,changeWorld}=await inspected();
 await session.loadWorldModel(caseId);assert.equal(session.snapshot().worldPhase,'ready');
 const verifiedPatient=session.snapshot().patient,worldReply=deferred();
 changeWorld(()=>worldReply.promise);
 const worldRead=session.loadWorldModel(caseId),doc=session.documentRequest(caseId,'');
 worldReply.resolve(new Response('private denial',{status}));await worldRead;
 documentReply.resolve(response({patient_id:patientId,case_id:caseId}));
 await assert.rejects(doc,/changed/);
 const view=session.snapshot();
 assert.equal(view.patient,verifiedPatient);assert.equal(view.connected,true);
 assert.equal(view.worldPhase,'error');assert.equal(view.recordsPhase,'error');
 for(const field of ['worldModel','cases','sourceIndex','original'])assert.equal(view[field],null,field);
 assert.doesNotMatch(JSON.stringify(view),/private denial|EP-ALPHA/);
 const count=calls.length;
 await session.loadOriginal(sourceId);await session.loadSources(caseId);
 assert.equal(await session.beginQuestionFromSourceReading(caseId,sourceId,8),false);
 assert.equal(calls.length,count,'case-dependent actions require a fresh mapping');
 await session.loadCases();await session.loadSources(caseId);await session.loadOriginal(sourceId);
 assert.ok(session.snapshot().original,'reopening Records requires new reads');
});

test('temporary World Model failure preserves independently verified Records and permits retry',async()=>{
 const {session,changeWorld}=await inspected();const before=session.snapshot();
 changeWorld(()=>response({},503));await session.loadWorldModel(caseId);
 const view=session.snapshot();
 assert.equal(view.worldPhase,'error');assert.equal(view.worldModel,null);
 for(const field of ['patient','cases','sourceIndex','original'])assert.equal(view[field],before[field],field);
 changeWorld();await session.loadWorldModel(caseId);
 assert.equal(session.snapshot().worldPhase,'ready');
});

for(const [label,recordsContext,journeyContext,allowed] of [
 ['same role and episode',episode,episode,true],
 ['same unassigned origin',{role:'metastasis',episode_id:null},{role:'metastasis',episode_id:null},true],
 ['changed episode',episode,{...episode,episode_id:'EP-BETA'},false],
 ['changed role',episode,{...episode,role:'metastasis'},false],
 ['lost attribution',{role:'metastasis',episode_id:null},null,false],
 ['added attribution',null,episode,false],
]){
 test('Records to Journey handoff: '+label,async()=>{
  const {session}=await inspected({recordsContext,journeyContext});
  assert.equal(await session.beginQuestionFromSourceReading(caseId,sourceId,8),allowed);
  if(allowed)assert.equal(session.snapshot().questionDraft?.source_id,sourceId);
  else{
   assert.equal(session.snapshot().questionDraft,null);
   assert.equal(session.snapshot().worldModel,null);
   assert.equal(session.snapshot().worldPhase,'error');
  }
 });
}

test('Records cannot hand off a line with two conflicting episode attributions',async()=>{
 const {session,calls}=await inspected({ambiguous:true});
 const count=calls.length;
 assert.equal(await session.beginQuestionFromSourceReading(caseId,sourceId,8),false);
 assert.equal(session.snapshot().questionDraft,null);
 assert.equal(calls.length,count);
});

const questionOperations={
 preflight:s=>s.prepareDraftQuestion(),save:s=>s.savePreparedQuestion(),history:s=>s.loadSavedQuestions(caseId),
 brief:s=>s.prepareSourceBrief(questionId),packet:s=>s.loadQuestionSourcePacket(questionId),
};
async function preparedWorkflow(){
 const fixture=await inspected(),s=fixture.session;
 await s.loadWorldModel(caseId);s.chooseQuestionDraft(sourceId,8);
 s.changeQuestionDraft('Which fictional episode requires independent verification?');
 await s.prepareDraftQuestion();
 assert.ok(s.snapshot().composerPreview);
 await s.loadSavedQuestions(caseId);
 assert.ok(s.snapshot().original&&s.snapshot().questions);
 return fixture;
}
for(const [action,request] of Object.entries(questionOperations)){
 for(const status of [403,404])test(action+' '+status+' with revoked source access clears all inspected presentations',async()=>{
  const {session:s,replies,changeWorld}=await preparedWorkflow();
  replies.set(action,()=>new Response('private denial',{status}));
  changeWorld(()=>new Response('private denial',{status}));
  await request(s);
  const state=s.snapshot();
  assert.equal(state.patient.patient_id,patientId);assert.equal(state.connected,true);
  for(const field of ['cases','sourceIndex','worldModel','original','questionDraft','composerPreview','questions','sourceBrief','sourceQuotePacket'])
   assert.equal(state[field],null,field);
  assert.doesNotMatch(JSON.stringify(state),/private denial|EP-ALPHA|Which fictional episode/);
 });
 test('a late '+action+' denial cannot clear a newly reopened source',async()=>{
  const {session:s,replies}=await preparedWorkflow(),held=deferred();
  replies.set(action,()=>held.promise);
  const waiting=request(s);
  await s.loadSources(caseId);await s.loadOriginal(sourceId);await s.loadWorldModel(caseId);
  const fresh=s.snapshot();
  held.resolve(response({},404));await waiting;
  for(const field of ['cases','sourceIndex','worldModel','original'])assert.equal(s.snapshot()[field],fresh[field],field);
 });
}

test('a denied retry withholds all source text and recovers the exact original save after reauthorization',async()=>{
 const {session:s,replies,writes,changeWorld}=await preparedWorkflow();
 const {question}=s.snapshot().composerPreview;
 replies.set('save',()=>response({},503));await s.savePreparedQuestion();
 assert.match(s.snapshot().questionSaveMessage,/outcome unknown/);
 changeWorld(()=>response({},404));replies.set('save',()=>response({},404));await s.savePreparedQuestion();
 assert.doesNotMatch(JSON.stringify(s.snapshot()),/Which fictional episode|EP-ALPHA/);
 const count=writes.length;
 await s.savePreparedQuestion();assert.equal(writes.length,count);
 replies.delete('save');changeWorld();
 await s.loadCases();await s.loadWorldModel(caseId);
 s.chooseQuestionDraft(sourceId,8);s.changeQuestionDraft(question);
 await s.prepareDraftQuestion();await s.savePreparedQuestion();
 assert.ok(s.snapshot().savedQuestion.duplicate);assert.equal(writes.length,3);
 await s.savePreparedQuestion();assert.equal(writes.length,4);
 assert.equal(new Set(writes).size,1,'reauthorization must not create a new command');
});

test('a delayed source recheck cannot redisplay protected content after a credential switch',async()=>{
 const {session:s,replies,changeWorld,calls}=await preparedWorkflow();
 const started=deferred(),held=deferred();
 replies.set('packet',()=>response({},404));
 changeWorld(()=>{started.resolve();return held.promise;});
 const pending=s.loadQuestionSourcePacket(questionId);await started.promise;
 const view=s.snapshot();
 for(const field of ['original','sourceIndex','worldModel','questions','composerPreview'])assert.equal(view[field],null,field);
 const count=calls.length;
 s.connect(token+'2');
 held.resolve(response(world()));await pending;
 assert.equal(s.snapshot().patient,null);assert.equal(s.snapshot().cases,null);
 assert.equal(calls.length,count,'never check another case mapping or history with the replacement credential');
});

test('a question-only denial permits source inspection after fresh verification but keeps the rejected question list hidden',async()=>{
 const {session:s,replies,calls}=await preparedWorkflow();
 const old=s.snapshot().worldModel;
 replies.set('history',()=>response({},403));const count=calls.length;
 await s.loadSavedQuestions(caseId);
 assert.deepEqual(calls.slice(count).map(url=>url.split('/').at(-1)),['questions','world-model','case-bindings','sources']);
 assert.notEqual(s.snapshot().worldModel,old);assert.deepEqual(s.snapshot().worldModel,old);
 assert.equal(s.snapshot().questionListPhase,'error');assert.equal(s.snapshot().questions,null);
 assert.equal(s.snapshot().original,null);
});

test('Overview shows reassessment after independent question access returns and Records has a fresh source receipt',async()=>{
 const {session:s,replies}=await preparedWorkflow(),earlier=s.snapshot().sourceIndex;
 const nextReceipt='ACCESS-'+'E'.repeat(32);
 replies.set('sources',()=>response({...earlier,access_receipt_id:nextReceipt}));
 replies.set('history',()=>response({},404));await s.loadSavedQuestions(caseId);
 assert.equal(s.snapshot().sourceIndex?.access_receipt_id,nextReceipt);
 assert.equal(s.snapshot().original,null);
 assert.equal(secondOpinionPreparation(s.snapshot()).state,'needs_check');
 const items=history();items.questions[0].source_sha256=earlier.sources[0].sha256;
 items.questions.push({...items.questions[0],question_id:'QUESTION-'+'B'.repeat(32),
  source_snapshot_sha256:'f'.repeat(64),source_context_state:'source_reassessment_required'});
 replies.set('history',()=>response(items));
 replies.set('followthrough',()=>response({contract:'oi.pg-question-followthrough/1',patient_id:patientId,case_id:caseId,
  access_receipt_id:'ACCESS-'+'F'.repeat(32),evaluated_on:'2026-11-05',tasks:[],synthetic:true,
  clinical_approval:false,external_notification_sent:false}));
 await s.loadSavedQuestions(caseId);await s.loadFollowthrough(caseId);
 const view=secondOpinionPreparation(s.snapshot());
 assert.equal(view.state,'needs_reassessment');
 assert.deepEqual(view.questions,{current:1,reassessment:1});assert.deepEqual(view.records,{current:1,historical:0});
 assert.equal(view.coordination.open,0);
});

test('a denied source-index recheck clears Records even when the other independent reads succeeded',async()=>{
 const {session:s,replies}=await preparedWorkflow();
 replies.set('history',()=>response({},403));replies.set('sources',()=>response({},404));
 await s.loadSavedQuestions(caseId);
 for(const field of ['original','sourceIndex','worldModel','cases','questions'])assert.equal(s.snapshot()[field],null,field);
 assert.equal(secondOpinionPreparation(s.snapshot()),null);
});

test('a late source index cannot restore Records after switching credentials during the recheck',async()=>{
 const {session:s,replies}=await preparedWorkflow(),index=s.snapshot().sourceIndex;
 const started=deferred(),held=deferred();
 replies.set('history',()=>response({},403));replies.set('sources',()=>{started.resolve();return held.promise;});
 const waiting=s.loadSavedQuestions(caseId);await started.promise;
 assert.equal(s.snapshot().original,null);assert.equal(s.snapshot().sourceIndex,null);
 s.connect(token+'2');held.resolve(response(index));await waiting;
 for(const field of ['patient','cases','sourceIndex','original','worldModel'])assert.equal(s.snapshot()[field],null,field);
});
