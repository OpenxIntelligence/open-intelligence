import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {ready,transportFor,response,packet,original,permissions,
 questionId,evidenceId,assessmentId,reportId} from './authored-evidence-fixtures.mjs';

const rationale='Independently authored comparison; applicability remains uncertain.';
const receipt=(kind,duplicate)=>({
 import:{evidence_id:evidenceId,version:1,duplicate},
 assessment:{assessment_id:assessmentId,question_id:questionId,duplicate},
 withdrawal:{withdrawal_id:'WITHDRAWAL-'+'A'.repeat(32),evidence_id:evidenceId,duplicate},
 report:{report_id:reportId,question_id:questionId,duplicate},
})[kind];
const save=(session,kind)=>({
 import:()=>session.importQuestionEvidence(questionId,original,'abstract',permissions()),
 assessment:()=>session.assessQuestionEvidence(questionId,evidenceId,'café experiment','supports','limited',rationale),
 withdrawal:()=>session.withdrawQuestionEvidence(questionId,evidenceId,rationale),
 report:()=>session.prepareEvidenceReport(questionId,[assessmentId]),
})[kind]();

// The unchanged server contract uses 201/false for a new effect and 200/true
// for a duplicate. A contradictory pair is not confirmation of either outcome.
for(const kind of ['import','assessment','withdrawal','report']){
 for(const [status,duplicate] of [[200,false],[201,true]]){
  test(`${kind}: contradictory ${status}/${duplicate} preserves exact unknown intent through recovery`,async()=>{
   const writes=[];let reads=0,valid=false;
   const session=new RegistrySession(transportFor((url,init)=>{
    if(init.method==='POST'){
     writes.push({path:url,body:init.body});
     return response(receipt(kind,valid?true:duplicate),valid?200:status);
    }
    reads++;return response(packet());
   }));
   await ready(session);await session.loadQuestionEvidence(questionId);
   const initialReads=reads;await save(session,kind);
   assert.equal(session.snapshot().evidenceWritePhase,'unknown');
   assert.equal(session.snapshot().evidenceReceipt,null);
   assert.equal(session.snapshot().evidencePacket,null);
   const intent=session.snapshot().evidenceWriteIntent;
   assert.ok(intent);assert.equal(reads,initialReads,'no automatic read after an unverified success');
   await session.retryEvidenceWrite();
   assert.equal(session.snapshot().evidenceWritePhase,'unknown');
   assert.equal(session.snapshot().evidenceWriteIntent,intent);
   assert.equal(session.snapshot().evidenceReceipt,null);
   assert.deepEqual(writes[1],writes[0],'a contradictory recovery cannot replace request identity');
   await session.loadQuestionEvidence(questionId);
   await save(session,kind);assert.equal(writes.length,2,'new intent stays blocked');
   valid=true;await session.retryEvidenceWrite();
   assert.equal(writes.length,3);assert.deepEqual(writes[2],writes[0]);
   assert.equal(session.snapshot().evidenceWritePhase,'saved');
   assert.equal(session.snapshot().evidenceWriteIntent,null);
   assert.equal(session.snapshot().evidenceReceipt.duplicate,true);
  });
 }
 for(const [status,duplicate] of [[201,false],[200,true]]){
  test(`${kind}: coherent ${status}/${duplicate} confirms the original write`,async()=>{
   let writes=0;
   const session=new RegistrySession(transportFor((url,init)=>{
    if(init.method==='POST'){writes++;return response(receipt(kind,duplicate),status);}
    return response(packet());
   }));
   await ready(session);await session.loadQuestionEvidence(questionId);await save(session,kind);
   assert.equal(writes,1);assert.equal(session.snapshot().evidenceWritePhase,'saved');
   assert.equal(session.snapshot().evidenceReceipt.duplicate,duplicate);
   assert.equal(session.snapshot().evidenceWriteIntent,null);
  });
 }
 test(`${kind}: retry may legitimately create the effect when the first delivery never committed`,async()=>{
  const writes=[];
  const session=new RegistrySession(transportFor((url,init)=>{
   if(init.method==='POST'){
    writes.push({path:url,body:init.body});
    if(writes.length===1)throw new TypeError('simulated failure before server commit');
    return response(receipt(kind,false),201);
   }
   return response(packet());
  }));
  await ready(session);await session.loadQuestionEvidence(questionId);await save(session,kind);
  assert.equal(session.snapshot().evidenceWritePhase,'unknown');
  await session.retryEvidenceWrite();assert.deepEqual(writes[1],writes[0]);
  assert.equal(session.snapshot().evidenceWritePhase,'saved');
  assert.equal(session.snapshot().evidenceReceipt.duplicate,false);
 });
}
for(const [status,duplicate] of [[200,false],[201,true]]){
 test(`contradictory ${status}/${duplicate} assessment cannot discard or replace its unfinished comparison`,async()=>{
  let valid=false;const writes=[];
  const session=new RegistrySession(transportFor((url,init)=>{
   if(init.method==='POST'){
    writes.push({path:url,body:init.body});
    return response(receipt('assessment',valid?true:duplicate),valid?200:status);
   }
   return response(packet());
  }));
  await ready(session);await session.loadQuestionEvidence(questionId);
  assert.equal(session.selectEvidenceComparison(questionId,evidenceId),true);
  assert.equal(session.editEvidenceComparison({quote:'café experiment',relation:'supports',applicability:'limited',rationale}),true);
  const draft=session.snapshot().evidenceComparisonDraft;
  await session.saveEvidenceComparison();
  assert.equal(session.snapshot().evidenceWritePhase,'unknown');
  assert.equal(session.snapshot().evidenceComparisonDraft,draft);
  assert.equal(session.snapshot().evidenceReceipt,null);
  assert.equal(session.editEvidenceComparison({rationale:'Replacement must not be sent.'}),false);
  assert.equal(session.discardEvidenceComparison(),false);
  await session.saveEvidenceComparison();assert.equal(writes.length,1);
  valid=true;await session.retryEvidenceWrite();
  assert.deepEqual(writes[1],writes[0]);assert.equal(session.snapshot().evidenceWritePhase,'saved');
  assert.equal(session.snapshot().evidenceComparisonDraft,null);
 });
}
