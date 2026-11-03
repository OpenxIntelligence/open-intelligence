import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {ready,transportFor,response,packet,questionId,patientId,caseId,evidenceId,assessmentId,
 reportId,report,preflightHash,fingerprint,cases,original,permissions} from './authored-evidence-fixtures.mjs';

// Only HTTP is replaced. These checks exercise one real session, its two
// independently authorized evidence paths and its exact-write recovery state.
const metadataHash='e'.repeat(64),linkId='EVIDENCE-LINK-'+'F'.repeat(32);
const record={citation:'FICT-CONTINUITY@1',id:'FICT-CONTINUITY',version:'1',source_kind:'fictional',
 title:'Original fictional continuity metadata',licence:'original-synthetic',
 link:'https://example.invalid/fictional/continuity',metadata_sha256:metadataHash,
 availability:'metadata_only',rights_status:'granted'};
const scope={patient_id:patientId,case_id:caseId,question_id:questionId,
 source_context_state:'current_unreviewed_question',source_access_receipt_id:'ACCESS-'+'C'.repeat(32),
 synthetic:true,model_executed:false,content_appraised:false,clinical_approval:false};
const search=()=>({contract:'oi.pg-question-evidence-search/1',...scope,query:'fictional',records:[record]});
const links=()=>({contract:'oi.pg-question-evidence-links/1',...scope,links:[]});
const linkReceipt=()=>({link_id:linkId,citation:record.citation,metadata_sha256:metadataHash,duplicate:true});

test('one saved question can discover metadata and inspect its separate authored report',async()=>{
 const reads=[];
 const s=new RegistrySession(transportFor((url,init)=>{
  reads.push([url,init.method]);
  return response(url.endsWith('/evidence-search')?search():url.includes('/evidence-reports/')?report():packet());
 }));
 await ready(s);await s.searchQuestionEvidence(questionId,'fictional');
 assert.equal(s.snapshot().evidenceSearch.records[0].citation,'FICT-CONTINUITY@1');
 await s.loadQuestionEvidence?.(questionId);
 assert.equal(s.snapshot().evidencePhase,'ready','authored evidence must remain available alongside citation discovery');
 assert.equal(s.snapshot().evidencePacket.question.question_id,questionId);
 await s.readEvidenceReport(questionId,reportId);
 assert.equal(s.snapshot().evidenceReport.report_id,reportId);
 assert.equal(s.snapshot().evidenceReport.body,report().body);
 assert.equal(s.snapshot().evidenceSearch.records[0].citation,'FICT-CONTINUITY@1');
 assert.ok(reads.some(([url])=>url.endsWith('/evidence-search')));
 assert.ok(reads.some(([url])=>url.endsWith('/evidence')));
 assert.ok(reads.some(([url])=>url.endsWith('/evidence-reports/'+reportId)));
 assert.equal(s.snapshot().evidenceReport.model_executed,false);
 assert.equal(s.snapshot().evidenceReport.clinical_approval,false);
});

test('denied metadata access neither grants nor disables an independently authorized authored report',async()=>{
 let metadataAllowed=false,authoredAllowed=true;
 const s=new RegistrySession(transportFor(url=>{
  if(url.endsWith('/evidence-search'))return metadataAllowed?response(search()):response({detail:'PRIVATE METADATA'},403);
  if(!authoredAllowed)return response({detail:'PRIVATE CONTENT'},403);
  return response(url.includes('/evidence-reports/')?report():packet());
 }));
 await ready(s);await s.searchQuestionEvidence(questionId,'fictional');
 assert.equal(s.snapshot().evidenceSearchPhase,'error');assert.equal(s.snapshot().evidenceSearch,null);
 await s.loadQuestionEvidence?.(questionId);
 assert.equal(s.snapshot().evidencePhase,'ready','metadata denial is not authored-content authorization');
 await s.readEvidenceReport(questionId,reportId);assert.equal(s.snapshot().evidenceReport.report_id,reportId);
 metadataAllowed=true;authoredAllowed=false;
 await s.loadQuestionEvidence(questionId);
 assert.equal(s.snapshot().evidencePacket,null);assert.equal(s.snapshot().evidenceReport,null);
 await s.searchQuestionEvidence(questionId,'fictional');
 assert.equal(s.snapshot().evidenceSearch.records[0].citation,record.citation);
 assert.equal(s.snapshot().evidencePacket,null,'metadata permission cannot restore a denied authored quotation');
 assert.ok(!JSON.stringify(s.snapshot()).includes('PRIVATE'));
});

