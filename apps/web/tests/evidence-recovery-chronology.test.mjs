import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
import {ready,transportFor,response,packet,signPacket,report,
 questionId,evidenceId,assessmentId,reportId} from './authored-evidence-fixtures.mjs';

// These cases catch either donor overwriting the other: receipt acceptance must
// remain conservative while chronology failure removes only disclosure state.
for(const [status,duplicate] of [[201,true],[200,false]]){
 test(`contradictory ${status}/${duplicate} receipt survives invalid chronology until exact recovery`,async()=>{
  const writes=[];let reads=0,coherent=false,malformed=false;
  const session=new RegistrySession(transportFor((url,init)=>{
   if(init.method==='POST'){
    writes.push({path:url,body:init.body});
    return response({assessment_id:assessmentId,question_id:questionId,
     duplicate:coherent?true:duplicate},coherent?200:status);
   }
   reads++;
   if(url.includes('/evidence-reports/'))return response(report());
   const value=packet();
   if(malformed)value.assessments[0].created_at='2026-02-30T12:00:00Z';
   return response(signPacket(value));
  }));
  await ready(session);await session.loadQuestionEvidence(questionId);
  await session.readEvidenceReport(questionId,reportId);
  assert.equal(session.snapshot().evidenceReport.body,report().body);
  const before=reads;
  await session.assessQuestionEvidence(questionId,evidenceId,'café experiment',
   'supports','limited','Independently fictional comparison with unresolved applicability.');
  assert.equal(session.snapshot().evidenceWritePhase,'unknown');
  assert.equal(session.snapshot().evidenceReceipt,null);
  assert.equal(reads,before,'an inconsistent receipt must not trigger a success refresh');
  const intent=session.snapshot().evidenceWriteIntent;
  assert.ok(intent);assert.equal(writes.length,1);

  malformed=true;await session.loadQuestionEvidence(questionId);
  assert.equal(session.snapshot().evidencePhase,'error');
  assert.equal(session.snapshot().evidencePacket,null);
  assert.equal(session.snapshot().evidenceReport,null);
  assert.equal(session.snapshot().evidenceWritePhase,'unknown');
  assert.equal(session.snapshot().evidenceWriteIntent,intent,
   'a failed disclosure check cannot determine whether the earlier write committed');
  await session.assessQuestionEvidence(questionId,evidenceId,'café experiment',
   'context','unknown','A replacement must not supersede the unresolved original intent.');
  assert.equal(writes.length,1);

  coherent=true;await session.retryEvidenceWrite();
  assert.equal(writes.length,2);assert.deepEqual(writes[1],writes[0]);
  assert.equal(session.snapshot().evidenceWritePhase,'saved');
  assert.equal(session.snapshot().evidenceReceipt.assessment_id,assessmentId);
  assert.equal(session.snapshot().evidenceReceipt.duplicate,true);
  assert.equal(session.snapshot().evidenceWriteIntent,null);
  assert.equal(session.snapshot().evidencePhase,'error',
   'receipt recovery does not authorize malformed refreshed history');
  assert.equal(session.snapshot().evidencePacket,null);
  assert.equal(session.snapshot().evidenceReport,null);
  assert.equal(await session.readEvidenceReport(questionId,reportId),null);

  malformed=false;await session.loadQuestionEvidence(questionId);
  await session.readEvidenceReport(questionId,reportId);
  assert.equal(session.snapshot().evidencePhase,'ready');
  assert.equal(session.snapshot().evidenceReport.body,report().body);
  assert.equal(writes.length,2,'explicit read recovery must not create another write');
 });
}
