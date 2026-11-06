import assert from 'node:assert/strict';
import test from 'node:test';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {readLaboratoryCitationReport} from '../.test-dist/laboratory-citation-report.js';
import {parseSourceWorldModel} from '../.test-dist/source-world-model.js';
import {caseId,patient,projection,codedProjection,fictionalCoding} from './laboratory-projection-fixture.mjs';

const model=projection(),qid='QUESTION-'+'A'.repeat(32),receipt='ACCESS-'+'D'.repeat(32);
function fixture(o=model.laboratory_observations[1]){
 const anchor={source_id:o.source_id,source_version:o.document_version,source_sha256:o.source_sha256,
  observation_reference:o.observation_reference,source_snapshot_sha256:model.snapshot_fingerprint,preflight_sha256:'e'.repeat(64)};
 const question={...anchor,question_id:qid,question:'What was recorded for this fictional specimen?',source_context_state:'current_unreviewed_question'};
 const result={anchor_kind:'fhir_observation',kind:'laboratory',source_id:o.source_id,document_id:o.document_id,
  version:o.document_version,sha256:o.source_sha256,resource_reference:o.observation_reference,
  specimen_reference:o.specimen_reference,specimen_type_text:o.specimen_type_text,specimen_collected_at:o.specimen_collected_at,
  report_reference:o.report_reference,loinc_code:o.loinc_code,effective_at:o.effective_at,issued_at:o.issued_at,status:o.status,
  value_text:o.value_text,unit_code:o.unit_code,absent_reason:o.absent_reason,
  ...(o.status==='reported_coded'?{coded_result:{...o.coded_result}}:{}),source_reported:true,
  review_state:'not_established',clinical_review:'not_performed'};
 const citations={contract:'oi.pg-question-evidence-links/1',patient_id:patient,case_id:caseId,question_id:qid,
  source_context_state:question.source_context_state,source_access_receipt_id:receipt,synthetic:true,model_executed:false,
  content_appraised:false,clinical_approval:false,question_anchor:anchor,links:[]};
 const wire={report_sha256:'a'.repeat(64),contract:'oi.laboratory-source-citation-inspection/2',question:question.question,reported_result:result,
   clinical_review:'not_performed',claim_appraisal:'not_performed',citations};
 return {question,result,citations,wire};
}
const response=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}});
test('inspection binds exact question, source and measurement; no inferred values or clinical review',()=>{
 for(const observation of model.laboratory_observations){
  const {question,result,citations,wire}=fixture(observation);
  assert.deepEqual(readLaboratoryCitationReport(wire,model,question).result,result);
  for(const forged of [
   ...[null, undefined, 'A'.repeat(64), 'a'.repeat(63), 'a'.repeat(63)+'\n'].map(report_sha256=>({...wire,report_sha256})),
   {...wire,question:'A different question?'},{...wire,clinical_review:'approved'},{...wire,claim_appraisal:'performed'},
   {...wire,citations:{...citations,patient_id:'PATIENT-OTHER'}},{...wire,citations:{...citations,clinical_approval:true}},
   {...wire,reported_result:{...result,resource_reference:'Observation/other'}},
   {...wire,reported_result:{...result,specimen_reference:'Specimen/other'}},
   {...wire,reported_result:{...result,value_text:'999.00'}},
   {...wire,reported_result:{...result,issued_at:'2026-02-30T12:00:00Z'}},
  ])assert.throws(()=>readLaboratoryCitationReport(forged,model,question));
 }
});
test('historical report needs exact original version, explicit stale state, and no hidden citation metadata',()=>{
 const {question,result,citations,wire}=fixture();
 const historical={...model,current_sources:[],laboratory_observations:[],history:[{...model.current_sources[0],state:'superseded'}]};
 const old={...question,source_context_state:'source_reassessment_required'};
 const stale={...wire,citations:{...citations,source_context_state:old.source_context_state}};
 assert.deepEqual(readLaboratoryCitationReport(stale,historical,old).result,result);
 assert.throws(()=>readLaboratoryCitationReport(wire,historical,old));
 assert.throws(()=>readLaboratoryCitationReport({...stale,reported_result:{...result,version:2}},historical,old));
 const link={link_id:'EVIDENCE-LINK-'+'A'.repeat(32),citation:'FICT-TEST@1',metadata_sha256:'a'.repeat(64),
  created_at:'2026-11-03T10:00:00Z',actor_label:'ACTOR-TEST',status:'rights_restricted',record:null};
 const withLink=record=>({...stale,citations:{...stale.citations,links:[{...link,record}]}});
 assert.equal(readLaboratoryCitationReport(withLink(null),historical,old).citations.links[0].record,null);
 assert.throws(()=>readLaboratoryCitationReport(withLink({title:'Previously visible'}),historical,old));
});
test('the current patient record accepts only scalar laboratory absence codes',()=>{
 const absent=model.laboratory_observations.find(o=>o.status==='reported_absent');
 const withReason=reason=>({...model,laboratory_observations:model.laboratory_observations.map(o=>
   o===absent?{...o,absent_reason:reason}:o)});
 for(const code of ['unknown','not-performed','error','masked']){
   const current=parseSourceWorldModel(withReason(code),patient,caseId);
   assert.equal(current.laboratory_observations.find(o=>o.status==='reported_absent').absent_reason,code);
   assert.throws(()=>parseSourceWorldModel(withReason([code]),patient,caseId));
 }
});

