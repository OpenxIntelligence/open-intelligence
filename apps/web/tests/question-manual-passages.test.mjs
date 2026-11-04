import {test} from 'node:test';
import assert from 'node:assert/strict';
import {QuestionPassageClient,decodeManualContext,decodeSelection} from '../.test-dist/question-passages.js';
import * as manualModule from '../.test-dist/question-passages.js';
import {decodeEvidenceReport} from '../.test-dist/authored-evidence.js';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {question,report,reportId,patientId,caseId,questionId,hash,ready,transportFor,response,packet,world,deferred,cases} from './authored-evidence-fixtures.mjs';
import {sourceIndex} from './source-images-fixtures.mjs';

const scope={patient_id:patientId,case_id:caseId,question_id:questionId};
function sign(value){const {context_sha256,access_receipt_id,...content}=value;return {...value,context_sha256:hash(content)};}
function context(empty=false){
 const anchor={patient_id:patientId,case_id:caseId,source_id:'SRC-'+'B'.repeat(32),document_id:'DOC-MANUAL',source_version:1,
  original_sha256:'a'.repeat(64),extraction_method:'pypdf-text-v1',extraction_sha256:'b'.repeat(64),annotation_revision_id:'ANN-'+'C'.repeat(32),
  annotation_revision:1,review_sha256:'c'.repeat(64),selected_by:'FIXTURE-ACTOR',selected_at:'2026-11-03T11:00:00Z',selection_key:'marker',
  selected_state:'pending',quote:'A fictional 🧪 marker remains pending.',line:2,page:2,classification_origin:'user_selected',clinical_review:'not_performed'};
 return sign({contract:'oi.question-manual-passages/1',...scope,revision_id:empty?null:'PASSAGES-'+'D'.repeat(32),revision:empty?0:1,
  attached_by:empty?null:'FIXTURE-ACTOR',attached_at:empty?null:'2026-11-03T12:00:00Z',
  passages:empty?[]:[{anchor,anchor_sha256:hash(anchor),source_state:'current',latest_annotation_revision_id:anchor.annotation_revision_id,selection_state:'current_unreviewed_selection'}],
  state:'current_unreviewed',access_receipt_id:'ACCESS-'+'E'.repeat(32)});
}
const ref=()=>{const p=context().passages[0],a=p.anchor;return {source_id:a.source_id,annotation_revision_id:a.annotation_revision_id,selection_key:a.selection_key,anchor_sha256:p.anchor_sha256};};

test('exact manual PDF context and frozen report retain physical page, attribution and separate classification',async()=>{
 const value=context(),got=await decodeManualContext(value,scope,true);
 assert.equal(got.passages[0].anchor.page,2);assert.equal(got.passages[0].anchor.selected_by,'FIXTURE-ACTOR');
 assert.ok(Object.isFrozen(got.passages[0].anchor));
 const selection={...value.passages[0],contract:'oi.reviewed-document-selection/1',synthetic:true,clinical_approval:false,model_execution:false,access_receipt_id:value.access_receipt_id};
 assert.equal((await decodeSelection(selection,scope,ref())).anchor_sha256,ref().anchor_sha256);
 const {access_receipt_id,...frozen}=value,r=report();r.snapshot.manual_passages=frozen;r.snapshot_sha256=hash(r.snapshot);
 assert.deepEqual((await decodeEvidenceReport(r,question(),reportId)).snapshot.manual_passages,frozen);
 r.snapshot.manual_passages.question_id='QUESTION-'+'F'.repeat(32);r.snapshot.manual_passages=sign(r.snapshot.manual_passages);r.snapshot_sha256=hash(r.snapshot);
 await assert.rejects(()=>decodeEvidenceReport(r,question(),reportId));
});

