import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
import * as drafts from '../.test-dist/authored-evidence-session.js';
import {ready,transportFor,response,packet,world,questionId,patientId,caseId,evidenceId,deferred} from './authored-evidence-fixtures.mjs';

const rationale='An independently authored comparison retained only under verified case access.';
const sourceIndex=()=>({contract:'oi.synthetic-original-sources/1',patient_id:patientId,case_id:caseId,
 access_receipt_id:'ACCESS-'+'C'.repeat(32),sources:world().current_sources,source_reported_assertions:[],
 synthetic:true,clinical_interpretation:false,research_review_invalidation_integrated:false});
function sessionFor(documentResponse,evidenceResponse=()=>response(packet())){
 const fallback=transportFor(evidenceResponse);
 return new RegistrySession((url,init)=>url.endsWith('/sources')?response(sourceIndex()):
  url.includes('/documents')?documentResponse(url,init):fallback(url,init));
}
async function begin(session){
 await ready(session);await session.loadSources(caseId);await session.loadWorldModel(caseId);
 await session.loadSavedQuestions(caseId);await session.loadQuestionEvidence(questionId);
 assert.equal(session.selectEvidenceComparison?.(questionId,evidenceId),true);
 assert.equal(session.editEvidenceComparison?.({quote:'café experiment',relation:'unknown',applicability:'limited',rationale}),true);
 return session.snapshot().evidenceComparisonDraft;
}

// Removing documentRequest's shared investigation reset would leave retained
// comparison text or a late evidence packet available after document denial.
for(const status of [401,403,404])for(const path of ['', '/SRC-'+'A'.repeat(32)+'/original']){
 test(`document ${status} at ${path||'list'} clears comparison and rejects a late evidence response`,async()=>{
  let hold=false;const pending=deferred();
  const session=sessionFor(()=>new Response('PRIVATE DOCUMENT DENIAL',{status}),
   ()=>hold?pending.promise:response(packet()));
  await begin(session);hold=true;const reading=session.loadQuestionEvidence(questionId);
  const result=await session.documentRequest(caseId,path);
  assert.equal(result.status,status);assert.equal(session.snapshot().evidenceComparisonDraft,null);
  assert.equal(session.snapshot().evidencePacket,null);assert.equal(session.snapshot().sourceIndex,null);
  assert.equal(session.snapshot().connected,status!==401);
  pending.resolve(response(packet()));await reading;
  assert.equal(session.snapshot().evidenceComparisonDraft,null);assert.equal(session.snapshot().evidencePacket,null);
  assert.ok(!JSON.stringify(session.snapshot()).includes(rationale));
  assert.ok(!JSON.stringify(session.snapshot()).includes('PRIVATE DOCUMENT DENIAL'));
  await ready(session);await session.loadSources(caseId);await session.loadWorldModel(caseId);
  await session.loadSavedQuestions(caseId);hold=false;await session.loadQuestionEvidence(questionId);
  assert.equal(session.snapshot().evidenceComparisonDraft,null,'fresh authority cannot resurrect the cleared draft');
 });
}

test('temporary document failure preserves independently verified comparison input',async()=>{
 const session=sessionFor(()=>response({},503));const draft=await begin(session);
 assert.equal((await session.documentRequest(caseId,'')).status,503);
 assert.equal(session.snapshot().evidenceComparisonDraft,draft);
 assert.equal(drafts.activeComparisonDraft?.(session.snapshot()),draft);
 assert.equal(session.editEvidenceComparison({rationale:'Still editable after a temporary document service failure.'}),true);
});

test('a stale document denial cannot erase a comparison created after explicit reauthorization',async()=>{
 const held=deferred();const session=sessionFor(()=>held.promise);await begin(session);
 const old=session.documentRequest(caseId,'');const rejected=assert.rejects(old,/changed/);
 const fresh=await begin(session);held.resolve(new Response('Denied',{status:403}));await rejected;
 assert.equal(session.snapshot().evidenceComparisonDraft,fresh);
 assert.equal(drafts.activeComparisonDraft?.(session.snapshot()),fresh);
});