test('uncertain citation and comparison writes retain distinct exact intents across same-case refresh',async()=>{
 const linkBodies=[],assessmentBodies=[];let recover=false;
 const s=new RegistrySession(transportFor((url,init)=>{
  if(url.endsWith('/evidence-search'))return response(search());
  if(url.endsWith('/evidence-links')){
   if(init.method!=='POST')return response(links());
   linkBodies.push(init.body);if(!recover)throw Error('citation response lost after possible commit');
   return response(linkReceipt());
  }
  if(url.endsWith('/evidence-assessments')){
   assessmentBodies.push(init.body);if(!recover)throw Error('comparison response lost after possible commit');
   return response({assessment_id:assessmentId,question_id:questionId,duplicate:true});
  }
  return response(packet());
 }));
 await ready(s);await s.searchQuestionEvidence(questionId,'fictional');
 await s.saveQuestionEvidence(questionId,record.citation);
 assert.equal(s.snapshot().evidenceLinkPhase,'unknown');
 const citationIntent=s.snapshot().evidenceLinkIntent;
 await s.loadQuestionEvidence?.(questionId);
 assert.equal(s.snapshot().evidencePhase,'ready','an uncertain citation receipt cannot replace the authored-evidence workflow');
 await s.assessQuestionEvidence(questionId,evidenceId,'café experiment','supports','limited','Independent fictional comparison remains uncertain.');
 assert.equal(s.snapshot().evidenceWritePhase,'unknown');
 const comparisonIntent=s.snapshot().evidenceWriteIntent;
 assert.equal(s.snapshot().evidenceLinkIntent,citationIntent);
 assert.notEqual(JSON.parse(comparisonIntent.body).request_key,citationIntent.body.request_key);
 assert.equal(citationIntent.body.expected_preflight_sha256,preflightHash);
 assert.equal(citationIntent.body.expected_source_snapshot_sha256,fingerprint);
 await s.loadWorldModel(caseId);await s.loadSavedQuestions(caseId);
 assert.equal(s.snapshot().evidenceLinkIntent,citationIntent);
 assert.equal(s.snapshot().evidenceWriteIntent,comparisonIntent);
 recover=true;await s.retryQuestionEvidenceLink();
 assert.equal(s.snapshot().evidenceLinkReceipt.duplicate,true);
 assert.equal(s.snapshot().evidenceWriteIntent,comparisonIntent,'citation recovery must not consume the comparison intent');
 await s.retryEvidenceWrite();
 assert.equal(s.snapshot().evidenceReceipt.assessment_id,assessmentId);
 assert.equal(linkBodies.length,2);assert.equal(linkBodies[1],linkBodies[0]);
 assert.equal(assessmentBodies.length,2);assert.equal(assessmentBodies[1],assessmentBodies[0]);
});

for(const endpoint of ['/case-bindings','/world-model','/questions']){
 test('common '+endpoint+' denial clears both evidence recovery scopes',async()=>{
  let denied=false;
  const fallback=transportFor((url,init)=>{
   if(url.endsWith('/evidence-search'))return response(search());
   if(init.method==='POST')throw Error('delivery lost after a possible commit');
   return response(packet());
  });
  const s=new RegistrySession((url,init)=>denied&&url.endsWith(endpoint)?response({detail:'PRIVATE SCOPE'},403):fallback(url,init));
  await ready(s);await s.searchQuestionEvidence(questionId,'fictional');await s.saveQuestionEvidence(questionId,record.citation);
  await s.loadQuestionEvidence(questionId);
  await s.assessQuestionEvidence(questionId,evidenceId,'café experiment','supports','limited','Independently fictional proposal remains uncertain.');
  assert.equal(s.snapshot().evidenceLinkPhase,'unknown');assert.equal(s.snapshot().evidenceWritePhase,'unknown');
  denied=true;
  if(endpoint==='/case-bindings')await s.loadCases();
  if(endpoint==='/world-model')await s.loadWorldModel(caseId);
  if(endpoint==='/questions')await s.loadSavedQuestions(caseId);
  assert.equal(s.snapshot().evidenceLinkIntent,null);
  assert.equal(s.snapshot().evidenceWriteIntent,null,'a shared patient/source/question denial must clear authored recovery as well');
  assert.equal(s.snapshot().evidencePacket,null);assert.equal(s.snapshot().evidenceReport,null);
  assert.ok(!JSON.stringify(s.snapshot()).includes('PRIVATE SCOPE'));
 });
}

