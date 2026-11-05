import {test} from 'node:test';
import assert from 'node:assert/strict';
import {RegistrySession} from '../.test-dist/registry-client.js';
import * as drafts from '../.test-dist/authored-evidence-session.js';
import {ready,transportFor,response,packet,signPacket,question,history,
 questionId,patientId,caseId,evidenceId,assessmentId,hash,deferred,token} from './authored-evidence-fixtures.mjs';
const rationale='Authored fictional rationale; relevance remains uncertain.';
const clean=()=>signPacket({...packet(),assessments:[],reports:[]});
const active=s=>drafts.activeComparisonDraft?.(s.snapshot())??null;
async function start(s){await ready(s);await s.loadQuestionEvidence(questionId);
 assert.equal(s.selectEvidenceComparison?.(questionId,evidenceId),true,'choose an exact scoped comparison draft');
 assert.equal(s.editEvidenceComparison?.({quote:'café experiment',relation:'supports',applicability:'limited',rationale}),true);
 return s.snapshot().evidenceComparisonDraft;}

test('comparison drafting is local and captures exact source, evidence and rights',async()=>{
 const calls=[];const s=new RegistrySession(transportFor((u,i)=>{calls.push([u,i]);return response(clean());}));const d=await start(s),p=s.snapshot().evidencePacket;
 assert.equal(calls.length,1);assert.equal(calls[0][1].method,'GET');
 for(const [k,v] of Object.entries({patient_id:patientId,case_id:caseId,question_id:questionId,source_snapshot_sha256:p.question.source_snapshot_sha256,preflight_sha256:p.question.preflight_sha256,evidence_id:evidenceId,evidence_sha256:p.evidence[0].sha256,rights_sha256:p.evidence[0].rights_sha256}))assert.equal(d[k],v,k);
 assert.equal(d.rationale,rationale);assert.equal(d.dirty,true);assert.ok(Object.isFrozen(d));assert.equal(active(s),d);
});
test('same-question refresh hides input while checking and preserves it after unchanged reauthorization',async()=>{
 const wait=deferred();let delay=false;const s=new RegistrySession(transportFor(()=>delay?wait.promise:response(clean())));const d=await start(s);
 delay=true;const pending=s.loadQuestionEvidence(questionId);assert.equal(s.snapshot().evidencePacket,null);assert.equal(active(s),null);assert.equal(s.snapshot().evidenceComparisonDraft,d);
 const p=clean();p.access_receipt_id='ACCESS-'+'B'.repeat(32);wait.resolve(response(p));await pending;assert.equal(active(s),d);
});
test('workspace dismissal retains a hidden comparison until a fresh matching read',async()=>{
 let reads=0;const s=new RegistrySession(transportFor(()=>{reads++;return response(clean());}));const d=await start(s);s.dismissQuestionEvidence();
 assert.equal(active(s),null);assert.equal(s.snapshot().evidenceComparisonDraft,d);assert.equal(s.editEvidenceComparison?.({rationale:'Cannot edit hidden context.'}),false);
 await s.saveEvidenceComparison?.();assert.equal(reads,1);await s.loadQuestionEvidence(questionId);assert.equal(reads,2);assert.equal(active(s),d);
});
test('selecting the same evidence never erases the authored rationale',async()=>{
 const s=new RegistrySession(transportFor(()=>response(clean())));const d=await start(s);assert.equal(s.selectEvidenceComparison(questionId,evidenceId),true);assert.equal(s.snapshot().evidenceComparisonDraft,d);
});
test('another evidence selection requires explicit discard of a dirty comparison',async()=>{
 const other='EVIDENCE-'+'B'.repeat(32),p=clean();p.evidence=[...p.evidence,{...p.evidence[0],evidence_id:other,evidence_key:'EV-TWO'}];
 const s=new RegistrySession(transportFor(()=>response(signPacket(p))));const d=await start(s);assert.equal(s.selectEvidenceComparison(questionId,other),false);assert.equal(s.snapshot().evidenceComparisonDraft,d);assert.match(s.snapshot().evidenceDraftMessage,/discard/i);
 assert.equal(s.discardEvidenceComparison?.(),true);assert.equal(s.selectEvidenceComparison(questionId,other),true);assert.equal(active(s).evidence_id,other);
});
test('another question cannot inherit a dirty comparison, while its original question can resume it',async()=>{
 const other='QUESTION-'+'B'.repeat(32),otherQ={...question(),question_id:other,question:'Another independently fictional question?'};
 const base=transportFor(u=>response(signPacket({...clean(),question:u.includes(other)?otherQ:question()})));
 const s=new RegistrySession((u,i)=>u.endsWith('/questions')?response({...history(),questions:[question(),otherQ]}):base(u,i));const d=await start(s);await s.loadQuestionEvidence(other);
 assert.equal(active(s),null);assert.equal(s.snapshot().evidenceComparisonDraft,d);assert.equal(s.selectEvidenceComparison(other,evidenceId),false);await s.saveEvidenceComparison?.();assert.notEqual(s.snapshot().evidenceWritePhase,'saved');await s.loadQuestionEvidence(questionId);assert.equal(active(s),d);
});
for(const change of ['rights','evidence','source'])test(`refreshed ${change} cannot silently retarget a draft`,async()=>{
 let p=clean(),writes=0;const s=new RegistrySession(transportFor((u,i)=>{if(i.method==='POST')writes++;return response(p);}));const d=await start(s);p=clean();
 if(change==='rights'){p.evidence[0].permissions.abstract.ml_use='allowed';p.evidence[0].rights_sha256=hash(p.evidence[0].permissions);}
 if(change==='evidence'){p.evidence[0].state='superseded';p.evidence.push({...p.evidence[0],evidence_id:'EVIDENCE-'+'B'.repeat(32),version:2,state:'current',sha256:'e'.repeat(64)});}
 if(change==='source'){p.source_snapshot_sha256='c'.repeat(64);p.question.source_context_state='source_reassessment_required';}
 p=signPacket(p);await s.loadQuestionEvidence(questionId);assert.equal(s.snapshot().evidencePhase,'ready');assert.equal(active(s),null);assert.equal(s.snapshot().evidenceComparisonDraft,d);
 assert.equal(s.editEvidenceComparison?.({rationale:'A silent rebinding is forbidden.'}),false);await s.saveEvidenceComparison?.();assert.equal(writes,0);
});
for(const failure of [403,404,'network','malformed','withheld'])test(`fresh ${failure} result clears the draft without revival`,async()=>{
 let fail=false;const s=new RegistrySession(transportFor(()=>{if(!fail)return response(clean());if(failure==='network')throw Error('private diagnostic');if(failure==='malformed')return response({secret:'invalid'});
 if(failure==='withheld'){const p=clean();p.evidence[0].title=null;p.evidence[0].statement=null;return response(signPacket(p));}return response({secret:'private diagnostic'},failure);}));
 await start(s);fail=true;await s.loadQuestionEvidence(questionId);assert.equal(s.snapshot().evidenceComparisonDraft,null);assert.equal(active(s),null);assert.doesNotMatch(s.snapshot().evidenceDraftMessage,/private diagnostic/);fail=false;await s.loadQuestionEvidence(questionId);assert.equal(active(s),null);
});
for(const change of ['disconnect','credential','patient','case','source-refresh'])test(`${change} resets transient comparison without another write`,async()=>{
 let writes=0;const s=new RegistrySession(transportFor((u,i)=>{if(i.method==='POST')writes++;return response(clean());}));await start(s);
 if(change==='disconnect')s.disconnect();if(change==='credential')s.connect(token+'2');if(change==='patient')await s.read('PAT-EXAMPLE-002');if(change==='case')await s.loadWorldModel('CASE-BETA');if(change==='source-refresh')await s.loadWorldModel(caseId);
 assert.equal(s.snapshot().evidenceComparisonDraft,null);assert.equal(active(s),null);assert.equal(writes,0);
});
test('confirmed assessment clears its draft and preserves submitted references',async()=>{
 const bodies=[];const s=new RegistrySession(transportFor((u,i)=>{if(i.method==='POST'){bodies.push(JSON.parse(i.body));return response({assessment_id:assessmentId,question_id:questionId,duplicate:false},201);}return response(clean());}));
 const d=await start(s);await s.saveEvidenceComparison?.();assert.equal(s.snapshot().evidenceWritePhase,'saved');assert.equal(s.snapshot().evidenceComparisonDraft,null);assert.equal(bodies.length,1);
 for(const k of ['quote','rationale','evidence_sha256','rights_sha256'])assert.equal(bodies[0][k],d[k]);assert.equal(bodies[0].expected_source_snapshot_sha256,d.source_snapshot_sha256);
});
test('unknown delivery locks edit/discard and preserves exact retry identity',async()=>{
 let fail=true;const bodies=[];const s=new RegistrySession(transportFor((u,i)=>{if(i.method==='POST'){bodies.push(i.body);if(fail)throw Error('lost delivery');return response({assessment_id:assessmentId,question_id:questionId,duplicate:true});}return response(clean());}));
 const d=await start(s);await s.saveEvidenceComparison?.();assert.equal(s.snapshot().evidenceWritePhase,'unknown');const intent=s.snapshot().evidenceWriteIntent;
 assert.equal(s.snapshot().evidenceComparisonDraft,d);assert.equal(s.editEvidenceComparison?.({rationale:'Not a replacement intent.'}),false);assert.equal(s.discardEvidenceComparison?.(),false);await s.saveEvidenceComparison?.();assert.equal(bodies.length,1);assert.equal(s.snapshot().evidenceWriteIntent,intent);
 fail=false;await s.retryEvidenceWrite();assert.equal(bodies.length,2);assert.equal(bodies[0],bodies[1]);assert.equal(s.snapshot().evidenceComparisonDraft,null);
});
test('late pre-denial response cannot restore cleared draft or disclosure',async()=>{
 const wait=deferred();let mode='ready';const s=new RegistrySession(transportFor(()=>mode==='late'?wait.promise:mode==='denied'?response({},403):response(clean())));await start(s);
 mode='late';const pending=s.loadQuestionEvidence(questionId);mode='denied';await s.loadQuestionEvidence(questionId);assert.equal(s.snapshot().evidenceComparisonDraft,null);wait.resolve(response(clean()));await pending;assert.equal(active(s),null);assert.equal(s.snapshot().evidenceComparisonDraft,null);assert.equal(s.snapshot().evidencePacket,null);
});
test('malformed edits cannot replace captured identities or introduce unbounded values',async()=>{
 const s=new RegistrySession(transportFor(()=>response(clean())));const d=await start(s);
 for(const patch of [null,[],{evidence_id:'EVIDENCE-FORGED'},{relation:'approved'},{applicability:'certain'},{quote:12},{rationale:'x'.repeat(601)},{quote:'x'.repeat(401)},{rationale:'\ud800'}]){assert.equal(s.editEvidenceComparison?.(patch),false);assert.equal(s.snapshot().evidenceComparisonDraft,d);}
});