test('false provenance, forged freshness, foreign scope and duplicate anchors fail closed after rehashing',async()=>{
 const changes=[c=>c.patient_id='PAT-OTHER',c=>c.question_id='QUESTION-'+'F'.repeat(32),c=>c.passages[0].anchor.classification_origin='source_authored',
  c=>c.passages[0].anchor.clinical_review='approved',c=>c.passages[0].anchor.line=true,c=>c.passages[0].anchor.page=null,
  c=>c.passages[0].anchor.selected_at='2026-11-03T12:00:00+00:99',c=>c.passages[0].anchor.selected_at='2026-02-30T12:00:00Z',
  c=>c.passages[0].selection_state='selection_reassessment_required',c=>c.revision=true,c=>c.state='reassessment_required',
  c=>c.passages.push(structuredClone(c.passages[0])),c=>{const p=structuredClone(c.passages[0]);p.anchor.quote='Changed quotation';c.passages.push(p);}];
 for(const change of changes){const c=context();change(c);c.passages.forEach(p=>p.anchor_sha256=hash(p.anchor));await assert.rejects(()=>decodeManualContext(sign(c),scope,true));}
 const c=context();c.passages[0].anchor.quote='Silently changed';await assert.rejects(()=>decodeManualContext(c,scope,true));
});

test('lost manual-context response preserves byte-identical retry and recovers one revision',async()=>{
 const sent=[];let saved=false;
 const client=new QuestionPassageClient(scope,async body=>{
  if(!body)return {status:200,body:context(!saved)};
  sent.push(body);if(!saved){saved=true;throw Error('Response lost after commit');}
  return {status:200,body:{revision_id:context().revision_id,question_id:questionId,duplicate:true}};
 });
 await client.load();await client.replace([ref()]);assert.equal(client.snapshot().phase,'uncertain');assert.equal(client.snapshot().packet,null);
 await client.replace([]);assert.equal(sent.length,1);await client.retry();
 assert.deepEqual(sent,[sent[0],sent[0]]);assert.equal(client.snapshot().packet.revision,1);assert.equal(client.snapshot().pending,null);
 assert.equal(JSON.parse(sent[0]).expected_context_sha256,context(true).context_sha256);
});

test('denial or conflict clears local disclosure, while malformed success keeps exact uncertain intent',async()=>{
 for(const status of [401,403,404,409]){
  const client=new QuestionPassageClient(scope,async body=>body?{status,body:'PRIVATE'}:{status:200,body:context()});
  await client.load();await client.replace([]);assert.equal(client.snapshot().phase,'error');assert.equal(client.snapshot().packet,null);assert.equal(client.snapshot().pending,null);
 }
 const client=new QuestionPassageClient(scope,async body=>body?{status:201,body:{revision_id:context().revision_id,question_id:'QUESTION-'+'F'.repeat(32),duplicate:false}}:{status:200,body:context()});
 await client.load();await client.replace([]);assert.equal(client.snapshot().phase,'uncertain');assert.ok(client.snapshot().pending);
});

test('late reads cannot replace a newer context or repopulate a disposed patient scope',async()=>{
 const held=deferred();let calls=0;
 const client=new QuestionPassageClient(scope,async()=>++calls===1?held.promise:{status:200,body:context(true)});
 const old=client.load();await client.load();held.resolve({status:200,body:context()});await old;
 assert.equal(client.snapshot().packet.revision,0);
 const second=deferred(),disposed=new QuestionPassageClient(scope,()=>second.promise);const reading=disposed.load();disposed.dispose();second.resolve({status:200,body:context()});await reading;
 assert.equal(disposed.snapshot().packet,null);
});