test('a successful binding refresh without the previous case removes both uncertain evidence intents',async()=>{
 let removed=false;
 const fallback=transportFor((url,init)=>{
  if(url.endsWith('/evidence-search'))return response(search());
  if(init.method==='POST')throw Error('delivery lost');
  return response(packet());
 });
 const s=new RegistrySession((url,init)=>removed&&url.endsWith('/case-bindings')?
  response({...cases(),mappings:cases().mappings.filter(row=>row.case_id!==caseId)}):fallback(url,init));
 await ready(s);await s.searchQuestionEvidence(questionId,'fictional');await s.saveQuestionEvidence(questionId,record.citation);
 await s.loadQuestionEvidence(questionId);
 await s.assessQuestionEvidence(questionId,evidenceId,'café experiment','supports','limited','Independently fictional proposal remains uncertain.');
 assert.equal(s.snapshot().evidenceWritePhase,'unknown');removed=true;await s.loadCases();
 assert.equal(s.snapshot().evidenceLinkIntent,null);
 assert.equal(s.snapshot().evidenceWriteIntent,null,'an unavailable case cannot retain an authored-content recovery payload');
});

for(const status of [403,404]){
 test('same-patient '+status+' recheck clears protected evidence intent and cannot retry',async()=>{
  let denied=false,writes=0;
  const fallback=transportFor((url,init)=>{
   if(url.endsWith('/evidence-search'))return response(search());
   if(init.method==='POST'){writes++;throw Error('response lost after possible commit');}
   return response(packet());
  });
  const s=new RegistrySession((url,init)=>denied&&url==='/v1/patients/'+patientId?
   response({detail:'PRIVATE IDENTITY'},status):fallback(url,init));
  await ready(s);await s.searchQuestionEvidence(questionId,'fictional');await s.saveQuestionEvidence(questionId,record.citation);
  await s.loadQuestionEvidence(questionId);await s.importQuestionEvidence(questionId,original,'abstract',permissions());
  assert.equal(s.snapshot().evidenceLinkPhase,'unknown');assert.equal(s.snapshot().evidenceWritePhase,'unknown');
  assert.ok(s.snapshot().evidenceWriteIntent.body.includes('Fictional comparison manuscript'));
  denied=true;await s.read(patientId);
  assert.equal(s.snapshot().patient,null);assert.equal(s.snapshot().phase,'error');
  assert.equal(s.snapshot().evidenceLinkIntent,null);
  assert.equal(s.snapshot().evidenceWriteIntent,null,'explicit patient denial cannot retain protected original bytes in retry state');
  assert.ok(!JSON.stringify(s.snapshot()).includes('Fictional comparison manuscript'));
  assert.ok(!JSON.stringify(s.snapshot()).includes('PRIVATE IDENTITY'));
  const before=writes;await s.retryEvidenceWrite();await s.retryQuestionEvidenceLink();
  assert.equal(writes,before,'denied patient scope cannot send either earlier write');
 });
}

test('temporary same-patient service failure preserves exact authored recovery without authorizing retry',async()=>{
 let unavailable=false,writes=0;
 const fallback=transportFor((url,init)=>{
  if(init.method==='POST'){writes++;throw Error('delivery lost after possible commit');}
  return response(packet());
 });
 const s=new RegistrySession((url,init)=>unavailable&&url==='/v1/patients/'+patientId?
  response({detail:'temporarily unavailable'},503):fallback(url,init));
 await ready(s);await s.loadQuestionEvidence(questionId);await s.importQuestionEvidence(questionId,original,'abstract',permissions());
 const intent=s.snapshot().evidenceWriteIntent;assert.equal(s.snapshot().evidenceWritePhase,'unknown');
 unavailable=true;await s.read(patientId);
 assert.equal(s.snapshot().patient,null);assert.equal(s.snapshot().evidencePacket,null);
 assert.equal(s.snapshot().evidenceWriteIntent,intent);assert.equal(s.snapshot().evidenceWritePhase,'unknown');
 await s.retryEvidenceWrite();assert.equal(writes,1,'temporary failure is not a current patient or case grant');
 unavailable=false;await s.read(patientId);await s.loadCases();
 assert.equal(s.snapshot().evidenceWriteIntent,intent,'successful scoped recheck retains the exact recovery key');
});