test('reopening a superseded result rejects malformed absence codes without a current Observation',()=>{
 const {question,result,citations,wire}=fixture(model.laboratory_observations.find(o=>o.status==='reported_absent'));
 const old={...question,source_context_state:'source_reassessment_required'};
 const historical={...model,current_sources:[],laboratory_observations:[],history:[{...model.current_sources[0],state:'superseded'}]};
 const inspect=reason=>readLaboratoryCitationReport({...wire,reported_result:{...result,absent_reason:reason},
   citations:{...citations,source_context_state:old.source_context_state}},historical,old);
 for(const code of ['unknown','not-performed','error','masked']){
   assert.equal(inspect(code).result.absent_reason,code);
   assert.throws(()=>inspect([code]));
 }
});

async function sessionFor(readReport){
 const {question,citations}=fixture();
 const binding={case_id:caseId,patient_id:patient,source_organization:'ORG-A',source_system:'SYS-A',source_subject_ref:'SUBJECT-A',review_ref:'REVIEW-A',
  status:'active',revision:1,created_at:'2026-11-02T10:00:00Z',revoked_at:null,source_identity_verified:false,clinical_sources_linked:false,clinical_conclusions:false};
 const s=new RegistrySession(async(url,init)=>{
  if(url.endsWith('/source-citation-report/versioned')){assert.equal(init.method,'GET');assert.equal(init.cache,'no-store');return readReport();}
  if(url.endsWith('/evidence-links'))return response(citations);
  if(url.endsWith('/composer/laboratory-questions'))return response({patient_id:patient,case_id:caseId,access_receipt_id:receipt,questions:[question]});
  if(url.endsWith('/world-model'))return response(model);
  if(url.endsWith('/case-bindings'))return response({patient_id:patient,mappings:[binding],synthetic:true,source_identity_verified:false,clinical_sources_linked:false});
  return response({patient_id:patient,origin_org:'ORG-A',status:'active',revision:1,created_at:'2026-11-02T10:00:00Z'});
 });
 s.connect('fictional_lab_report_testing_token_00000000001');await s.read(patient);await s.loadCases();
 await s.loadWorldModel(caseId);await s.loadLabQuestions(s.snapshot().worldModel);
 assert.equal(s.snapshot().labQuestionHistory?.questions[0]?.question_id,qid);return s;
}
test('superseded report response cannot republish titles or erase a newer authorized inspection',async()=>{
 for(const status of [200,404]){
  let send;const hold=new Promise(r=>send=r);const s=await sessionFor(()=>hold);
  const p=s.readLaboratoryCitationReport(qid,new AbortController().signal);
  await s.loadQuestionEvidenceLinks(qid,'laboratory');
  send(response(fixture().wire,status));await assert.rejects(p);
  assert.equal(s.snapshot().patient.patient_id,patient);
  assert.equal(s.snapshot().evidenceLinks.question_id,qid);
 }
});
test('a new citation read invalidates a completed report, and denied report erases scoped patient data',async()=>{
 let status=200;const s=await sessionFor(()=>response(fixture().wire,status));
 const {report,generation}=await s.readLaboratoryCitationReport(qid,new AbortController().signal);
 assert.equal(report.result.value_text,'-0.25');assert.equal(generation,s.snapshot().evidenceGeneration);
 await s.loadQuestionEvidenceLinks(qid,'laboratory');assert.notEqual(generation,s.snapshot().evidenceGeneration);
 status=404;await assert.rejects(s.readLaboratoryCitationReport(qid,new AbortController().signal));
 for(const key of ['patient','worldModel','labQuestionHistory','evidenceLinks','evidenceSearch'])assert.equal(s.snapshot()[key],null);
});