async function sessionFor(reply){
 const sourceIndex={contract:'oi.synthetic-original-sources/1',patient_id:patientId,case_id:caseId,access_receipt_id:'ACCESS-'+'C'.repeat(32),sources:world().current_sources,source_reported_assertions:[],synthetic:true,clinical_interpretation:false,research_review_invalidation_integrated:false};
 const fallback=transportFor(()=>response(packet()));
 const session=new RegistrySession((url,init)=>url.endsWith('/sources')?response(sourceIndex):url.endsWith('/manual-passages')||url.includes('/selections/')?reply(url,init):fallback(url,init));
 await ready(session);await session.loadSources(caseId);await session.loadWorldModel(caseId);await session.loadSavedQuestions(caseId);await session.loadQuestionEvidence(questionId);
 return session;
}
for(const status of [401,403,404])test(`manual-context ${status} clears shared patient content and rejects a late read`,async()=>{
 const held=deferred();let calls=0;const session=await sessionFor(()=>++calls===1?held.promise:new Response('PRIVATE',{status}));
 const old=session.questionPassageRequest(caseId,questionId),rejection=assert.rejects(old,/changed/);
 assert.equal((await session.questionPassageRequest(caseId,questionId)).status,status);
 assert.equal(session.snapshot().evidencePacket,null);assert.equal(session.snapshot().sourceIndex,null);
 held.resolve(response(context()));await rejection;
 assert.equal(session.snapshot().evidencePacket,null);
});
test('selection transport validates scope inside the immutable source anchor',async()=>{
 const c=context(),p=c.passages[0],selection={...p,contract:'oi.reviewed-document-selection/1',synthetic:true,clinical_approval:false,model_execution:false,access_receipt_id:c.access_receipt_id};
 const session=await sessionFor(()=>response(selection));
 const path='/'+p.anchor.source_id+'/selections/'+p.anchor.annotation_revision_id+'/'+p.anchor.selection_key;
 assert.equal((await session.documentRequest(caseId,path)).status,200);
 selection.anchor.patient_id='PAT-OTHER';await assert.rejects(()=>session.documentRequest(caseId,path),/scope/);
});

test('manual context has independent question authority without a loaded Records source-index',async()=>{
 const fallback=transportFor(()=>response(packet()));
 const session=new RegistrySession((url,init)=>url.endsWith('/manual-passages')?response(context(true)):fallback(url,init));
 await ready(session);await session.loadWorldModel(caseId);await session.loadSavedQuestions(caseId);await session.loadQuestionEvidence(questionId);
 assert.equal(session.snapshot().sourceIndex,null);
 assert.equal((await session.questionPassageRequest(caseId,questionId)).status,200);
});
test('question document picker has independent question authority without a loaded Records source-index',async()=>{
 const fallback=transportFor(()=>response(packet()));
 const session=new RegistrySession((url,init)=>url.endsWith('/documents')?response({patient_id:patientId,case_id:caseId,documents:[]}):fallback(url,init));
 await ready(session);await session.loadWorldModel(caseId);await session.loadSavedQuestions(caseId);await session.loadQuestionEvidence(questionId);
 assert.equal(session.snapshot().sourceIndex,null);
 assert.equal((await session.documentRequest(caseId,'',undefined,questionId)).status,200);
});

test('denied recovery retains the exact uncertain request until authority returns',async()=>{
 const sent=[];let step=0;
 const client=new QuestionPassageClient(scope,async body=>{
  if(!body)return {status:200,body:context(step===0)};
  sent.push(body);step++;if(step===1)throw Error('Lost committed response');
  if(step===2)return {status:404,body:{detail:'Unavailable'}};
  return {status:200,body:{revision_id:context().revision_id,question_id:questionId,duplicate:true}};
 });
 await client.load();await client.replace([ref()]);const exact=client.snapshot().pending;
 await client.retry();assert.equal(client.snapshot().phase,'uncertain');assert.equal(client.snapshot().pending,exact);
 await client.retry();assert.equal(client.snapshot().packet.revision,1);assert.deepEqual(sent,[exact,exact,exact]);
});

test('session-owned exact intent survives an in-flight panel disposal and evidence refresh',async()=>{
 const held=deferred(),session=await sessionFor(()=>response(context(true)));
 assert.equal(typeof session.manualPassageIntentStore,'function','manual recovery needs the existing session owner');
 const store=session.manualPassageIntentStore(scope),sent=[];
 const request=async body=>{if(!body)return {status:200,body:context(true)};sent.push(body);return held.promise;};
 const first=new QuestionPassageClient(scope,request,store);await first.load();const saving=first.replace([ref()]);
 const exact=first.snapshot().pending;first.dispose();await session.loadQuestionEvidence(questionId);
 held.resolve({status:201,body:{revision_id:context().revision_id,question_id:questionId,duplicate:false}});await saving;
 const recovered=new QuestionPassageClient(scope,async body=>body?(sent.push(body),{status:200,body:{revision_id:context().revision_id,question_id:questionId,duplicate:true}}):{status:200,body:context()},session.manualPassageIntentStore(scope));
 assert.equal(recovered.snapshot().phase,'uncertain');assert.equal(recovered.snapshot().pending,exact);
 assert.equal(recovered.snapshot().packet,null,'retained identifiers are not content disclosure authority');
 await recovered.retry();assert.deepEqual(sent,[exact,exact]);assert.equal(store.read(),null);
});