for(const field of ['content_item','version','statement_line','evidence_key'])test(`changed ${field} cannot reuse a captured draft even when digest fields are unchanged`,async()=>{
 let p=clean();p.evidence[0].permissions.api_output={...p.evidence[0].permissions.abstract};p.evidence[0].rights_sha256=hash(p.evidence[0].permissions);p=signPacket(p);
 const s=new RegistrySession(transportFor(()=>response(p)));const d=await start(s);
 p=structuredClone(p);p.evidence[0][field]=({content_item:'api_output',version:2,statement_line:7,evidence_key:'EV-OTHER'})[field];p=signPacket(p);
 await s.loadQuestionEvidence(questionId);assert.equal(s.snapshot().evidencePhase,'ready');assert.equal(s.snapshot().evidenceComparisonDraft,d);assert.equal(active(s),null);
});

test('an in-flight save locks the retained draft until its exact receipt returns',async()=>{
 const wait=deferred();let posts=0;const s=new RegistrySession(transportFor((u,i)=>{if(i.method==='POST'){posts++;return wait.promise;}return response(clean());}));
 const d=await start(s);const pending=s.saveEvidenceComparison();assert.equal(s.snapshot().evidenceWritePhase,'saving');assert.equal(s.snapshot().evidenceComparisonDraft,d);
 assert.equal(s.discardEvidenceComparison(),false);assert.equal(s.editEvidenceComparison({rationale:'Replacement during save must fail.'}),false);assert.equal(s.selectEvidenceComparison(questionId,evidenceId),false);
 await s.saveEvidenceComparison();assert.equal(posts,1);wait.resolve(response({assessment_id:assessmentId,question_id:questionId,duplicate:false},201));await pending;assert.equal(s.snapshot().evidenceComparisonDraft,null);
});

