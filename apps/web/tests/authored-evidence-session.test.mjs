import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {downloadEvidenceReport} from '../.test-dist/authored-evidence.js';
import {ready,transportFor,response,packet,questionId,patientId,caseId,evidenceId,assessmentId,reportId,report,original,permissions,deferred,token} from './authored-evidence-fixtures.mjs';

test('evidence read uses the existing bearer and strict patient/case/question scope',async()=>{
 const calls=[];const s=new RegistrySession(transportFor((url,init)=>{calls.push([url,init]);return response(packet());}));await ready(s);await s.loadQuestionEvidence(questionId);
 assert.equal(s.snapshot().evidencePhase,'ready');assert.equal(calls.length,1);
 assert.equal(calls[0][0],`/v1/patients/${patientId}/cases/${caseId}/questions/${questionId}/evidence`);
 assert.equal(calls[0][1].headers.Authorization,'Bearer '+token);assert.equal(calls[0][1].credentials,'omit');assert.equal(calls[0][1].cache,'no-store');
});

test('context changes and navigation discard late evidence and report responses',async()=>{
 for(const change of ['patient','case','credential','world','questions','navigation']){
  const wait=deferred();const s=new RegistrySession(transportFor(()=>wait.promise));await ready(s);const pending=s.loadQuestionEvidence(questionId);
  if(change==='patient')await s.read('PAT-EXAMPLE-002');if(change==='case')await s.loadWorldModel('CASE-BETA');if(change==='credential')s.connect('fictional_test_credential_000000000002');if(change==='world')await s.loadWorldModel(caseId);if(change==='questions')await s.loadSavedQuestions(caseId);if(change==='navigation')s.dismissQuestionEvidence();
  wait.resolve(response(packet()));await pending;assert.equal(s.snapshot().evidencePacket,null,change);
 }
 let delayed=false;const wait=deferred();const s=new RegistrySession(transportFor(url=>url.includes('/evidence-reports/')&&delayed?wait.promise:response(packet())));await ready(s);await s.loadQuestionEvidence(questionId);delayed=true;
 const pending=s.readEvidenceReport(questionId,reportId);s.dismissQuestionEvidence();wait.resolve(response(report()));assert.equal(await pending,null);assert.equal(s.snapshot().evidenceReport,null);
});

test('unknown comparison write locks changed intent and recovers the same exact key after source refresh',async()=>{
 const bodies=[];let fail=true;const s=new RegistrySession(transportFor((url,init)=>{
  if(url.endsWith('/evidence-assessments')){bodies.push(init.body);if(fail)throw Error('lost after commit');return response({assessment_id:assessmentId,question_id:questionId,duplicate:true});}
  return response(packet());
 }));await ready(s);await s.loadQuestionEvidence(questionId);
 await s.assessQuestionEvidence(questionId,evidenceId,'café experiment','supports','limited','Fictional comparison remains uncertain.');
 assert.equal(s.snapshot().evidenceWritePhase,'unknown');const intent=s.snapshot().evidenceWriteIntent;
 await s.assessQuestionEvidence(questionId,evidenceId,'café experiment','contradicts','limited','Changed comparison remains uncertain.');assert.equal(bodies.length,1);assert.equal(s.snapshot().evidenceWriteIntent,intent);
 await s.loadWorldModel(caseId);assert.equal(s.snapshot().evidenceWritePhase,'unknown');assert.equal(s.snapshot().evidencePacket,null);await s.loadSavedQuestions(caseId);
 fail=false;await s.retryEvidenceWrite();assert.equal(bodies.length,2);assert.equal(bodies[0],bodies[1]);assert.equal(s.snapshot().evidenceWritePhase,'saved');assert.equal(s.snapshot().evidenceWriteIntent,null);
 assert.equal(s.snapshot().evidenceReceipt.assessment_id,assessmentId);assert.equal(s.snapshot().evidencePacket.question.question_id,questionId);
});

test('navigation while a write is in flight retains recoverable intent without restoring disclosure',async()=>{
 const wait=deferred(),bodies=[];let first=true;const s=new RegistrySession(transportFor((url,init)=>{
  if(init.method==='POST'){bodies.push(init.body);if(first){first=false;return wait.promise;}return response({evidence_id:evidenceId,version:1,duplicate:true});}
  return response(packet());
 }));await ready(s);await s.loadQuestionEvidence(questionId);
 const pending=s.importQuestionEvidence(questionId,original,'abstract',permissions());s.dismissQuestionEvidence();assert.equal(s.snapshot().evidenceWritePhase,'unknown');
 wait.resolve(response({evidence_id:evidenceId,version:1,duplicate:false},201));await pending;assert.equal(s.snapshot().evidencePacket,null);assert.equal(s.snapshot().evidenceWritePhase,'unknown');
 await s.retryEvidenceWrite();assert.equal(bodies[0],bodies[1]);assert.equal(s.snapshot().evidenceWritePhase,'saved');
});

