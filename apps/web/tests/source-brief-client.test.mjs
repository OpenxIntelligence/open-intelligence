import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {RegistrySession} from '../.test-dist/registry-client.js';

// Independently fictional source and durable question; no medical dataset.
const patientId='PAT-EXAMPLE-001',caseId='CASE-ALPHA';
const sourceId='SRC-'+'A'.repeat(32),questionId='QUESTION-'+'A'.repeat(32);
const token='fictional_test_credential_000000000001';
const fingerprint='a'.repeat(64),sourceHash='d'.repeat(64),preflightHash='b'.repeat(64);
const questionText='What reported uncertainty still requires independent verification?';
const questionsPath=`/v1/patients/${patientId}/cases/${caseId}/questions`;
const briefPath=questionsPath+'/'+questionId+'/brief';
const digest=body=>createHash('sha256').update(body,'utf8').digest('hex');
const response=(value,status=200)=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});
const deferred=()=>{let resolve;return{promise:new Promise(r=>resolve=r),resolve:value=>resolve(value)};};
const patient=(id=patientId)=>({patient_id:id,origin_org:'FICT-ORG',status:'active',revision:1,created_at:'2026-11-02T10:00:00Z'});
const cases=()=>({patient_id:patientId,synthetic:true,source_identity_verified:false,clinical_sources_linked:false,
 mappings:[caseId,'CASE-BETA'].map(id=>({case_id:id,patient_id:patientId,source_organization:'FICT-ORG',
 source_system:'FICT-TEXT',source_subject_ref:'FICT-SUBJECT',review_ref:'FICT-REVIEW',status:'active',revision:1,
 created_at:'2026-11-02T10:00:00Z',revoked_at:null,source_identity_verified:false,clinical_sources_linked:false,clinical_conclusions:false}))});
const world=()=>({contract:'oi.pg-source-world-model/1',patient_id:patientId,case_id:caseId,
 access_receipt_id:'ACCESS-'+'A'.repeat(32),synthetic:true,authority:'source_report_only_unreviewed',
 clinical_interpretation:false,research_review_invalidation_integrated:false,composer_execution_authorized:false,
 snapshot_fingerprint:fingerprint,as_of_received_at:'2026-11-02T10:00:00Z',
 summary:{current_sources:1,historical_sources:0,current_observations:1,unresolved_observations:1,source_disagreements:0},
 current_sources:[{source_id:sourceId,document_id:'DOC-ONE',version:1,sha256:sourceHash,kind:'pathology',
 event_date:'2026-01-10',issued_at:'2026-01-11',received_at:'2026-11-02T10:00:00Z',specimen_id:'SPECIMEN-ONE',state:'current',supersedes_id:null}],
 history:[],observations:[{source_id:sourceId,document_id:'DOC-ONE',document_version:1,source_sha256:sourceHash,
 source_kind:'pathology',finding_key:'marker',reported_state:'not-reported',source_statement:'Fictional café <script>literal</script>.',
 source_line:8,specimen_id:'SPECIMEN-ONE',event_date:'2026-01-10',issued_at:'2026-01-11',review_state:'not_established',clinical_meaning:null}],
 unresolved_refs:[{source_id:sourceId,source_line:8}],conflicts:[],limitations:['Independently fictional source context only.']});
const question=()=>({question_id:questionId,patient_id:patientId,case_id:caseId,question:questionText,
 source_id:sourceId,source_line:8,source_sha256:sourceHash,source_version:1,
 source_snapshot_sha256:fingerprint,source_snapshot_contract:'oi.pg-source-world-model/1',preflight_sha256:preflightHash,
 created_at:'2026-11-02T12:00:00Z',source_context_state:'current_unreviewed_question',
 human_review_state:'not_submitted',clinical_approval:false,model_executed:false});
const history=(items=[question()])=>({contract:'oi.synthetic-source-questions/2',access_receipt_id:'ACCESS-'+'B'.repeat(32),
 patient_id:patientId,case_id:caseId,questions:items,synthetic:true,clinical_review_connected:false,clinical_approval:false});
const selectedSource=()=>({source_id:sourceId,document_id:'DOC-ONE',version:1,sha256:sourceHash,line:8,
 finding_key:'marker',reported_state:'not-reported',statement:'Fictional café <script>literal</script>.',kind:'pathology',
 event_date:'2026-01-10',issued_at:'2026-01-11',specimen_id:'SPECIMEN-ONE'});
