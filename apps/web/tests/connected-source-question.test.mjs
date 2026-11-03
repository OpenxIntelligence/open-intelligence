import {test} from 'node:test';
import {createHash} from 'node:crypto';
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

const QID2='QUESTION-'+'E'.repeat(32);
const OTHER='Which original fictional source still needs independent verification?';
const hash=value=>createHash('sha256').update(value,'utf8').digest('hex');
const stable=value=>Array.isArray(value)?'['+value.map(stable).join(',')+']':
 value!==null&&typeof value==='object'?'{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+stable(value[k])).join(',')+'}':JSON.stringify(value);
const item=(id=QID,text=QUESTION)=>({question_id:id,patient_id:PID,case_id:CASE,question:text,
 source_id:SID,source_line:8,source_sha256:sha,source_version:1,
 source_snapshot_sha256:'a'.repeat(64),source_snapshot_contract:'oi.pg-source-world-model/1',
 preflight_sha256:text===QUESTION?'c'.repeat(64):'b'.repeat(64),created_at:'2026-11-02T12:00:00Z',
 source_context_state:'current_unreviewed_question',human_review_state:'not_submitted',clinical_approval:false,model_executed:false});
const history=rows=>({contract:'oi.synthetic-source-questions/2',access_receipt_id:'ACCESS-'+'B'.repeat(32),
 patient_id:PID,case_id:CASE,questions:rows,synthetic:true,clinical_review_connected:false,clinical_approval:false});
function packet(q){
 const value={contract:'oi.synthetic-question-source-review-packet/1',patient_id:PID,case_id:CASE,
  question_id:q.question_id,question:q.question,
  original_anchor:{source_id:q.source_id,source_line:q.source_line,source_sha256:q.source_sha256,
   source_version:q.source_version,source_snapshot_sha256:q.source_snapshot_sha256,
   source_snapshot_contract:q.source_snapshot_contract,preflight_sha256:q.preflight_sha256},
  source_context_state:'current_unreviewed_source',current_source_snapshot_sha256:'a'.repeat(64),
  selected_statement:world().observations[0],related_statements:[],related_statement_count_total:0,
  related_statements_truncated:false,current_source_count:1,current_observation_count:1,
  external_biomedical_evidence_qualified:false,published_evidence_rights_verified:false,
  medical_interpretation_performed:false,clinical_review_connected:false,clinical_approval:false,
  reviewer_identity_verified:false,synthetic:true,review_next_step:'independent_source_verification_required'};
 return {...value,packet_sha256:hash(stable(value)),source_access_receipt_id:'ACCESS-'+'F'.repeat(32)};
}
function brief(q){
 const body=q.question+'\n'+world().observations[0].source_statement+'\nNo clinical approval.\n';
 return {contract:'oi.synthetic-source-brief/2',synthetic:true,patient_id:PID,case_id:CASE,
  source_snapshot_contract:'oi.pg-source-world-model/1',source_snapshot_sha256:'a'.repeat(64),
  access_receipt_id:'ACCESS-'+'C'.repeat(32),question:q,selected_source:prepared(q.question).selected_source,
  prepared_at:'2026-11-02T12:01:00Z',media_type:'text/plain;charset=utf-8',body,body_sha256:hash(body),
  clinical_approval:false,model_executed:false,biomedical_evidence_included:false};
}
function connected(options={}){
 const rows=options.empty?[]:[item(),item(QID2,OTHER)],calls=[];
 const s=new RegistrySession(async(url,init)=>{
  calls.push([url,init]);
  if(url.endsWith('/case-bindings'))return response(bindings());
  if(url===path+'/world-model')return response(world());
  if(url===path+'/composer/source-preflight'){
   const question=JSON.parse(init.body).question;
   return response(prepared(question,question===QUESTION?'c'.repeat(64):'b'.repeat(64)));
  }
  if(url===path+'/questions'){
   if(init.method==='GET')return response(history(rows));
   const q=JSON.parse(init.body).question;rows.push(item(QID,q));
   return response({question_id:QID,duplicate:false},201);
  }
  if(url.endsWith('/source-review-packet')){
   const q=rows.find(q=>url.includes('/'+q.question_id+'/'));
   return options.packet?options.packet(q):response(packet(q));
  }
  if(url.endsWith('/brief')){
   const q=rows.find(q=>url.includes('/'+q.question_id+'/'));
   return options.brief?options.brief(q):response(brief(q));
  }
  return response(patient());
 });
 return {s,rows,calls};
}
async function ready(options={}){
 const f=connected(options),s=f.s;s.connect(TOKEN);await s.read(PID);await s.loadCases();
 await s.loadWorldModel(CASE);await s.loadSavedQuestions(CASE);
 assert.equal(s.snapshot().questionListPhase,'ready');return f;
}

