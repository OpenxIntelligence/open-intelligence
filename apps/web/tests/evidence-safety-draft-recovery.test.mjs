import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {ready,transportFor,response,packet,signPacket,questionId,evidenceId,assessmentId} from './authored-evidence-fixtures.mjs';

// Independently authored fixture: a correctly hashed packet with an impossible
// date must not reauthorize a draft. Exercise the real decoder and session.
function impossiblePacket(){
 const value=packet();value.evidence[0].created_at='2026-02-30T12:00:00Z';
 return signPacket(value);
}
async function begin(session){
 await ready(session);await session.loadQuestionEvidence(questionId);
 assert.equal(session.selectEvidenceComparison?.(questionId,evidenceId),true);
 assert.equal(session.editEvidenceComparison?.({quote:'café experiment',relation:'contradicts',
  applicability:'limited',rationale:'Fictional unresolved comparison for composition acceptance.'}),true);
 return session.snapshot().evidenceComparisonDraft;
}

test('invalid chronology with a valid digest clears a retained comparison without an implicit write',async()=>{
 let invalid=false;const writes=[];
 const session=new RegistrySession(transportFor((url,init)=>{
  if(init.method==='POST')writes.push({url,body:init.body});
  return response(invalid?impossiblePacket():packet());
 }));
 const draft=await begin(session);
 session.dismissQuestionEvidence();assert.equal(session.snapshot().evidenceComparisonDraft,draft);
 invalid=true;await session.loadQuestionEvidence(questionId);
 assert.equal(session.snapshot().evidencePhase,'error');
 assert.equal(session.snapshot().evidencePacket,null);
 assert.equal(session.snapshot().evidenceComparisonDraft,null);
 assert.equal(writes.length,0);
 invalid=false;await session.loadQuestionEvidence(questionId);
 assert.equal(session.snapshot().evidencePhase,'ready');
 assert.equal(session.snapshot().evidenceComparisonDraft,null,'fresh valid data does not resurrect cleared input');
});

test('chronology failure clears disclosure but preserves exact recovery after a contradictory receipt',async()=>{
 let invalid=false,coherent=false;const writes=[];
 const session=new RegistrySession(transportFor((url,init)=>{
  if(init.method==='POST'){
   writes.push({url,body:init.body});
   return response({assessment_id:assessmentId,question_id:questionId,duplicate:true},coherent?200:201);
  }
  return response(invalid?impossiblePacket():packet());
 }));
 const draft=await begin(session);await session.saveEvidenceComparison();
 const intent=session.snapshot().evidenceWriteIntent;
 assert.ok(intent);assert.equal(session.snapshot().evidenceWritePhase,'unknown');
 assert.equal(session.snapshot().evidenceComparisonDraft,draft);
 assert.equal(session.snapshot().evidenceReceipt,null);
 invalid=true;await session.loadQuestionEvidence(questionId);
 assert.equal(session.snapshot().evidencePhase,'error');
 assert.equal(session.snapshot().evidencePacket,null);
 assert.equal(session.snapshot().evidenceComparisonDraft,null);
 assert.equal(session.snapshot().evidenceWriteIntent,intent);
 assert.equal(session.snapshot().evidenceWritePhase,'unknown');
 coherent=true;await session.retryEvidenceWrite();
 assert.equal(writes.length,2);assert.deepEqual(writes[1],writes[0]);
 assert.equal(session.snapshot().evidenceWritePhase,'saved');
 assert.equal(session.snapshot().evidenceReceipt.assessment_id,assessmentId);
 assert.equal(session.snapshot().evidenceWriteIntent,null);
 assert.equal(session.snapshot().evidencePhase,'error','receipt recovery does not override failed packet validation');
 assert.equal(session.snapshot().evidencePacket,null);
 invalid=false;await session.loadQuestionEvidence(questionId);
 assert.equal(session.snapshot().evidencePhase,'ready');
 assert.equal(session.snapshot().evidenceComparisonDraft,null);
 assert.equal(writes.length,2);
});