test('unsaved additions and removals block report binding until explicit save or discard',()=>{
 assert.equal(typeof manualModule.manualReportBinding,'function');
 const packet=context(),saved=packet.passages;
 assert.equal(manualModule.manualReportBinding(packet,saved,'idle').blocked,false);
 const removed=manualModule.manualReportBinding(packet,[],'idle');assert.equal(removed.blocked,true);assert.equal(removed.context,null);
 assert.equal(manualModule.manualReportBinding(context(true),saved,'idle').blocked,true);
 assert.equal(manualModule.manualReportBinding(packet,saved,'saving').blocked,true);
 assert.equal(manualModule.manualReportBinding(null,[],'uncertain').blocked,true);
 assert.equal(manualModule.manualReportBinding(packet,saved,'idle').context.context_sha256,packet.context_sha256);
});

function draftStore(){let value=null;return {read:()=>value,write:next=>{value=next;}};}
function selectionReply(p=context().passages[0]){return {status:200,body:{...p,contract:'oi.reviewed-document-selection/1',synthetic:true,clinical_approval:false,model_execution:false,access_receipt_id:context().access_receipt_id}};}

test('unsaved additions resume only after fresh context and exact selection checks, without writes',async()=>{
 const store=draftStore(),held=deferred();let writes=0,reads=0;
 const request=async body=>{if(body)writes++;return {status:200,body:context(true)};};
 const first=new QuestionPassageClient(scope,request,undefined,store,async()=>selectionReply());
 await first.load();assert.equal(first.choose?.(context().passages[0]),true);
 assert.equal(JSON.stringify(store.read()).includes('fictional'),false,'draft store must contain references, not quotations');
 first.dispose();
 const resumed=new QuestionPassageClient(scope,request,undefined,store,async()=>{reads++;return held.promise;});
 const checking=resumed.load();await new Promise(resolve=>setTimeout(resolve,0));
 assert.equal(resumed.snapshot().chosen.length,0,'no cached quotation while fresh authority is pending');
 held.resolve(selectionReply());await checking;
 assert.equal(reads,1);assert.equal(resumed.snapshot().chosen[0].anchor_sha256,ref().anchor_sha256);
 assert.equal(resumed.snapshot().draftStatus,'ready');assert.equal(writes,0);
 await resumed.load();assert.equal(resumed.snapshot().chosen.length,1);assert.equal(writes,0);
});

test('unsaved removal survives refresh; changed saved context blocks reuse until explicit discard',async()=>{
 const store=draftStore();let changed=false;
 const client=new QuestionPassageClient(scope,async()=>({status:200,body:context(changed)}),undefined,store,async()=>selectionReply());
 await client.load();assert.equal(client.remove?.(ref().anchor_sha256),true);await client.load();
 assert.deepEqual(client.snapshot().chosen,[]);assert.equal(client.snapshot().draftStatus,'ready');
 changed=true;await client.load();assert.equal(client.snapshot().draftStatus,'conflict');
 assert.deepEqual(client.snapshot().chosen,[]);await client.discardDraft();
 assert.equal(store.read(),null);assert.equal(client.snapshot().draftStatus,'none');
});

for(const status of [401,403,404,503])test(`resumed selection ${status} withholds text and handles draft retention`,async()=>{
 const store=draftStore();let denied=false;
 const client=new QuestionPassageClient(scope,async()=>({status:200,body:context(true)}),undefined,store,async()=>denied?{status,body:null}:selectionReply());
 await client.load();assert.equal(client.choose?.(context().passages[0]),true);denied=true;await client.load();
 assert.deepEqual(client.snapshot().chosen,[]);assert.equal(client.snapshot().packet,null);
 assert.equal(store.read()!==null,status===503);
});