const brief=(body='Source-linked question\nFictional café <script>literal</script>.\nNo clinical approval.\n')=>({
 contract:'oi.synthetic-source-brief/2',synthetic:true,patient_id:patientId,case_id:caseId,
 source_snapshot_contract:'oi.pg-source-world-model/1',source_snapshot_sha256:fingerprint,
 access_receipt_id:'ACCESS-'+'C'.repeat(32),question:question(),selected_source:selectedSource(),
 prepared_at:'2026-11-02T12:01:00Z',media_type:'text/plain;charset=utf-8',body,body_sha256:digest(body),
 clinical_approval:false,model_executed:false,biomedical_evidence_included:false});

function sessionFor(transport,{questionRows=()=>[question()],model=()=>world()}={}){
 return new RegistrySession((url,init)=>{
  if(url.endsWith('/case-bindings'))return response(cases());
  if(url.endsWith('/world-model'))return response({...model(),case_id:url.includes('/CASE-BETA/')?'CASE-BETA':caseId});
  if(url===questionsPath)return response(history(questionRows()));
  if(url.endsWith('/brief'))return transport(url,init);
  return response(patient(url.endsWith('PAT-EXAMPLE-002')?'PAT-EXAMPLE-002':patientId));
 });
}
async function ready(session){
 session.connect(token);await session.read(patientId);await session.loadCases();
 await session.loadWorldModel(caseId);await session.loadSavedQuestions(caseId);
 assert.equal(session.snapshot().questionListPhase,'ready');
 assert.equal(typeof session.prepareSourceBrief,'function','A current saved question has no source-brief workflow yet');
}
async function withDownloadCapture(run){
 const originalDocument=Object.getOwnPropertyDescriptor(globalThis,'document');
 const originalCreate=URL.createObjectURL,originalRevoke=URL.revokeObjectURL;
 const blobs=[],clicks=[];
 URL.createObjectURL=blob=>{blobs.push(blob);return originalCreate(blob);};
 URL.revokeObjectURL=url=>originalRevoke(url);
 Object.defineProperty(globalThis,'document',{configurable:true,value:{
  body:{append(){}},createElement(tag){assert.equal(tag,'a');return{
   href:'',download:'',click(){clicks.push({href:this.href,download:this.download});},remove(){},
  };},
 }});
 try{await run({blobs,clicks});}finally{
  URL.createObjectURL=originalCreate;URL.revokeObjectURL=originalRevoke;
  if(originalDocument)Object.defineProperty(globalThis,'document',originalDocument);else delete globalThis.document;
 }
}

test('current saved question prepares a verified brief through an independent authenticated POST',async()=>{
 const calls=[];const s=sessionFor((url,init)=>{calls.push([url,init]);return response(brief());});
 await ready(s);const result=await s.prepareSourceBrief(questionId);
 assert.equal(s.snapshot().briefPhase,'ready');
 assert.equal(result,s.snapshot().sourceBrief);
 assert.equal(result.question.question_id,questionId);
 assert.equal(result.body,'Source-linked question\nFictional café <script>literal</script>.\nNo clinical approval.\n');
 assert.equal(result.clinical_approval,false);assert.equal(result.model_executed,false);
 assert.equal(result.biomedical_evidence_included,false);
 assert.equal(calls.length,1);assert.equal(calls[0][0],briefPath);
 const init=calls[0][1];assert.equal(init.method,'POST');assert.equal(init.headers.Authorization,'Bearer '+token);
 assert.equal(init.credentials,'omit');assert.equal(init.redirect,'error');assert.equal(init.cache,'no-store');
 assert.deepEqual(JSON.parse(init.body),{synthetic:true,source_snapshot_contract:'oi.pg-source-world-model/1',
  expected_source_snapshot_sha256:fingerprint,expected_preflight_sha256:preflightHash});
 assert.ok(Object.isFrozen(result)&&Object.isFrozen(result.question)&&Object.isFrozen(result.selected_source));
});

test('a brief requires the selected world line’s exact oncology role and nullable episode',async()=>{
 const model=world(),context={role:'metastasis',episode_id:null};
 model.observations[0].oncology=context;
 let source={...selectedSource(),oncology:{...context}};
 const s=sessionFor(()=>response({...brief(),selected_source:source}),{model:()=>model});
 await ready(s);
 const verified=await s.prepareSourceBrief(questionId);
 assert.deepEqual(verified.selected_source.oncology,context);
 assert.ok(Object.isFrozen(verified.selected_source.oncology));
 for(const wrong of [selectedSource(),{...selectedSource(),oncology:{...context,episode_id:'EP-B'}},
                      {...selectedSource(),oncology:{...context,role:'primary'}}]){
  source=wrong;
  assert.equal(await s.prepareSourceBrief(questionId),null);
 }
});

