import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';

const PID='PAT-EXAMPLE-001',CASE='CASE-ALPHA',SID='SRC-'+'A'.repeat(32);
const TOKEN='fictional_test_credential_000000000001';
const QUESTION='Can the reported fictional marker be traced to its exact original source?';
const QID='QUESTION-'+'C'.repeat(32);
const sha='d'.repeat(64);
const response=(v,status=200)=>new Response(JSON.stringify(v),{status,headers:{'Content-Type':'application/json'}});
const later=()=>{let resolve;return {promise:new Promise(r=>resolve=r),resolve};};
const patient=(pid=PID)=>({patient_id:pid,origin_org:'FICT-ORG',created_at:'2026-11-02T10:00:00Z',status:'active',revision:1});
const bindings=()=>({patient_id:PID,synthetic:true,source_identity_verified:false,
 clinical_sources_linked:false,mappings:[{case_id:CASE,patient_id:PID,
 source_organization:'FICT-ORG',source_system:'FICT-TEXT',source_subject_ref:'SUBJECT-A',
 review_ref:'REVIEW-A',status:'active',revision:1,created_at:'2026-11-02T10:00:00Z',
 revoked_at:null,source_identity_verified:false,clinical_sources_linked:false,clinical_conclusions:false}]});
const world=()=>({
 contract:'oi.pg-source-world-model/1',patient_id:PID,case_id:CASE,
 access_receipt_id:'ACCESS-'+'A'.repeat(32),synthetic:true,
 authority:'source_report_only_unreviewed',clinical_interpretation:false,
 research_review_invalidation_integrated:false,composer_execution_authorized:false,
 snapshot_fingerprint:'a'.repeat(64),as_of_received_at:'2026-11-02T10:00:00Z',
 summary:{current_sources:1,historical_sources:0,current_observations:1,unresolved_observations:1,source_disagreements:0},
 current_sources:[{source_id:SID,document_id:'DOC-ONE',version:1,sha256:sha,kind:'pathology',
  event_date:'2026-01-10',issued_at:'2026-01-11',received_at:'2026-11-02T10:00:00Z',
  specimen_id:'SPECIMEN-ONE',state:'current',supersedes_id:null}],
 history:[],observations:[{source_id:SID,document_id:'DOC-ONE',document_version:1,
  source_sha256:sha,source_kind:'pathology',finding_key:'marker',reported_state:'not-reported',
  source_statement:'Independent fictional statement.',source_line:8,specimen_id:'SPECIMEN-ONE',
  event_date:'2026-01-10',issued_at:'2026-01-11',review_state:'not_established',clinical_meaning:null}],
 unresolved_refs:[{source_id:SID,source_line:8}],conflicts:[],
 limitations:['Independently fictional source context.'],
});
const prepared=(question,hash='b'.repeat(64))=>({
 contract:'oi.synthetic-source-composer-preflight/2',
 source_snapshot_contract:'oi.pg-source-world-model/1',
 access_receipt_id:'ACCESS-'+'B'.repeat(32),patient_id:PID,case_id:CASE,question,
 source_snapshot_sha256:'a'.repeat(64),
 selected_source:{source_id:SID,document_id:'DOC-ONE',version:1,sha256:sha,line:8,
  finding_key:'marker',reported_state:'not-reported',statement:'Independent fictional statement.',
  kind:'pathology',event_date:'2026-01-10',issued_at:'2026-01-11',specimen_id:'SPECIMEN-ONE'},
 source_context_only:true,biomedical_evidence_rights_verified:false,
 model_execution_authorized:false,durable_question_created:false,durable_review_connected:false,
 clinical_approval:false,clinical_interpretation:'not_performed',
 reassessment_policy:'revalidate_source_and_authority_before_any_future_write',
 limitations:'Only independently fictional source text. No model execution or professional clinical review.',
 preflight_sha256:hash,
});
const path='/v1/patients/'+PID+'/cases/'+CASE;
function makeSession(options={}){
 const requests=[];
 let writes=0;
 const s=new RegistrySession(async(url,init)=>{
  requests.push([url,init]);
  if(url.endsWith('/case-bindings'))return response(bindings());
  if(url===path+'/world-model')return response(world());
  if(url===path+'/composer/source-preflight'){
   if(options.delayedPreflight)return options.delayedPreflight.promise;
   const q=JSON.parse(init.body).question;
   return response(prepared(q,q===QUESTION?'c'.repeat(64):'b'.repeat(64)));
  }
  if(url===path+'/questions'){
   writes++;
   if(options.failFirstWrite&&writes===1)throw Error('uncertain fictional network');
   return response({question_id:QID,duplicate:writes>1},writes>1?200:201);
  }
  return response(patient());
 });
 return {s,requests,get writes(){return writes}};
}
async function ready(transport){
 const fixture=transport||makeSession();
 const s=fixture.s;
 s.connect(TOKEN);await s.read(PID);await s.loadCases();await s.loadWorldModel(CASE);
 assert.equal(s.snapshot().worldPhase,'ready');
 return fixture;
}

