import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {activeComparisonDraft} from '../.test-dist/authored-evidence-session.js';
import {ready,transportFor,response,packet,questionId,patientId,caseId,
 evidenceId,assessmentId,reportId,report,original,evidence,deferred} from './authored-evidence-fixtures.mjs';

const historical=()=>({...report(),state:'historical_reassessment_required'});
const originalResponse=()=>({contract:'oi.h1-evidence-original/1',patient_id:patientId,
 case_id:caseId,evidence_id:evidenceId,sha256:evidence().sha256,original_text:original,
 access_receipt_id:'ACCESS-'+'A'.repeat(32),synthetic:true});
async function draft(s){
 await ready(s);await s.loadQuestionEvidence(questionId);
 assert.equal(s.selectEvidenceComparison(questionId,evidenceId),true);
 assert.equal(s.editEvidenceComparison({quote:'café experiment',rationale:'Unfinished fictional comparison with uncertainty.'}),true);
 return s.snapshot().evidenceComparisonDraft;
}

test('a newly historical report invalidates stale comparison actions and retains the exact unsent draft',async()=>{
 const writes=[];const s=new RegistrySession(transportFor((url,init)=>{
  if(init.method==='POST')writes.push(init.body);
  if(url.endsWith('/original'))return response(originalResponse());
  return response(url.includes('/evidence-reports/')?historical():packet());
 }));const captured=await draft(s);await s.loadEvidenceOriginal(questionId,evidenceId);
 const result=await s.readEvidenceReport(questionId,reportId);
 assert.equal(result.state,'historical_reassessment_required');assert.equal(result.body,report().body);
 assert.equal(s.snapshot().evidencePacket,null,'the older current packet can no longer drive the workspace');
 assert.equal(s.snapshot().evidenceOriginal,null);
 assert.equal(s.snapshot().evidenceComparisonDraft,captured,'freshness change must not erase unsent work');
 assert.equal(activeComparisonDraft(s.snapshot()),null);
 assert.equal(s.editEvidenceComparison({rationale:'A changed rationale must remain blocked.'}),false);
 await s.saveEvidenceComparison();await s.prepareEvidenceReport(questionId,[assessmentId]);
 assert.equal(writes.length,0,'no stale comparison or report command may be sent');
});

test('newly historical report rejects an original response started under the older packet',async()=>{
 const pending=deferred();const s=new RegistrySession(transportFor(url=>url.endsWith('/original')?
  pending.promise:response(url.includes('/evidence-reports/')?historical():packet())));
 await ready(s);await s.loadQuestionEvidence(questionId);
 const reading=s.loadEvidenceOriginal(questionId,evidenceId);
 await s.readEvidenceReport(questionId,reportId);pending.resolve(response(originalResponse()));
 assert.equal(await reading,null);assert.equal(s.snapshot().evidenceOriginal,null);
 assert.equal(s.snapshot().evidenceReport.state,'historical_reassessment_required');
});

test('historical report remains freshly readable without restoring its stale evidence packet',async()=>{
 let reads=0;const s=new RegistrySession(transportFor(url=>response(url.includes('/evidence-reports/')?
  {...historical(),access_receipt_id:'ACCESS-'+String(++reads).repeat(32)}:packet())));
 await ready(s);await s.loadQuestionEvidence(questionId);
 const first=await s.readEvidenceReport(questionId,reportId),second=await s.readEvidenceReport(questionId,reportId);
 assert.equal(reads,2);assert.equal(second.body,first.body);assert.notEqual(second.access_receipt_id,first.access_receipt_id);
 assert.equal(s.snapshot().evidencePacket,null);assert.equal(s.snapshot().evidenceReport,second);
});

test('historical-only report rechecks denial, immutable identity and status without cached disclosure',async()=>{
 for(const mode of ['denied','promoted','changed','withheld']){
  let next=false,reads=0;const s=new RegistrySession(transportFor(url=>{
   if(!url.includes('/evidence-reports/'))return response(packet());reads++;
   if(!next)return response(historical());
   if(mode==='denied')return response({},404);
   if(mode==='promoted')return response(report());
   if(mode==='changed')return response({...historical(),prepared_at:'2026-11-03T12:01:00Z'});
   return response({...historical(),state:'content_withheld',body:null,snapshot:null});
  }));const captured=await draft(s);await s.readEvidenceReport(questionId,reportId);
  assert.equal(s.snapshot().evidenceComparisonDraft,captured);
  next=true;const result=await s.readEvidenceReport(questionId,reportId);
  assert.equal(reads,2,mode);assert.equal(result?.body??null,null,mode);
  assert.equal(s.snapshot().evidenceReport?.body??null,null,mode);
  assert.equal(s.snapshot().evidencePacket,null,mode);assert.equal(s.snapshot().evidenceComparisonDraft,null,mode);
 }
});

test('historical-only report cannot reappear after navigation or a patient change',async()=>{
 for(const change of ['navigation','patient']){
  const waiting=deferred();let delayed=false;const s=new RegistrySession(transportFor(url=>url.includes('/evidence-reports/')?
   delayed?waiting.promise:response(historical()):response(packet())));
  await ready(s);await s.loadQuestionEvidence(questionId);await s.readEvidenceReport(questionId,reportId);
  delayed=true;const pending=s.readEvidenceReport(questionId,reportId);
  if(change==='navigation')s.dismissQuestionEvidence();else await s.read('PAT-EXAMPLE-002');
  waiting.resolve(response(historical()));assert.equal(await pending,null,change);
  assert.equal(s.snapshot().evidenceReport,null,change);assert.equal(s.snapshot().evidencePacket,null,change);
 }
});

test('unchanged and already historical report reads retain the independently refreshed packet',async()=>{
 for(const status of ['current_unreviewed','historical_reassessment_required']){
  const p=packet();p.reports[0].state=status;
  const s=new RegistrySession(transportFor(url=>response(url.includes('/evidence-reports/')?{...report(),state:status}:p)));
  const captured=await draft(s),inspected=s.snapshot().evidencePacket;
  await s.readEvidenceReport(questionId,reportId);
  assert.equal(s.snapshot().evidencePacket,inspected,status);assert.equal(activeComparisonDraft(s.snapshot()),captured,status);
 }
});

test('fresh report invalidation preserves an uncertain comparison intent and its exact recovery',async()=>{
 const writes=[];let recover=false;const s=new RegistrySession(transportFor((url,init)=>{
  if(init.method==='POST'){
   writes.push(init.body);if(!recover)throw Error('Lost confirmation after possible commit');
   return response({assessment_id:assessmentId,question_id:questionId,duplicate:true});
  }
  return response(url.includes('/evidence-reports/')?historical():packet());
 }));const captured=await draft(s);await s.saveEvidenceComparison();
 const intent=s.snapshot().evidenceWriteIntent;await s.loadQuestionEvidence(questionId);
 await s.readEvidenceReport(questionId,reportId);
 assert.equal(s.snapshot().evidencePacket,null);assert.equal(s.snapshot().evidenceComparisonDraft,captured);
 assert.equal(s.snapshot().evidenceWritePhase,'unknown');assert.equal(s.snapshot().evidenceWriteIntent,intent);
 recover=true;await s.retryEvidenceWrite();
 assert.equal(writes.length,2);assert.equal(writes[1],writes[0]);assert.equal(s.snapshot().evidenceWritePhase,'saved');
});