test('unknown, legacy, stale or differently anchored saved questions cannot request an export',async()=>{
 const wrong=[
  [],[{...question(),source_context_state:'source_reassessment_required'}],
  [{...question(),source_snapshot_contract:'oi.synthetic-postgres-world-model-sources/1',source_context_state:'source_reassessment_required'}],
  [{...question(),source_snapshot_sha256:'f'.repeat(64)}],
  [{...question(),source_line:9}],[{...question(),source_version:2}],
  [{...question(),source_sha256:'f'.repeat(64)}],
 ];
 for(const rows of wrong){
  let calls=0;const s=sessionFor(()=>{calls++;return response(brief());},{questionRows:()=>rows});
  await ready(s);assert.equal(await s.prepareSourceBrief(questionId),null);
  assert.equal(calls,0);assert.equal(s.snapshot().sourceBrief,null);
 }
});

test('altered brief authority, question identity, provenance, bytes or contract is refused',async()=>{
 const wrong=[
  {...brief(),contract:'oi.synthetic-source-brief/1'},
  {...brief(),synthetic:false},{...brief(),patient_id:'PAT-EXAMPLE-002'},
  {...brief(),case_id:'CASE-BETA'},{...brief(),source_snapshot_contract:'oi.synthetic-postgres-world-model-sources/1'},
  {...brief(),source_snapshot_sha256:'f'.repeat(64)},{...brief(),access_receipt_id:'not-an-access-receipt'},
  {...brief(),clinical_approval:true},{...brief(),model_executed:true},{...brief(),biomedical_evidence_included:true},
  {...brief(),unrecognized:true},{...brief(),media_type:'text/html'},
  {...brief(),prepared_at:'invalid'},
  {...brief(),question:{...question(),question_id:'QUESTION-'+'B'.repeat(32)}},
  {...brief(),question:{...question(),question:'A different saved question for another purpose?'}},
  {...brief(),question:{...question(),preflight_sha256:'f'.repeat(64)}},
  {...brief(),question:{...question(),created_at:'2026-11-02T12:00:01Z'}},
  {...brief(),question:{...question(),source_context_state:'source_reassessment_required'}},
  {...brief(),question:{...question(),extra:true}},
  {...brief(),selected_source:{...selectedSource(),statement:'An unrelated source statement.'}},
  {...brief(),selected_source:{...selectedSource(),line:9}},
  {...brief(),selected_source:{...selectedSource(),version:2}},
  {...brief(),selected_source:{...selectedSource(),specimen_id:'SPECIMEN-OTHER'}},
  {...brief(),selected_source:{...selectedSource(),extra:true}},
  {...brief(),body:''},{...brief(),body:'changed after hashing'},
  {...brief(),body_sha256:'F'.repeat(64)},brief('\ud800'),brief('é'.repeat(33000)),
 ];
 for(const value of wrong){
  const s=sessionFor(()=>response(value));await ready(s);
  assert.equal(await s.prepareSourceBrief(questionId),null,JSON.stringify(value).slice(0,150));
  assert.equal(s.snapshot().sourceBrief,null);assert.equal(s.snapshot().briefPhase,'error');
 }
});

test('revoked export, unknown scope and stale source clear an earlier preview without trusting response detail',async()=>{
 for(const status of [401,403,404,409,503]){
  let denied=false;const s=sessionFor(()=>denied?response({detail:'PRIVATE RESPONSE DETAIL'},status):response(brief()));
  await ready(s);assert.ok(await s.prepareSourceBrief(questionId));denied=true;
  assert.equal(await s.prepareSourceBrief(questionId),null);assert.equal(s.snapshot().sourceBrief,null);
  assert.ok(!JSON.stringify(s.snapshot()).includes('PRIVATE RESPONSE DETAIL'));
  if(status===401)assert.equal(s.snapshot().connected,false);
 }
});

test('a newer question selection prevents an older response from replacing its brief',async()=>{
 const waiting=deferred(),otherId='QUESTION-'+'B'.repeat(32);
 const otherQuestion={...question(),question_id:otherId,question:'What other source uncertainty needs verification?'};
 const s=sessionFor(url=>url===briefPath?waiting.promise:response({...brief(),question:otherQuestion}),
  {questionRows:()=>[question(),otherQuestion]});
 await ready(s);const pending=s.prepareSourceBrief(questionId);
 const current=await s.prepareSourceBrief(otherId);assert.equal(current.question.question_id,otherId);
 waiting.resolve(response(brief()));assert.equal(await pending,null);
 assert.equal(s.snapshot().sourceBrief,current);
});

test('patient, case, credentials, World Model and question refresh invalidate an in-flight brief',async()=>{
 for(const change of ['patient','case','credentials','world','questions']){
  const waiting=deferred();const s=sessionFor(()=>waiting.promise);await ready(s);
  const pending=s.prepareSourceBrief(questionId);
  if(change==='patient')await s.read('PAT-EXAMPLE-002');
  if(change==='case')await s.loadWorldModel('CASE-BETA');
  if(change==='credentials')s.connect('fictional_test_credential_000000000002');
  if(change==='world')await s.loadWorldModel(caseId);
  if(change==='questions')await s.loadSavedQuestions(caseId);
  waiting.resolve(response(brief()));assert.equal(await pending,null,change);
  assert.equal(s.snapshot().sourceBrief,null,change);
 }
});

