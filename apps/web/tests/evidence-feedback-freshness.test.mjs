import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {activeComparisonDraft} from '../.test-dist/authored-evidence-session.js';
import {ready,transportFor,response,packet,questionId,evidenceId,assessmentId,reportId,report} from './authored-evidence-fixtures.mjs';

test('a bulk rejected edit requires correction or acknowledgement of every rejected field',async()=>{
 for(const reverse of [false,true]){
  const writes=[];
  const s=new RegistrySession(transportFor((url,init)=>{
   if(init.method==='POST'){
    writes.push(JSON.parse(init.body));
    return response({assessment_id:assessmentId,question_id:questionId,duplicate:false},201);
   }
   return response(packet());
  }));
  await ready(s);await s.loadQuestionEvidence(questionId);s.selectEvidenceComparison(questionId,evidenceId);
  const accepted={quote:'café experiment',rationale:'Accepted fictional rationale retaining explicit uncertainty.'};
  s.editEvidenceComparison(accepted);const draft=s.snapshot().evidenceComparisonDraft;
  const entries=[['quote','x'.repeat(401)],['rationale','x'.repeat(601)]];
  assert.equal(s.editEvidenceComparison(Object.fromEntries(reverse?entries.reverse():entries)),false);
  assert.equal(s.snapshot().evidenceComparisonDraft,draft,'rejected bulk input remains atomic');
  assert.deepEqual([...s.snapshot().evidenceRejectedFields].sort(),['quote','rationale']);
  s.editEvidenceComparison({quote:accepted.quote});
  await s.loadQuestionEvidence(questionId);await s.saveEvidenceComparison();
  assert.deepEqual(s.snapshot().evidenceRejectedFields,['rationale']);
  assert.equal(writes.length,0,'correcting the passage cannot accept the rejected rationale');
  assert.equal(s.acknowledgeRejectedEvidenceComparisonField('rationale'),true);
  await s.saveEvidenceComparison();assert.equal(writes.length,1);
  assert.equal(writes[0].rationale,accepted.rationale);
 }
});

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
