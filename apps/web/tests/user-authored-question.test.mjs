import {test} from 'node:test';
import {createHash} from 'node:crypto';
import assert from 'node:assert/strict';
import {RegistrySession,patientContinuity} from '../.test-dist/registry-client.js';

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
const OTHER='Which wording in this fictional original still needs independent verification?';
const hash=value=>createHash('sha256').update(value,'utf8').digest('hex');
const stable=value=>Array.isArray(value)?'['+value.map(stable).join(',')+']':
 value!==null&&typeof value==='object'?'{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+stable(value[k])).join(',')+'}':JSON.stringify(value);
const savedQuestion=()=>({question_id:QID,patient_id:PID,case_id:CASE,question:QUESTION,
 source_id:SID,source_line:8,source_sha256:sha,source_version:1,
 source_snapshot_sha256:'a'.repeat(64),source_snapshot_contract:'oi.pg-source-world-model/1',
 preflight_sha256:'c'.repeat(64),created_at:'2026-11-02T12:00:00Z',
 source_context_state:'current_unreviewed_question',human_review_state:'not_submitted',clinical_approval:false,model_executed:false});
const history=()=>({contract:'oi.synthetic-source-questions/2',access_receipt_id:'ACCESS-'+'B'.repeat(32),
 patient_id:PID,case_id:CASE,questions:[savedQuestion()],synthetic:true,clinical_review_connected:false,clinical_approval:false});
function sourcePacket(){
 const q=savedQuestion();
 const value={contract:'oi.synthetic-question-source-review-packet/1',patient_id:PID,case_id:CASE,
  question_id:QID,question:QUESTION,
  original_anchor:{source_id:SID,source_line:8,source_sha256:sha,source_version:1,
   source_snapshot_sha256:q.source_snapshot_sha256,source_snapshot_contract:q.source_snapshot_contract,
   preflight_sha256:q.preflight_sha256},
  source_context_state:'current_unreviewed_source',current_source_snapshot_sha256:'a'.repeat(64),
  selected_statement:world().observations[0],related_statements:[],related_statement_count_total:0,
  related_statements_truncated:false,current_source_count:1,current_observation_count:1,
  external_biomedical_evidence_qualified:false,published_evidence_rights_verified:false,
  medical_interpretation_performed:false,clinical_review_connected:false,clinical_approval:false,
  reviewer_identity_verified:false,synthetic:true,review_next_step:'independent_source_verification_required'};
 return {...value,packet_sha256:hash(stable(value)),source_access_receipt_id:'ACCESS-'+'F'.repeat(32)};
}
function sourceBrief(){
 const body=QUESTION+'\n'+world().observations[0].source_statement+'\nNo clinical approval.\n';
 return {contract:'oi.synthetic-source-brief/2',synthetic:true,patient_id:PID,case_id:CASE,
  source_snapshot_contract:'oi.pg-source-world-model/1',source_snapshot_sha256:'a'.repeat(64),
  access_receipt_id:'ACCESS-'+'C'.repeat(32),question:savedQuestion(),selected_source:prepared(QUESTION).selected_source,
  prepared_at:'2026-11-02T12:01:00Z',media_type:'text/plain;charset=utf-8',body,body_sha256:hash(body),
  clinical_approval:false,model_executed:false,biomedical_evidence_included:false};
}
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
   if(init.method==='GET')return response(history());
   writes++;
   if(options.failFirstWrite&&writes===1)throw Error('uncertain fictional network');
   return response({question_id:QID,duplicate:writes>1},writes>1?200:201);
  }
  if(url.endsWith('/source-review-packet'))return options.delayedPacket?.promise??response(sourcePacket());
  if(url.endsWith('/brief'))return options.delayedBrief?.promise??response(sourceBrief());
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
test('patient overview follows actual draft, uncertain retry, confirmed save and disconnect',async()=>{
 const fixture=await ready(makeSession({failFirstWrite:true}));
 const {s}=fixture;
 s.chooseQuestionDraft(SID,8);s.changeQuestionDraft(QUESTION);
 assert.equal(patientContinuity(s.snapshot()).draft,'unsaved');
 await s.prepareDraftQuestion();await s.savePreparedQuestion();
 assert.equal(patientContinuity(s.snapshot()).draft,'needs_attention');
 const first=JSON.parse(fixture.requests.filter(([url])=>url===path+'/questions')[0][1].body);
 s.dismissSourceBrief();s.dismissSourceQuotePacket();
 await s.savePreparedQuestion();
 const second=JSON.parse(fixture.requests.filter(([url])=>url===path+'/questions')[1][1].body);
 assert.equal(first.request_key,second.request_key);
 assert.equal(patientContinuity(s.snapshot()).draft,'saved');
 s.disconnect();assert.equal(patientContinuity(s.snapshot()),null);
});

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

