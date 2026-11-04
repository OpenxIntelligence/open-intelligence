import {test} from 'node:test';
import assert from 'node:assert/strict';
import {QuestionPassageClient,decodeManualContext,decodeSelection} from '../.test-dist/question-passages.js';
import {decodeEvidenceReport} from '../.test-dist/authored-evidence.js';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {question,report,reportId,patientId,caseId,questionId,hash,ready,transportFor,response,packet,world,deferred} from './authored-evidence-fixtures.mjs';

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