test('context changes during asynchronous byte verification cannot restore a prepared brief',async()=>{
 const entered=deferred(),release=deferred(),original=crypto.subtle.digest;
 crypto.subtle.digest=async function(...args){entered.resolve();await release.promise;return original.apply(this,args);};
 try{
  const s=sessionFor(()=>response(brief()));await ready(s);
  const pending=s.prepareSourceBrief(questionId);await entered.promise;
  await s.loadWorldModel(caseId);release.resolve();
  assert.equal(await pending,null);assert.equal(s.snapshot().sourceBrief,null);
 }finally{release.resolve();crypto.subtle.digest=original;}
});

test('download rechecks the server and exports only its newly verified UTF-8 bytes',async()=>{
 let calls=0;const secondBody='New authorized brief\nFictional café — source-only.\n';
 const s=sessionFor(()=>response(++calls===1?brief():brief(secondBody)));await ready(s);
 await s.prepareSourceBrief(questionId);assert.equal(calls,1);
 const {downloadSourceBrief}=await import('../.test-dist/source-brief.js');
 await withDownloadCapture(async({blobs,clicks})=>{
  await downloadSourceBrief(s,questionId);assert.equal(calls,2);
  assert.equal(blobs.length,1);assert.equal(clicks.length,1);
  assert.equal(await blobs[0].text(),secondBody);
  assert.equal(blobs[0].type,'text/plain;charset=utf-8');
  assert.equal(clicks[0].download,'open-intelligence-source-question-brief.txt');
 });
});

test('denied or corrupt fresh export never creates a Blob from an earlier preview',async()=>{
 for(const freshResponse of [()=>response({},403),()=>response({},409),()=>response({...brief(),body:'not the hashed body'}),()=>response(brief(''))]){
  let calls=0;const s=sessionFor(()=>++calls===1?response(brief()):freshResponse());await ready(s);
  await s.prepareSourceBrief(questionId);
  const {downloadSourceBrief}=await import('../.test-dist/source-brief.js');
  await withDownloadCapture(async({blobs,clicks})=>{
   await downloadSourceBrief(s,questionId);assert.equal(calls,2);
   assert.equal(blobs.length,0);assert.equal(clicks.length,0);assert.equal(s.snapshot().sourceBrief,null);
  });
 }
});

test('a patient switch during download digest creates no Blob or click',async()=>{
 const s=sessionFor(()=>response(brief()));await ready(s);await s.prepareSourceBrief(questionId);
 const {downloadSourceBrief}=await import('../.test-dist/source-brief.js');
 const entered=deferred(),release=deferred(),original=crypto.subtle.digest;
 crypto.subtle.digest=async function(...args){entered.resolve();await release.promise;return original.apply(this,args);};
 try{
  await withDownloadCapture(async({blobs,clicks})=>{
   const pending=downloadSourceBrief(s,questionId);await entered.promise;
   await s.read('PAT-EXAMPLE-002');release.resolve();await pending;
   assert.equal(blobs.length,0);assert.equal(clicks.length,0);assert.equal(s.snapshot().sourceBrief,null);
  });
 }finally{release.resolve();crypto.subtle.digest=original;}
});

test('an export deadline during digest clears loading and creates no Blob',async()=>{
 const s=sessionFor(()=>response(brief()));await ready(s);await s.prepareSourceBrief(questionId);
 const {downloadSourceBrief}=await import('../.test-dist/source-brief.js');
 const entered=deferred(),release=deferred(),originalDigest=crypto.subtle.digest;
 const originalTimeout=globalThis.setTimeout;let expire;
 crypto.subtle.digest=async function(...args){entered.resolve();await release.promise;return originalDigest.apply(this,args);};
 globalThis.setTimeout=function(callback,delay,...args){
  if(delay===10000)expire=callback;
  return originalTimeout(callback,delay,...args);
 };
 try{
  await withDownloadCapture(async({blobs,clicks})=>{
   const pending=downloadSourceBrief(s,questionId);await entered.promise;
   assert.equal(typeof expire,'function');expire();release.resolve();await pending;
   assert.equal(s.snapshot().briefPhase,'error','Expired byte verification must release the loading state');
   assert.equal(s.snapshot().sourceBrief,null);assert.equal(blobs.length,0);assert.equal(clicks.length,0);
  });
 }finally{release.resolve();crypto.subtle.digest=originalDigest;globalThis.setTimeout=originalTimeout;}
});