test('authored question reaches exact source inspection and brief without being rewritten or approved',async()=>{
 const {s,calls}=await ready({empty:true});
 s.chooseQuestionDraft(SID,8);s.changeQuestionDraft(QUESTION);await s.prepareDraftQuestion();
 await s.savePreparedQuestion();await s.loadSavedQuestions(CASE);
 await s.loadQuestionSourcePacket(QID);const p=s.snapshot().sourceQuotePacket;
 assert.ok(p);assert.equal(p.question,QUESTION);assert.equal(p.original_anchor.source_id,SID);
 const b=await s.prepareSourceBrief(QID);assert.ok(b);
 assert.equal(b.question.question,p.question);assert.equal(b.question.preflight_sha256,p.original_anchor.preflight_sha256);
 assert.equal(b.selected_source.statement,p.selected_statement.source_statement);
 assert.equal(b.source_snapshot_sha256,p.current_source_snapshot_sha256);
 assert.equal(s.snapshot().sourceQuotePacket,p,'Same saved question can keep both inspected views');
 assert.equal(b.clinical_approval,false);assert.equal(p.clinical_approval,false);assert.equal(b.model_executed,false);
 assert.equal(b.body_sha256,hash(b.body));
 assert.equal(calls.filter(([u])=>u.endsWith('/brief')).length,1);
 assert.equal(calls.filter(([u])=>u.endsWith('/source-review-packet')).length,1);
});

test('late source inspection for A cannot restore beside a freshly prepared brief for B',async()=>{
 const pending=later();const {s}=await ready({packet:q=>q.question_id===QID?pending.promise:response(packet(q))});
 const read=s.loadQuestionSourcePacket(QID);await s.prepareSourceBrief(QID2);
 pending.resolve(response(packet(item())));await read;
 assert.equal(s.snapshot().sourceBrief?.question.question_id,QID2);
 assert.equal(s.snapshot().sourceQuotePacket,null,'Late quote A must not accompany brief B');
 assert.notEqual(s.snapshot().sourceQuotePhase,'loading');
});

test('late brief for A cannot restore beside a newly inspected saved question B',async()=>{
 const pending=later();const {s}=await ready({brief:q=>q.question_id===QID?pending.promise:response(brief(q))});
 const read=s.prepareSourceBrief(QID);await s.loadQuestionSourcePacket(QID2);
 pending.resolve(response(brief(item())));const result=await read;
 assert.equal(result,null,'Obsolete brief must not be returned to the downloader');
 assert.equal(s.snapshot().sourceQuotePacket?.question_id,QID2);
 assert.equal(s.snapshot().sourceBrief,null);assert.notEqual(s.snapshot().briefPhase,'loading');
});

test('selecting another saved question clears both completed previews rather than mixing their identities',async()=>{
 const {s}=await ready();await s.loadQuestionSourcePacket(QID);await s.prepareSourceBrief(QID);
 assert.ok(s.snapshot().sourceQuotePacket&&s.snapshot().sourceBrief);
 await s.loadQuestionSourcePacket(QID2);
 assert.equal(s.snapshot().sourceBrief,null);
 assert.equal(s.snapshot().sourceQuotePacket.question_id,QID2);
 await s.prepareSourceBrief(QID);
 assert.equal(s.snapshot().sourceQuotePacket,null);
 assert.equal(s.snapshot().sourceBrief.question.question_id,QID);
});

test('inspection denial cannot grant export or conceal its separate fresh request',async()=>{
 const {s,calls}=await ready({packet:()=>response({detail:'not authorized'},404)});
 await s.loadQuestionSourcePacket(QID);assert.equal(s.snapshot().sourceQuotePacket,null);
 const b=await s.prepareSourceBrief(QID);assert.ok(b);
 assert.equal(calls.filter(([u])=>u.endsWith('/source-review-packet')).length,1);
 assert.equal(calls.filter(([u])=>u.endsWith('/brief')).length,1);
 const exportDenied=await ready({brief:()=>response({detail:'not authorized'},404)});
 await exportDenied.s.loadQuestionSourcePacket(QID);assert.ok(exportDenied.s.snapshot().sourceQuotePacket);
 assert.equal(await exportDenied.s.prepareSourceBrief(QID),null);
 assert.equal(exportDenied.s.snapshot().sourceBrief,null);
 assert.equal(exportDenied.s.snapshot().sourceQuotePacket,null,'Export authority failure clears the shared context');
});

test('source re-read and disconnect remove authored and inspected material across all three features',async()=>{
 const {s}=await ready();s.chooseQuestionDraft(SID,8);s.changeQuestionDraft(QUESTION);
 await s.loadQuestionSourcePacket(QID);await s.prepareSourceBrief(QID);
 await s.loadWorldModel(CASE);
 assert.equal(s.snapshot().questionDraft,null);assert.equal(s.snapshot().sourceQuotePacket,null);
 assert.equal(s.snapshot().sourceBrief,null);assert.equal(s.snapshot().questions,null);
 s.disconnect();assert.equal(s.snapshot().patient,null);assert.equal(JSON.stringify(s.snapshot()).includes(TOKEN),false);
});