test('coded results preserve the exact tuple, independent of key order; rejected variants cannot enter the World Model or a historical report',()=>{
 const {system,code}=fictionalCoding;
 for(const coding of [{system,code},{system,code,version:'0'},{system,code,display:'0'},fictionalCoding,
   {system,code:'A'.repeat(64),version:'9'.repeat(64),display:'!'.repeat(120)}]){
   const w=codedProjection(coding),current=parseSourceWorldModel(w,patient,caseId);
   const o=w.laboratory_observations[0],parsed=current.laboratory_observations[0];
   assert.deepEqual(parsed.coded_result,coding);assert.ok(Object.isFrozen(parsed.coded_result));
   assert.equal(current.summary.unresolved_observations,1,'only the absent observation counts');
   const {question,wire}=fixture(o);
   wire.reported_result.coded_result=Object.fromEntries(Object.entries(coding).reverse());
   const report=readLaboratoryCitationReport(wire,current,question);
   assert.deepEqual(report.result.coded_result,coding);assert.ok(Object.isFrozen(report.result.coded_result));
   o.coded_result.code='MUTATED';assert.equal(parsed.coded_result.code,coding.code);
 }
 const src=codedProjection(),o=src.laboratory_observations[0],{question,wire}=fixture(o);
 const historical={...src,current_sources:[],laboratory_observations:[],history:[{...src.current_sources[0],state:'superseded'}]};
 const old={...question,source_context_state:'source_reassessment_required'};
 wire.citations.source_context_state=old.source_context_state;
 const wrongCodes=[null,[{system,code}],{}, {system:'http://loinc.org',code},{system},{system,code:123},
   ...['', ' SPACE','A B','A\n','Aé','A\x7f','_first','X'.repeat(65)].flatMap(bad=>[{system,code:bad},{system,code,version:bad}]),
   ...[null,'',' label','label ','label\t','label\u202e','é','d'.repeat(121)].map(display=>({system,code,display})),
   {system,code,version:null},{system,code,clinical_review:'approved'}];
 const badFields=[...wrongCodes.map(coded_result=>({coded_result})),{value_text:'0'},{unit_code:'1'},{absent_reason:'unknown'},
   {status:'reported_value',value_text:'0',unit_code:'1'},{status:'reported_absent',absent_reason:'unknown'},{status:['reported_coded']},
   {interpretation:'inferred'}];
 for(const fields of badFields){
   const w=codedProjection();Object.assign(w.laboratory_observations[0],fields);
   assert.throws(()=>parseSourceWorldModel(w,patient,caseId),JSON.stringify(fields));
   assert.throws(()=>readLaboratoryCitationReport({...wire,reported_result:{...wire.reported_result,...fields}},historical,old));
 }
 const w=codedProjection();delete w.laboratory_observations[0].coded_result;
 assert.throws(()=>parseSourceWorldModel(w,patient,caseId));
 delete wire.reported_result.coded_result;
 assert.throws(()=>readLaboratoryCitationReport(wire,historical,old));
 for(const index of [0,2])for(const injected of [null,fictionalCoding]){
   const legacy=projection(),legacyObs=legacy.laboratory_observations[index],{question,wire}=fixture(legacyObs);
   legacyObs.coded_result=injected;wire.reported_result.coded_result=injected;
   assert.throws(()=>parseSourceWorldModel(legacy,patient,caseId));
   assert.throws(()=>readLaboratoryCitationReport(wire,model,question));
 }
});