test('a corrected exact selection blocks draft reuse even when the saved passage set did not change',async()=>{
 const store=draftStore();let changed=false;
 const client=new QuestionPassageClient(scope,async()=>({status:200,body:context(true)}),undefined,store,async()=>{
  const p=structuredClone(context().passages[0]);if(changed){p.latest_annotation_revision_id='ANN-'+'F'.repeat(32);p.selection_state='selection_reassessment_required';}
  return selectionReply(p);
 });
 await client.load();assert.equal(client.choose?.(context().passages[0]),true);changed=true;await client.load();
 assert.equal(client.snapshot().draftStatus,'conflict');assert.deepEqual(client.snapshot().chosen,[]);
 assert.ok(store.read());
});

test('session draft survives evidence refresh but denial clears it and invalidates old store callbacks',async()=>{
 const session=await sessionFor(()=>response({},403));
 const store=session.manualPassageDraftStore(scope),draft=Object.freeze({expected_context_sha256:context(true).context_sha256,references:Object.freeze([ref()])});
 store.write(draft);await session.loadQuestionEvidence(questionId);assert.equal(store.read(),draft);
 await session.questionPassageRequest(caseId,questionId);
 await ready(session);await session.loadQuestionEvidence(questionId);
 const fresh=session.manualPassageDraftStore(scope);assert.equal(fresh.read(),null);
 fresh.write(draft);store.write(null);assert.equal(fresh.read(),draft,'late clearing cannot erase a new draft');
 session.disconnect();store.write(draft);fresh.write(draft);
 await ready(session);await session.loadQuestionEvidence(questionId);
 assert.equal(session.manualPassageDraftStore(scope).read(),null);
});

test('disposing during retained selection checks cannot revive quotations or lose the retained reference draft',async()=>{
 const store=draftStore(),held=deferred();store.write(Object.freeze({expected_context_sha256:context(true).context_sha256,references:Object.freeze([ref()])}));
 const client=new QuestionPassageClient(scope,async()=>({status:200,body:context(true)}),undefined,store,()=>held.promise);
 const checking=client.load();await new Promise(resolve=>setTimeout(resolve,0));client.dispose();held.resolve(selectionReply());await checking;
 assert.equal(client.snapshot().packet,null);assert.deepEqual(client.snapshot().chosen,[]);assert.ok(store.read());
});

test('saving unsent choices transfers recovery to the exact command, and conflict blocks submission',async()=>{
 const store=draftStore(),intent=draftStore();let writes=0,changed=false;
 const request=async body=>{if(body){writes++;throw Error('Response lost');}return {status:200,body:context(!changed)};};
 const client=new QuestionPassageClient(scope,request,intent,store,async()=>selectionReply());
 await client.load();client.choose(context().passages[0]);changed=true;await client.load();
 assert.equal(client.snapshot().draftStatus,'conflict');await client.replace([ref()]);assert.equal(writes,0);
 await client.discardDraft();client.remove(ref().anchor_sha256);await client.replace([]);
 assert.equal(store.read(),null);assert.ok(intent.read());assert.equal(client.snapshot().phase,'uncertain');
 assert.deepEqual(client.snapshot().chosen,[]);assert.equal(writes,1);
 assert.equal(manualModule.manualReportBinding(context(true),[],'idle','conflict').blocked,true);
});

for(const status of [503,403])test(`question list retry after ${status} distinguishes temporary failure from revoked authority`,async()=>{
 let fail=false;const fallback=transportFor(()=>response(packet()));
 const session=new RegistrySession((url,init)=>fail&&url.endsWith('/questions')?response({},status):fallback(url,init));
 await ready(session);const store=session.manualPassageDraftStore(scope);
 const draft=Object.freeze({expected_context_sha256:context(true).context_sha256,references:Object.freeze([ref()])});
 store.write(draft);fail=true;await session.loadSavedQuestions(caseId);assert.equal(store.read(),null,'failed question read withholds draft access');
 fail=false;await session.loadSavedQuestions(caseId);
 assert.equal(session.manualPassageDraftStore(scope).read(),status===503?draft:null);
 await session.loadSavedQuestions('CASE-OTHER');await session.loadSavedQuestions(caseId);
 assert.equal(session.manualPassageDraftStore(scope).read(),null,'an actual case switch clears unsent choices');
});

