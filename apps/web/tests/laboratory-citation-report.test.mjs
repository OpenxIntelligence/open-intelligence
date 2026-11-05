import assert from 'node:assert/strict';
import test from 'node:test';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {readLaboratoryCitationReport} from '../.test-dist/laboratory-citation-report.js';
import {caseId,patient,projection} from './laboratory-projection-fixture.mjs';

const model=projection(),qid='QUESTION-'+'A'.repeat(32),receipt='ACCESS-'+'D'.repeat(32);
function fixture(o=model.laboratory_observations[1]){
 const anchor={source_id:o.source_id,source_version:o.document_version,source_sha256:o.source_sha256,
  observation_reference:o.observation_reference,source_snapshot_sha256:model.snapshot_fingerprint,preflight_sha256:'e'.repeat(64)};
 const question={...anchor,question_id:qid,question:'What was recorded for this fictional specimen?',source_context_state:'current_unreviewed_question'};
 const result={anchor_kind:'fhir_observation',kind:'laboratory',source_id:o.source_id,document_id:o.document_id,
  version:o.document_version,sha256:o.source_sha256,resource_reference:o.observation_reference,
  specimen_reference:o.specimen_reference,specimen_type_text:o.specimen_type_text,specimen_collected_at:o.specimen_collected_at,
  report_reference:o.report_reference,loinc_code:o.loinc_code,effective_at:o.effective_at,issued_at:o.issued_at,status:o.status,
  value_text:o.value_text,unit_code:o.unit_code,absent_reason:o.absent_reason,source_reported:true,
  review_state:'not_established',clinical_review:'not_performed'};
 const citations={contract:'oi.pg-question-evidence-links/1',patient_id:patient,case_id:caseId,question_id:qid,
  source_context_state:question.source_context_state,source_access_receipt_id:receipt,synthetic:true,model_executed:false,
  content_appraised:false,clinical_approval:false,question_anchor:anchor,links:[]};
 const wire={contract:'oi.laboratory-source-citation-inspection/1',question:question.question,reported_result:result,
   clinical_review:'not_performed',claim_appraisal:'not_performed',citations};
 return {question,result,citations,wire};
}
const response=(data,status=200)=>new Response(JSON.stringify(data),{status,headers:{'Content-Type':'application/json'}});
test('inspection binds exact question, source and measurement; no inferred values or clinical review',()=>{
 for(const observation of model.laboratory_observations){
  const {question,result,citations,wire}=fixture(observation);
  assert.deepEqual(readLaboratoryCitationReport(wire,model,question).result,result);
  for(const forged of [
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
async function sessionFor(readReport){
 const {question,citations}=fixture();
 const binding={case_id:caseId,patient_id:patient,source_organization:'ORG-A',source_system:'SYS-A',source_subject_ref:'SUBJECT-A',review_ref:'REVIEW-A',
  status:'active',revision:1,created_at:'2026-11-02T10:00:00Z',revoked_at:null,source_identity_verified:false,clinical_sources_linked:false,clinical_conclusions:false};
 const s=new RegistrySession(async(url,init)=>{
  if(url.endsWith('/source-citation-report')){assert.equal(init.method,'GET');assert.equal(init.cache,'no-store');return readReport();}
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