test('a superseded coded inspection stays bound to its original when a replacement reuses test, specimen and observation references',()=>{
 const w=codedProjection(),oldObs=w.laboratory_observations[0],{question,wire}=fixture(oldObs);
 const old={...question,source_context_state:'source_reassessment_required'};
 wire.citations.source_context_state=old.source_context_state;
 const src=w.current_sources[0],replacement={...src,source_id:'SRC-'+'B'.repeat(32),version:2,
   sha256:'9'.repeat(64),supersedes_id:src.source_id};
 w.current_sources=[replacement];w.history=[{...src,state:'superseded'}];
 w.snapshot_fingerprint='5'.repeat(64);w.summary.historical_sources++;
 for(const o of w.laboratory_observations)Object.assign(o,{source_id:replacement.source_id,document_version:2,source_sha256:replacement.sha256});
 for(const t of w.laboratory_timeline)t.source_id=replacement.source_id;
 oldObs.coded_result={...fictionalCoding,code:'DIFFERENT',version:'v2'};
 const now=parseSourceWorldModel(w,patient,caseId);
 const report=readLaboratoryCitationReport(wire,now,old);
 assert.deepEqual(report.result.coded_result,fictionalCoding);
 assert.equal(report.result.sha256,src.sha256);assert.equal(report.citations.source_context_state,'source_reassessment_required');
 assert.throws(()=>readLaboratoryCitationReport({...wire,reported_result:{...wire.reported_result,source_id:replacement.source_id}},now,old));

 const curr=codedProjection(),{question:q,wire:fresh}=fixture(curr.laboratory_observations[0]);
 for(const different of [{...fictionalCoding,code:'fic.a-01_2'},{...fictionalCoding,version:'v2'},
   {...fictionalCoding,display:'Different'}, {system:fictionalCoding.system,code:fictionalCoding.code}]){
   assert.throws(()=>readLaboratoryCitationReport({...fresh,reported_result:{...fresh.reported_result,coded_result:different}},curr,q));
 }
});

test('historical quantity inspection retains its decimal, visible-character and code-point boundaries',()=>{
 const {question,result,citations,wire}=fixture();
 const old={...question,source_context_state:'source_reassessment_required'};
 const historical={...model,current_sources:[],laboratory_observations:[],history:[{...model.current_sources[0],state:'superseded'}]};
 const inspect=fields=>readLaboratoryCitationReport({...wire,reported_result:{...result,...fields},
   citations:{...citations,source_context_state:old.source_context_state}},historical,old);
 for(const unit_code of ['mg\u00ad/L','a\tb','a\u2028b','a\u2029b','a\ud800b','🧪'.repeat(33),'']){
   assert.throws(()=>inspect({unit_code}));
 }
 for(const value_text of [' 4.20 ','1e2','', '1'.repeat(65)])assert.throws(()=>inspect({value_text}));
 for(const unit_code of ['🧪'.repeat(32),' mg/L ']){
   assert.equal(inspect({value_text:'-0.00',unit_code}).result.unit_code,unit_code);
 }
});