test('selection preserves withdrawal access for current evidence on a historical question without reusing draft text',async()=>{
 let p=clean();const s=new RegistrySession(transportFor(()=>response(p)));const d=await start(s);
 assert.equal(drafts.evidenceSelectionMode?.(s.snapshot(),evidenceId),'comparison');
 p=clean();p.source_snapshot_sha256='c'.repeat(64);p.question.source_context_state='source_reassessment_required';p=signPacket(p);
 await s.loadQuestionEvidence(questionId);
 assert.equal(drafts.evidenceSelectionMode?.(s.snapshot(),evidenceId),'withdrawal_only');
 assert.equal(active(s),null);assert.equal(s.snapshot().evidenceComparisonDraft,d);
});
test('selection distinguishes withheld current evidence from superseded, foreign and unresolved contexts',async()=>{
 let p=clean();const s=new RegistrySession(transportFor(()=>response(p)));await start(s);
 p=clean();p.evidence[0].statement=null;p.evidence[0].title=null;p=signPacket(p);await s.loadQuestionEvidence(questionId);
 const state=s.snapshot();assert.equal(drafts.evidenceSelectionMode?.(state,evidenceId),'withdrawal_only');
 for(const patch of [{evidencePhase:'loading'},{evidenceWritePhase:'saving'},
  {evidenceWritePhase:'unknown'},{connected:false},{patient:{...state.patient,patient_id:'PAT-OTHER'}},
  {questionsCaseId:'CASE-OTHER'},{cases:[]}])assert.equal(drafts.evidenceSelectionMode?.({...state,...patch},evidenceId),null);
 assert.equal(drafts.evidenceSelectionMode?.(state,'EVIDENCE-'+'F'.repeat(32)),null);
 assert.equal(drafts.evidenceSelectionMode?.({...state,evidencePacket:{...state.evidencePacket,
  evidence:[{...state.evidencePacket.evidence[0],state:'superseded'}]}},evidenceId),null);
});