for(const action of ['start','resume','edit','prepare','default preflight'])
test(action+' authoring clears the earlier saved question quotation and brief together',async()=>{
 const f=await ready(),s=f.s;
 if(!['start','default preflight'].includes(action)){
  s.chooseQuestionDraft(SID,8);s.changeQuestionDraft(action==='edit'?QUESTION:OTHER);
 }
 await s.loadSavedQuestions(CASE);await s.loadQuestionSourcePacket(QID);await s.prepareSourceBrief(QID);
 assert.equal(s.snapshot().sourceQuotePacket.question_id,QID);
 assert.equal(s.snapshot().sourceBrief.question.question_id,QID);
 const before=f.requests.length;
 const preparing=action==='prepare'?s.prepareDraftQuestion():action==='default preflight'?
  s.prepareSourceContext(SID,8):action==='edit'?s.changeQuestionDraft(OTHER):s.chooseQuestionDraft(SID,8);
 const switched=s.snapshot();await preparing;
 assert.equal(switched.sourceQuotePacket,null,'A previous saved quotation must disappear synchronously');
 assert.equal(switched.sourceBrief,null,'A previous saved brief must disappear synchronously');
 assert.notEqual(switched.sourceQuotePhase,'loading');assert.notEqual(switched.briefPhase,'loading');
 assert.equal(s.snapshot().sourceQuotePacket,null);assert.equal(s.snapshot().sourceBrief,null);
 if(['start','resume','edit'].includes(action))assert.equal(f.requests.length,before,'Draft changes do not fetch or save');
 else{
  assert.equal(s.snapshot().composerPhase,'ready');assert.equal(s.snapshot().questions,null);
  assert.notEqual(s.snapshot().composerPreview.question,QUESTION);
 }
 assert.equal(f.writes,0);assert.equal(s.snapshot().worldPhase,'ready');
});

for(const action of ['start','edit','prepare'])for(const reader of ['packet','brief'])
test('delayed '+reader+' cannot restore old saved-question content after draft '+action,async()=>{
 const pending=later();const f=await ready(makeSession(reader==='packet'?
  {delayedPacket:pending}:{delayedBrief:pending})),s=f.s;
 if(action!=='start'){s.chooseQuestionDraft(SID,8);s.changeQuestionDraft(action==='edit'?QUESTION:OTHER);}
 await s.loadSavedQuestions(CASE);
 const reading=reader==='packet'?s.loadQuestionSourcePacket(QID):s.prepareSourceBrief(QID);
 assert.equal(s.snapshot()[reader==='packet'?'sourceQuotePhase':'briefPhase'],'loading');
 const preparing=action==='prepare'?s.prepareDraftQuestion():
  action==='edit'?s.changeQuestionDraft(OTHER):s.chooseQuestionDraft(SID,8);
 const switched=s.snapshot();
 pending.resolve(response(reader==='packet'?sourcePacket():sourceBrief()));
 const [result]=await Promise.all([reading,preparing]);
 assert.equal(switched.sourceQuotePacket,null);assert.equal(switched.sourceBrief,null);
 assert.notEqual(switched.sourceQuotePhase,'loading');assert.notEqual(switched.briefPhase,'loading');
 assert.equal(s.snapshot().sourceQuotePacket,null);assert.equal(s.snapshot().sourceBrief,null);
 if(reader==='brief')assert.equal(result,null,'A superseded brief must not reach the downloader');
 assert.equal(f.writes,0);assert.equal(s.snapshot().worldPhase,'ready');
});