test('changing patient or credential discards uncertain intent and cannot retry into a new scope',async()=>{
 for(const change of ['patient','credential','case']){
  let writes=0;const s=new RegistrySession(transportFor((url,init)=>{if(init.method==='POST'){writes++;throw Error('unknown');}return response(packet());}));await ready(s);await s.loadQuestionEvidence(questionId);await s.importQuestionEvidence(questionId,original,'abstract',permissions());assert.equal(s.snapshot().evidenceWritePhase,'unknown');
  if(change==='patient')await s.read('PAT-EXAMPLE-002');if(change==='credential')s.connect('fictional_test_credential_000000000002');if(change==='case')await s.loadWorldModel('CASE-BETA');
  assert.equal(s.snapshot().evidenceWriteIntent,null);await s.retryEvidenceWrite();assert.equal(writes,1);
 }
});

test('refreshing the current case bindings retains the exact uncertain evidence intent',async()=>{
 const bodies=[];let fail=true;const s=new RegistrySession(transportFor((url,init)=>{
  if(init.method==='POST'){bodies.push(init.body);if(fail)throw Error('lost response');return response({evidence_id:evidenceId,version:1,duplicate:true});}
  return response(packet());
 }));await ready(s);await s.loadQuestionEvidence(questionId);await s.importQuestionEvidence(questionId,original,'abstract',permissions());
 const intent=s.snapshot().evidenceWriteIntent;await s.loadCases();assert.equal(s.snapshot().evidenceWriteIntent,intent);assert.equal(s.snapshot().evidenceWritePhase,'unknown');
 fail=false;await s.retryEvidenceWrite();assert.equal(bodies.length,2);assert.equal(bodies[0],bodies[1]);assert.equal(s.snapshot().evidenceWritePhase,'saved');
});

test('withdrawn report metadata replaces every cached evidence excerpt and never exposes a body',async()=>{
 const s=new RegistrySession(transportFor(url=>response(url.includes('/evidence-reports/')?{...report(),state:'content_withheld',body:null,snapshot:null}:packet())));
 await ready(s);await s.loadQuestionEvidence(questionId);assert.ok(s.snapshot().evidencePacket.evidence[0].statement);
 const value=await s.readEvidenceReport(questionId,reportId);assert.equal(value.state,'content_withheld');assert.equal(value.body,null);assert.equal(s.snapshot().evidencePacket,null);assert.equal(s.snapshot().evidenceOriginal,null);
});

test('unknown or denied original download clears a previously inspected evidence packet',async()=>{
 const s=new RegistrySession(transportFor(url=>url.endsWith('/original')?response({detail:'PRIVATE'},404):response(packet())));
 await ready(s);await s.loadQuestionEvidence(questionId);assert.equal(await s.loadEvidenceOriginal(questionId,evidenceId),null);assert.equal(s.snapshot().evidencePacket,null);assert.equal(s.snapshot().evidenceOriginal,null);
});

test('fresh denied report download clears its prior body and never creates a Blob',async()=>{
 let denied=false,reads=0;const s=new RegistrySession(transportFor(url=>{if(url.includes('/evidence-reports/')){reads++;return denied?response({detail:'PRIVATE'},403):response(report());}return response(packet());}));await ready(s);await s.loadQuestionEvidence(questionId);await s.readEvidenceReport(questionId,reportId);assert.ok(s.snapshot().evidenceReport.body);denied=true;
 const saved=URL.createObjectURL;let blobs=0;URL.createObjectURL=()=>{blobs++;return 'blob:unexpected';};
 try{await downloadEvidenceReport(s,questionId,reportId);}finally{URL.createObjectURL=saved;}
 assert.equal(reads,2);assert.equal(blobs,0);assert.equal(s.snapshot().evidenceReport,null);assert.ok(!JSON.stringify(s.snapshot()).includes('PRIVATE'));
});

test('forged or oversized successful write responses remain uncertain, never falsely confirmed',async()=>{
 for(const value of [{assessment_id:assessmentId,question_id:'QUESTION-'+'B'.repeat(32),duplicate:false},{assessment_id:assessmentId,question_id:questionId,duplicate:false,extra:true}]){
  const s=new RegistrySession(transportFor((url,init)=>init.method==='POST'?response(value,201):response(packet())));await ready(s);await s.loadQuestionEvidence(questionId);await s.assessQuestionEvidence(questionId,evidenceId,'café experiment','supports','limited','Fictional comparison remains uncertain.');assert.equal(s.snapshot().evidenceWritePhase,'unknown');assert.equal(s.snapshot().evidenceReceipt,null);
 }
});
