import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {activeComparisonDraft} from '../.test-dist/authored-evidence-session.js';
import {ready,transportFor,response,packet,questionId,evidenceId,reportId,report} from './authored-evidence-fixtures.mjs';

for(const ending of ['refresh','denial']){
 test('rejected comparison edit remains explicit through historical report and '+ending,async()=>{
  let denied=false,writes=0;
  const s=new RegistrySession(transportFor((url,init)=>{
   if(init.method==='POST')writes++;
   if(denied)return response({},403);
   return response(url.includes('/evidence-reports/')?{...report(),state:'historical_reassessment_required'}:packet());
  }));
  await ready(s);await s.loadQuestionEvidence(questionId);
  assert.equal(s.selectEvidenceComparison(questionId,evidenceId),true);
  const rationale='Previously accepted fictional rationale with unresolved uncertainty.';
  s.editEvidenceComparison({quote:'café experiment',rationale});
  assert.equal(s.editEvidenceComparison({rationale:'x'.repeat(601)}),false);
  assert.deepEqual(s.snapshot().evidenceRejectedFields,['rationale']);
  await s.readEvidenceReport(questionId,reportId);
  assert.equal(s.snapshot().evidencePacket,null);
  assert.equal(activeComparisonDraft(s.snapshot()),null);
  assert.deepEqual(s.snapshot().evidenceRejectedFields,['rationale']);
  assert.equal(s.acknowledgeRejectedEvidenceComparisonField('rationale'),false,'hidden draft cannot be acknowledged without current authority');
  await s.saveEvidenceComparison();assert.equal(writes,0);
  denied=ending==='denial';await s.loadQuestionEvidence(questionId);
  if(denied){
   assert.equal(s.snapshot().evidenceComparisonDraft,null);
   assert.deepEqual(s.snapshot().evidenceRejectedFields,[]);
   denied=false;await s.loadQuestionEvidence(questionId);
   assert.equal(s.snapshot().evidenceComparisonDraft,null);
  }else{
   assert.equal(activeComparisonDraft(s.snapshot()).rationale,rationale);
   assert.deepEqual(s.snapshot().evidenceRejectedFields,['rationale']);
   await s.saveEvidenceComparison();assert.equal(writes,0);
   assert.equal(s.acknowledgeRejectedEvidenceComparisonField('rationale'),true);
   assert.deepEqual(s.snapshot().evidenceRejectedFields,[]);
  }
  assert.equal(writes,0);
 });
}