test('authored draft is tied to an exact current source and is not sent on selection alone',async()=>{
 const {s,requests}=await ready();
 const before=requests.length;
 s.chooseQuestionDraft(SID,8);
 assert.equal(requests.length,before);
 assert.equal(s.snapshot().questionDraft.case_id,CASE);
 assert.equal(s.snapshot().questionDraft.source_id,SID);
 assert.equal(s.snapshot().questionDraft.source_line,8);
 assert.equal(s.snapshot().questionDraft.snapshot_fingerprint,'a'.repeat(64));
 assert.equal(s.snapshot().composerPreview,null);
 s.chooseQuestionDraft('SRC-'+'F'.repeat(32),8);
 assert.equal(s.snapshot().questionDraft.source_id,SID);
 s.changeQuestionDraft(QUESTION);
 assert.equal(s.snapshot().questionDraft.question,QUESTION);
 assert.equal(s.snapshot().savedQuestion,null);
 assert.equal(requests.length,before);
});
test('custom question is separately preflighted, then saved through the existing canonical API',async()=>{
 const {s,requests}=await ready();
 s.chooseQuestionDraft(SID,8);
 s.changeQuestionDraft(QUESTION);
 await s.prepareDraftQuestion();
 assert.equal(s.snapshot().composerPhase,'ready');
 assert.equal(s.snapshot().composerPreview.question,QUESTION);
 const packet=requests.find(([url])=>url===path+'/composer/source-preflight');
 assert.equal(JSON.parse(packet[1].body).question,QUESTION);
 assert.equal(JSON.parse(packet[1].body).source_line,8);
 assert.equal(packet[1].method,'POST');
 assert.equal(packet[1].credentials,'omit');
 assert.equal(packet[1].redirect,'error');
 await s.savePreparedQuestion();
 assert.equal(s.snapshot().savedQuestion.question_id,QID);
 const post=requests.find(([url])=>url===path+'/questions');
 assert.equal(JSON.parse(post[1].body).question,QUESTION);
 assert.equal(JSON.parse(post[1].body).expected_preflight_sha256,'c'.repeat(64));
 assert.equal(JSON.parse(post[1].body).expected_source_snapshot_sha256,'a'.repeat(64));
 assert.equal(s.snapshot().questionDraft.question,QUESTION);
 assert.equal(s.snapshot().composerPreview.model_execution_authorized,false);
 assert.equal(s.snapshot().composerPreview.clinical_approval,false);
});
test('editing an already prepared question revokes old preview and save key until new preflight',async()=>{
 const f=await ready(),s=f.s;
 s.chooseQuestionDraft(SID,8);
 await s.prepareDraftQuestion();
 const first=s.snapshot().composerPreview;
 assert.ok(first);
 s.changeQuestionDraft(QUESTION);
 assert.equal(s.snapshot().composerPreview,null);
 assert.equal(s.snapshot().composerPhase,'idle');
 await s.savePreparedQuestion();
 assert.equal(f.writes,0);
 assert.equal(s.snapshot().questionSavePhase,'error');
 await s.prepareDraftQuestion();
 assert.equal(s.snapshot().composerPreview.question,QUESTION);
 assert.notEqual(s.snapshot().composerPreview.preflight_sha256,first.preflight_sha256);
 await s.savePreparedQuestion();
 assert.equal(f.writes,1);
});
test('a late first preflight cannot silently restore the old question after an edit',async()=>{
 const delay=later(),f=await ready(makeSession({delayedPreflight:delay}));
 const s=f.s;s.chooseQuestionDraft(SID,8);
 const pending=s.prepareDraftQuestion();
 assert.equal(s.snapshot().composerPhase,'loading');
 s.changeQuestionDraft(QUESTION);
 assert.equal(s.snapshot().composerPreview,null);
 delay.resolve(response(prepared('What source provenance and reported uncertainty require independent verification?')));
 await pending;
 assert.equal(s.snapshot().composerPreview,null);
 assert.equal(s.snapshot().questionDraft.question,QUESTION);
 await s.savePreparedQuestion();
 assert.equal(f.writes,0);
});
test('invalid draft is never posted; text remains visibly editable for correction',async()=>{
 const f=await ready(),s=f.s;
 s.chooseQuestionDraft(SID,8);
 const before=f.requests.length;
 s.changeQuestionDraft(' short question ');
 await s.prepareDraftQuestion();
 assert.equal(f.requests.length,before);
 assert.equal(s.snapshot().composerPhase,'error');
 s.changeQuestionDraft('x'.repeat(501));
 assert.equal(s.snapshot().questionDraft.question,' short question ');
 s.changeQuestionDraft(QUESTION);
 await s.prepareDraftQuestion();
 assert.equal(s.snapshot().composerPhase,'ready');
});
test('draft is memory-only; case refresh, patient switch and disconnect remove its source linkage',async()=>{
 const f=await ready(),s=f.s;
 s.chooseQuestionDraft(SID,8);
 s.changeQuestionDraft(QUESTION);
 assert.equal(s.snapshot().questionDraft.question,QUESTION);
 await s.loadWorldModel(CASE);
 assert.equal(s.snapshot().questionDraft,null);
 s.chooseQuestionDraft(SID,8);s.changeQuestionDraft(QUESTION);
 await s.read('PAT-OTHER');
 assert.equal(s.snapshot().questionDraft,null);
 s.disconnect();
 assert.equal(s.snapshot().questionDraft,null);
 assert.equal(s.snapshot().patient,null);
 assert.equal(JSON.stringify(s.snapshot()).includes(TOKEN),false);
});
test('uncertain write cannot be silently discarded or rewritten under a new request key',async()=>{
 const f=await ready(makeSession({failFirstWrite:true})),s=f.s;
 s.chooseQuestionDraft(SID,8);s.changeQuestionDraft(QUESTION);
 await s.prepareDraftQuestion();await s.savePreparedQuestion();
 assert.equal(f.writes,1);
 assert.ok(s.snapshot().questionSaveMessage.startsWith('Save outcome unknown.'));
 s.changeQuestionDraft('Another independently fictional question with a new meaning?');
 s.discardQuestionDraft();
 s.chooseQuestionDraft(SID,8);
 assert.equal(s.snapshot().questionDraft.question,QUESTION);
 assert.equal(s.snapshot().composerPreview.question,QUESTION);
 await s.savePreparedQuestion();
 assert.equal(f.writes,2);
 const posts=f.requests.filter(([url])=>url===path+'/questions').map(([,init])=>JSON.parse(init.body));
 assert.equal(posts[0].request_key,posts[1].request_key);
 assert.equal(posts[0].question,posts[1].question);
 assert.equal(s.snapshot().savedQuestion.duplicate,true);
 s.changeQuestionDraft('Another independently fictional question with a new meaning?');
 assert.notEqual(s.snapshot().questionDraft.question,QUESTION);
 assert.equal(s.snapshot().composerPreview,null);
});
