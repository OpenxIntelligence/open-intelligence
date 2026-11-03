import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
import * as drafts from '../.test-dist/authored-evidence-session.js';
import {ready,transportFor,response,packet,questionId,patientId,caseId,evidenceId,deferred} from './authored-evidence-fixtures.mjs';

const rationale='An independently fictional comparison requiring later human appraisal.';
async function begin(session){
 await ready(session);await session.loadQuestionEvidence(questionId);
 assert.equal(session.selectEvidenceComparison?.(questionId,evidenceId),true);
 assert.equal(session.editEvidenceComparison?.({quote:'café experiment',relation:'unknown',applicability:'limited',rationale}),true);
 return session.snapshot().evidenceComparisonDraft;
}

for(const boundary of ['metadata','followthrough'])test(`${boundary} read denial preserves independently authorized comparison input`,async()=>{
 const requests=[];
 const session=new RegistrySession(transportFor((url,init)=>{
  requests.push([url,init.method]);
  return url.endsWith('/evidence')?response(packet()):response({detail:'PRIVATE INDEPENDENT ACTION'},403);
 }));
 const draft=await begin(session);
 if(boundary==='metadata')await session.loadQuestionEvidenceLinks(questionId);
 else await session.loadFollowthrough(caseId);
 assert.equal(session.snapshot().evidenceComparisonDraft,draft);
 assert.equal(drafts.activeComparisonDraft?.(session.snapshot()),draft);
 assert.equal(draft.rationale,rationale);assert.equal(requests.filter(([,method])=>method==='POST').length,0);
 assert.ok(!JSON.stringify(session.snapshot()).includes('PRIVATE INDEPENDENT ACTION'));
});

for(const endpoint of ['/case-bindings','/world-model','/questions','/patient'])test(`common ${endpoint} denial clears comparison input and rejects a late allowed packet`,async()=>{
 let deny=false,hold=false;const waiting=deferred();
 const fallback=transportFor(url=>hold&&url.endsWith('/evidence')?waiting.promise:response(packet()));
 const session=new RegistrySession((url,init)=>{
  const target=endpoint==='/patient'?url===`/v1/patients/${patientId}`:url.endsWith(endpoint);
  return deny&&target?response({detail:'PRIVATE COMMON AUTHORITY'},403):fallback(url,init);
 });
 await begin(session);hold=true;const pending=session.loadQuestionEvidence(questionId);deny=true;
 if(endpoint==='/case-bindings')await session.loadCases();
 if(endpoint==='/world-model')await session.loadWorldModel(caseId);
 if(endpoint==='/questions')await session.loadSavedQuestions(caseId);
 if(endpoint==='/patient')await session.read(patientId);
 assert.equal(session.snapshot().evidenceComparisonDraft,null);
 waiting.resolve(response(packet()));await pending;
 assert.equal(session.snapshot().evidenceComparisonDraft,null);
 assert.equal(session.snapshot().evidencePacket,null);
 assert.ok(!JSON.stringify(session.snapshot()).includes(rationale));
 assert.ok(!JSON.stringify(session.snapshot()).includes('PRIVATE COMMON AUTHORITY'));
});