for(const status of [400,409,422])test(`definitive save rejection ${status} retains the unsent reference set for explicit resolution`,async()=>{
 const store=draftStore(),intent=draftStore();let changed=false;
 const client=new QuestionPassageClient(scope,async body=>body?{status,body:null}:{status:200,body:context(!changed)},intent,store,async()=>selectionReply());
 await client.load();client.choose(context().passages[0]);const draft=store.read();
 changed=true;await client.replace([ref()]);
 assert.equal(intent.read(),null,'a known rejection is not an uncertain commit');
 assert.equal(store.read(),draft,'known rejection must not discard unsent work');
 await client.load();assert.equal(client.snapshot().draftStatus,'conflict');assert.deepEqual(client.snapshot().chosen,[]);
 await client.discardDraft();assert.equal(store.read(),null);assert.equal(client.snapshot().draftStatus,'none');
});

for(const [suffix,refresh] of [
 ['/case-bindings',s=>s.loadCases()],['/sources',s=>s.loadSources(caseId)],['/world-model',s=>s.loadWorldModel(caseId)],
])for(const status of [200,503,403,404])test(`same-case ${suffix} refresh ${status} retains only reauthorizable drafts`,async()=>{
 let override=false,writes=0;const fallback=transportFor(()=>response(packet()));
 const session=new RegistrySession((url,init)=>{
  if(init.method==='POST')writes++;
  if(override&&url.endsWith(suffix)&&status!==200)return response({},status);
  return url.endsWith('/sources')?response(sourceIndex()):fallback(url,init);
 });
 await ready(session);const oldStore=session.manualPassageDraftStore(scope);
 const draft=Object.freeze({expected_context_sha256:context(true).context_sha256,references:Object.freeze([ref()])});
 oldStore.write(draft);override=true;await refresh(session);
 assert.equal(oldStore.read(),null,'refresh invalidates prior callbacks and withholds draft access');
 override=false;await session.loadCases();await session.loadWorldModel(caseId);await session.loadSavedQuestions(caseId);
 const fresh=session.manualPassageDraftStore(scope),retained=[200,503].includes(status);
 assert.equal(fresh.read(),retained?draft:null,'temporary rechecks retain references; authority denial clears them');
 if(retained){
  let checks=0;const client=new QuestionPassageClient(scope,async()=>({status:200,body:context(true)}),undefined,fresh,async()=>{checks++;return selectionReply();});
  assert.deepEqual(client.snapshot().chosen,[]);await client.load();
  assert.equal(checks,1);assert.equal(client.snapshot().chosen.length,1);
 }
 const replacement=Object.freeze({...draft,references:Object.freeze([])});fresh.write(replacement);
 oldStore.write(null);oldStore.write(draft);assert.equal(fresh.read(),replacement,'late old callbacks cannot erase or replace a new draft');
 assert.equal(writes,0);
});

test('same-patient mapping refresh clears a draft when its case is no longer active',async()=>{
 let omit=false;const fallback=transportFor(()=>response(packet()));
 const session=new RegistrySession((url,init)=>{
  if(omit&&url.endsWith('/case-bindings')){const value=cases();value.mappings=value.mappings.filter(c=>c.case_id!==caseId);return response(value);}
  return fallback(url,init);
 });
 await ready(session);session.manualPassageDraftStore(scope).write(Object.freeze({expected_context_sha256:context(true).context_sha256,references:Object.freeze([ref()])}));
 omit=true;await session.loadCases();omit=false;await session.loadCases();await session.loadWorldModel(caseId);await session.loadSavedQuestions(caseId);
 assert.equal(session.manualPassageDraftStore(scope).read(),null);
});
